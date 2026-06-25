#!/usr/bin/env python3
"""Run FBR34KER Python host tests as isolated bounded modules."""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAN = re.compile(r"Ran (\d+) tests?")
SKIPPED = re.compile(r"skipped=(\d+)")


def terminate_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2.0)


def run_module(module: str, environment: dict[str, str], timeout: float) -> tuple[int, str, float]:
    started = time.monotonic()
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "unittest", "-v", module],
            cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, text=True,
            start_new_session=True,
        )
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_group(process)
            returncode = 124
        log.seek(0)
        output = log.read()
    return returncode, output, time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="total suite timeout in seconds")
    parser.add_argument("--module-timeout", type=float, default=60.0)
    parser.add_argument("--pattern", default="test_*.py")
    args = parser.parse_args()
    if args.timeout <= 0 or args.module_timeout <= 0:
        parser.error("timeouts must be positive")
    files = sorted((ROOT / "tests").glob(args.pattern))
    if not files:
        parser.error("no test modules matched")
    environment = os.environ.copy()
    for key in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "TARGET"):
        environment.pop(key, None)
    environment["FBR34KER_SKIP_QEMU_TESTS"] = "1"
    started = time.monotonic()
    total = 0
    skipped = 0
    print(f"[host-tests] isolated modules: {len(files)}, total-timeout={args.timeout:g}s, module-timeout={args.module_timeout:g}s", flush=True)
    for path in files:
        elapsed = time.monotonic() - started
        if elapsed >= args.timeout:
            print(f"host test suite exceeded total timeout before {path.name}", file=sys.stderr)
            return 1
        remaining = min(args.module_timeout, args.timeout - elapsed)
        module = f"tests.{path.stem}"
        returncode, output, duration = run_module(module, environment, remaining)
        ran = RAN.search(output)
        module_total = int(ran.group(1)) if ran else 0
        skipped_match = SKIPPED.search(output)
        module_skipped = int(skipped_match.group(1)) if skipped_match else 0
        total += module_total
        skipped += module_skipped
        status = "PASS" if returncode == 0 else "TIMEOUT" if returncode == 124 else "FAIL"
        print(f"[{status:7}] {module}: {module_total} tests, {module_skipped} skipped, {duration:.2f}s", flush=True)
        if returncode != 0:
            if output:
                print(output, end="" if output.endswith("\n") else "\n")
            return 1
    print(f"isolated host tests passed ({total} tests, {skipped} skipped, {time.monotonic()-started:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
