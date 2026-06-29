#!/usr/bin/env python3
"""Generate deterministic bridge-backed Beta evidence."""
from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAILURE_STAGES = ("console", "memory-map", "timer", "boot-evidence")


def run_json(command: list[str], expected: int) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode != expected:
        raise RuntimeError(
            f"unexpected exit {result.returncode} (expected {expected}): "
            f"{' '.join(command)}\n{result.stderr}\n{result.stdout}"
        )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("command did not return a JSON object")
    return value


def bridge_command(state: pathlib.Path, device: pathlib.Path,
                   inject: str | None = None) -> str:
    values = [sys.executable, str(ROOT / "host/reference_bridge.py"),
              "--state-dir", str(state), "--device-info", str(device)]
    if inject:
        values += ["--inject-failure", inject]
    return shlex.join(values)


def bringup_command(output: pathlib.Path, profile: pathlib.Path,
                    device: pathlib.Path, image: pathlib.Path,
                    state: pathlib.Path, evidence: pathlib.Path,
                    inject: str | None = None) -> list[str]:
    return [
        sys.executable, "host/hardware_bringup.py", "run",
        "--state-dir", str(output / "unused"),
        "--device-info", str(device),
        "--profile", str(profile),
        "--image", str(image),
        "--bridge-command", bridge_command(state, device, inject),
        "--authorized-session",
        "--authorization-id", "physical-validation-candidate",
        "--acknowledge-unsigned-code",
        "--evidence", str(evidence),
    ]


def qemu_status(output: pathlib.Path, run_qemu: bool,
                supplied: pathlib.Path | None = None) -> pathlib.Path:
    path = output / "qemu-summary.json"
    if supplied is not None:
        value = json.loads(supplied.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or "passed" not in value:
            raise RuntimeError("supplied QEMU summary is invalid")
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path
    qemu = shutil.which("qemu-system-aarch64")
    if not qemu:
        value = {"schema_version": 1, "project": "FBR34KER", "version": "0.4.3b",
                 "passed": False, "status": "unavailable",
                 "detail": "qemu-system-aarch64 is not installed"}
    elif not run_qemu:
        version = subprocess.run([qemu, "--version"], text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False).stdout.splitlines()
        value = {"schema_version": 1, "project": "FBR34KER", "version": "0.4.3b",
                 "passed": False, "status": "available-not-run",
                 "detail": version[0] if version else qemu}
    else:
        gate = output / "qemu-gate"
        diagnostics = output / "qemu-diagnostics"
        result = subprocess.run([
            sys.executable, "scripts/release_gate.py", "--version", "0.4.3b",
            "--release-stage", "physical-validation-candidate",
            "--output", str(gate), "--diagnostics", str(diagnostics),
        ], cwd=ROOT, check=False)
        summary = gate / "summary.json"
        if not summary.is_file():
            raise RuntimeError("QEMU gate did not produce summary.json")
        value = json.loads(summary.read_text(encoding="utf-8"))
        value["command_exit"] = result.returncode
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--image", type=pathlib.Path, required=True)
    parser.add_argument("--profile", type=pathlib.Path,
                        default=pathlib.Path("profiles/apple-a13-iphone-recovery.json"))
    parser.add_argument("--device-info", type=pathlib.Path,
                        default=pathlib.Path("examples/a13-device-info.json"))
    parser.add_argument("--run-qemu", action="store_true")
    parser.add_argument("--qemu-summary", type=pathlib.Path,
                        help="use an existing canonical QEMU gate summary")
    args = parser.parse_args(argv)
    # Preserve a caller-supplied relative path so generated JSON remains
    # relocatable and reproducible across checkout locations.
    output = args.output
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)

    success = run_json(bringup_command(
        output, args.profile, args.device_info, args.image,
        output / "success-state", output / "success-session.zip"), 0)

    timer_state = output / "recovery-state"
    failure = run_json(bringup_command(
        output, args.profile, args.device_info, args.image, timer_state,
        output / "failure-session.zip", "timer"), 1)
    recovered = run_json(bringup_command(
        output, args.profile, args.device_info, args.image, timer_state,
        output / "recovered-session.zip"), 0)

    failure_matrix: list[dict[str, Any]] = []
    for stage in FAILURE_STAGES:
        evidence = output / "failure-matrix" / f"{stage}.zip"
        value = run_json(bringup_command(
            output, args.profile, args.device_info, args.image,
            output / "failure-matrix" / f"{stage}-state", evidence, stage), 1)
        failure_matrix.append({
            "stage": stage,
            "failure_observed": not value.get("passed", True),
            "failed_stage": value.get("failed_stage"),
            "authorization_invalidated": value.get("authorization_invalidated_after_recovery", False),
            "evidence": str(evidence.relative_to(output)),
        })

    qemu = qemu_status(output, args.run_qemu, args.qemu_summary)
    report_command = [
        sys.executable, "host/physical_validation.py", "candidate-report",
        "--success", str(output / "success-session.zip"),
        "--failure", str(output / "failure-session.zip"),
        "--recovered", str(output / "recovered-session.zip"),
        "--qemu-summary", str(qemu),
        "--output", str(output / "candidate-report.json"),
    ]
    report = run_json(report_command, 0)
    summary = {
        "schema_version": 1,
        "project": "FBR34KER",
        "release_version": "0.4.3b",
        "release_name": "Beta",
        "candidate_ready": report["candidate_ready"],
        "physical_validation_complete": report["physical_validation_complete"],
        "success": success.get("passed", False),
        "failure_observed": not failure.get("passed", True),
        "recovered_after_reauthorization": recovered.get("passed", False),
        "failure_matrix": failure_matrix,
        "qemu_runtime": report["proof"]["qemu_runtime"],
        "physical_runtime": report["proof"]["physical_runtime"],
        "limitations": report["limitations"],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output / "summary.json")
    return 0 if summary["candidate_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
