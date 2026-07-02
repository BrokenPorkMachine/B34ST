#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Automated Smoke Test Workflow for B34ST/QEMU
# Unified script to simplify smoke test orchestration

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Determine build mode and paths
def setup_environment():
    """Setup environment and determine build configuration"""
    # Check for operational build (security model = 1)
    operational_build = os.environ.get('SECURITY_MODEL') == '1'
    
    if operational_build:
        build_dir = ROOT / "build-exploit"
        binary_name = "fbr34ker-operational.bin"
    else:
        build_dir = ROOT / "build"
        binary_name = "fbr34ker.bin"
    
    binary_path = build_dir / binary_name
    
    # Check if binary exists
    if not binary_path.exists():
        raise FileNotFoundError(
            f"Required binary not found: {binary_path}\n" \
            f"Run: make {'build-operational' if operational_build else ''}."
        )
    
    return binary_path, operational_build


@dataclass
class TestStep:
    name: str
    command: list[str]
    description: str = ""


class SmokeTestRunner:
    def __init__(self, binary_path: pathlib.Path, operational: bool):
        self.binary_path = binary_path
        self.operational = operational
        self.test_results = []
        self.evidence_dir = ROOT / "runtime-artifacts" / "smoke-tests"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def run_step(self, step: TestStep) -> dict:
        """Run a single test step and capture evidence"""
        print(f"\n{'='*60}")
        print(f"Running: {step.name}")
        print(f"Description: {step.description}")
        print(f"Command: {' '.join(step.command)}")
        print(f"{'='*60}")

        start_time = time.time()
        output_file = None
        passed = False
        detail = ""

        try:
            # Run command
            result = subprocess.run(
                step.command,
                capture_output=True,
                text=True,
                cwd=ROOT
            )

            # Save output to file
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", step.name).strip("-").lower()
            output_file = f"{timestamp}-{safe_name}.log"
            output_path = self.evidence_dir / output_file

            with output_path.open("w", encoding="utf-8") as f:
                f.write(f"Command: {' '.join(step.command)}\n")
                f.write(f"Return Code: {result.returncode}\n")
                f.write(f"Stdout:\n{result.stdout}\n")
                f.write(f"Stderr:\n{result.stderr}\n")

            duration_ms = int((time.time() - start_time) * 1000)

            # Determine if passed based on return code
            passed = result.returncode == 0
            if result.returncode != 0:
                detail = f"Command failed with exit code {result.returncode}"
            else:
                detail = "Command executed successfully"

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            detail = f"Error during execution: {e}"

        result = {
            "step": step.name,
            "passed": passed,
            "duration_ms": duration_ms,
            "output_file": output_file,
            "detail": detail,
            "command": step.command,
            "description": step.description
        }

        self.test_results.append(result)

        status = "PASS" if passed else "FAIL"
        print(f"\n{step.name}: {status}")
        print(f"Duration: {duration_ms}ms")
        print(f"Detail: {detail}")

        return result

    def save_results(self):
        """Save test results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        results_file = self.evidence_dir / f"smoke-test-results-{timestamp}.json"

        results = {
            "timestamp": datetime.now().isoformat(),
            "binary_path": str(self.binary_path),
            "operational": self.operational,
            "total_tests": len(self.test_results),
            "passed_tests": sum(1 for r in self.test_results if r["passed"]),
            "failed_tests": sum(1 for r in self.test_results if not r["passed"]),
            "steps": self.test_results
        }

        with results_file.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n{'='*60}")
        print(f"Test results saved to: {results_file.relative_to(ROOT)}")
        print(f"Total: {len(self.test_results)}, Passed: {results['passed_tests']}, Failed: {results['failed_tests']}")
        print(f"{'='*60}")

        return results_file

    def print_summary(self):
        """Print a summary of test results"""
        print(f"\n{'='*60}")
        print("SMOKE TEST SUMMARY")
        print(f"{'='*60}")

        for result in self.test_results:
            status = "✓" if result["passed"] else "✗"
            print(f"{status} {result['step']}")
            print(f"   Duration: {result['duration_ms']}ms")
            print(f"   Detail: {result['detail']}")
            print()

        passed = sum(1 for r in self.test_results if r["passed"])
        failed = sum(1 for r in self.test_results if not r["passed"])

        print(f"Total: {len(self.test_results)}, Passed: {passed}, Failed: {failed}")

        if failed > 0:
            print(f"\nFailed steps:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['step']}: {result['detail']}")

        print(f"{'='*60}")


def build_if_needed():
    """Build the B34ST monitor if needed"""
    operational = os.environ.get('SECURITY_MODEL') == '1'

    if operational:
        # Check if operational build exists
        if not (ROOT / "build-exploit" / "fbr34ker-operational.bin").exists():
            print("\nBuilding operational B34ST monitor...")
            subprocess.run(["make", "build-operational"], check=True)
    else:
        # Check if default build exists
        if not (ROOT / "build" / "fbr34ker.bin").exists():
            print("\nBuilding default B34ST monitor...")
            subprocess.run(["make"], check=True)

    print("Build complete")


def main():
    parser = argparse.ArgumentParser(
        description="Automated smoke test workflow for B34ST",
        prog="smoke-test-runner.sh"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check if build exists and exit without running tests"
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Build only, don't run tests"
    )
    parser.add_argument(
        "--operational",
        action="store_true",
        help="Use operational build (security model = 1)"
    )
    parser.add_argument(
        "--output-dir",
        help="Custom output directory for test artifacts"
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        help="Specific test steps to run (run 'list' to see available)"
    )

    args = parser.parse_args()

    # Set security model for the build
    if args.operational:
        os.environ['SECURITY_MODEL'] = '1'

    try:
        # Setup environment and get binary path
        binary_path, operational_mode = setup_environment()

        if args.check_only:
            print(f"Build mode: {'operational' if operational_mode else 'default'}")
            print(f"Binary path: {binary_path}")
            print(f"Exists: {binary_path.exists()}")
            return 0

        # Build if needed
        if not args.build_only:
            build_if_needed()

        # Get updated binary path after potential build
        binary_path, operational_mode = setup_environment()

        # Define test steps
        base_steps = [
            TestStep(
                "version-check",
                ["fbr34ker", "version"],
                "Check B34ST version information"
            ),
            TestStep(
                "doctor-check",
                ["fbr34ker", "doctor"],
                "Run toolchain doctor check"
            ),
            TestStep(
                "device-detect",
                ["fbr34ker", "detect"],
                "Detect available devices"
            ),
            TestStep(
                "simple-qemu",
                [
                    "qemu-system-aarch64",
                    "-cpu", "cortex-a72",
                    "-m", "1024",
                    "-drive", f"format=raw,file={binary_path}",
                    "-nographic",
                    "-serial", "stdio",
                    "-display", "none"
                ],
                "Run a simple QEMU test (limited time)"
            )
        ]

        # Filter steps if specific ones requested
        if args.steps:
            if "list" in args.steps:
                print("\nAvailable smoke test steps:")
                for i, step in enumerate(base_steps, 1):
                    print(f"{i}. {step.name}: {step.description}")
                return 0

            steps = []
            for step in base_steps:
                if step.name in args.steps or step.name.startswith(tuple(args.steps)):
                    steps.append(step)
            
            if not steps:
                print(f"Error: No matching test steps found for: {args.steps}")
                return 1
        else:
            steps = base_steps

        # Initialize runner
        runner = SmokeTestRunner(binary_path, operational_mode)

        # Run tests
        for step in steps:
            runner.run_step(step)

        # Save and print results
        results_file = runner.save_results()
        runner.print_summary()

        # Determine exit code
        failed_count = sum(1 for r in runner.test_results if not r["passed"])

        if failed_count > 0:
            print(f"\nSmoke tests failed: {failed_count} step(s) failed")
            return 1
        else:
            print(f"\nAll smoke tests passed!")
            return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"Error during build/test: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
