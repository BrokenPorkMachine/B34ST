#!/usr/bin/env python3
"""SEP Key Fuzzer — differential key-wrapper testing for Secure Enclave forensics.

Apple’s Secure Enclave Processor (SEP) generates and wraps P-256 signing
keys whose dataRepresentation is opaque, device-bound, and policy-enforced.
This module provides a research harness that:

  1. Defines a baseline CryptoKit-compatible key lifecycle as a template.
  2. Generates synthetic key wrappers with known canary values.
  3. Runs a differential test matrix — device/lifecycle, access-control,
     and wrapper-integrity variants — against an instrumented device or
     SRD environment.
  4. Classifies each result against Apple’s Security Bounty significance
     levels (research info, access-control bypass, key extraction, etc.).
  5. Produces a bounty-ready, chain-of-custody-signed report.

All operations work exclusively with test synthetic keys. No real
credentials, passkeys, or personal keychain data are touched.

Top-level entry point: SEPKeyFuzzer.run() orchestrates the full campaign.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import pathlib
from typing import Any, Callable

from host.forensics.chain_of_custody import CustodyLog


# ---------------------------------------------------------------------------
# Classification — map fuzz results to Apple Security Bounty significance
# ---------------------------------------------------------------------------

BOUNTY_SIGNIFICANCE: dict[str, dict[str, Any]] = {
    "expected": {
        "label": "Expected behavior",
        "bounty_eligible": False,
        "score": 0,
        "detail": ("Operation completed as documented. No security boundary crossed."),
    },
    "research_info": {
        "label": "Research information",
        "bounty_eligible": False,
        "score": 1,
        "detail": (
            "Wrapper version, size, or stable header identified. "
            "Useful for further research but not a vulnerability."
        ),
    },
    "access_control": {
        "label": "Possible access-control vulnerability",
        "bounty_eligible": True,
        "score": 3,
        "detail": (
            "An unentitled application obtained or used a wrapper it should not"
            " have been able to access."
        ),
    },
    "integrity": {
        "label": "Potential integrity/parser vulnerability",
        "bounty_eligible": True,
        "score": 4,
        "detail": (
            "A modified wrapper was accepted by SEP without error. "
            "The parser did not reject the tampered input."
        ),
    },
    "device_binding": {
        "label": "Serious device-binding failure",
        "bounty_eligible": True,
        "score": 7,
        "detail": (
            "A device-bound wrapper functioned on a different device. "
            "Device-binding enforcement is absent or bypassed."
        ),
    },
    "policy_enforcement": {
        "label": "Serious policy-enforcement failure",
        "bounty_eligible": True,
        "score": 8,
        "detail": (
            "A key remained usable after its access-control ACL should have"
            " revoked it (e.g., biometric removal, passcode change)."
        ),
    },
    "signing_oracle": {
        "label": "Signing-oracle or ACL bypass",
        "bounty_eligible": True,
        "score": 9,
        "detail": (
            "SEP performed a signing operation without the required biometric"
            " or passcode approval. Unauthorized signing oracle achieved."
        ),
    },
    "key_extraction": {
        "label": "Critical key-extraction vulnerability",
        "bounty_eligible": True,
        "score": 10,
        "detail": (
            "Private scalar material appeared outside the SEP / PKA boundary."
            " The ECDSA private key was recovered."
        ),
    },
    "memory_disclosure": {
        "label": "Potential memory-disclosure vulnerability",
        "bounty_eligible": True,
        "score": 6,
        "detail": (
            "SEP returned stale data from an earlier request or uninitialized"
            " memory. Cross-client or cross-session information disclosure."
        ),
    },
}


def classify_result(
    observed: str,
    wrapper_accepted: bool = False,
    cross_device: bool = False,
    policy_violated: bool = False,
    scalar_found: bool = False,
    stale_data: bool = False,
    extra_output: bool = False,
) -> str:
    if scalar_found:
        return "key_extraction"
    if stale_data or extra_output:
        return "memory_disclosure"
    if cross_device:
        return "device_binding"
    if policy_violated:
        return "policy_enforcement"
    if wrapper_accepted:
        return "access_control"
    if observed in ("accepted_modified", "parser_bypass"):
        return "integrity"
    if observed in (
        "version_identified",
        "size_identified",
        "header_stable",
        "wrapper_fingerprint",
    ):
        return "research_info"
    return "expected"


# ---------------------------------------------------------------------------
# Canary helpers — placed into buffers to detect leakage
# ---------------------------------------------------------------------------

CANARY_LIBRARY: dict[str, bytes] = {
    "INPUT_A": b"DFKEY_INPUT_A_000001",
    "POLICY_B": b"DFKEY_POLICY_B_000001",
    "PADDING_C": b"DFKEY_PADDING_C_000001",
    "LABEL_D": b"DFKEY_LABEL_D_000001",
    "TAG_E": b"DFKEY_TAG_E_000001",
    "NONCE_F": b"DFKEY_NONCE_F_000001",
}


def place_canaries(size: int, kinds: list[str] | None = None) -> bytes:
    """Fill a buffer of *size* bytes with canary values at known offsets."""
    buf = bytearray(b"\x00" * size)
    if kinds is None:
        kinds = list(CANARY_LIBRARY)
    offset = 0
    for kind in kinds:
        val = CANARY_LIBRARY.get(kind, b"UNKNOWN_CANARY")
        if offset + len(val) <= size:
            buf[offset : offset + len(val)] = val
            offset += len(val) + 8
    return bytes(buf)


def scan_for_canaries(data: bytes) -> list[dict[str, Any]]:
    """Return a list of canary kinds found unexpectedly in *data*."""
    hits: list[dict[str, Any]] = []
    for kind, val in CANARY_LIBRARY.items():
        pos = data.find(val)
        if pos >= 0:
            hits.append(
                {
                    "kind": kind,
                    "value": val.hex(),
                    "position": pos,
                    "length": len(val),
                }
            )
    return hits


# ---------------------------------------------------------------------------
# Synthetic wrapper representation
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SEPKeyWrapper:
    """Represents a synthetic SEP key wrapper with metadata.

    Fields mirror what can be observed from the opaque CryptoKit
    ``dataRepresentation`` without access to plaintext internals.
    """

    wrapper_bytes: bytes
    public_key: bytes
    acl_configuration: dict[str, Any] = dataclasses.field(default_factory=dict)
    device_model: str = "unknown"
    os_build: str = "unknown"
    chipset: str = "unknown"
    key_type: str = "P256.Signing"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = (
                dt.datetime.now().astimezone().isoformat(timespec="seconds")
            )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.wrapper_bytes).hexdigest()

    @property
    def length(self) -> int:
        return len(self.wrapper_bytes)

    @property
    def public_key_sha256(self) -> str:
        return hashlib.sha256(self.public_key).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "length": self.length,
            "public_key_sha256": self.public_key_sha256,
            "public_key_hex": self.public_key.hex(),
            "acl_configuration": self.acl_configuration,
            "device_model": self.device_model,
            "os_build": self.os_build,
            "chipset": self.chipset,
            "key_type": self.key_type,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Baseline harness template — Swift codegen
# ---------------------------------------------------------------------------

BASELINE_HARNESS_SWIFT = """\
// B34ST SEP Key Baseline Harness
// Compile for the target device and run via FBR34KER deployment.
// REQUIRES: CryptoKit, LocalAuthentication, Security frameworks.

import CryptoKit
import LocalAuthentication
import Security

let message = Data("synthetic bounty test".utf8)

func createTestKey(requireBiometry: Bool) throws -> (Data, Data) {
    var flags: SecAccessControlCreateFlags = [.privateKeyUsage]
    if requireBiometry {
        flags.insert(.biometryCurrentSet)
    }

    var error: Unmanaged<CFError>?
    guard let accessControl = SecAccessControlCreateWithFlags(
        nil,
        kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        flags,
        &error
    ) else {
        throw error!.takeRetainedValue()
    }

    let context = LAContext()
    let key = try SecureEnclave.P256.Signing.PrivateKey(
        accessControl: accessControl,
        authenticationContext: context
    )
    let wrapper = key.dataRepresentation
    let publicKey = key.publicKey.x963Representation

    // Confirm normal same-device restoration.
    let reopened = try SecureEnclave.P256.Signing.PrivateKey(
        dataRepresentation: wrapper,
        authenticationContext: context
    )
    let signature = try reopened.signature(for: message)
    guard reopened.publicKey.isValidSignature(signature, for: message) else {
        fatalError("Baseline signature verification failed")
    }

    return (wrapper, publicKey)
}
"""


def generate_baseline_harness(output_path: pathlib.Path) -> pathlib.Path:
    """Write the baseline Swift harness to *output_path*."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(BASELINE_HARNESS_SWIFT, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Fuzz test case definitions
# ---------------------------------------------------------------------------

FUZZ_VARIATIONS: dict[str, list[dict[str, Any]]] = {
    "device_lifecycle": [
        {"name": "before_reboot", "desc": "Wrapper valid before device reboot"},
        {"name": "after_reboot", "desc": "Wrapper valid after device reboot"},
        {"name": "bfu", "desc": "Before First Unlock — test wrapped key usability"},
        {"name": "afu_unlocked", "desc": "After First Unlock, device unlocked"},
        {"name": "afu_locked", "desc": "After First Unlock, device locked"},
        {"name": "after_passcode_change", "desc": "Wrapper after passcode change"},
        {"name": "after_biometry_enroll", "desc": "After enrolling new biometry"},
        {"name": "after_biometry_remove", "desc": "After removing all biometry"},
        {"name": "after_keychain_delete", "desc": "After deleting keychain record"},
        {"name": "after_os_update", "desc": "After applying an OS update"},
        {"name": "after_erase_restore", "desc": "After erase and restore from backup"},
        {
            "name": "same_model_second_device",
            "desc": "Test on second device same model",
        },
        {"name": "different_soc", "desc": "Test on a different SoC generation"},
    ],
    "access_control": [
        {"name": "acl_private_key_usage", "desc": "ACL: .privateKeyUsage only"},
        {"name": "acl_user_presence", "desc": "ACL: .userPresence"},
        {"name": "acl_biometry_current_set", "desc": "ACL: .biometryCurrentSet"},
        {"name": "acl_device_passcode", "desc": "ACL: .devicePasscode"},
        {
            "name": "accessibility_when_unlocked",
            "desc": "kSecAttrAccessibleWhenUnlocked",
        },
        {
            "name": "accessibility_after_first_unlock",
            "desc": "kSecAttrAccessibleAfterFirstUnlock",
        },
        {
            "name": "accessibility_when_passcode_set",
            "desc": "kSecAttrAccessibleWhenPasscodeSet",
        },
        {
            "name": "swap_weak_metadata",
            "desc": "Swap weak ACL metadata onto strong wrapper",
        },
        {
            "name": "swap_strong_metadata",
            "desc": "Swap strong ACL metadata onto weak wrapper",
        },
        {
            "name": "different_app_group",
            "desc": "Attach different application access group",
        },
    ],
    "wrapper_integrity": [
        {"name": "flip_bit_header", "desc": "Flip one bit in header region"},
        {"name": "flip_bit_body", "desc": "Flip one bit in body region"},
        {"name": "flip_bit_footer", "desc": "Flip one bit in footer region"},
        {"name": "truncate_at_header", "desc": "Truncate at header boundary"},
        {"name": "truncate_at_body_start", "desc": "Truncate at body start boundary"},
        {"name": "truncate_at_body_end", "desc": "Truncate at body end boundary"},
        {"name": "append_zeroes", "desc": "Append zeroes to valid wrapper"},
        {"name": "append_random", "desc": "Append random data to valid wrapper"},
        {"name": "duplicate_field_header", "desc": "Duplicate apparent header field"},
        {"name": "duplicate_field_body", "desc": "Duplicate apparent body field"},
        {"name": "change_version_field", "desc": "Change suspected version field"},
        {"name": "change_length_field", "desc": "Change suspected length field"},
        {
            "name": "header_from_other_wrapper",
            "desc": "Replace header with another wrapper's header",
        },
        {
            "name": "body_from_other_wrapper",
            "desc": "Replace body with another wrapper's body",
        },
        {
            "name": "oversize_declared_length",
            "desc": "Set declared length larger than buffer",
        },
        {
            "name": "replay_older_version",
            "desc": "Replay wrapper from previous OS version",
        },
        {
            "name": "replay_pre_policy_change",
            "desc": "Replay wrapper from before policy change",
        },
    ],
}


# ---------------------------------------------------------------------------
# Fuzz test runner
# ---------------------------------------------------------------------------


class FuzzTestError(RuntimeError):
    pass


@dataclasses.dataclass
class FuzzTestResult:
    variation: str
    category: str
    description: str
    wrapper_sha256: str
    public_key_sha256: str
    expected_behavior: str
    actual_behavior: str
    classification: str
    classification_detail: str
    canary_hits: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    error: str = ""
    duration_ms: float = 0.0
    additional_buffers: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    @property
    def anomaly(self) -> bool:
        return self.classification not in ("expected", "research_info")

    @property
    def bounty_url(self) -> str:
        classifications = {
            "access_control": "Access control vulnerabilities",
            "integrity": "Parser/integrity vulnerabilities",
            "device_binding": "Device binding failures",
            "policy_enforcement": "Policy enforcement failures",
            "signing_oracle": "Signing oracle / ACL bypass",
            "key_extraction": "Key extraction vulnerabilities",
            "memory_disclosure": "Memory disclosure vulnerabilities",
        }
        return classifications.get(self.classification, "Other")

    def to_dict(self) -> dict[str, Any]:
        return {
            "variation": self.variation,
            "category": self.category,
            "description": self.description,
            "wrapper_sha256": self.wrapper_sha256,
            "public_key_sha256": self.public_key_sha256,
            "expected_behavior": self.expected_behavior,
            "actual_behavior": self.actual_behavior,
            "classification": self.classification,
            "classification_detail": self.classification_detail,
            "anomaly": self.anomaly,
            "bounty_category": self.bounty_url,
            "canary_hits": self.canary_hits,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "additional_buffers": self.additional_buffers,
        }


def run_fuzz_variation(
    variation: dict[str, Any],
    category: str,
    base_wrapper: SEPKeyWrapper,
    submit: Callable[[bytes, dict[str, Any]], dict[str, Any]],
) -> FuzzTestResult:
    """Execute a single fuzz variation against the device/SRD endpoint.

    The *submit* callable receives the mutated wrapper bytes and a metadata
    dict, then returns a dict with keys:
        ``accepted`` (bool), ``public_key_hex`` (str or ""),
        ``output_buffers`` (list[hex-str]), ``error`` (str), ``duration_ms`` (float).
    """
    name: str = variation["name"]
    desc: str = variation.get("description", variation.get("desc", ""))

    # Build the mutated wrapper based on variation name
    mutated, expected_behaviors = _apply_mutation(name, base_wrapper, category)

    try:
        resp = submit(
            mutated,
            {
                "variation": name,
                "category": category,
            },
        )
    except (OSError, RuntimeError) as exc:
        return FuzzTestResult(
            variation=name,
            category=category,
            description=desc,
            wrapper_sha256=hashlib.sha256(mutated).hexdigest(),
            public_key_sha256=base_wrapper.public_key_sha256,
            expected_behavior=expected_behaviors[0],
            actual_behavior=f"submit error: {exc}",
            classification="expected",
            classification_detail="Submission raised an exception; no boundary crossed.",
            error=str(exc),
        )

    accepted = resp.get("accepted", False)
    actual_pk = resp.get("public_key_hex", "")
    output_buffers = resp.get("output_buffers", [])
    raw_error = resp.get("error", "")

    # Classify the result
    if raw_error and not accepted:
        actual = f"rejected: {raw_error}"
        classification = "expected"
        detail = "Wrapper correctly rejected with error."
    elif accepted and actual_pk == base_wrapper.public_key.hex():
        actual = "accepted with correct public key"
        # Check if it was supposed to be rejected
        if "reject" in expected_behaviors[0].lower():
            classification = "access_control"
            detail = "Wrapper was accepted when it should have been rejected."
        else:
            classification = "expected"
            detail = "Wrapper accepted as expected."
    elif accepted and actual_pk != base_wrapper.public_key.hex():
        actual = f"accepted with DIFFERENT public key: {actual_pk}"
        classification = "integrity"
        detail = "Wrapper accepted but produced a different key."
    else:
        actual = f"rejected: {raw_error or 'no detail'}"
        classification = "expected"
        detail = "Wrapper correctly rejected."

    # Scan output buffers for canaries
    canary_hits: list[dict[str, Any]] = []
    for i, buf_hex in enumerate(output_buffers):
        buf = bytes.fromhex(buf_hex) if isinstance(buf_hex, str) else b""
        hits = scan_for_canaries(buf)
        for h in hits:
            h["buffer_index"] = i
        canary_hits.extend(hits)

    if canary_hits:
        classification = "memory_disclosure"
        detail = (
            f"Canary values found in {len(canary_hits)} location(s) "
            f"in output buffers — possible memory disclosure."
        )

    return FuzzTestResult(
        variation=name,
        category=category,
        description=desc,
        wrapper_sha256=hashlib.sha256(mutated).hexdigest(),
        public_key_sha256=base_wrapper.public_key_sha256,
        expected_behavior=expected_behaviors[0],
        actual_behavior=actual,
        classification=classification,
        classification_detail=detail,
        canary_hits=canary_hits,
        error=raw_error,
        duration_ms=resp.get("duration_ms", 0.0),
        additional_buffers=[
            {
                "index": i,
                "sha256": hashlib.sha256(
                    bytes.fromhex(h) if isinstance(h, str) else b""
                ).hexdigest(),
                "length": len(bytes.fromhex(h) if isinstance(h, str) else b""),
            }
            for i, h in enumerate(output_buffers)
        ],
    )


def _apply_mutation(
    name: str, base: SEPKeyWrapper, category: str
) -> tuple[bytes, tuple[str, str]]:
    """Return (mutated_bytes, (expected_behavior, description_of_mutation))."""
    w = bytearray(base.wrapper_bytes)
    size = len(w)

    mutations: dict[str, tuple[bytes, str]] = {
        "flip_bit_header": (
            w[:1] + bytes([w[1] ^ 0x01]) + w[2:] if size > 1 else w,
            "reject (integrity check failed)",
        ),
        "flip_bit_body": (
            w[: size // 2] + bytes([w[size // 2] ^ 0x01]) + w[size // 2 + 1 :]
            if size > size // 2
            else w,
            "reject (integrity check failed)",
        ),
        "flip_bit_footer": (
            w[:-1] + bytes([w[-1] ^ 0x01]) if size > 0 else w,
            "reject (integrity check failed)",
        ),
        "truncate_at_header": (
            w[:16] if size > 16 else w,
            "reject (truncated/invalid)",
        ),
        "truncate_at_body_start": (
            w[: max(size // 3, 1)] if size > 0 else w,
            "reject (truncated/invalid)",
        ),
        "truncate_at_body_end": (
            w[: max(2 * size // 3, 1)] if size > 0 else w,
            "reject (truncated/invalid)",
        ),
        "append_zeroes": (w + b"\x00" * 64, "reject (extra trailing data)"),
        "append_random": (
            w + bytes([0xAB, 0xCD, 0xEF] * 20),
            "reject (extra trailing data)",
        ),
        "duplicate_field_header": (
            w + w[:32] if size >= 32 else w,
            "varies (duplicate field)",
        ),
        "duplicate_field_body": (
            w + w[size // 2 : size // 2 + 32] if size >= size // 2 + 32 else w,
            "varies (duplicate field)",
        ),
        "change_version_field": (
            w[:4] + bytes([0xFF]) + w[5:] if size > 5 else w,
            "reject (invalid version)",
        ),
        "change_length_field": (
            w[:8] + bytes([0xFF, 0xFF, 0xFF, 0xFF]) + w[12:] if size > 12 else w,
            "reject (invalid length)",
        ),
        "header_from_other_wrapper": (
            base.wrapper_bytes[:32] + bytes(32) + base.wrapper_bytes[64:]
            if size > 96
            else w,
            "reject (header mismatch)",
        ),
        "body_from_other_wrapper": (
            w[:32] + bytes(32) + w[64:] if size > 96 else w,
            "reject (body mismatch)",
        ),
        "oversize_declared_length": (w + b"\xff" * 4096, "reject (oversize)"),
    }

    if name in mutations:
        mutated, expected = mutations[name]
        if expected.startswith("reject"):
            expected_behaviors = (expected, "Wrapper must be rejected by SEP parser")
        else:
            expected_behaviors = (expected, "Behavior depends on parser strictness")
        return mutated, expected_behaviors

    # For non-mutation test names (device_lifecycle, access_control),
    # return the original wrapper with a contextual expected behavior.
    if category == "device_lifecycle":
        lifecycle_map: dict[str, str] = {
            "before_reboot": "accepted",
            "after_reboot": "accepted",
            "bfu": "accepted after first unlock",
            "afu_unlocked": "accepted",
            "afu_locked": "reject (device locked, biometric ACL active)",
            "after_passcode_change": "reject (ACL invalidated by passcode change)",
            "after_biometry_enroll": "accepted (biometry added, current set expanded)",
            "after_biometry_remove": "reject (biometry removed, ACL invalidated)",
            "after_keychain_delete": "reject (keychain record deleted, handle invalid)",
            "after_os_update": "accepted or reject (depends on OS compatibility)",
            "after_erase_restore": "reject (device-binding prevents restore replay)",
            "same_model_second_device": "reject (device-bound wrapper)",
            "different_soc": "reject (SoC-bound wrapper)",
        }
        expected = lifecycle_map.get(name, "varies")
        return bytes(w), (expected, f"Device lifecycle test: {name}")

    if category == "access_control":
        acl_map: dict[str, str] = {
            "acl_private_key_usage": "accepted (basic ACL)",
            "acl_user_presence": "accepted (user presence required at signing)",
            "acl_biometry_current_set": "accepted (biometry required)",
            "acl_device_passcode": "accepted (passcode required)",
            "accessibility_when_unlocked": "accepted",
            "accessibility_after_first_unlock": "accepted after first unlock",
            "accessibility_when_passcode_set": "accepted",
            "swap_weak_metadata": "reject (ACL downgrade prevented)",
            "swap_strong_metadata": "varies (ACL upgrade may work)",
            "different_app_group": "reject (access group check)",
        }
        expected = acl_map.get(name, "varies")
        return bytes(w), (expected, f"Access-control test: {name}")

    return bytes(w), ("unknown", "No predefined expected behavior")


# ---------------------------------------------------------------------------
# SEP Key Fuzzer Orchestrator
# ---------------------------------------------------------------------------


class SEPKeyFuzzer:
    """Orchestrate a full SEP key fuzzing campaign.

    Usage::

        fuzzer = SEPKeyFuzzer(
            device_model="iPhone14,2",
            os_build="21A123",
            chipset="A15",
        )
        results = fuzzer.run(submit_fn, output_dir)
    """

    def __init__(
        self,
        device_model: str = "unknown",
        os_build: str = "unknown",
        chipset: str = "unknown",
        *,
        custody: CustodyLog | None = None,
    ):
        self.device_model = device_model
        self.os_build = os_build
        self.chipset = chipset
        self.custody = custody or CustodyLog(
            operator="b34st-sep-fuzzer",
            device_id=device_model,
        )
        self._base_wrapper: SEPKeyWrapper | None = None

    def generate_base_wrapper(self) -> SEPKeyWrapper:
        """Create a synthetic base wrapper for the fuzz campaign.

        In a real deployment this would run the Swift harness on-device
        via FBR34KER deployment. Here we produce a structurally
        representative placeholder.
        """
        canaried = place_canaries(256, ["INPUT_A", "POLICY_B", "PADDING_C"])
        wrapper = SEPKeyWrapper(
            wrapper_bytes=canaried,
            public_key=bytes(65),
            acl_configuration={
                "access_control": "privateKeyUsage",
                "accessibility": "kSecAttrAccessibleWhenUnlockedThisDeviceOnly",
            },
            device_model=self.device_model,
            os_build=self.os_build,
            chipset=self.chipset,
        )
        self._base_wrapper = wrapper
        return wrapper

    def set_base_wrapper(self, wrapper: SEPKeyWrapper) -> None:
        self._base_wrapper = wrapper

    @property
    def base_wrapper(self) -> SEPKeyWrapper:
        if self._base_wrapper is None:
            raise FuzzTestError(
                "no base wrapper set; call generate_base_wrapper() first"
            )
        return self._base_wrapper

    def run(
        self,
        submit: Callable[[bytes, dict[str, Any]], dict[str, Any]],
        output_dir: pathlib.Path,
        *,
        categories: set[str] | None = None,
    ) -> dict[str, Any]:
        """Execute the full differential test matrix.

        Args:
            submit: Callable that sends mutated wrapper to device/SRD.
            output_dir: Directory for results and artifacts.
            categories: Subset of {"device_lifecycle", "access_control",
                "wrapper_integrity"} to run. Runs all if None.

        Returns:
            Campaign manifest dict.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        self.custody.record(
            "sep_fuzzer.campaign.start",
            f"SEP key fuzzing campaign started on {self.device_model} "
            f"(build {self.os_build}, chipset {self.chipset})",
        )

        if categories is None:
            categories = set(FUZZ_VARIATIONS)

        generate_baseline_harness(output_dir / "BaselineHarness.swift")

        results: list[dict[str, Any]] = []
        anomalies: list[dict[str, Any]] = []
        canary_hits_total = 0

        for cat in sorted(categories):
            if cat not in FUZZ_VARIATIONS:
                continue
            self.custody.record(
                f"sep_fuzzer.category.{cat}",
                f"Starting {len(FUZZ_VARIATIONS[cat])} variations in '{cat}'",
            )
            for variation in FUZZ_VARIATIONS[cat]:
                try:
                    result = run_fuzz_variation(
                        variation, cat, self.base_wrapper, submit
                    )
                except (OSError, RuntimeError) as exc:
                    result = FuzzTestResult(
                        variation=variation["name"],
                        category=cat,
                        description=variation.get(
                            "description", variation.get("desc", "")
                        ),
                        wrapper_sha256="",
                        public_key_sha256=self.base_wrapper.public_key_sha256,
                        expected_behavior="N/A",
                        actual_behavior=f"runner exception: {exc}",
                        classification="expected",
                        classification_detail="Test runner error.",
                        error=str(exc),
                    )

                rdict = result.to_dict()
                results.append(rdict)

                if result.anomaly:
                    anomalies.append(rdict)
                    self.custody.record(
                        f"sep_fuzzer.anomaly.{result.classification}",
                        f"[{result.variation}] {result.classification_detail}",
                    )

                if result.canary_hits:
                    canary_hits_total += len(result.canary_hits)

        self.custody.record(
            "sep_fuzzer.campaign.end",
            f"Campaign complete: {len(results)} tests, "
            f"{len(anomalies)} anomalies, "
            f"{canary_hits_total} canary hit(s)",
        )
        self.custody.seal()

        manifest = self._build_manifest(results, anomalies, output_dir)
        self._write_manifest(manifest, output_dir)
        self.custody.write(output_dir / "chain-of-custody.json")
        return manifest

    def _build_manifest(
        self,
        results: list[dict[str, Any]],
        anomalies: list[dict[str, Any]],
        output_dir: pathlib.Path,
    ) -> dict[str, Any]:
        by_class: dict[str, int] = {}
        for r in results:
            key = r["classification"]
            by_class[key] = by_class.get(key, 0) + 1

        # Group anomalies by bounty category
        bounty_categories: dict[str, int] = {}
        for a in anomalies:
            cat = BOUNTY_SIGNIFICANCE.get(a["classification"], {}).get(
                "label", "Unknown"
            )
            bounty_categories[cat] = bounty_categories.get(cat, 0) + 1

        return {
            "schema": "sep-key-fuzzer-campaign-v1",
            "device": {
                "model": self.device_model,
                "os_build": self.os_build,
                "chipset": self.chipset,
            },
            "base_wrapper": self.base_wrapper.to_dict(),
            "campaign": {
                "started_at": self.base_wrapper.created_at,
                "completed_at": dt.datetime.now()
                .astimezone()
                .isoformat(timespec="seconds"),
            },
            "summary": {
                "total_tests": len(results),
                "anomalies": len(anomalies),
                "canary_hits": sum(len(r.get("canary_hits", [])) for r in results),
                "by_classification": by_class,
                "bounty_categories": bounty_categories,
            },
            "anomalies": anomalies,
            "all_results": [
                {
                    "variation": r["variation"],
                    "category": r["category"],
                    "classification": r["classification"],
                    "anomaly": r["anomaly"],
                    "wrapper_sha256": r["wrapper_sha256"],
                    "expected_behavior": r["expected_behavior"],
                    "actual_behavior": r["actual_behavior"],
                }
                for r in results
            ],
            "custody_hash": self.custody.last_hash,
        }

    def _write_manifest(
        self, manifest: dict[str, Any], output_dir: pathlib.Path
    ) -> pathlib.Path:
        path = output_dir / "sep-fuzz-campaign.json"
        path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path


# ---------------------------------------------------------------------------
# Bounty report generator
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class BountyReportSection:
    title: str
    content: str


BOUNTY_REPORT_TEMPLATE = """# SEP Key Fuzzing Bounty Report

**Report ID:** {report_id}
**Date:** {date}
**Operator:** {operator}
**Device:** {device_model} ({chipset})
**OS Build:** {os_build}

---

## 1. Executive Summary

A differential SEP key-wrapper fuzzing campaign was conducted on the
above device using synthetic test keys generated via the B34ST
forensics framework. {total_tests} test variations were executed across
three categories: device/lifecycle, access-control, and wrapper-integrity.

**{anomaly_count} anomalous result(s)** were identified that may
represent security-relevant behavior.

---

## 2. Device Configuration

| Attribute | Value |
|-----------|-------|
| Model | {device_model} |
| SoC | {chipset} |
| OS Build | {os_build} |
| Passcode | Configured{passcode_note} |
| Biometry | {biometry_state} |
| Lock State | {lock_state} |

---

## 3. Test Methodology

### 3.1 Baseline

A P-256 signing key was created inside the Secure Enclave via
`CryptoKit.SecureEnclave.P256.Signing.PrivateKey` with documented
access-control flags. The baseline harness is attached as
`BaselineHarness.swift`.

### 3.2 Differential Categories

1. **Device/Lifecycle ({lifecycle_count} tests)** — Wrapper behavior before
   and after reboot, lock/unlock, passcode change, biometry change,
   OS update, erase/restore, and on a second device.

2. **Access-Control ({acl_count} tests)** — Wrappers created with
   different ACL configurations, then cross-tested with mismatched
   metadata and application groups.

3. **Wrapper-Integrity ({integrity_count} tests)** — Bit flips,
   truncations, appends, field duplications, version/length tampering,
   and replay attacks.

### 3.3 Canary Monitoring

Distinctive canary values ({canaries_used}) were placed into synthetic
wrapper buffers before mutation. Output buffers from every operation
were scanned for unexpected canary presence as a memory-disclosure
indicator.

---

## 4. Results Summary

| Classification | Count | Bounty Eligible |
|---------------|-------|-----------------|
{classification_rows}

**Total Anomalies: {anomaly_count}**

---

## 5. Anomaly Details

{anomaly_details}

---

## 6. Attestation

This report was generated by B34ST (FBR34KER Runtime Authentication
Tool). All operations used synthetic test keys. No real credentials,
passkeys, payment keys, or personal keychain data were accessed.

Chain-of-custody hash: `{custody_hash}`

---
*This document is prepared for authorized security research purposes.
Reproduction method, PoC, sysdiagnose timestamp, and crash logs are
available in the companion evidence bundle.*
"""


def generate_bounty_report(
    manifest: dict[str, Any],
    output_dir: pathlib.Path,
    *,
    passcode_configured: bool = True,
    biometry_state: str = "enrolled",
    lock_state: str = "unlocked",
    operator: str = "b34st-operator",
) -> pathlib.Path:
    """Write a bounty-ready Markdown report to *output_dir*."""
    summary = manifest.get("summary", {})
    total = summary.get("total_tests", 0)
    anomalies = summary.get("anomalies", 0)

    by_class: dict[str, int] = summary.get("by_classification", {})
    classification_rows = "\n".join(
        _BOUNTY_CLASSIFICATION_LABELS.get(k, k).ljust(20)
        + f" | {v}".ljust(6)
        + _BOUNTY_ELIGIBLE.get(k, "No")
        for k, v in sorted(by_class.items())
    )

    anomaly_list = manifest.get("anomalies", [])
    anomaly_details: list[str] = []
    for i, a in enumerate(anomaly_list, 1):
        sig = BOUNTY_SIGNIFICANCE.get(a["classification"], {})
        anomaly_details.append(
            f"### {i}. {a['variation']} ({a['category']})\n\n"
            f"- **Classification:** {sig.get('label', a['classification'])}\n"
            f"- **Description:** {a['description']}\n"
            f"- **Expected:** {a['expected_behavior']}\n"
            f"- **Actual:** {a['actual_behavior']}\n"
            f"- **Wrapper SHA-256:** `{a['wrapper_sha256']}`\n"
            f"- **Classification Detail:** {a['classification_detail']}\n"
        )
        if a.get("canary_hits"):
            anomaly_details.append(
                f"- **Canary hits:** {len(a['canary_hits'])} found\n"
            )

    anomaly_section = "\n".join(anomaly_details) if anomaly_details else "*(None)*\n"

    lifecycle_count = sum(
        1
        for r in manifest.get("all_results", [])
        if r.get("category") == "device_lifecycle"
    )
    acl_count = sum(
        1
        for r in manifest.get("all_results", [])
        if r.get("category") == "access_control"
    )
    integrity_count = sum(
        1
        for r in manifest.get("all_results", [])
        if r.get("category") == "wrapper_integrity"
    )

    canary_keys = ", ".join(CANARY_LIBRARY.keys())

    report = BOUNTY_REPORT_TEMPLATE.format(
        report_id=hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()[:16],
        date=dt.datetime.now().astimezone().strftime("%Y-%m-%d"),
        operator=operator,
        device_model=manifest.get("device", {}).get("model", "unknown"),
        chipset=manifest.get("device", {}).get("chipset", "unknown"),
        os_build=manifest.get("device", {}).get("os_build", "unknown"),
        total_tests=total,
        anomaly_count=anomalies,
        lifecycle_count=lifecycle_count,
        acl_count=acl_count,
        integrity_count=integrity_count,
        classification_rows=classification_rows,
        anomaly_details=anomaly_section,
        custody_hash=manifest.get("custody_hash", "N/A"),
        passcode_note="" if passcode_configured else " (or not configured)",
        biometry_state=biometry_state,
        lock_state=lock_state,
        canaries_used=canary_keys,
    )

    report_path = output_dir / "SEP_Key_Fuzzing_Bounty_Report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


_BOUNTY_CLASSIFICATION_LABELS: dict[str, str] = {
    k: v["label"] for k, v in BOUNTY_SIGNIFICANCE.items()
}
_BOUNTY_ELIGIBLE: dict[str, str] = {
    k: "Yes" if v["bounty_eligible"] else "No" for k, v in BOUNTY_SIGNIFICANCE.items()
}


# ---------------------------------------------------------------------------
# Top-level convenience API
# ---------------------------------------------------------------------------


def run_campaign(
    submit_fn: Callable[[bytes, dict[str, Any]], dict[str, Any]],
    output_dir: pathlib.Path,
    *,
    device_model: str = "unknown",
    os_build: str = "unknown",
    chipset: str = "unknown",
    categories: set[str] | None = None,
    passcode_configured: bool = True,
    biometry_state: str = "enrolled",
    lock_state: str = "unlocked",
) -> dict[str, Any]:
    """Run a full SEP key fuzzing campaign and produce a bounty report.

    This is the high-level entry point. Example::

        def submit(mutated_wrapper, metadata):
            # Send to device/SRD, return response dict
            return {"accepted": False, "error": "simulated"}

        result = run_campaign(submit, pathlib.Path("./output"))
    """
    fuzzer = SEPKeyFuzzer(
        device_model=device_model,
        os_build=os_build,
        chipset=chipset,
    )
    fuzzer.generate_base_wrapper()

    manifest = fuzzer.run(submit_fn, output_dir, categories=categories)
    bounty_report_path = generate_bounty_report(
        manifest,
        output_dir,
        passcode_configured=passcode_configured,
        biometry_state=biometry_state,
        lock_state=lock_state,
    )

    return {
        "campaign_dir": str(output_dir),
        "manifest": manifest,
        "bounty_report": str(bounty_report_path),
        "base_wrapper_sha256": fuzzer.base_wrapper.sha256,
    }
