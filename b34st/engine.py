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

from b34st.environment import (
    EnvironmentPlanError,
    build_environment_plan,
    load_and_validate_plan,
    write_plan,
)
from b34st.version import __version__, __release_name__

ROOT = pathlib.Path(__file__).resolve().parent.parent


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
        if command in {"-h", "--help"}:
            self._show_help()
            return 0
        if command == "--version":
            self._show_version()
            return 0

        try:
            if command in {"control-panel", "menu"}:
                from b34st.control_panel import run_control_panel
                return run_control_panel()
            elif command == "research-runtime":
                from b34st.research_runtime import main as research_runtime_main
                return research_runtime_main(argv[1:])
            elif command == "validate-session":
                return self._validate_session(argv[1:])
            elif command == "physical-validation":
                return self._physical_validation(argv[1:])
            elif command == "hardware-prepare":
                return self._hardware_prepare(argv[1:])
            elif command == "environment-plan":
                return self._environment_plan(argv[1:])
            elif command == "environment-validate":
                return self._environment_validate(argv[1:])
            elif command == "fbr34ker":
                import subprocess
                return subprocess.run(
                    [self._fbr34ker_command(), *argv[1:]],
                    cwd=ROOT,
                    check=False,
                ).returncode
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

    @staticmethod
    def _fbr34ker_command() -> str:
        launcher = ROOT / "fbr34ker"
        return str(launcher) if launcher.is_file() else "fbr34ker"

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
        print("  b34st control-panel           Open the operator control panel")
        print("  b34st research-runtime        Run the evidence-gated runtime orchestrator")
        print("  b34st validate-session         Validate a session bundle")
        print("  b34st physical-validation       Perform physical validation operations")
        print("  b34st hardware-prepare         Read-only hardware preparation")
        print("  b34st environment-plan         Plan an iOS 17+ research environment")
        print("  b34st environment-validate     Validate an environment manifest")
        print("  b34st fbr34ker <args...>       Run a backend FBR34KER command")
        print("  b34st --version               Show version information\n")
        print("\nFor FBR34KER's full validation workflow:\n")
        print("  ./fbr34ker validate-session --bundle <file>")
        print("  ./fbr34ker physical-validation candidate-report <options>")
        print("  ./fbr34ker hardware-prepare --list-categories\n")
        print("B34ST v0.2.3 is part of FBR34KER 0.2.3 Physical Validation Candidate")

    def _validate_session(self, argv: list[str]) -> int:
        """Validate a session bundle using FBR34KER's validate-session command."""
        self.log("B34ST: Wrapping FBR34KER validate-session command")

        parser = argparse.ArgumentParser(
            prog="b34st validate-session",
            description="Validate a session bundle using FBR34KER's validate-session command.",
        )
        parser.add_argument("--bundle", required=True, help="Path to session bundle")
        parser.add_argument("--profile", help="Device profile")

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        bundle_path = args.bundle
        self.log(f"Checking bundle file: {bundle_path}")

        # Import and run FBR34KER's validate-session implementation
        try:
            import subprocess

            # Build the full fbr34ker command
            cmd = [
                self._fbr34ker_command(), "validate-session", "--bundle", bundle_path
            ]

            # Add profile if specified
            if args.profile:
                cmd.extend(["--profile", args.profile])

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

        parser = argparse.ArgumentParser(
            prog="b34st physical-validation",
            description="Perform physical validation using FBR34KER's physical-validation command.",
        )
        parser.add_argument("subcommand", nargs="?", choices=["candidate-report"], help="Physical validation subcommand")
        parser.add_argument("--success", required=True, help="Successful bundle path")
        parser.add_argument("--failure", required=True, help="Failure bundle path")
        parser.add_argument("--recovered", required=True, help="Recovered bundle path")
        parser.add_argument("--qemu-summary", help="QEMU summary path")
        parser.add_argument("--output", help="Output report path")

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        # Build the fbr34ker command
        cmd = [self._fbr34ker_command(), "physical-validation", "candidate-report"]
        cmd.extend(["--success", args.success])
        cmd.extend(["--failure", args.failure])
        cmd.extend(["--recovered", args.recovered])
        if args.qemu_summary:
            cmd.extend(["--qemu-summary", args.qemu_summary])
        if args.output:
            cmd.extend(["--output", args.output])

        try:
            import subprocess
            import json

            self.log(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

            if result.returncode == 0:
                if args.output and pathlib.Path(args.output).exists():
                    self.log(f"Candidate report generated: {args.output}")
                    # Display first part of report
                    with open(args.output, "r") as f:
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

        parser = argparse.ArgumentParser(
            prog="b34st hardware-prepare",
            description="Handle hardware preparation using FBR34KER's hardware-prepare command.",
        )
        parser.add_argument("--list-categories", action="store_true", help="List preparation categories")
        parser.add_argument("--save-checklists", help="Save checklists to directory")
        parser.add_argument("--validate-bundle", help="Validate existing bundle")

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        if not args.list_categories and not args.save_checklists and not args.validate_bundle:
            self.log("hardware-prepare: no valid action specified", "WARN")
            self._show_hardware_categories()
            return 1

        if args.list_categories:
            self._show_hardware_categories()
            return 0

        if args.save_checklists:
            checklist_dir = args.save_checklists
            self.log(f"Generating hardware checklists: {checklist_dir}")

            try:
                import subprocess

                # Run FBR34KER's hardware-prepare with save-checklists
                cmd = [
                    self._fbr34ker_command(), "hardware-prepare",
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

        if args.validate_bundle:
            try:
                import subprocess
                cmd = [
                    self._fbr34ker_command(), "hardware-prepare",
                    "--validate-bundle", args.validate_bundle
                ]
                self.log(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
                if result.returncode == 0:
                    print(result.stdout)
                    return 0
                else:
                    self.log(f"FBR34KER hardware-prepare validate-bundle failed: {result.stderr}", "ERROR")
                    return result.returncode
            except Exception as e:
                raise B34STError(f"Failed to validate bundle: {e}")

        return 0

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

    def _environment_plan(self, argv: list[str]) -> int:
        parser = argparse.ArgumentParser(
            prog="b34st environment-plan",
            description="Create a bounded iOS 17+ research-environment manifest.",
        )
        parser.add_argument("--ios", required=True, help="Target iOS version")
        parser.add_argument("--product", required=True, help="Apple product identifier")
        parser.add_argument(
            "--mode",
            choices=("simulation", "research-runtime"),
            default="simulation",
        )
        parser.add_argument(
            "--owner-authorized",
            action="store_true",
            help="Confirm the target is owned by or explicitly authorized for the operator",
        )
        parser.add_argument(
            "--capability",
            action="append",
            default=[],
            help="Request a bounded capability; may be repeated",
        )
        parser.add_argument("--output", type=pathlib.Path)

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        try:
            plan = build_environment_plan(
                ios_version=args.ios,
                product=args.product,
                mode=args.mode,
                owner_authorized=args.owner_authorized,
                requested_capabilities=args.capability,
            )
        except EnvironmentPlanError as exc:
            raise B34STError(str(exc)) from exc

        if args.output:
            write_plan(plan, args.output)
            self.log(f"Environment plan written: {args.output}")
        else:
            print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    def _environment_validate(self, argv: list[str]) -> int:
        parser = argparse.ArgumentParser(
            prog="b34st environment-validate",
            description="Validate a B34ST environment manifest and its security boundary.",
        )
        parser.add_argument("--plan", required=True, type=pathlib.Path)

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        try:
            _plan, errors = load_and_validate_plan(args.plan)
        except EnvironmentPlanError as exc:
            raise B34STError(str(exc)) from exc
        if errors:
            for error in errors:
                self.log(error, "ERROR")
            return 1
        self.log(f"Environment plan valid: {args.plan}")
        return 0


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
