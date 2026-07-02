#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Evidence Collection Standardization Script
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

# Import evidence collection utilities from b34stool.py
try:
    sys.path.insert(0, str(ROOT))
    from b34st.b34stool import Colors, Session
except ImportError:
    # Fallback to manual evidence collection
    class Colors:
        if os.isatty(1):
            BOLD = "\033[1m"
            DIM = "\033[2m"
            RED = "\033[31m"
            GREEN = "\033[32m"
            YELLOW = "\033[33m"
            CYAN = "\033[36m"
            RESET = "\033[0m"
        else:
            BOLD = DIM = RED = GREEN = YELLOW = CYAN = RESET = ""

    def display_path(path: pathlib.Path) -> pathlib.Path:
        try:
            return path.relative_to(ROOT)
        except ValueError:
            return path


def run_command_and_capture(
    operation: str, command: list[str], extra_args: list[str] | None = None
) -> dict[str, Any]:
    """Run a command and capture evidence"""
    import subprocess

    extra_args = extra_args or []
    full_command = command + extra_args

    # Run the command
    result = subprocess.run(full_command, capture_output=True, text=True)

    # Create evidence
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


def collect_evidence_from_operation(operation: str, extra_args: list[str] | None = None) -> None:
    """Collect evidence from a specific operation"""
    # Map operations to commands
    operation_commands = {
        "system.version": ["fbr34ker", "version"],
        "system.doctor": ["fbr34ker", "doctor"],
        "device.exploit": ["fbr34ker", "exploit"],
    }

    if operation not in operation_commands:
        # Try direct mapping
        base_cmd = operation.split(".")
        command = ["fbr34ker"] + base_cmd[1:] if len(base_cmd) > 1 else []
    else:
        command = operation_commands[operation]

    print(f"{Colors.BOLD}Collecting evidence for: {operation}{Colors.RESET}")

    try:
        evidence = run_command_and_capture(operation, command, extra_args)

        # Save evidence
        evidence_dir = ROOT / "runtime-artifacts" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        # Generate safe filename
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", operation).strip("-").lower()
        timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{safe_name}.json"
        filepath = evidence_dir / filename

        with filepath.open("w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2, sort_keys=True)

        print(f"{Colors.GREEN}Evidence saved to: {filepath.relative_to(ROOT)}{Colors.RESET}")

    except Exception as e:
        print(f"{Colors.RED}Error collecting evidence: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)


def list_operations():
    """List available operations for evidence collection"""
    operations = [
        "system.version",
        "system.doctor",
        "device.info",
        "device.detect",
        "device.pwndfu",
        "device.exploit",
        "usbliter8.jailbreak",
        "ipsw.catalog",
        "ipsw.download",
        "boot-image.build",
        "forensics.acquire",
    ]

    print("Available operations for evidence collection:")
    for op in operations:
        print(f"  {op}")


def main():
    parser = argparse.ArgumentParser(
        description="B34ST Evidence Collection Standardization", prog="collect-evidence.py"
    )
    parser.add_argument("operation", nargs="?", help="Operation to collect evidence for")
    parser.add_argument(
        "--extra-args", nargs="+", default=[], help="Extra arguments for the operation"
    )
    parser.add_argument("--list-operations", action="store_true", help="List available operations")
    parser.add_argument("--output-dir", help="Custom output directory for evidence files")

    args = parser.parse_args()

    if args.list_operations:
        list_operations()
        return 0

    if not args.operation:
        parser.error("the following arguments are required: operation")

    collect_evidence_from_operation(args.operation, args.extra_args)


if __name__ == "__main__":
    raise SystemExit(main())
