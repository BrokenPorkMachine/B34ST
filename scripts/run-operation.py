#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Run a single operation with evidence collection
# Provides unified evidence collection across all B34ST tools

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Map operation keys to actual commands
OPERATION_MAP = {
    "system.version": ["fbr34ker", "version"],
    "system.doctor": ["fbr34ker", "doctor"],
    "device.info": ["fbr34ker", "device"],
    "device.detect": ["fbr34ker", "detect"],
    "device.exploit": ["fbr34ker", "exploit", "--auto"],
    "usbliter8.jailbreak": ["fbr34ker", "jailbreak"],
    "ipsw.catalog": ["fbr34ker", "ipsw", "catalog"],
    "ipsw.download": ["fbr34ker", "ipsw", "download"],
    "boot-image.build": ["fbr34ker", "boot-image", "build"],
    "forensics.acquire": ["fbr34ker", "forensics", "acquire"],
}


def run_command_and_capture(
    operation: str, command: list[str], extra_args: list[str] | None = None
) -> dict[str, Any]:
    """Run a command and capture evidence"""
    import subprocess

    extra_args = extra_args or []
    full_command = command + extra_args

    result = subprocess.run(full_command, capture_output=True, text=True, cwd=ROOT)

    evidence = {
        "schema_version": 1,
        "operation": operation,
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "command": full_command,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output_summary": result.stdout.strip().split("\n")[-1] if result.stdout else "No output",
    }

    return evidence


def main():
    parser = argparse.ArgumentParser(
        description="Run a single B34ST operation with evidence collection", prog="run-operation.py"
    )
    parser.add_argument("operation", help="Operation key to run")
    parser.add_argument("extra_args", nargs="*", help="Extra arguments for the operation")
    parser.add_argument("--output", help="Output file for evidence JSON")

    args = parser.parse_args()

    # Find operation
    if args.operation not in OPERATION_MAP:
        print(f"Error: Unknown operation: {args.operation}", file=sys.stderr)
        print("Available operations:")
        for k in sorted(OPERATION_MAP.keys()):
            print(f"  {k}")
        return 1

    command = OPERATION_MAP[args.operation]

    print(f"Running: {args.operation}")
    print(f"Command: {' '.join(command + args.extra_args)}")

    try:
        evidence = run_command_and_capture(args.operation, command, args.extra_args)

        # Save evidence
        if args.output:
            output_path = pathlib.Path(args.output)
        else:
            evidence_dir = ROOT / "runtime-artifacts" / "evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", args.operation).strip("-").lower()
            timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"{timestamp}-{safe_name}.json"
            output_path = evidence_dir / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2, sort_keys=True)

        print(f"Evidence saved to: {output_path.relative_to(ROOT)}")
        print(f"Exit code: {evidence['exit_code']}")
        return evidence["exit_code"]

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
