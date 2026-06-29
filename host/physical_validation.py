#!/usr/bin/env python3
"""Validate FBR34KER runtime evidence and enforce profile maturity gates."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from boot_image import BootImageError, load_profile
from session_bundle import SessionBundleError, read_session_bundle, verify_session_bundle

RELEASE_VERSION = "0.5.0b"
MATURITY_ORDER = (
    "simulated",
    "qemu-verified",
    "bridge-verified",
    "console-verified",
    "boot-evidence-verified",
    "physical-runtime-verified",
)
LEGACY_MATURITY = {
    "simulator-validated": "simulated",
    "bridge-validated": "bridge-verified",
    "console-validated": "console-verified",
    "boot-evidence-validated": "boot-evidence-verified",
    "physical-runtime-validated": "physical-runtime-verified",
}


class ValidationError(RuntimeError):
    pass


def _json_member(files: dict[str, bytes], name: str) -> Any:
    try:
        return json.loads(files[name].decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid or missing {name}") from exc


def _console_markers(console: str) -> dict[str, bool]:
    lowered = console.lower()
    return {
        "entry_observed": "fbr34ker" in lowered and ("entry" in lowered or "monitor" in lowered),
        "console_stage": "console" in lowered and "passed" in lowered,
        "boot_evidence_stage": "boot-evidence" in lowered and "passed" in lowered,
    }


def validate_bundle(path: pathlib.Path) -> dict[str, Any]:
    integrity = verify_session_bundle(path)
    files = read_session_bundle(path)
    session = _json_member(files, "session.json")
    profile = _json_member(files, "profile.json")
    boot = _json_member(files, "boot-evidence.json")
    console = files.get("console.log", b"").decode("utf-8", "replace")
    if not isinstance(session, dict) or not isinstance(profile, dict) or not isinstance(boot, dict):
        raise ValidationError("session evidence JSON objects are malformed")
    markers = _console_markers(console)
    stages = session.get("stages", [])
    stage_map = {
        str(item.get("stage")): str(item.get("status"))
        for item in stages if isinstance(item, dict) and item.get("stage")
    }
    adapter = session.get("adapter", {}) if isinstance(session.get("adapter"), dict) else {}
    adapter_id = str(adapter.get("adapter_id", "unknown"))
    adapter_transport = str(session.get("adapter_transport", "unknown"))
    physical_claim = bool(session.get("physical_execution_verified", False))
    bridge_backed = adapter_transport == "persistent-bridge" or (
        adapter_id not in {"", "unknown"} and "simulator" not in adapter_id
    )
    exact_profile = bool(profile.get("requires_exact_product", False))
    required_stages = [str(value) for value in profile.get("required_bringup_stages", [])]
    missing_stages = [stage for stage in required_stages if stage_map.get(stage) != "passed"]
    checks = {
        "bundle_integrity": bool(integrity.get("valid")),
        "session_passed": bool(session.get("passed")),
        "exact_product_profile": exact_profile,
        "console_entry_observed": markers["entry_observed"],
        "console_stage_passed": stage_map.get("console") == "passed" or markers["console_stage"],
        "boot_evidence_present": bool(boot),
        "boot_evidence_stage_passed": stage_map.get("boot-evidence") == "passed" or markers["boot_evidence_stage"],
        "required_stages_passed": not missing_stages,
        "bridge_backed": bridge_backed,
        "physical_execution_claim": physical_claim,
    }
    proof = "physical" if physical_claim and bridge_backed else "bridge" if bridge_backed else "simulator"
    valid = all(checks[name] for name in (
        "bundle_integrity", "session_passed", "exact_product_profile",
        "console_entry_observed", "console_stage_passed", "boot_evidence_present",
        "boot_evidence_stage_passed", "required_stages_passed",
    ))
    return {
        "schema_version": 1,
        "project": "FBR34KER",
        "release_version": RELEASE_VERSION,
        "bundle": str(path),
        "valid": valid,
        "proof_class": proof,
        "checks": checks,
        "missing_required_stages": missing_stages,
        "profile_id": session.get("profile_id") or profile.get("profile_id"),
        "session_id": session.get("session_id"),
        "adapter_id": adapter_id,
        "adapter_transport": adapter_transport,
        "integrity": integrity,
    }


def _read_summary(path: pathlib.Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError("runtime summary must be an object")
    return value


def candidate_report(success_bundle: pathlib.Path, failure_bundle: pathlib.Path,
                     recovered_bundle: pathlib.Path,
                     qemu_summary: pathlib.Path | None = None) -> dict[str, Any]:
    success = validate_bundle(success_bundle)
    recovered = validate_bundle(recovered_bundle)
    failure_files = read_session_bundle(failure_bundle)
    failure = _json_member(failure_files, "session.json")
    if not isinstance(failure, dict):
        raise ValidationError("failure session is malformed")
    qemu = _read_summary(qemu_summary)
    qemu_passed = bool(qemu and qemu.get("passed"))
    failure_observed = not bool(failure.get("passed")) and bool(failure.get("failure"))
    auth_invalidated = bool(failure.get("authorization_invalidated_after_recovery"))
    bridge_proof = bool(success["valid"] and recovered["valid"])
    physical_proof = bool(
        success["checks"]["physical_execution_claim"]
        or recovered["checks"]["physical_execution_claim"]
    )
    candidate_ready = bridge_proof and failure_observed and auth_invalidated
    validation_complete = candidate_ready and qemu_passed and physical_proof
    return {
        "schema_version": 1,
        "project": "FBR34KER",
        "release_version": RELEASE_VERSION,
        "release_name": "Beta",
        "candidate_ready": candidate_ready,
        "physical_validation_complete": validation_complete,
        "proof": {
            "bridge_console": bridge_proof,
            "failure_observed": failure_observed,
            "authorization_invalidated_after_reset": auth_invalidated,
            "recovered_after_reauthorization": bool(recovered["valid"]),
            "qemu_runtime": qemu_passed,
            "physical_runtime": physical_proof,
        },
        "success": success,
        "recovered": recovered,
        "qemu": qemu or {"passed": False, "status": "unavailable-or-not-supplied"},
        "limitations": [
            value for value, present in (
                ("QEMU runtime proof is not present.", not qemu_passed),
                ("Physical-device execution proof is not present.", not physical_proof),
            ) if present
        ],
    }


def normalize_maturity(value: object) -> str:
    text = str(value or "simulated")
    return LEGACY_MATURITY.get(text, text)


def permitted_maturity(validation: dict[str, Any], *, qemu_passed: bool = False,
                       physical_attested: bool = False) -> str:
    checks = validation["checks"]
    if checks["physical_execution_claim"] and validation["valid"] and physical_attested:
        return "physical-runtime-verified"
    if validation["valid"] and checks["boot_evidence_present"] and checks["bridge_backed"]:
        return "boot-evidence-verified"
    if checks["console_entry_observed"] and checks["bridge_backed"]:
        return "console-verified"
    if checks["bridge_backed"] and checks["bundle_integrity"]:
        return "bridge-verified"
    if qemu_passed:
        return "qemu-verified"
    return "simulated"



def verify_physical_attestation(path: pathlib.Path | None,
                                evidence: pathlib.Path) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValidationError("unsupported physical attestation schema")
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    required_true = (
        "operator_authorized", "device_owned_or_authorized", "observed_console",
        "observed_boot_evidence", "observed_safe_reset",
    )
    if value.get("evidence_bundle_sha256") != digest:
        raise ValidationError("physical attestation does not match the evidence bundle")
    if not all(value.get(name) is True for name in required_true):
        raise ValidationError("physical attestation is missing required acknowledgements")
    if not isinstance(value.get("operator"), str) or not value["operator"].strip():
        raise ValidationError("physical attestation operator is missing")
    return value

def promote_profile(profile_path: pathlib.Path, evidence: pathlib.Path,
                    requested: str, output: pathlib.Path,
                    qemu_summary: pathlib.Path | None = None,
                    physical_attestation: pathlib.Path | None = None) -> dict[str, Any]:
    if requested not in MATURITY_ORDER:
        raise ValidationError(f"unsupported maturity: {requested}")
    profile = load_profile(profile_path)
    validation = validate_bundle(evidence)
    qemu = _read_summary(qemu_summary)
    attestation = verify_physical_attestation(physical_attestation, evidence)
    allowed = permitted_maturity(
        validation, qemu_passed=bool(qemu and qemu.get("passed")),
        physical_attested=attestation is not None,
    )
    if MATURITY_ORDER.index(requested) > MATURITY_ORDER.index(allowed):
        raise ValidationError(f"evidence permits at most {allowed}, not {requested}")
    updated = copy.deepcopy(profile)
    updated["maturity"] = requested
    updated["maturity_evidence"] = {
        "schema_version": 1,
        "session_id": validation.get("session_id"),
        "proof_class": validation.get("proof_class"),
        "bundle_sha256_verified": validation["checks"]["bundle_integrity"],
        "console_entry_observed": validation["checks"]["console_entry_observed"],
        "boot_evidence_verified": validation["checks"]["boot_evidence_present"],
        "physical_execution_verified": validation["checks"]["physical_execution_claim"],
        "physical_attestation_verified": attestation is not None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"updated": True, "profile_id": updated.get("profile_id"),
            "previous": normalize_maturity(profile.get("maturity")),
            "maturity": requested, "maximum_permitted": allowed, "output": str(output)}


def explain_failure(path: pathlib.Path) -> dict[str, Any]:
    files = read_session_bundle(path)
    session = _json_member(files, "session.json")
    if not isinstance(session, dict):
        raise ValidationError("session is malformed")
    failure = session.get("failure")
    failed_stage = session.get("failed_stage")
    if session.get("passed"):
        explanation = "The session passed; no failing stage was recorded."
        action = "Validate and archive the evidence bundle before profile promotion."
    elif failed_stage:
        explanation = f"Bring-up stopped at {failed_stage}: {failure or 'unspecified adapter failure'}."
        action_map = {
            "console": "Verify the bridge console capability and target entry-point handoff.",
            "board-inventory": "Compare CPID, product type, and exact profile selection.",
            "memory-map": "Compare image placements with adapter-reported writable and executable regions.",
            "timer": "Confirm the timer source advances before enabling interrupt-driven tests.",
            "interrupts": "Keep interrupts masked and validate controller/timer routing separately.",
            "watchdog": "Disable automatic watchdog use until reset behavior is independently proven.",
            "boot-evidence": "Collect raw evidence and verify persistence/CRC before profile promotion.",
        }
        action = action_map.get(str(failed_stage), "Review transfer.log, trace.json, and crash-report.json before retrying.")
    else:
        explanation = f"The session failed before staged bring-up: {failure or 'unspecified failure'}."
        action = "Check authorization, profile matching, image integrity, and adapter memory regions."
    return {"schema_version": 1, "passed": bool(session.get("passed")),
            "failed_stage": failed_stage, "failure": failure,
            "explanation": explanation, "recommended_action": action,
            "authorization_invalidated": bool(session.get("authorization_invalidated_after_recovery"))}


def checklist(profile_path: pathlib.Path) -> dict[str, Any]:
    profile = load_profile(profile_path)
    return {
        "schema_version": 1,
        "project": "FBR34KER",
        "release_version": RELEASE_VERSION,
        "profile_id": profile.get("profile_id"),
        "maturity": normalize_maturity(profile.get("maturity")),
        "checks": [
            {"id": "exact-profile", "required": True, "description": "Match CPID and exact product type."},
            {"id": "authorized-session", "required": True, "description": "Obtain a new explicit authorization after every reset."},
            {"id": "image-integrity", "required": True, "description": "Verify the FBRI manifest and every component hash."},
            {"id": "memory-policy", "required": True, "description": "Validate every placement against adapter-reported regions."},
            {"id": "send-only-first", "required": True, "description": "Complete transfer verification before a separate execution decision."},
            {"id": "console-proof", "required": True, "description": "Capture a FBR34KER entry banner and console stage result."},
            {"id": "boot-evidence", "required": True, "description": "Export and verify boot evidence before profile promotion."},
            {"id": "safe-reset", "required": True, "description": "Reset once and confirm authorization is invalidated."},
        ],
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-session")
    validate.add_argument("bundle", type=pathlib.Path)
    candidate = sub.add_parser("candidate-report")
    candidate.add_argument("--success", type=pathlib.Path, required=True)
    candidate.add_argument("--failure", type=pathlib.Path, required=True)
    candidate.add_argument("--recovered", type=pathlib.Path, required=True)
    candidate.add_argument("--qemu-summary", type=pathlib.Path)
    candidate.add_argument("--output", type=pathlib.Path)
    promote = sub.add_parser("promote-profile")
    promote.add_argument("profile", type=pathlib.Path)
    promote.add_argument("evidence", type=pathlib.Path)
    promote.add_argument("maturity", choices=MATURITY_ORDER)
    promote.add_argument("--qemu-summary", type=pathlib.Path)
    promote.add_argument("--physical-attestation", type=pathlib.Path)
    promote.add_argument("--output", type=pathlib.Path, required=True)
    explain = sub.add_parser("explain-failure")
    explain.add_argument("bundle", type=pathlib.Path)
    check = sub.add_parser("checklist")
    check.add_argument("profile", type=pathlib.Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate-session":
            result = validate_bundle(args.bundle)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["valid"] else 1
        if args.command == "candidate-report":
            result = candidate_report(args.success, args.failure, args.recovered, args.qemu_summary)
            encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(encoded, encoding="utf-8")
            print(encoded, end="")
            return 0 if result["candidate_ready"] else 1
        if args.command == "promote-profile":
            result = promote_profile(args.profile, args.evidence, args.maturity,
                                     args.output, args.qemu_summary,
                                     args.physical_attestation)
        elif args.command == "explain-failure":
            result = explain_failure(args.bundle)
        else:
            result = checklist(args.profile)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, ValidationError,
            SessionBundleError, BootImageError) as exc:
        print(f"physical validation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
