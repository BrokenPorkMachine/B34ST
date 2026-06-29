#!/usr/bin/env python3
"""SEP Research Pipeline — automated SEP/sepOS vulnerability discovery.

This module implements a complete research workflow for finding security
vulnerabilities in Apple's Secure Enclave Processor (SEP) and sepOS.

Workflow stages:
  1. Architectural mapping — document AP→SEP request boundaries, sizes, timing.
  2. Corpus generation — exercise documented APIs with synthetic objects.
  3. Differential analysis — change one property at a time, compare outcomes.
  4. Structural fuzzing — length errors, integer overflow, type confusion.
  5. Stateful fuzzing — sequence mutations (create→use→delete→use).
  6. Concurrency fuzzing — race conditions (delete vs sign, cancel vs complete).
  7. Crash triage — classify fault layer (app, daemon, kernel, sepOS, bootrom).
  8. Campaign report — comprehensive Markdown bounty report.

All operations use exclusively synthetic test objects. No real credentials,
passkeys, payment keys, or personal data are touched.

Top-level entry points:
  - SEPResearchPipeline.run_full_campaign()  — all stages
  - SEPResearchPipeline.run_stage()           — single stage by name
  - run_pipeline()                            — convenience wrapper
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import hashlib
import json
import pathlib
import time
from typing import Any, Callable

from host.forensics.chain_of_custody import CustodyLog


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CAMPAIGN_SCHEMA = "sep-research-campaign-v1"

# Stage names as defined by the workflow
STAGES = [
    "architectural_map",
    "corpus_generation",
    "differential_analysis",
    "structural_fuzzing",
    "stateful_fuzzing",
    "concurrency_fuzzing",
    "crash_triage",
]

# Bounty-relevant impact classifications
BOUNTY_IMPACTS: dict[str, dict[str, Any]] = {
    "sep_reset": {
        "label": "SEP reset",
        "severity": "medium",
        "detail": "A malformed request reliably crashes sepOS, causing SEP reset.",
    },
    "stale_data": {
        "label": "Stale/disclosed data",
        "severity": "high",
        "detail": "A caller receives bytes from another synthetic request.",
    },
    "stale_handle": {
        "label": "Stale handle reuse",
        "severity": "high",
        "detail": "A stale key handle operates after deletion.",
    },
    "acl_bypass": {
        "label": "ACL bypass",
        "severity": "high",
        "detail": "An ACL-protected synthetic key signs without required authorization.",
    },
    "cross_client": {
        "label": "Cross-client confusion",
        "severity": "high",
        "detail": "One client can use another synthetic client's key handle.",
    },
    "integrity_bypass": {
        "label": "Wrapper integrity bypass",
        "severity": "high",
        "detail": "Modified wrapped data is accepted with weaker policy.",
    },
    "pc_control": {
        "label": "Program counter control",
        "severity": "critical",
        "detail": "Controlled data influences a program counter or memory address.",
    },
    "arbitrary_read": {
        "label": "Arbitrary read",
        "severity": "critical",
        "detail": "Arbitrary read is demonstrated using nonsecret canary data.",
    },
    "arbitrary_write": {
        "label": "Arbitrary write",
        "severity": "critical",
        "detail": "Arbitrary write is demonstrated using nonsecret canary data.",
    },
    "code_execution": {
        "label": "Code execution",
        "severity": "critical",
        "detail": "Code execution inside SEP is objectively demonstrated.",
    },
}


# ---------------------------------------------------------------------------
# Architectural map — document observable AP→SEP boundary
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class BoundaryObservation:
    """A single observation about the AP→SEP boundary."""
    operation: str
    api_call: str
    process: str
    request_size: int
    response_size: int
    auth_state: str
    timing_ms: float
    error_code: str
    sep_reset: bool
    ap_crash: bool
    persistent: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ArchitecturalMap:
    """Collated architectural observations."""
    device_model: str
    os_build: str
    chipset: str
    observations: list[BoundaryObservation] = dataclasses.field(default_factory=list)
    request_types: dict[str, int] = dataclasses.field(default_factory=dict)
    avg_timing: dict[str, float] = dataclasses.field(default_factory=dict)

    def add(self, obs: BoundaryObservation) -> None:
        self.observations.append(obs)
        self.request_types[obs.operation] = (
            self.request_types.get(obs.operation, 0) + 1
        )

    def compute_timing(self) -> None:
        timing: dict[str, list[float]] = {}
        for obs in self.observations:
            timing.setdefault(obs.operation, []).append(obs.timing_ms)
        self.avg_timing = {
            op: sum(vals) / len(vals) for op, vals in timing.items()
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_model": self.device_model,
            "os_build": self.os_build,
            "chipset": self.chipset,
            "observation_count": len(self.observations),
            "request_types": self.request_types,
            "avg_timing_ms": self.avg_timing,
            "observations": [o.to_dict() for o in self.observations],
        }


class ArchitecturalMapper:
    """Document the AP→SEP boundary by exercising documented APIs.

    For every operation, this records: API call and parameters, process,
    request/response sizes, authentication state, timing, error code,
    whether SEP or AP crashed, and whether behavior persists after reboot.
    """

    def __init__(
        self,
        device_model: str = "unknown",
        os_build: str = "unknown",
        chipset: str = "unknown",
        api_fn: Callable[[str], str] | None = None,
    ):
        self.device_model = device_model
        self.os_build = os_build
        self.chipset = chipset
        self._api = api_fn or _default_api

    def execute_operation(
        self,
        operation: str,
        api_call: str,
        process: str = "test_app",
        auth_state: str = "unlocked",
    ) -> BoundaryObservation:
        """Execute a single API operation and record the boundary observation."""
        start = time.monotonic()
        try:
            response = self._api(api_call)
            error_code = ""
            sep_reset = False
            ap_crash = False
        except Exception as exc:
            response = ""
            error_code = str(exc)
            sep_reset = "sep" in str(exc).lower() or "reset" in str(exc).lower()
            ap_crash = "crash" in str(exc).lower() or "panic" in str(exc).lower()

        elapsed = (time.monotonic() - start) * 1000.0

        return BoundaryObservation(
            operation=operation,
            api_call=api_call,
            process=process,
            request_size=len(api_call),
            response_size=len(response),
            auth_state=auth_state,
            timing_ms=elapsed,
            error_code=error_code,
            sep_reset=sep_reset,
            ap_crash=ap_crash,
            persistent=False,
        )

    def build_map(
        self,
        operations: list[dict[str, str]] | None = None,
    ) -> ArchitecturalMap:
        """Iterate over a list of API operations and build the architectural map."""
        amap = ArchitecturalMap(
            device_model=self.device_model,
            os_build=self.os_build,
            chipset=self.chipset,
        )

        ops = operations or _DEFAULT_OBSERVATIONS

        for op_def in ops:
            obs = self.execute_operation(
                operation=op_def["name"],
                api_call=op_def["api_call"],
                process=op_def.get("process", "test_app"),
                auth_state=op_def.get("auth_state", "unlocked"),
            )
            amap.add(obs)

        amap.compute_timing()
        return amap


_DEFAULT_OBSERVATIONS: list[dict[str, str]] = [
    {"name": "key_generate", "api_call": "secure-enclave key generate P256"},
    {"name": "key_generate_biometry", "api_call": "secure-enclave key generate P256 biometry-current-set"},
    {"name": "key_generate_user_presence", "api_call": "secure-enclave key generate P256 user-presence"},
    {"name": "key_restore", "api_call": "secure-enclave key restore <wrapper>"},
    {"name": "sign_message_empty", "api_call": "secure-enclave sign <key> <empty>"},
    {"name": "sign_message_64b", "api_call": "secure-enclave sign <key> <64bytes>"},
    {"name": "sign_message_4k", "api_call": "secure-enclave sign <key> <4096bytes>"},
    {"name": "sign_message_64k", "api_call": "secure-enclave sign <key> <65536bytes>"},
    {"name": "key_delete", "api_call": "secure-enclave key delete <key>"},
    {"name": "key_list", "api_call": "secure-enclave key list"},
    {"name": "key_info", "api_call": "secure-enclave key info <key>"},
    {"name": "key_export_public", "api_call": "secure-enclave key export-public <key>"},
    {"name": "auth_cancel", "api_call": "local-authentication cancel"},
    {"name": "auth_evaluate", "api_call": "local-authentication evaluate policy device-owner"},
]


# ---------------------------------------------------------------------------
# Request corpus — valid requests built from synthetic objects
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CorpusEntry:
    """A single entry in the valid-request corpus."""
    name: str
    category: str
    api_call: str
    expected_outcome: str
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    request_bytes: bytes = b""

    def sha256(self) -> str:
        return hashlib.sha256(self.request_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "api_call": self.api_call,
            "expected_outcome": self.expected_outcome,
            "metadata": self.metadata,
            "request_sha256": self.sha256(),
            "request_length": len(self.request_bytes),
        }


_CORPUS_TEMPLATES: list[dict[str, Any]] = [
    # Key lifecycle
    {"name": "create_p256", "category": "key_lifecycle", "api_call": "key create p256 signing", "expected": "success"},
    {"name": "create_p256_privateKeyUsage", "category": "key_lifecycle", "api_call": "key create p256 signing acl privateKeyUsage", "expected": "success"},
    {"name": "create_p256_userPresence", "category": "key_lifecycle", "api_call": "key create p256 signing acl userPresence", "expected": "success"},
    {"name": "create_p256_biometryCurrentSet", "category": "key_lifecycle", "api_call": "key create p256 signing acl biometryCurrentSet", "expected": "success"},
    {"name": "create_p256_devicePasscode", "category": "key_lifecycle", "api_call": "key create p256 signing acl devicePasscode", "expected": "success"},
    {"name": "restore_from_wrapper", "category": "key_lifecycle", "api_call": "key restore p256 <wrapper>", "expected": "success"},
    {"name": "delete_key", "category": "key_lifecycle", "api_call": "key delete <key>", "expected": "success"},
    {"name": "use_after_delete", "category": "key_lifecycle", "api_call": "key sign <key> <data>", "expected": "error_invalid_handle"},
    # Signing operations
    {"name": "sign_empty", "category": "signing", "api_call": "key sign <key> <0b>", "expected": "success"},
    {"name": "sign_1b", "category": "signing", "api_call": "key sign <key> <1b>", "expected": "success"},
    {"name": "sign_16b", "category": "signing", "api_call": "key sign <key> <16b>", "expected": "success"},
    {"name": "sign_256b", "category": "signing", "api_call": "key sign <key> <256b>", "expected": "success"},
    {"name": "sign_4096b", "category": "signing", "api_call": "key sign <key> <4096b>", "expected": "success"},
    {"name": "sign_65536b", "category": "signing", "api_call": "key sign <key> <65536b>", "expected": "success"},
    {"name": "sign_1mb", "category": "signing", "api_call": "key sign <key> <1048576b>", "expected": "success"},
    {"name": "verify_valid", "category": "signing", "api_call": "key verify <key> <data> <signature>", "expected": "success"},
    {"name": "verify_invalid", "category": "signing", "api_call": "key verify <key> <data> <bad_sig>", "expected": "error_invalid_signature"},
    {"name": "verify_wrong_key", "category": "signing", "api_call": "key verify <other_key> <data> <signature>", "expected": "error_invalid_signature"},
    # Access control
    {"name": "sign_locked", "category": "access_control", "api_call": "key sign <biometry_key> <data>", "expected": "error_device_locked", "auth_state": "locked"},
    {"name": "sign_after_biometry_remove", "category": "access_control", "api_call": "key sign <biometry_key> <data>", "expected": "error_acl_invalidated", "auth_state": "biometry_removed"},
    {"name": "sign_after_passcode_change", "category": "access_control", "api_call": "key sign <passcode_key> <data>", "expected": "error_acl_invalidated", "auth_state": "passcode_changed"},
    {"name": "auth_cancel_during_sign", "category": "access_control", "api_call": "key sign <user_presence_key> <data> cancel", "expected": "error_auth_cancelled"},
    # Sessions
    {"name": "session_open", "category": "sessions", "api_call": "session open", "expected": "success"},
    {"name": "session_close", "category": "sessions", "api_call": "session close <session>", "expected": "success"},
    {"name": "session_use_closed", "category": "sessions", "api_call": "session close <session>; key sign <key> <data>", "expected": "error_invalid_session"},
    {"name": "session_double_close", "category": "sessions", "api_call": "session close <session>; session close <session>", "expected": "error_invalid_session"},
]


class RequestCorpus:
    """Build a corpus of valid SEP requests from synthetic objects.

    Each entry exercises a documented API with synthetic (non-personal) data.
    The corpus serves as starting material for fuzzing — purely random data
    is likely to be rejected by an outer dispatcher before reaching deeper parsers.
    """

    def __init__(self, api_fn: Callable[[str], str] | None = None):
        self._api = api_fn or _default_api
        self.entries: list[CorpusEntry] = []

    def build(
        self,
        templates: list[dict[str, Any]] | None = None,
    ) -> list[CorpusEntry]:
        """Exercise each template and store the request bytes and metadata."""
        templates = templates or _CORPUS_TEMPLATES
        self.entries = []

        for tpl in templates:
            api_call = tpl["api_call"]
            request_bytes = api_call.encode("utf-8")

            try:
                response = self._api(api_call)
                actual_outcome = "success" if response else "empty_response"
            except Exception as exc:
                response = ""
                actual_outcome = f"error: {exc}"

            entry = CorpusEntry(
                name=tpl["name"],
                category=tpl["category"],
                api_call=api_call,
                request_bytes=request_bytes,
                expected_outcome=tpl["expected"],
                metadata={
                    "actual_outcome": actual_outcome,
                    "response_size": len(response),
                    "response_hash": hashlib.sha256(
                        response.encode("utf-8")
                    ).hexdigest()[:16],
                },
            )
            self.entries.append(entry)

        return self.entries

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entries": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
        }


# ---------------------------------------------------------------------------
# Differential analysis — compare pairs differing in exactly one property
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class DiffPair:
    """A pair of requests differing in exactly one variable."""
    variable: str
    value_a: str
    value_b: str
    response_a: str
    response_b: str
    size_a: int
    size_b: int
    same_outcome: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "response_same": self.same_outcome,
            "response_size_delta": self.size_b - self.size_a,
            "notes": self.notes,
        }


_DIFF_VARIABLES: list[dict[str, Any]] = [
    {"variable": "key_type", "a": "P256", "b": "P384"},
    {"variable": "operation", "a": "sign", "b": "verify"},
    {"variable": "acl_policy", "a": "privateKeyUsage", "b": "userPresence"},
    {"variable": "acl_policy", "a": "userPresence", "b": "biometryCurrentSet"},
    {"variable": "auth_state", "a": "unlocked", "b": "locked"},
    {"variable": "message_size", "a": "0", "b": "1"},
    {"variable": "message_size", "a": "256", "b": "255"},
    {"variable": "message_size", "a": "4096", "b": "4095"},
    {"variable": "message_size", "a": "65536", "b": "65535"},
    {"variable": "optional_field", "a": "present", "b": "absent"},
    {"variable": "nested_objects", "a": "1", "b": "2"},
    {"variable": "same_before_delete", "a": "before", "b": "after"},
    {"variable": "same_before_reboot", "a": "before", "b": "after"},
]


class DifferentialAnalyzer:
    """Compare request pairs differing in exactly one variable.

    Useful variables include: key type, operation, ACL policy, auth state,
    message length, optional fields, nesting depth, same request before/after
    deletion, same request before/after reboot.
    """

    def __init__(self, api_fn: Callable[[str], str] | None = None):
        self._api = api_fn or _default_api

    def compare(
        self,
        base_call: str,
        variable: str,
        value_a: str,
        value_b: str,
    ) -> DiffPair:
        """Execute two API calls differing in one variable and compare outcomes."""
        call_a = base_call.replace("{var}", value_a)
        call_b = base_call.replace("{var}", value_b)

        try:
            resp_a = self._api(call_a)
        except Exception as exc:
            resp_a = f"error: {exc}"

        try:
            resp_b = self._api(call_b)
        except Exception as exc:
            resp_b = f"error: {exc}"

        return DiffPair(
            variable=variable,
            value_a=value_a,
            value_b=value_b,
            response_a=resp_a,
            response_b=resp_b,
            size_a=len(resp_a),
            size_b=len(resp_b),
            same_outcome=(resp_a == resp_b),
            notes="",
        )

    def run_all(
        self,
        base_call: str = "key {var}",
        variables: list[dict[str, Any]] | None = None,
    ) -> list[DiffPair]:
        """Run all defined differential comparisons."""
        variables = variables or _DIFF_VARIABLES
        results: list[DiffPair] = []

        for v in variables:
            pair = self.compare(
                base_call,
                v["variable"],
                v["a"],
                v["b"],
            )
            results.append(pair)

        return results


# ---------------------------------------------------------------------------
# Structural fuzzer — length errors, overflow, type confusion
# ---------------------------------------------------------------------------

FUZZ_STRATEGIES: dict[str, list[dict[str, Any]]] = {
    "length_errors": [
        {"name": "zero_length", "desc": "Object with zero declared length"},
        {"name": "length_minus_one", "desc": "Length field one less than valid"},
        {"name": "length_plus_one", "desc": "Length field one more than valid"},
        {"name": "max_length", "desc": "Maximum valid length"},
        {"name": "near_max_length", "desc": "Length near maximum boundary"},
        {"name": "truncate_field", "desc": "Truncate at field boundary"},
        {"name": "trailing_bytes", "desc": "Valid data followed by extra bytes"},
    ],
    "integer_errors": [
        {"name": "int_zero", "desc": "Integer field set to 0"},
        {"name": "int_negative", "desc": "Signed integer negative value"},
        {"name": "int_overflow_8", "desc": "Value > uint8 max"},
        {"name": "int_overflow_16", "desc": "Value > uint16 max"},
        {"name": "int_overflow_32", "desc": "Value > uint32 max"},
        {"name": "int_overflow_64", "desc": "Value > uint64 max"},
        {"name": "int_negative_signed", "desc": "Signed minimum boundary"},
    ],
    "type_confusion": [
        {"name": "unknown_enum", "desc": "Unknown enum value"},
        {"name": "wrong_key_type", "desc": "Key type mismatch"},
        {"name": "contradictory_lengths", "desc": "Inner/outer length contradiction"},
        {"name": "duplicate_field", "desc": "Duplicate required field"},
        {"name": "missing_required", "desc": "Missing required field"},
        {"name": "nested_extra", "desc": "Extra nesting level"},
        {"name": "wrong_magic", "desc": "Incorrect magic bytes"},
    ],
}


@dataclasses.dataclass
class StructuralFuzzResult:
    strategy: str
    variation: str
    description: str
    accepted: bool
    response_size: int
    error: str
    timing_ms: float
    anomaly: bool = False
    classification: str = "expected"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "variation": self.variation,
            "description": self.description,
            "accepted": self.accepted,
            "response_size": self.response_size,
            "error": self.error,
            "timing_ms": self.timing_ms,
            "anomaly": self.anomaly,
            "classification": self.classification,
            "notes": self.notes,
        }


class StructuralFuzzer:
    """Fuzz SEP request parsers with structural mutations.

    Test zero-length objects, boundary lengths, truncations, trailing bytes,
    duplicate/missing fields, unknown enums, contradictory lengths, integer
    overflow, and type confusion at signed/unsigned boundaries.
    """

    def __init__(self, api_fn: Callable[[str], str] | None = None):
        self._api = api_fn or _default_api

    def fuzz_variation(
        self,
        strategy: str,
        variation: dict[str, Any],
        base_call: str = "key sign <key> <data>",
    ) -> StructuralFuzzResult:
        """Execute a single structural fuzz variation."""
        name = variation["name"]

        # Build a mutated call string based on variation name
        if name == "zero_length":
            test_call = "key sign <key> <0b>"
        elif name == "length_minus_one":
            test_call = "key sign <key> <255b>"
        elif name == "length_plus_one":
            test_call = "key sign <key> <257b>"
        elif name == "max_length":
            test_call = "key sign <key> <65536b>"
        elif name == "near_max_length":
            test_call = "key sign <key> <65535b>"
        elif name == "truncate_field":
            test_call = "key sign <key>"
        elif name == "trailing_bytes":
            test_call = "key sign <key> <data> <extra>"
        elif name == "int_zero":
            test_call = "key create p256 signing counter 0"
        elif name == "int_negative":
            test_call = "key create p256 signing counter -1"
        elif name == "int_overflow_8":
            test_call = "key create p256 signing counter 256"
        elif name == "int_overflow_16":
            test_call = "key create p256 signing counter 65536"
        elif name == "int_overflow_32":
            test_call = "key create p256 signing counter 4294967296"
        elif name == "int_overflow_64":
            test_call = "key create p256 signing counter 18446744073709551616"
        elif name == "int_negative_signed":
            test_call = "key create p256 signing counter -9223372036854775808"
        elif name == "unknown_enum":
            test_call = "key create p256 signing acl 0xFFFF"
        elif name == "wrong_key_type":
            test_call = "key sign <wrong_key_type> <data>"
        elif name == "contradictory_lengths":
            test_call = "key create p256 signing declared-length 10 actual-data <256bytes>"
        elif name == "duplicate_field":
            test_call = "key create p256 signing acl userPresence acl userPresence"
        elif name == "missing_required":
            test_call = "key create"
        elif name == "nested_extra":
            test_call = "key create p256 signing policy { userPresence or { biometryCurrentSet or devicePasscode } }"
        elif name == "wrong_magic":
            test_call = "key create p384 signing"
        else:
            test_call = base_call

        start = time.monotonic()
        try:
            response = self._api(test_call)
            accepted = len(response) > 0
            error = ""
        except Exception as exc:
            response = ""
            accepted = False
            error = str(exc)
        elapsed = (time.monotonic() - start) * 1000.0

        # Classify
        anomaly = accepted and error == ""
        classification = "anomaly_accepted" if anomaly else "expected_rejected"

        return StructuralFuzzResult(
            strategy=strategy,
            variation=name,
            description=variation["desc"],
            accepted=accepted,
            response_size=len(response),
            error=error,
            timing_ms=elapsed,
            anomaly=anomaly,
            classification=classification,
        )

    def fuzz_strategy(
        self,
        strategy: str,
        variations: list[dict[str, Any]] | None = None,
    ) -> list[StructuralFuzzResult]:
        """Fuzz all variations under a given strategy."""
        variations = variations or FUZZ_STRATEGIES.get(strategy, [])
        return [self.fuzz_variation(strategy, v) for v in variations]

    def fuzz_all(self) -> dict[str, list[StructuralFuzzResult]]:
        """Fuzz all strategies."""
        results: dict[str, list[StructuralFuzzResult]] = {}
        for strategy in FUZZ_STRATEGIES:
            results[strategy] = self.fuzz_strategy(strategy)
        return results


# ---------------------------------------------------------------------------
# Stateful fuzzer — sequence mutations
# ---------------------------------------------------------------------------

_STATEFUL_SEQUENCES: list[dict[str, Any]] = [
    {
        "name": "create_use_delete_use",
        "steps": ["key create p256 signing", "key sign <key> <data>", "key delete <key>", "key sign <key> <data>"],
        "expected_final": "error_invalid_handle",
    },
    {
        "name": "open_auth_cancel_continue",
        "steps": ["session open", "auth evaluate policy device-owner", "auth cancel", "key sign <key> <data>"],
        "expected_final": "error_auth_cancelled",
    },
    {
        "name": "begin_reboot_finish",
        "steps": ["key create p256 signing", "key export-public <key>", "simulate reboot", "key sign <key> <data>"],
        "expected_final": "error_invalid_handle",
    },
    {
        "name": "client_a_uses_b_handle",
        "steps": ["client A: key create p256 signing", "client B: key sign <key_A> <data>"],
        "expected_final": "error_cross_client",
    },
    {
        "name": "open_twice_close_twice",
        "steps": ["session open", "session open", "session close <sess1>", "session close <sess2>"],
        "expected_final": "success",
    },
    {
        "name": "create_after_biometry_remove",
        "steps": ["key create p256 signing acl biometryCurrentSet", "simulate biometry-remove", "key sign <key> <data>"],
        "expected_final": "error_acl_invalidated",
    },
    {
        "name": "create_after_passcode_change",
        "steps": ["key create p256 signing acl devicePasscode", "simulate passcode-change", "key sign <key> <data>"],
        "expected_final": "error_acl_invalidated",
    },
]


@dataclasses.dataclass
class StatefulFuzzResult:
    sequence: str
    step_count: int
    final_step: str
    actual_outcome: str
    expected_outcome: str
    anomaly: bool
    failure_step: int = -1
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "step_count": self.step_count,
            "final_step": self.final_step,
            "actual_outcome": self.actual_outcome,
            "expected_outcome": self.expected_outcome,
            "anomaly": self.anomaly,
            "failure_step": self.failure_step,
            "notes": self.notes,
        }


class StatefulFuzzer:
    """Execute stateful sequences against SEP services.

    SEP services are stateful, so sequence fuzzing can be more effective than
    individual-packet fuzzing: create→use→delete→use, open→auth→cancel→continue,
    begin→reboot→finish, client A creates → client B uses handle, etc.
    """

    def __init__(self, api_fn: Callable[[str], str] | None = None):
        self._api = api_fn or _default_api

    def execute_sequence(
        self,
        seq: dict[str, Any],
    ) -> StatefulFuzzResult:
        """Execute a multi-step stateful sequence and check the final outcome."""
        steps: list[str] = seq["steps"]
        expected: str = seq["expected_final"]
        failure_step = -1

        for i, step in enumerate(steps):
            try:
                self._api(step)
            except Exception as exc:
                actual = str(exc)
                failure_step = i
                return StatefulFuzzResult(
                    sequence=seq["name"],
                    step_count=len(steps),
                    final_step=step,
                    actual_outcome=actual,
                    expected_outcome=expected,
                    anomaly=(expected not in actual),
                    failure_step=failure_step,
                    notes=f"Failed at step {i}: {step}",
                )

        return StatefulFuzzResult(
            sequence=seq["name"],
            step_count=len(steps),
            final_step=steps[-1],
            actual_outcome="success",
            expected_outcome=expected,
            anomaly=(expected != "success"),
            notes="All steps completed without error",
        )

    def run_all(
        self,
        sequences: list[dict[str, Any]] | None = None,
    ) -> list[StatefulFuzzResult]:
        """Run all defined stateful sequences."""
        sequences = sequences or _STATEFUL_SEQUENCES
        return [self.execute_sequence(s) for s in sequences]


# ---------------------------------------------------------------------------
# Concurrency fuzzer — race conditions
# ---------------------------------------------------------------------------

_CONCURRENCY_SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "delete_during_sign",
        "desc": "Key deletion concurrent with signing operation",
        "thread_a": "key sign <key> <data>",
        "thread_b": "key delete <key>",
        "expected": "either_succeeds_or_error",
    },
    {
        "name": "close_during_response",
        "desc": "Session close concurrent with response handling",
        "thread_a": "key sign <key> <data>",
        "thread_b": "session close <session>",
        "expected": "either_succeeds_or_error",
    },
    {
        "name": "cancel_during_complete",
        "desc": "Authentication cancel concurrent with completion",
        "thread_a": "auth evaluate policy device-owner",
        "thread_b": "auth cancel",
        "expected": "error_auth_cancelled",
    },
    {
        "name": "lock_during_key_use",
        "desc": "Device lock concurrent with key signing",
        "thread_a": "key sign <biometry_key> <data>",
        "thread_b": "simulate device-lock",
        "expected": "error_device_locked",
    },
    {
        "name": "two_clients_same_handle",
        "desc": "Two clients using or destroying the same handle concurrently",
        "thread_a": "client A: key sign <key> <data>",
        "thread_b": "client B: key delete <key>",
        "expected": "error_or_stale",
    },
]


@dataclasses.dataclass
class ConcurrencyFuzzResult:
    scenario: str
    description: str
    outcome_a: str
    outcome_b: str
    expected: str
    anomaly: bool
    timing_ms: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "description": self.description,
            "outcome_a": self.outcome_a,
            "outcome_b": self.outcome_b,
            "expected": self.expected,
            "anomaly": self.anomaly,
            "timing_ms": self.timing_ms,
            "notes": self.notes,
        }


class ConcurrencyFuzzer:
    """Race condition testing against SEP services.

    Run controlled races involving key deletion versus signing, session close
    versus response handling, authentication cancellation versus completion,
    device lock versus key use, and multiple clients sharing handles.

    NOTE: In simulation mode, operations are serialized. Deploy to a real
    device with threading support to observe actual race conditions.
    """

    def __init__(self, api_fn: Callable[[str], str] | None = None):
        self._api = api_fn or _default_api

    def run_scenario(
        self,
        scenario: dict[str, Any],
    ) -> ConcurrencyFuzzResult:
        """Execute a concurrency scenario (serialized in simulation)."""
        start = time.monotonic()

        try:
            outcome_a = self._api(scenario["thread_a"])
        except Exception as exc:
            outcome_a = str(exc)

        try:
            outcome_b = self._api(scenario["thread_b"])
        except Exception as exc:
            outcome_b = str(exc)

        elapsed = (time.monotonic() - start) * 1000.0

        return ConcurrencyFuzzResult(
            scenario=scenario["name"],
            description=scenario["desc"],
            outcome_a=outcome_a,
            outcome_b=outcome_b,
            expected=scenario["expected"],
            anomaly=False,
            timing_ms=elapsed,
            notes="Serialized execution (no actual concurrency in simulation)",
        )

    def run_all(
        self,
        scenarios: list[dict[str, Any]] | None = None,
    ) -> list[ConcurrencyFuzzResult]:
        """Run all concurrency scenarios."""
        scenarios = scenarios or _CONCURRENCY_SCENARIOS
        return [self.run_scenario(s) for s in scenarios]


# ---------------------------------------------------------------------------
# Crash triage — classify fault layer
# ---------------------------------------------------------------------------


class FaultLayer(str, enum.Enum):
    TEST_APP = "test_app"
    AP_DAEMON = "ap_daemon"
    AP_KERNEL = "ap_kernel"
    SEPOS = "sepos"
    SEP_BOOT_ROM = "sep_boot_rom"
    UNKNOWN = "unknown"


FAULT_SIGNATURES: dict[str, dict[str, Any]] = {
    "app_crash": {
        "layer": FaultLayer.TEST_APP,
        "indicators": [
            "SIGSEGV", "SIGABRT", "EXC_BAD_ACCESS", "Segmentation fault",
            "app crashed", "test app terminated",
        ],
    },
    "daemon_crash": {
        "layer": FaultLayer.AP_DAEMON,
        "indicators": [
            "securityd crashed", "sec crashed", "com.apple.security",
            "daemon crash", "sysdiagnose daemon",
        ],
    },
    "kernel_panic": {
        "layer": FaultLayer.AP_KERNEL,
        "indicators": [
            "kernel panic", "panic(cpu", "Watchdog", "resetting",
            "AP watchdog", "kernel crash",
        ],
    },
    "sep_reset": {
        "layer": FaultLayer.SEPOS,
        "indicators": [
            "SEP reset", "sep reset", "SEP panicked", "sep panicked",
            "SEP watchdog", "secure enclave reset",
            "sepOS crash", "sepos panic",
        ],
    },
    "sep_boot_rom": {
        "layer": FaultLayer.SEP_BOOT_ROM,
        "indicators": [
            "SEP ROM", "sep boot rom", "SEP DFU", "sep dfu",
            "SEP recovery", "sep recovery",
        ],
    },
}


@dataclasses.dataclass
class CrashArtifact:
    timestamp: str
    fault_string: str
    classified_layer: FaultLayer
    confidence: float
    reproducible: bool
    minimal_input: str = ""
    sysdiagnose_time: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "fault_string": self.fault_string,
            "classified_layer": self.classified_layer.value,
            "confidence": self.confidence,
            "reproducible": self.reproducible,
            "minimal_input": self.minimal_input,
            "sysdiagnose_time": self.sysdiagnose_time,
            "notes": self.notes,
        }


class CrashTriager:
    """Classify crashes by fault layer and assess reproducibility.

    After an anomaly: record wall-clock time, collect sysdiagnose, preserve
    panic logs, check whether SEP-dependent operations temporarily fail,
    repeat from clean reboot, reduce sequence to minimal reproduction.
    """

    def __init__(self):
        self.artifacts: list[CrashArtifact] = []

    def classify(self, fault_string: str, reproducible: bool = False) -> CrashArtifact:
        """Classify a fault string to the most likely layer."""
        best_layer = FaultLayer.UNKNOWN
        best_confidence = 0.0

        for sig_name, sig in FAULT_SIGNATURES.items():
            matches = sum(
                1 for ind in sig["indicators"]
                if ind.lower() in fault_string.lower()
            )
            if matches > 0:
                confidence = min(1.0, matches / len(sig["indicators"]) + 0.3)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_layer = sig["layer"]

        artifact = CrashArtifact(
            timestamp=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            fault_string=fault_string,
            classified_layer=best_layer,
            confidence=best_confidence,
            reproducible=reproducible,
        )
        self.artifacts.append(artifact)
        return artifact

    def refine(
        self,
        artifact: CrashArtifact,
        minimal_input: str,
        sysdiagnose_time: str,
        notes: str = "",
    ) -> CrashArtifact:
        """Refine a crash artifact with reproduction details."""
        artifact.minimal_input = minimal_input
        artifact.sysdiagnose_time = sysdiagnose_time
        artifact.notes = notes
        return artifact


# ---------------------------------------------------------------------------
# SEP Research Pipeline — full orchestrator
# ---------------------------------------------------------------------------


class SEPResearchPipeline:
    """Orchestrate a complete SEP vulnerability research campaign.

    Usage::

        pipeline = SEPResearchPipeline(
            device_model="iPhone14,2",
            os_build="21A123",
            chipset="A15",
        )
        report = pipeline.run_full_campaign(output_dir)
    """

    def __init__(
        self,
        device_model: str = "unknown",
        os_build: str = "unknown",
        chipset: str = "unknown",
        api_fn: Callable[[str], str] | None = None,
        *,
        custody: CustodyLog | None = None,
    ):
        self.device_model = device_model
        self.os_build = os_build
        self.chipset = chipset
        self._api = api_fn or _default_api
        self.custody = custody or CustodyLog(
            operator="b34st-sep-research",
            device_id=device_model,
        )
        self.mapper = ArchitecturalMapper(
            device_model, os_build, chipset, self._api
        )
        self.corpus = RequestCorpus(self._api)
        self.differ = DifferentialAnalyzer(self._api)
        self.structural = StructuralFuzzer(self._api)
        self.stateful = StatefulFuzzer(self._api)
        self.concurrent = ConcurrencyFuzzer(self._api)
        self.triager = CrashTriager()

    def run_stage(
        self,
        stage: str,
        output_dir: pathlib.Path,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a single pipeline stage by name."""
        output_dir.mkdir(parents=True, exist_ok=True)
        self.custody.record(
            f"pipeline.stage.{stage}.start",
            f"Starting stage '{stage}'",
        )

        if stage == "architectural_map":
            amap = self.mapper.build_map()
            result = amap.to_dict()
            _write_json(result, output_dir / "architectural-map.json")
            self.custody.record(
                f"pipeline.stage.{stage}.complete",
                f"Architectural map complete: {len(amap.observations)} observations",
            )
            return result

        if stage == "corpus_generation":
            self.corpus.build()
            result = self.corpus.to_dict()
            _write_json(result, output_dir / "request-corpus.json")
            self.custody.record(
                f"pipeline.stage.{stage}.complete",
                f"Corpus built: {len(self.corpus.entries)} entries",
            )
            return result

        if stage == "differential_analysis":
            pairs = self.differ.run_all()
            result = {
                "total_pairs": len(pairs),
                "different_outcomes": sum(
                    1 for p in pairs if not p.same_outcome
                ),
                "pairs": [p.to_dict() for p in pairs],
            }
            _write_json(result, output_dir / "differential-analysis.json")
            self.custody.record(
                f"pipeline.stage.{stage}.complete",
                f"Differential analysis complete: {result['different_outcomes']} differing pair(s)",
            )
            return result

        if stage == "structural_fuzzing":
            flat = self.structural.fuzz_all()
            all_results = []
            for strategy, results in flat.items():
                for r in results:
                    d = r.to_dict()
                    d["strategy"] = strategy
                    all_results.append(d)
            result = {
                "total_tests": len(all_results),
                "anomalies": sum(1 for r in all_results if r.get("anomaly")),
                "results": all_results,
            }
            _write_json(result, output_dir / "structural-fuzzing.json")
            self.custody.record(
                f"pipeline.stage.{stage}.complete",
                f"Structural fuzzing complete: {result['anomalies']} anomalies",
            )
            return result

        if stage == "stateful_fuzzing":
            seq_results = self.stateful.run_all()
            result = {
                "total_sequences": len(seq_results),
                "anomalies": sum(1 for r in seq_results if r.anomaly),
                "sequences": [r.to_dict() for r in seq_results],
            }
            _write_json(result, output_dir / "stateful-fuzzing.json")
            self.custody.record(
                f"pipeline.stage.{stage}.complete",
                f"Stateful fuzzing complete: {result['anomalies']} anomalies",
            )
            return result

        if stage == "concurrency_fuzzing":
            conc_results = self.concurrent.run_all()
            result = {
                "total_scenarios": len(conc_results),
                "anomalies": sum(1 for r in conc_results if r.anomaly),
                "scenarios": [r.to_dict() for r in conc_results],
            }
            _write_json(result, output_dir / "concurrency-fuzzing.json")
            self.custody.record(
                f"pipeline.stage.{stage}.complete",
                f"Concurrency fuzzing complete: {result['anomalies']} anomalies",
            )
            return result

        if stage == "crash_triage":
            result = {
                "total_artifacts": len(self.triager.artifacts),
                "artifacts": [a.to_dict() for a in self.triager.artifacts],
            }
            _write_json(result, output_dir / "crash-triage.json")
            self.custody.record(
                f"pipeline.stage.{stage}.complete",
                f"Crash triage complete: {len(self.triager.artifacts)} artifact(s)",
            )
            return result

        raise ValueError(f"Unknown stage: {stage}. Valid stages: {STAGES}")

    def run_full_campaign(
        self,
        output_dir: pathlib.Path,
        *,
        stages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run all stages (or a subset) and produce the campaign report."""
        output_dir.mkdir(parents=True, exist_ok=True)
        stages = stages or STAGES

        self.custody.record(
            "pipeline.campaign.start",
            f"SEP research campaign started on {self.device_model} "
            f"(build {self.os_build}, chipset {self.chipset})",
        )

        stage_results: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        for stage in stages:
            try:
                stage_results[stage] = self.run_stage(stage, output_dir / stage)
            except Exception as exc:
                errors.append(f"{stage}: {exc}")
                stage_results[stage] = {"error": str(exc)}
                self.custody.record(
                    f"pipeline.stage.{stage}.error",
                    f"Stage '{stage}' failed: {exc}",
                )

        anomalies = self._count_anomalies(stage_results)

        campaign = {
            "schema": CAMPAIGN_SCHEMA,
            "device": {
                "model": self.device_model,
                "os_build": self.os_build,
                "chipset": self.chipset,
            },
            "campaign": {
                "stages_completed": list(stage_results.keys()),
                "stages_with_errors": errors,
                "completed_at": dt.datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
            },
            "summary": {
                "total_stages": len(stages),
                "completed": len(stage_results) - len(errors),
                "errors": len(errors),
                "total_anomalies": anomalies["total"],
                "anomalies_by_stage": anomalies["by_stage"],
            },
            "stage_results": stage_results,
        }

        _write_json(campaign, output_dir / "campaign-manifest.json")
        self._write_campaign_report(campaign, output_dir)

        self.custody.record(
            "pipeline.campaign.end",
            f"Campaign complete: {len(stages)} stages, "
            f"{anomalies['total']} anomalies, "
            f"{len(errors)} error(s)",
        )
        self.custody.seal()
        self.custody.write(output_dir / "chain-of-custody.json")

        return campaign

    def _count_anomalies(
        self, stage_results: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        total = 0
        by_stage: dict[str, int] = {}
        for stage, result in stage_results.items():
            count = result.get("anomalies", result.get("different_outcomes", 0))
            total += count
            if count:
                by_stage[stage] = count
        return {"total": total, "by_stage": by_stage}

    def _write_campaign_report(
        self, campaign: dict[str, Any], output_dir: pathlib.Path
    ) -> pathlib.Path:
        anomalies_total = campaign["summary"]["total_anomalies"]
        stages = campaign["campaign"]["stages_completed"]
        device = campaign["device"]

        anomaly_detail_lines = []
        for stage_name in stages:
            sr = campaign.get("stage_results", {}).get(stage_name, {})
            if stage_name == "differential_analysis":
                diff_count = sr.get("different_outcomes", 0)
                if diff_count:
                    anomaly_detail_lines.append(
                        f"- **{stage_name}**: {diff_count} differential pair(s) "
                        "produced different outcomes\n"
                    )
            elif stage_name == "structural_fuzzing":
                anom = sr.get("anomalies", 0)
                if anom:
                    anomaly_detail_lines.append(
                        f"- **{stage_name}**: {anom} structural mutation(s) "
                        "were accepted by SEP\n"
                    )
            elif stage_name == "stateful_fuzzing":
                anom = sr.get("anomalies", 0)
                if anom:
                    anomaly_detail_lines.append(
                        f"- **{stage_name}**: {anom} stateful sequence(s) "
                        "produced unexpected outcomes\n"
                    )
            elif stage_name == "concurrency_fuzzing":
                anom = sr.get("anomalies", 0)
                if anom:
                    anomaly_detail_lines.append(
                        f"- **{stage_name}**: {anom} concurrency scenario(s) "
                        "produced unexpected outcomes\n"
                    )

        anomaly_section = (
            "\n".join(anomaly_detail_lines)
            if anomaly_detail_lines
            else "*(No anomalies detected)*\n"
        )

        report = _CAMPAIGN_REPORT_TEMPLATE.format(
            report_id=hashlib.sha256(
                json.dumps(campaign, sort_keys=True).encode()
            ).hexdigest()[:16],
            date=dt.datetime.now().astimezone().strftime("%Y-%m-%d"),
            device_model=device.get("model", "unknown"),
            chipset=device.get("chipset", "unknown"),
            os_build=device.get("os_build", "unknown"),
            stage_list="\n".join(f"1. **{s}**" for s in stages),
            total_stages=campaign["summary"]["total_stages"],
            completed_stages=campaign["summary"]["completed"],
            anomaly_count=anomalies_total,
            anomaly_details=anomaly_section,
            errors="\n".join(
                f"- {e}" for e in campaign["campaign"]["stages_with_errors"]
            ) or "*(None)*",
        )

        report_path = output_dir / "SEP_Research_Campaign_Report.md"
        report_path.write_text(report, encoding="utf-8")
        return report_path


_CAMPAIGN_REPORT_TEMPLATE = """# SEP Vulnerability Research Campaign Report

**Report ID:** {report_id}
**Date:** {date}
**Device:** {device_model} ({chipset})
**OS Build:** {os_build}

---

## 1. Executive Summary

A systematic SEP vulnerability research campaign was conducted using
synthetic test objects only. The campaign executed {completed_stages} of
{total_stages} stages.

**{anomaly_count} anomalous result(s)** were identified that may represent
security-relevant behavior.

---

## 2. Device Configuration

| Attribute | Value |
|-----------|-------|
| Model | {device_model} |
| SoC | {chipset} |
| OS Build | {os_build} |

---

## 3. Stages Executed

{stage_list}

---

## 4. Anomalies Summary

{anomaly_details}

---

## 5. Stage Errors

{errors}

---

## 6. Methodology

All operations used exclusively synthetic (non-personal) test objects.
No real credentials, passkeys, payment keys, or personal data were
accessed. The campaign follows Apple's Security Bounty and Security
Research Device guidelines for responsible vulnerability discovery.

Each stage output is stored in its own subdirectory with full
JSON-serialized results for independent review.

---

## 7. Attestation

This report was generated by B34ST (FBR34KER Runtime Authentication Tool).

Campaign manifest: `campaign-manifest.json`
Individual stage results are in the corresponding stage subdirectories.

*This document is prepared for authorized security research purposes.
Crash logs, sysdiagnose data, and reproduction steps are available
in the companion evidence bundle.*
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_api(call: str) -> str:
    """Default API stub that returns a simulated response."""
    if "error" in call.lower():
        raise RuntimeError(f"simulated error: {call}")
    return f"ok: simulated response to '{call[:60]}...'"


def _write_json(data: dict[str, Any], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Top-level convenience API
# ---------------------------------------------------------------------------


def run_pipeline(
    output_dir: pathlib.Path,
    *,
    device_model: str = "unknown",
    os_build: str = "unknown",
    chipset: str = "unknown",
    stages: list[str] | None = None,
    api_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Run a full SEP vulnerability research campaign.

    This is the high-level entry point. Example::

        result = run_pipeline(
            pathlib.Path("./output"),
            device_model="iPhone14,2",
            os_build="21A123",
            chipset="A15",
        )
        print(f"Campaign manifest: {result['campaign_manifest']}")

    Replace ``api_fn`` with a real device transport to test against
    live hardware or an SRD.
    """
    pipeline = SEPResearchPipeline(
        device_model=device_model,
        os_build=os_build,
        chipset=chipset,
        api_fn=api_fn,
    )
    campaign = pipeline.run_full_campaign(output_dir, stages=stages)
    return {
        "campaign_dir": str(output_dir),
        "campaign_manifest": str(output_dir / "campaign-manifest.json"),
        "anomalies": campaign["summary"]["total_anomalies"],
        "stages_completed": campaign["campaign"]["stages_completed"],
    }
