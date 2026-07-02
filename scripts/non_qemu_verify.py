#!/usr/bin/env python3

"""Run the complete non-QEMU FBR34KER gate as isolated bounded stages."""
# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
import time
from dataclasses import asdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from release_gate import run_stage  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=pathlib.Path,
                        default=pathlib.Path("validation-logs/non-qemu"))
    parser.add_argument("--build-jobs", type=int, default=4)
    args = parser.parse_args(argv)
    if args.build_jobs <= 0:
        parser.error("--build-jobs must be positive")
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    started = time.monotonic()
    environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    stages: list[tuple[str, list[str], float]] = [
        ("host-readiness", [sys.executable, "scripts/doctor.py"], 45.0),
        ("host-tests", ["make", "check-launcher", "check-scripts", "check-install", "abi-check", "check-host"], 210.0),
        ("monitor-analysis", ["make", "analyze"], 180.0),
        ("sdk-analysis", ["make", "sdk-analyze"], 90.0),
        ("native-tests", ["make", "check-native", "check-loader-example"], 180.0),
        ("release-build", ["make", f"-j{args.build_jobs}", "all", "generic",
                           "hardware-probe", "modules", "sdk", "generic-loader",
                           "apple-boot-images"], 300.0),
        ("conformance", ["make", "loader-check", "loader-conformance-test", "sdk-test",
                         "deployment-simulate", "apple-bringup-simulate",
                         "physical-integration-simulate", "physical-validation-candidate"], 360.0),
        ("manifest", ["make", "manifest"], 180.0),
        ("layout-and-artifact-checks", ["make", "verify-layouts"], 120.0),
    ]
    results = []
    for name, command, timeout in stages:
        result = run_stage(name, command, output, timeout, environment=environment)
        results.append(result)
        print(f"[{result.status.upper():7}] {name}: {result.detail}", flush=True)
        if result.status != "passed":
            break
    passed = len(results) == len(stages) and all(item.status == "passed" for item in results)
    summary = {
        "schema_version": 1,
        "project": "FBR34KER",
        "version": args.version,
        "gate": "non-qemu",
        "passed": passed,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "stages": [asdict(item) for item in results],
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    if passed:
        print(f"FBR34KER {args.version} non-QEMU verification passed")
        print(output)
        return 0
    failed = results[-1]
    print(f"FBR34KER {args.version} non-QEMU verification failed: "
          f"{failed.name} ({failed.detail})", file=sys.stderr)
    if failed.log:
        print(f"stage log: {output / failed.log}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
