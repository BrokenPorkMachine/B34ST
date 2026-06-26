#!/usr/bin/env python3
"""Evidence-gated research-runtime orchestration for B34ST.

This module automates the repository's bounded validation and authorized
first-stage contracts. Target-specific exploit, kernel-patch, trust-cache, and
bootstrap-install implementations remain external inputs and must provide
machine-readable evidence before the state machine advances.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shlex
import struct
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "host"))

from boot_image import BootImageError, inspect_image, load_profile  # noqa: E402
from irecovery_boot import RecoveryError, load_device_info, validate_target  # noqa: E402
from physical_validation import ValidationError, validate_bundle  # noqa: E402

OWNER_ACK = "I OWN OR AM AUTHORIZED TO TEST THIS DEVICE"
EXECUTION_ACK = "START AUTHORIZED FIRST STAGE"

STAGE_ORDER = (
    "HOST_READY",
    "TARGET_PROFILE_VALIDATED",
    "KERNEL_IDENTIFIED",
    "MONITOR_IMAGE_VALIDATED",
    "MONITOR_RUNTIME",
    "SAFE_RESET_VERIFIED",
    "KERNEL_PATCH_ATTEMPTED",
    "KERNEL_PATCH_VERIFIED",
    "CODE_SIGNING_POLICY_VERIFIED",
    "TRUST_CACHE_ACCEPTED",
    "WRITABLE_RESEARCH_ENVIRONMENT",
    "BOOTSTRAP_VERIFIED",
    "BOOTSTRAP_ACTIVE",
    "USERSPACE_SHELL_RESPONDING",
    "RESEARCH_RUNTIME_READY",
    "JAILBREAK_ATTESTED",
)

EXTERNAL_EVIDENCE_STAGES = {
    "KERNEL_PATCH_ATTEMPTED",
    "KERNEL_PATCH_VERIFIED",
    "CODE_SIGNING_POLICY_VERIFIED",
    "TRUST_CACHE_ACCEPTED",
    "WRITABLE_RESEARCH_ENVIRONMENT",
    "BOOTSTRAP_ACTIVE",
    "USERSPACE_SHELL_RESPONDING",
}

READY_REQUIREMENTS = (
    "MONITOR_RUNTIME",
    "SAFE_RESET_VERIFIED",
    "KERNEL_IDENTIFIED",
    "KERNEL_PATCH_VERIFIED",
    "CODE_SIGNING_POLICY_VERIFIED",
    "TRUST_CACHE_ACCEPTED",
    "WRITABLE_RESEARCH_ENVIRONMENT",
    "BOOTSTRAP_VERIFIED",
    "BOOTSTRAP_ACTIVE",
    "USERSPACE_SHELL_RESPONDING",
)


class OrchestrationError(RuntimeError):
    pass


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _macho_uuid(data: bytes) -> str | None:
    """Return LC_UUID for a thin little/big-endian Mach-O when available."""
    if len(data) < 32:
        return None
    magic = data[:4]
    formats = {
        b"\xcf\xfa\xed\xfe": ("<", True),
        b"\xfe\xed\xfa\xcf": (">", True),
        b"\xce\xfa\xed\xfe": ("<", False),
        b"\xfe\xed\xfa\xce": (">", False),
    }
    selected = formats.get(magic)
    if selected is None:
        return None
    endian, is_64 = selected
    header_size = 32 if is_64 else 28
    try:
        ncmds = struct.unpack_from(endian + "I", data, 16)[0]
        sizeofcmds = struct.unpack_from(endian + "I", data, 20)[0]
    except struct.error:
        return None
    if ncmds > 65535 or sizeofcmds > len(data) - header_size:
        return None
    cursor = header_size
    end = header_size + sizeofcmds
    for _ in range(ncmds):
        if cursor + 8 > end:
            return None
        command, size = struct.unpack_from(endian + "II", data, cursor)
        if size < 8 or cursor + size > end:
            return None
        if command == 0x1B and size >= 24:
            raw = data[cursor + 8:cursor + 24]
            text = raw.hex()
            return "-".join((text[:8], text[8:12], text[12:16],
                             text[16:20], text[20:]))
        cursor += size
    return None


def inspect_kernelcache(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        raise OrchestrationError(f"kernelcache does not exist: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise OrchestrationError("kernelcache is empty")
    with path.open("rb") as stream:
        prefix = stream.read(min(size, 16 * 1024 * 1024))
    magic = prefix[:4].hex()
    uuid = _macho_uuid(prefix)
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "size": size,
        "sha256": sha256_file(path),
        "magic": magic,
        "macho_uuid": uuid,
        "format_recognized": uuid is not None or magic in {
            "cffaedfe", "feedfacf", "cefaedfe", "feedface",
        },
    }


def kernel_identity_template(
    inventory: dict[str, Any],
    *,
    product: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "b34st-reviewed-kernel-identity",
        "product": product,
        "ios_version": "REVIEW_REQUIRED",
        "build": "REVIEW_REQUIRED",
        "kernelcache_sha256": inventory["sha256"],
        "macho_uuid": inventory["macho_uuid"],
        "review": {
            "reviewer": "REVIEW_REQUIRED",
            "source": "REVIEW_REQUIRED",
            "approved": False,
        },
    }


def validate_kernel_identity(
    path: pathlib.Path,
    *,
    inventory: dict[str, Any],
    product: str,
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OrchestrationError(f"invalid kernel identity manifest: {exc}") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("kind") != "b34st-reviewed-kernel-identity"
    ):
        raise OrchestrationError("unsupported kernel identity manifest")
    if value.get("product") != product:
        raise OrchestrationError("kernel identity product does not match the device")
    if value.get("kernelcache_sha256") != inventory["sha256"]:
        raise OrchestrationError("kernelcache hash is not in the reviewed identity manifest")
    expected_uuid = value.get("macho_uuid")
    if expected_uuid and expected_uuid != inventory["macho_uuid"]:
        raise OrchestrationError("kernelcache UUID does not match the reviewed identity manifest")
    for field in ("ios_version", "build"):
        item = value.get(field)
        if not isinstance(item, str) or not item or item == "REVIEW_REQUIRED":
            raise OrchestrationError(f"kernel identity {field} is not reviewed")
    review = value.get("review")
    if (
        not isinstance(review, dict)
        or review.get("approved") is not True
        or not isinstance(review.get("reviewer"), str)
        or not review["reviewer"].strip()
        or not isinstance(review.get("source"), str)
        or not review["source"].strip()
    ):
        raise OrchestrationError("kernel identity manifest is not approved")
    return value


def validate_stage_evidence(
    path: pathlib.Path,
    *,
    expected_stage: str,
    kernel_sha256: str,
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OrchestrationError(f"invalid stage evidence {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise OrchestrationError("stage evidence must use schema_version 1")
    if value.get("stage") != expected_stage:
        raise OrchestrationError(
            f"evidence stage is {value.get('stage')!r}, expected {expected_stage!r}"
        )
    if value.get("status") != "verified":
        raise OrchestrationError("stage evidence status must be 'verified'")
    target = value.get("target")
    if not isinstance(target, dict) or target.get("kernelcache_sha256") != kernel_sha256:
        raise OrchestrationError("stage evidence does not match this kernelcache")
    observations = value.get("observations")
    if not isinstance(observations, list) or not observations or not all(
        isinstance(item, str) and item.strip() for item in observations
    ):
        raise OrchestrationError("stage evidence requires non-empty observations")
    if expected_stage in {"KERNEL_PATCH_VERIFIED", "CODE_SIGNING_POLICY_VERIFIED"}:
        rollback = value.get("rollback")
        if not isinstance(rollback, dict) or rollback.get("available") is not True:
            raise OrchestrationError(f"{expected_stage} requires rollback.available=true")
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "document": value,
    }


def stage_evidence_template(stage: str, kernel_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "stage": stage,
        "status": "replace-with-verified-after-independent-check",
        "target": {"kernelcache_sha256": kernel_sha256},
        "observations": [],
        "rollback": {
            "available": False,
            "evidence": "Describe restoration of original values or uninstall path.",
        },
        "producer": {
            "name": "external-reviewed-adapter",
            "version": "replace-me",
        },
    }


def audit_legacy_components() -> dict[str, Any]:
    """Record why legacy state models cannot satisfy runtime evidence gates."""
    findings = {
        "kernel/kernel_patches.c": {
            "classification": "UNVERIFIED_MUTATION_MODEL",
            "reason": "Contains fixed base-relative offsets and optional MMIO writes; no exact-kernel hash binding or read-back proof.",
        },
        "kernel/secure_boot_bypass.c": {
            "classification": "UNVERIFIED_STATE_MODEL",
            "reason": "State flags and fixed offsets do not prove Image4, iBoot, or code-signing policy changes.",
        },
        "kernel/persistence.c": {
            "classification": "IN_MEMORY_MODEL",
            "reason": "Internal storage and hook state are not a signed userspace bootstrap or verified launch environment.",
        },
        "kernel/usbliter8_exploit.c": {
            "classification": "UNVERIFIED_TARGET_MODEL",
            "reason": "Hard-coded patch words and state transitions lack target firmware identity, provenance, independent read-back, and reconnect evidence.",
        },
        "scripts/run_exploit.py": {
            "classification": "LEGACY_ORCHESTRATOR",
            "reason": "Runs mutation-labelled shell commands and interprets textual success; it is not accepted as stage evidence.",
        },
    }
    for relative, finding in findings.items():
        path = ROOT / relative
        finding["present"] = path.is_file()
        finding["sha256"] = sha256_file(path) if path.is_file() else None
    return {
        "schema_version": 1,
        "result": "external-reviewed-adapters-required",
        "accepted_as_runtime_evidence": False,
        "components": findings,
    }


class RuntimeSession:
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.report_path = self.output / "runtime-state.json"
        self.log_path = self.output / "orchestrator.log"
        self.report: dict[str, Any] = {
            "schema_version": 1,
            "project": "B34ST",
            "operation": "guided-research-runtime",
            "created_at": dt.datetime.now().astimezone().isoformat(),
            "states": {stage: {"status": "BLOCKED"} for stage in STAGE_ORDER},
            "artifacts": {},
            "commands": [],
            "blockers": [],
            "limitations": [
                "No exploit payload, kernel patch, code-signing bypass, trust-cache injection, or bootstrap installer is generated by this orchestrator.",
                "External evidence must match the exact kernelcache SHA-256.",
                "JAILBREAK_ATTESTED is an evidence state, not an inferred transport result.",
            ],
        }
        self.save()

    def save(self) -> None:
        self.report_path.write_text(
            json.dumps(self.report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def log(self, message: str) -> None:
        timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{timestamp}] {message}\n")

    def set_state(self, stage: str, status: str, **evidence: Any) -> None:
        if stage not in STAGE_ORDER or status not in {"VERIFIED", "ATTEMPTED", "BLOCKED"}:
            raise OrchestrationError(f"invalid state update: {stage}={status}")
        self.report["states"][stage] = {"status": status, **evidence}
        self.log(f"STATE {stage}={status}")
        self.save()

    def artifact(self, name: str, value: dict[str, Any]) -> None:
        self.report["artifacts"][name] = value
        self.save()

    def run(self, command: list[str], label: str) -> subprocess.CompletedProcess[str]:
        printable = shlex.join(command)
        self.log(f"START {label}: {printable}")
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        transcript = self.output / f"{len(self.report['commands']) + 1:02d}-{label}.log"
        transcript.write_text(result.stdout, encoding="utf-8")
        self.report["commands"].append({
            "label": label,
            "command": command,
            "exit_code": result.returncode,
            "transcript": str(transcript),
        })
        self.log(f"END {label}: exit={result.returncode}")
        self.save()
        print(result.stdout, end="")
        return result

    def finalize(self) -> None:
        missing = [
            stage for stage in READY_REQUIREMENTS
            if self.report["states"][stage]["status"] != "VERIFIED"
        ]
        self.report["blockers"] = missing
        if not missing:
            self.set_state(
                "RESEARCH_RUNTIME_READY",
                "VERIFIED",
                requirements=list(READY_REQUIREMENTS),
            )
        else:
            self.set_state(
                "RESEARCH_RUNTIME_READY",
                "BLOCKED",
                missing=missing,
            )
        self.save()


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{label}{suffix}: ").strip() or default
    except (EOFError, KeyboardInterrupt):
        return ""


def _yes(label: str) -> bool:
    return _prompt(f"{label} (y/N)").lower() in {"y", "yes"}


def _path_prompt(label: str, default: str = "") -> pathlib.Path:
    value = _prompt(label, default)
    if not value:
        raise OrchestrationError(f"{label} is required")
    path = pathlib.Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def _default_output() -> pathlib.Path:
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    return ROOT / "runtime-artifacts" / "b34st" / "research-runtime" / stamp


def _write_templates(session: RuntimeSession, kernel_sha256: str) -> None:
    directory = session.output / "evidence-templates"
    directory.mkdir(parents=True, exist_ok=True)
    for stage in sorted(EXTERNAL_EVIDENCE_STAGES):
        path = directory / f"{stage.lower()}.json"
        path.write_text(
            json.dumps(stage_evidence_template(stage, kernel_sha256),
                       indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    session.artifact("evidence_templates", {"directory": str(directory)})


def _verify_bootstrap(
    session: RuntimeSession,
    path: pathlib.Path,
    expected_sha256: str,
) -> None:
    if not path.is_file():
        raise OrchestrationError(f"bootstrap archive does not exist: {path}")
    actual_sha256 = sha256_file(path)
    if (
        len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
        or actual_sha256 != expected_sha256
    ):
        raise OrchestrationError(
            "bootstrap SHA-256 does not match the independently trusted digest"
        )
    record = {
        "path": str(path.resolve()),
        "size": path.stat().st_size,
        "sha256": actual_sha256,
        "trust_basis": "operator-supplied independent SHA-256",
    }
    session.artifact("bootstrap", record)
    session.set_state("BOOTSTRAP_VERIFIED", "VERIFIED", **record)


def _import_external_evidence(
    session: RuntimeSession,
    kernel_sha256: str,
) -> None:
    print("\nExternal runtime evidence")
    print("Leave a path blank to keep that state blocked.")
    for stage in sorted(EXTERNAL_EVIDENCE_STAGES, key=STAGE_ORDER.index):
        value = _prompt(f"{stage} evidence JSON")
        if not value:
            continue
        path = pathlib.Path(value).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        evidence = validate_stage_evidence(
            path, expected_stage=stage, kernel_sha256=kernel_sha256
        )
        session.set_state(stage, "VERIFIED", evidence=evidence)


def guided(args: argparse.Namespace) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise OrchestrationError("guided mode requires an interactive TTY")

    output = args.output or _default_output()
    session = RuntimeSession(output)
    print("B34ST guided research-runtime orchestrator")
    print(f"Evidence directory: {session.output}")
    print("\nThis script automates validation and evidence handling.")
    print("Target-specific exploit and kernel mutation implementations remain external.")

    if _prompt(f'Type "{OWNER_ACK}" to continue') != OWNER_ACK:
        raise OrchestrationError("owner/authorization acknowledgement was not accepted")

    doctor = session.run(
        [sys.executable, "scripts/doctor.py"],
        "host-readiness",
    )
    if doctor.returncode != 0:
        session.set_state("HOST_READY", "BLOCKED", transcript=doctor.stdout[-4000:])
        session.finalize()
        return 1
    session.set_state("HOST_READY", "VERIFIED")
    audit = audit_legacy_components()
    audit_path = session.output / "legacy-component-audit.json"
    audit_path.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    session.artifact("legacy_component_audit", {
        "path": str(audit_path),
        "sha256": sha256_file(audit_path),
        "result": audit["result"],
    })

    profile_path = _path_prompt(
        "Exact target profile",
        "profiles/apple-a12-iphone-recovery.json",
    )
    device_path = _path_prompt(
        "Device identity JSON",
        "examples/a12-device-info.json",
    )
    profile = load_profile(profile_path)
    device = load_device_info(device_path)
    validate_target(profile, device)
    if not profile.get("requires_exact_product"):
        raise OrchestrationError("physical workflow requires an exact-product profile")
    session.artifact("profile", {
        "path": str(profile_path.resolve()),
        "sha256": sha256_file(profile_path),
        "profile_id": profile.get("profile_id"),
    })
    session.artifact("device", device.public_dict())
    session.set_state("TARGET_PROFILE_VALIDATED", "VERIFIED")

    kernel_path = _path_prompt("Decrypted kernelcache path")
    kernel = inspect_kernelcache(kernel_path)
    session.artifact("kernelcache", kernel)
    if not kernel["format_recognized"]:
        raise OrchestrationError("kernelcache format was not recognized as Mach-O")
    identity_value = _prompt("Reviewed kernel identity manifest path")
    if not identity_value:
        identity_path = session.output / "kernel-identity-template.json"
        identity_path.write_text(
            json.dumps(
                kernel_identity_template(kernel, product=device.product or "unknown"),
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        session.artifact("kernel_identity_template", {
            "path": str(identity_path),
            "sha256": sha256_file(identity_path),
        })
        session.set_state(
            "KERNEL_IDENTIFIED",
            "BLOCKED",
            reason="review and approve the generated kernel identity manifest",
        )
        session.finalize()
        print(f"Review required: {identity_path}")
        return 1
    identity_path = pathlib.Path(identity_value).expanduser()
    if not identity_path.is_absolute():
        identity_path = ROOT / identity_path
    identity = validate_kernel_identity(
        identity_path,
        inventory=kernel,
        product=device.product or "unknown",
    )
    session.artifact("kernel_identity", {
        "path": str(identity_path.resolve()),
        "sha256": sha256_file(identity_path),
        "ios_version": identity["ios_version"],
        "build": identity["build"],
    })
    session.set_state(
        "KERNEL_IDENTIFIED",
        "VERIFIED",
        sha256=kernel["sha256"],
        macho_uuid=kernel["macho_uuid"],
        ios_version=identity["ios_version"],
        build=identity["build"],
    )
    _write_templates(session, kernel["sha256"])

    image_path = _path_prompt(
        "FBR34KER boot image",
        f"build-apple/{profile['family']}/boot.img",
    )
    image = inspect_image(image_path)
    if image.get("manifest", {}).get("profile_id") != profile.get("profile_id"):
        raise OrchestrationError("boot image profile does not match the selected profile")
    session.artifact("boot_image", {
        "path": str(image_path.resolve()),
        "sha256": image["sha256"],
        "family": image["family"],
        "profile_id": image["manifest"]["profile_id"],
    })
    session.set_state("MONITOR_IMAGE_VALIDATED", "VERIFIED")

    bootstrap_value = _prompt("Trusted bootstrap archive path (optional)")
    if bootstrap_value:
        bootstrap_path = pathlib.Path(bootstrap_value).expanduser()
        if not bootstrap_path.is_absolute():
            bootstrap_path = ROOT / bootstrap_path
        expected_bootstrap_hash = _prompt(
            "Expected bootstrap SHA-256 from an independent trusted source"
        ).lower()
        _verify_bootstrap(session, bootstrap_path, expected_bootstrap_hash)

    adapter_kind = _prompt("External first-stage type (bridge/adapter/skip)", "skip")
    if adapter_kind in {"bridge", "adapter"}:
        adapter_command = _prompt("External authorized adapter command")
        if not adapter_command:
            raise OrchestrationError("external adapter command is required")
        if _prompt(f'Type "{EXECUTION_ACK}" to upload and start the monitor') != EXECUTION_ACK:
            raise OrchestrationError("first-stage execution was not confirmed")
        authorization_id = _prompt(
            "Session authorization identifier",
            f"b34st-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}",
        )
        evidence = session.output / "monitor-session.zip"
        command = [
            sys.executable,
            "host/hardware_bringup.py",
            "run",
            "--state-dir",
            str(session.output / "adapter-state"),
            "--device-info",
            str(device_path),
            "--profile",
            str(profile_path),
            "--image",
            str(image_path),
            f"--{adapter_kind}-command",
            adapter_command,
            "--authorized-session",
            "--authorization-id",
            authorization_id,
            "--acknowledge-unsigned-code",
            "--evidence",
            str(evidence),
        ]
        result = session.run(command, "authorized-monitor-start")
        if result.returncode == 0:
            validation = validate_bundle(evidence)
            if validation["valid"] and validation["checks"]["bridge_backed"]:
                session.set_state(
                    "MONITOR_RUNTIME",
                    "VERIFIED",
                    evidence_bundle=str(evidence),
                    validation=validation,
                )
        if session.report["states"]["MONITOR_RUNTIME"]["status"] == "VERIFIED":
            if _yes("Run one safe reset to prove authorization invalidation"):
                reset_command = [
                    sys.executable,
                    "host/hardware_bringup.py",
                    "recover",
                    "--state-dir",
                    str(session.output / "adapter-state"),
                    "--device-info",
                    str(device_path),
                    f"--{adapter_kind}-command",
                    adapter_command,
                    "--authorized-session",
                    "--authorization-id",
                    authorization_id,
                ]
                reset = session.run(reset_command, "safe-reset")
                try:
                    reset_value = json.loads(reset.stdout)
                except json.JSONDecodeError:
                    reset_value = {}
                if (
                    reset.returncode == 0
                    and reset_value.get("reset") is True
                    and reset_value.get("authorized") is False
                ):
                    session.set_state(
                        "SAFE_RESET_VERIFIED",
                        "VERIFIED",
                        result=reset_value,
                    )
                    session.set_state(
                        "MONITOR_RUNTIME",
                        "BLOCKED",
                        reason="safe reset ended the first monitor session",
                    )
                    if _yes("Reauthorize and establish the final monitor session"):
                        final_authorization_id = _prompt(
                            "New session authorization identifier",
                            f"b34st-final-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}",
                        )
                        final_evidence = session.output / "final-monitor-session.zip"
                        final_command = list(command)
                        final_command[final_command.index(authorization_id)] = final_authorization_id
                        final_command[final_command.index(str(evidence))] = str(final_evidence)
                        final_result = session.run(
                            final_command,
                            "authorized-monitor-restart",
                        )
                        if final_result.returncode == 0:
                            final_validation = validate_bundle(final_evidence)
                            if (
                                final_validation["valid"]
                                and final_validation["checks"]["bridge_backed"]
                            ):
                                session.set_state(
                                    "MONITOR_RUNTIME",
                                    "VERIFIED",
                                    evidence_bundle=str(final_evidence),
                                    validation=final_validation,
                                    reauthorized_after_safe_reset=True,
                                )
    else:
        print("First-stage execution skipped; MONITOR_RUNTIME remains blocked.")

    _import_external_evidence(session, kernel["sha256"])
    session.finalize()
    if session.report["states"]["RESEARCH_RUNTIME_READY"]["status"] == "VERIFIED":
        if _yes("Create final operator attestation for this evidence set"):
            operator = _prompt("Operator name")
            if operator:
                attestation = {
                    "schema_version": 1,
                    "operator": operator,
                    "created_at": dt.datetime.now().astimezone().isoformat(),
                    "pre_attestation_runtime_state_sha256": sha256_file(session.report_path),
                    "requirements": list(READY_REQUIREMENTS),
                    "owner_authorized": True,
                    "result": "JAILBREAK_ATTESTED",
                }
                path = session.output / "jailbreak-attestation.json"
                path.write_text(
                    json.dumps(attestation, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                session.set_state(
                    "JAILBREAK_ATTESTED",
                    "VERIFIED",
                    attestation=str(path),
                )
    print(f"\nRuntime state: {session.report_path}")
    if session.report["blockers"]:
        print("Blocked stages:")
        for stage in session.report["blockers"]:
            print(f"- {stage}")
        return 1
    return 0


def inspect_command(args: argparse.Namespace) -> int:
    value = inspect_kernelcache(args.kernelcache)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value["format_recognized"] else 1


def template_command(args: argparse.Namespace) -> int:
    document = stage_evidence_template(args.stage, args.kernelcache_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


def kernel_identity_template_command(args: argparse.Namespace) -> int:
    inventory = inspect_kernelcache(args.kernelcache)
    document = kernel_identity_template(inventory, product=args.product)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


def validate_evidence_command(args: argparse.Namespace) -> int:
    result = validate_stage_evidence(
        args.input,
        expected_stage=args.stage,
        kernel_sha256=args.kernelcache_sha256,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command")
    guided_parser = sub.add_parser("guided", help="run the interactive orchestrator")
    guided_parser.add_argument("--output", type=pathlib.Path)
    inspect_parser = sub.add_parser("inspect-kernelcache")
    inspect_parser.add_argument("kernelcache", type=pathlib.Path)
    identity = sub.add_parser("kernel-identity-template")
    identity.add_argument("kernelcache", type=pathlib.Path)
    identity.add_argument("--product", required=True)
    identity.add_argument("--output", type=pathlib.Path, required=True)
    template = sub.add_parser("evidence-template")
    template.add_argument("stage", choices=sorted(EXTERNAL_EVIDENCE_STAGES))
    template.add_argument("--kernelcache-sha256", required=True)
    template.add_argument("--output", type=pathlib.Path, required=True)
    validate = sub.add_parser("validate-evidence")
    validate.add_argument("input", type=pathlib.Path)
    validate.add_argument("--stage", choices=sorted(EXTERNAL_EVIDENCE_STAGES), required=True)
    validate.add_argument("--kernelcache-sha256", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in {None, "guided"}:
            if args.command is None:
                args.output = None
            return guided(args)
        if args.command == "inspect-kernelcache":
            return inspect_command(args)
        if args.command == "kernel-identity-template":
            return kernel_identity_template_command(args)
        if args.command == "evidence-template":
            return template_command(args)
        return validate_evidence_command(args)
    except (
        OrchestrationError,
        BootImageError,
        RecoveryError,
        ValidationError,
        OSError,
        ValueError,
    ) as exc:
        print(f"research-runtime error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
