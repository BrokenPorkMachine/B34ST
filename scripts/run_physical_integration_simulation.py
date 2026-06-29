#!/usr/bin/env python3
"""Generate deterministic persistent-bridge integration evidence."""
from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(command: list[str], expected: int) -> dict[str, object]:
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode != expected:
        raise RuntimeError(f"unexpected exit {result.returncode}: {result.stderr}")
    return json.loads(result.stdout)


def bridge_command(state: pathlib.Path, device: pathlib.Path, inject: str | None = None) -> str:
    values = [sys.executable, str(ROOT / "host/reference_bridge.py"),
              "--state-dir", str(state), "--device-info", str(device)]
    if inject:
        values += ["--inject-failure", inject]
    return shlex.join(values)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--image", type=pathlib.Path, required=True)
    parser.add_argument("--profile", type=pathlib.Path,
                        default=pathlib.Path("profiles/apple-a13-iphone-recovery.json"))
    parser.add_argument("--device-info", type=pathlib.Path,
                        default=pathlib.Path("examples/a13-device-info.json"))
    args = parser.parse_args(argv)
    output = args.output.resolve()
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    common = [sys.executable, "host/hardware_bringup.py", "run",
              "--state-dir", str(output / "unused"),
              "--device-info", str(args.device_info), "--profile", str(args.profile),
              "--image", str(args.image), "--authorized-session",
              "--authorization-id", "physical-integration-simulation",
              "--acknowledge-unsigned-code"]
    success_state = output / "success-state"
    success = run([*common, "--bridge-command", bridge_command(success_state, args.device_info),
                   "--evidence", str(output / "success-session.zip")], 0)
    recovery_state = output / "recovery-state"
    failure = run([*common, "--bridge-command", bridge_command(recovery_state, args.device_info, "timer"),
                   "--evidence", str(output / "failure-session.zip")], 1)
    recovered = run([*common, "--bridge-command", bridge_command(recovery_state, args.device_info),
                     "--evidence", str(output / "recovered-session.zip")], 0)
    summary = {
        "schema_version": 1,
        "project": "FBR34KER",
        "release_version": "0.4.1",
        "workflow": "persistent-first-stage-bridge-simulation",
        "success": success["passed"],
        "failure_observed": not failure["passed"],
        "failure_stage": failure["failed_stage"],
        "reset_invalidated_authorization": failure["authorization_invalidated_after_recovery"],
        "recovered_after_reauthorization": recovered["passed"],
        "physical_execution_verified": False,
    }
    (output / "simulation-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output / "simulation-summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
