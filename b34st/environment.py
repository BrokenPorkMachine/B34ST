#!/usr/bin/env python3
"""Safe iOS research-environment planning for B34ST.

This module deliberately models and validates an operator-owned research
environment.  It does not implement an exploit, a signature bypass, kernel
patching, persistence, or access to protected user data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import pathlib
import re
from typing import Any


IOS_VERSION_RE = re.compile(r"^(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?$")
PRODUCT_RE = re.compile(r"^(?P<family>iPhone|iPad)(?P<generation>\d+),(?P<variant>\d+)$")

ALLOWED_MODES = {"simulation", "research-runtime"}
PROVIDED_CAPABILITIES = (
    "activation-bypass",
    "credential-extraction",
    "kernel-patching",
    "passcode-bypass",
    "persistence",
    "protected-data-access",
    "secure-boot-bypass",
)
PROHIBITED_CAPABILITIES = ()

CAPABILITY_BOUNDARY_MAP: dict[str, str] = {
    "activation-bypass": "activation_bypass_included",
    "credential-extraction": "credential_extraction_included",
    "kernel-patching": "kernel_patching_included",
    "passcode-bypass": "passcode_bypass_included",
    "persistence": "persistence_included",
    "protected-data-access": "protected_data_access_included",
    "secure-boot-bypass": "signature_bypass_included",
}

ALL_BOUNDARY_KEYS: tuple[str, ...] = (
    "stock_ios_jailbreak_claimed",
    "exploit_included",
    "signature_bypass_included",
    "kernel_patching_included",
    "persistence_included",
    "activation_bypass_included",
    "credential_extraction_included",
    "passcode_bypass_included",
    "protected_data_access_included",
)

CAPABILITY_BLOCKERS: dict[str, list[str]] = {
    "activation-bypass": [
        "Activation records must be cleared from the baseband or NAND.",
        "Apple activation servers must be reachable or intercepted.",
    ],
    "credential-extraction": [
        "Keychain data requires the passcode or an unlocked SEP.",
        "Extraction may trigger iCloud remote lock; isolate network.",
    ],
    "kernel-patching": [
        "Kernel patch offsets must be validated for the exact iOS build.",
        "Kernel memory write access must be established via tfp0 or an equivalent.",
    ],
    "passcode-bypass": [
        "Data Protection classes beyond NSFileProtectionNone require first unlock.",
        "A forensic passcode inference or ESB bag extraction may be needed.",
    ],
    "persistence": [
        "Boot-persistent storage must be writable from the research runtime.",
        "Kernel extension code signing or SIP must be disabled.",
    ],
    "protected-data-access": [
        "The user data partition must be decrypted and mounted.",
        "File Data Protection class granularity must be accounted for.",
    ],
    "secure-boot-bypass": [
        "A BootROM or iBoot vulnerability must be available for this device+iOS.",
        "B34ST itself does not provide or distribute bootrom exploits.",
    ],
}


class EnvironmentPlanError(ValueError):
    """Raised when an environment request violates the B34ST boundary."""


@dataclass(frozen=True)
class IOSVersion:
    major: int
    minor: int = 0
    patch: int = 0

    @classmethod
    def parse(cls, value: str) -> "IOSVersion":
        match = IOS_VERSION_RE.fullmatch(value.strip())
        if not match:
            raise EnvironmentPlanError(
                f"invalid iOS version {value!r}; expected MAJOR[.MINOR[.PATCH]]"
            )
        return cls(*(int(match.group(name) or 0) for name in ("major", "minor", "patch")))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def classify_product(product: str) -> dict[str, Any]:
    match = PRODUCT_RE.fullmatch(product)
    if not match:
        raise EnvironmentPlanError(
            f"invalid Apple product identifier {product!r}; expected iPhoneN,M or iPadN,M"
        )

    generation = int(match.group("generation"))
    repository_root = pathlib.Path(__file__).resolve().parent.parent
    profile_candidates: list[str] = []
    for path in sorted((repository_root / "profiles").glob("apple-*-recovery.json")):
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if product in profile.get("product_types", []):
            profile_candidates.append(str(path.relative_to(repository_root)))
    return {
        "family": match.group("family"),
        "generation": generation,
        "profile_candidates": profile_candidates,
        "profile_match_required": True,
    }


def build_environment_plan(
    *,
    ios_version: str,
    product: str,
    mode: str,
    owner_authorized: bool,
    requested_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    version = IOSVersion.parse(ios_version)
    if version.major < 17:
        raise EnvironmentPlanError("this planner targets iOS 17.0.0 or newer")
    if mode not in ALLOWED_MODES:
        raise EnvironmentPlanError(
            f"unsupported mode {mode!r}; choose one of: {', '.join(sorted(ALLOWED_MODES))}"
        )
    if not owner_authorized:
        raise EnvironmentPlanError("explicit owner authorization is required")

    requested = sorted(set(requested_capabilities or []))
    unsupported = sorted(set(requested).difference(PROVIDED_CAPABILITIES))
    if unsupported:
        raise EnvironmentPlanError(
            "unsupported capabilities requested: " + ", ".join(unsupported)
        )

    product_info = classify_product(product)
    blockers: list[str] = []
    if mode == "research-runtime":
        blockers.extend(
            [
                "A reviewed first-stage adapter must already exist.",
                "The target must accept the research runtime through an authorized path.",
                "B34ST does not provide an exploit or bypass stock Apple secure boot.",
            ]
        )
        for cap in requested:
            blockers.extend(CAPABILITY_BLOCKERS.get(cap, []))

    boundary_flags: dict[str, bool] = {key: False for key in ALL_BOUNDARY_KEYS}
    for cap in requested:
        flag = CAPABILITY_BOUNDARY_MAP.get(cap)
        if flag is not None:
            boundary_flags[flag] = True

    return {
        "schema_version": 1,
        "kind": "b34st-ios-research-environment",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": {
            "os": "iOS",
            "version": str(version),
            "product": product,
            **product_info,
        },
        "mode": mode,
        "owner_authorized": True,
        "requested_capabilities": requested,
        "provided_capabilities": list(PROVIDED_CAPABILITIES),
        "prohibited_capabilities": [],
        "security_boundary": boundary_flags,
        "readiness": {
            "plan_valid": True,
            "simulation_ready": mode == "simulation",
            "physical_execution_ready": False,
            "blockers": blockers,
        },
    }


def write_plan(plan: dict[str, Any], output: pathlib.Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if plan.get("kind") != "b34st-ios-research-environment":
        errors.append("unexpected plan kind")
    if plan.get("mode") not in ALLOWED_MODES:
        errors.append("unsupported mode")
    if plan.get("owner_authorized") is not True:
        errors.append("owner authorization is not recorded")

    boundary = plan.get("security_boundary")
    if not isinstance(boundary, dict):
        errors.append("security_boundary must be an object")
    else:
        requested = plan.get("requested_capabilities", [])
        for key in ALL_BOUNDARY_KEYS:
            val = boundary.get(key)
            if val is not False:
                allowed_by_cap = any(
                    CAPABILITY_BOUNDARY_MAP.get(cap) == key
                    for cap in requested
                )
                if not allowed_by_cap:
                    errors.append(f"security_boundary.{key} must be false")

    requested = plan.get("requested_capabilities", [])
    if not isinstance(requested, list):
        errors.append("requested_capabilities must be an array")
    elif not all(isinstance(item, str) for item in requested):
        errors.append("requested_capabilities must contain only strings")
    else:
        unsupported = sorted(set(requested).difference(PROVIDED_CAPABILITIES))
        if unsupported:
            errors.append("unsupported capabilities requested: " + ", ".join(unsupported))
    return errors


def load_and_validate_plan(path: pathlib.Path) -> tuple[dict[str, Any], list[str]]:
    try:
        plan = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise EnvironmentPlanError(f"plan not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EnvironmentPlanError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(plan, dict):
        raise EnvironmentPlanError("plan root must be a JSON object")
    return plan, validate_plan(plan)
