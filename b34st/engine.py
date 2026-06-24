#!/usr/bin/env python3
"""B34ST (B34KER/STAR) Validation Engine

Core validation logic for B34ST runtime authentication.
Implements deterministic validation, profile maturity enforcement,
and evidence-based authentication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

from b34st.version import __version__, __release_name__


class B34STError(Exception):
    """B34ST-specific error class."""

    pass


class B34STCLI:
    """B34ST command-line interface wrapper for FBR34KER validation."""

    def __init__(self, verbose: bool = False, quiet: bool = False):
        self.verbose = verbose
        self.quiet = quiet

    def run(self, argv: list[str]) -> int:
        """Run B34ST CLI command."""
        if not argv:
            self._show_help()
            return 0

        command = argv[0]

        try:
            if command == "validate-session":
                return self._validate_session(argv[1:])
            elif command == "physical-validation":
                return self._physical_validation(argv[1:])
            elif command == "hardware-prepare":
                return self._hardware_prepare(argv[1:])
            else:
                self.log(f"Unknown command: {command}", "ERROR")
                self._show_help()
                return 1

        except B34STError as e:
            self.log(f"B34ST Error: {e}", "ERROR")
            return 1
        except Exception as e:
            self.log(f"Unexpected error: {e}", "ERROR")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return 1

    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        if self.quiet and level != "ERROR":
            return

        prefix = "INFO:" if level not in ["ERROR", "WARN"] else "ERROR:" if level == "ERROR" else "WARN:"
        print(f"{prefix} {message}", file=sys.stderr if level != "INFO" else sys.stdout)

    def _show_version(self):
        """Show B34ST version information."""
        print(f"B34ST {__version__} ({__release_name__})")
        print("FBR34KER Runtime Authentication Tool")
        print("Physical Validation Candidate")
        print("\nB34ST v0.2.3 is a lightweight CLI wrapper for FBR34KER's\nphysical validation framework, providing access to:\n")
        print("• Bundle validation")
        print("• Candidate report generation")
        print("• Hardware preparation checklists")

    def _show_help(self):
        """Show B34ST CLI help."""
        self._show_version()
        print("\nB34ST (B34KER/STAR) - Runtime Authentication Tool")
        print("\nB34ST is now a lightweight CLI that provides access to\nFBR34KER's core validation capabilities.\n")
        print("\nAvailable commands:")
        print("  b34st validate-session         Validate a session bundle")
        print("  b34st physical-validation       Perform physical validation operations")
        print("  b34st hardware-prepare         Read-only hardware preparation")
        print("  b34st --version               Show version information\n")
        print("\nFor FBR34KER's full validation workflow:\n")
        print("  ./fbr34ker validate-session --bundle <file>")
        print("  ./fbr34ker physical-validation candidate-report <options>")
        print("  ./fbr34ker hardware-prepare --list-categories\n")
        print("B34ST v0.2.3 is part of FBR34KER 0.2.3 Physical Validation Candidate")

    def _validate_session(self, argv: list[str]) -> int:
        """Validate a session bundle using FBR34KER's validate-session command."""
        self.log("B34ST: Wrapping FBR34KER validate-session command")

        # Check for required arguments
        if "--bundle" not in argv:
            raise B34STError("Missing --bundle argument")

        # Find the bundle value
        import re

        bundle_arg_idx = argv.index("--bundle")
        if bundle_arg_idx + 1 >= len(argv):
            raise B34STError("Missing bundle file path")

        bundle_path = argv[bundle_arg_idx + 1]
        self.log(f"Checking bundle file: {bundle_path}")

        # Import and run FBR34KER's validate-session implementation
        try:
            import subprocess

            # Build the full fbr34ker command
            cmd = [
                "fbr34ker", "validate-session", "--bundle", bundle_path
            ]

            # Add profile if specified
            if "--profile" in argv:
                profile_arg_idx = argv.index("--profile")
                if profile_arg_idx + 1 < len(argv):
                    cmd.extend(["--profile", argv[profile_arg_idx + 1]])

            # Execute FBR34KER command
            self.log(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

            if result.returncode == 0:
                print(result.stdout)
                return 0
            else:
                self.log(f"FBR34KER validation failed: {result.stderr}", "ERROR")
                return result.returncode

        except ImportError as e:
            raise B34STError(f"FBR34KER not available: {e}")
        except Exception as e:
            raise B34STError(f"Failed to validate bundle: {e}")

    def _physical_validation(self, argv: list[str]) -> int:
        """Perform physical validation using FBR34KER's physical-validation command."""
        self.log("B34ST: Wrapping FBR34KER physical-validation command")

        if "--success" not in argv:
            raise B34STError("Missing --success argument")

        # Extract arguments from the wrapper
        try:
            import subprocess
            import json

            # Find arguments
            bundle_files = {}
            output_file = None
            qemu_summary = None

            i = 0
            while i < len(argv):
                if argv[i] == "--success":
                    bundle_files["success"] = argv[i + 1]
                    i += 1
                elif argv[i] == "--failure":
                    bundle_files["failure"] = argv[i + 1]
                    i += 1
                elif argv[i] == "--recovered":
                    bundle_files["recovered"] = argv[i + 1]
                    i += 1
                elif argv[i] == "--output":
                    output_file = argv[i + 1]
                    i += 1
                elif argv[i] == "--qemu-summary":
                    qemu_summary = argv[i + 1]
                    i += 1
                else:
                    i += 1

            if len(bundle_files) != 3:
                raise B34STError("Must provide all three bundles: --success, --failure, --recovered")

            # Build the fbr34ker command
            cmd = ["fbr34ker", "physical-validation", "candidate-report"]
            for key, path in bundle_files.items():
                cmd.extend([f"--{key}", path])
            if output_file:
                cmd.extend(["--output", output_file])
            if qemu_summary:
                cmd.extend(["--qemu-summary", qemu_summary])

            self.log(f"Running: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

            if result.returncode == 0:
                if output_file and pathlib.Path(output_file).exists():
                    self.log(f"Candidate report generated: {output_file}")
                    # Display first part of report
                    with open(output_file, "r") as f:
                        report = json.load(f)
                        self.log(f"Candidate ready: {report.get('candidate_ready', 'unknown')}")
                        self.log(f"Physical validation complete: {report.get('physical_validation_complete', 'unknown')}")
                print(result.stdout)
                return result.returncode
            else:
                self.log(f"FBR34KER physical-validation failed: {result.stderr}", "ERROR")
                return result.returncode

        except ImportError as e:
            raise B34STError(f"FBR34KER not available: {e}")
        except Exception as e:
            raise B34STError(f"Failed to perform physical validation: {e}")

    def _hardware_prepare(self, argv: list[str]) -> int:
        """Handle hardware preparation using FBR34KER's hardware-prepare command."""
        self.log("B34ST: Wrapping FBR34KER hardware-prepare command")

        if "--list-categories" in argv:
            self._show_hardware_categories()
            return 0

        if "--save-checklists" in argv:
            checklist_arg_idx = argv.index("--save-checklists")
            if checklist_arg_idx + 1 >= len(argv):
                raise B34STError("Missing checklist directory path")

            checklist_dir = argv[checklist_arg_idx + 1]
            self.log(f"Generating hardware checklists: {checklist_dir}")

            try:
                import subprocess

                # Run FBR34KER's hardware-prepare with save-checklists
                cmd = [
                    "fbr34ker", "hardware-prepare",
                    "--save-checklists", checklist_dir
                ]

                self.log(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

                if result.returncode == 0:
                    print(result.stdout)
                    return 0
                else:
                    self.log(f"FBR34KER hardware-prepare failed: {result.stderr}", "ERROR")
                    return result.returncode

            except Exception as e:
                raise B34STError(f"Failed to generate hardware checklists: {e}")

        self.log("hardware-prepare: no valid action specified", "WARN")
        self._show_hardware_categories()
        return 1

    def _show_hardware_categories(self):
        """Show available hardware preparation categories."""
        categories = [
            "console",
            "board-inventory",
            "memory-map",
            "timer",
            "interrupts",
            "watchdog",
            "boot-evidence",
        ]

        print("B34ST Hardware Preparation Categories:")
        print("(These are generated via FBR34KER's hardware-prepare command)")
        for cat in categories:
            print(f"  - {cat}")
        print("\nFor detailed checklists:")
        print("  b34st hardware-prepare --save-checklists <directory>")


def main() -> int:
    """Main B34ST CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="b34st",
        description="B34ST - FBR34KER Runtime Authentication Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
B34ST (B34KER/STAR) is a lightweight CLI wrapper for FBR34KER that
provides access to deterministic validation workflows, profile maturity
enforcement, and evidence-based authentication for A12/A13 iPhone hardware.

B34ST v0.2.3 is part of FBR34KER 0.2.3 Physical Validation Candidate.
It integrates with existing FBR34KER validation capabilities while
providing a streamlined interface for common operations.
        """,
    )

    parser.add_argument(
        "--version", action="store_true", help="Show B34ST version and exit"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress non-essential output"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )

    if len(sys.argv) == 1:
        print("B34ST - FBR34KER Runtime Authentication Tool")
        print(f"Version {__version__} ({__release_name__})")
        print("\nB34ST v0.2.3 is a lightweight CLI wrapper for FBR34KER")
        print("\nAvailable commands:")
        print("  b34st validate-session         Validate a session bundle")
        print("  b34st physical-validation       Perform physical validation operations")
        print("  b34st hardware-prepare         Read-only hardware preparation")
        print("\nFor detailed help:")
        print("  b34st <command> --help")
        return 0

    args = parser.parse_args(sys.argv[1:])

    cli = B34STCLI(args.verbose, args.quiet)

    return cli.run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

