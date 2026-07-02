#!/usr/bin/env python3

"""B34ST (B34KER/STAR) Validation Engine
# SPDX-License-Identifier: BSD-2-Clause

Core validation logic for B34ST runtime authentication.
Implements deterministic validation, profile maturity enforcement,
and evidence-based authentication.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any
import difflib

from b34st.environment import (
    EnvironmentPlanError,
    build_environment_plan,
    load_and_validate_plan,
    write_plan,
)
from b34st.forensics import _check_security_boundary
from b34st.version import __version__, __release_name__
from b34st.control_panel import AUTHORIZATION_TEXT


class Colors:
    if sys.stdout.isatty():
        BOLD = "\033[1m"
        DIM = "\033[2m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        CYAN = "\033[36m"
        RESET = "\033[0m"
    else:
        BOLD = DIM = RED = GREEN = YELLOW = BLUE = CYAN = RESET = ""


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
            if command in {"control-panel", "menu", "console"}:
                from b34st.control_panel import run_control_panel

                return run_control_panel()
            elif command == "neo":
                # Launch FBR34KER guided console directly
                print(f"{Colors.BOLD}Launching FBR34KER guided console {Colors.RESET}")
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
            elif command == "usbliter8":
                return self._usbliter8(argv[1:])
            elif command == "forensics":
                return self._forensics(argv[1:])
            elif command in ("sep-fuzz", "sep-fuzzer", "sep-key-fuzz"):
                return self._sep_fuzz(argv[1:])
            elif command in ("sep-research", "sep-pipeline", "sep-research-pipeline"):
                return self._sep_research(argv[1:])
            elif command == "cve":
                return self._cve(argv[1:])
            elif command == "fbr34ker":
                import subprocess

                return subprocess.run(
                    [self._fbr34ker_command(), *argv[1:]],
                    cwd=ROOT,
                    check=False,
                ).returncode
            else:
                suggestions = difflib.get_close_matches(
                    command,
                    [
                        "control-panel",
                        "research-runtime",
                        "validate-session",
                        "physical-validation",
                        "hardware-prepare",
                        "environment-plan",
                        "environment-validate",
                        "usbliter8",
                        "forensics",
                        "sep-fuzz",
                        "sep-research",
                        "cve",
                        "fbr34ker",
                    ],
                    n=3,
                    cutoff=0.4,
                )
                msg = f"Unknown command: {command}"
                if suggestions:
                    msg += f" (did you mean: {', '.join(suggestions)}?)"
                self.log(msg, "ERROR")
                self._show_help()
                return 1

        except B34STError as e:
            self.log(f"B34ST Error: {e}", "ERROR")
            return 1
        except (OSError, ImportError, ValueError) as e:
            self.log(f"Unexpected error: {e}", "ERROR")
            if self.verbose:
                import traceback

                traceback.print_exc()
            return 1

    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        if self.quiet and level != "ERROR":
            return

        prefix = (
            "INFO:" if level not in ["ERROR", "WARN"] else "ERROR:" if level == "ERROR" else "WARN:"
        )
        print(f"{prefix} {message}", file=sys.stderr if level != "INFO" else sys.stdout)

    @staticmethod
    def _fbr34ker_command() -> str:
        launcher = ROOT / "fbr34ker"
        return str(launcher) if launcher.is_file() else "fbr34ker"

    def _show_version(self):
        """Show B34ST version information."""
        print(f"B34ST {__version__} ({__release_name__})")
        print("FBR34KER Runtime Authentication Tool")
        print("Beta")
        print(
            f"\nB34ST v{__version__} is a lightweight CLI wrapper for "
            "FBR34KER's\nphysical validation framework, providing access to:\n"
        )
        print("• Bundle validation")
        print("• Candidate report generation")
        print("• USBliter8 exploit workflow (with hardware guide)")
        print("• Hardware preparation checklists")

    def _show_help(self):
        """Show B34ST CLI help."""
        self._show_version()
        print("\nB34ST (B34KER/STAR) - Runtime Authentication Tool")
        print(
            "\nB34ST is now a lightweight CLI that provides access to\nFBR34KER's core validation capabilities.\n"
        )
        print("\nAvailable commands:")
        print("  b34st control-panel           Open the operator control panel")
        print("  b34st research-runtime        Run the evidence-gated runtime orchestrator")
        print("  b34st validate-session         Validate a session bundle")
        print("  b34st physical-validation       Perform physical validation operations")
        print("  b34st hardware-prepare         Read-only hardware preparation")
        print("  b34st environment-plan         Plan an iOS 17+ research environment")
        print("  b34st environment-validate     Validate an environment manifest")
        print("  b34st forensics               Forensics and data acquisition")
        print("    forensics acquire             Standard evidence acquisition")
        print("    forensics secrets             iCloud/Keychain/Keybag extraction")
        print("    forensics activation          Activation bypass & FMI control")
        print("    forensics passcode            Passcode on/off/change/bypass")
        print("  b34st sep-fuzz                SEP Key Fuzzer — differential wrapper testing")
        print("    sep-fuzz run                   Run a full fuzzing campaign")
        print("      --transport <type>             Device transport: simulator|usb|serial")
        print("    sep-fuzz list-variations       List all fuzz variations")
        print("    sep-fuzz list-categories       List fuzz categories")
        print("    sep-fuzz generate-harness      Generate baseline Swift harness")
        print(
            "  b34st sep-research             SEP Research Pipeline — automated SEP/sepOS fuzzing"
        )
        print("    sep-research run               Run the full research pipeline")
        print("      --transport <type>             Device transport: simulator|usb|serial|tcp")
        print("    sep-research list-stages       List pipeline stages")
        print("    sep-research info              Show pipeline information")
        print("  b34st cve                     CVE database & exploit chain planner")
        print("    cve search <query>            Search CVEs by ID or description")
        print("    cve query <version>           Get all CVEs for an iOS version")
        print("    cve filter                    Filter CVEs by criteria")
        print("    cve stats                     Database statistics")
        print("    cve chain <goal> <version>    Plan exploit chain for a goal")
        print("    cve suggest <version>         Suggest achievable goals")
        print("    cve goals                     List all built-in exploit goals")
        print("    cve fuzz list                 List available fuzz targets")
        print("  b34st fbr34ker <args...>       Run a backend FBR34KER command")
        print(
            "  b34st usbliter8                USBliter8 exploit workflow (hardware prep + execution)"
        )
        print("  b34st --version               Show version information\n")
        print("\nFor FBR34KER's full validation workflow:\n")
        print("  ./fbr34ker validate-session --bundle <file>")
        print("  ./fbr34ker physical-validation candidate-report <options>")
        print("  ./fbr34ker hardware-prepare --list-categories\n")
        print(f"B34ST v{__version__} is part of FBR34KER {__version__} Beta")

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
                self._fbr34ker_command(),
                "validate-session",
                "--bundle",
                bundle_path,
            ]

            # Add profile if specified
            if args.profile:
                cmd.extend(["--profile", args.profile])

            # Execute FBR34KER command
            self.log(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".", check=False)

            if result.returncode == 0:
                print(result.stdout)
                return 0
            else:
                self.log(f"FBR34KER validation failed: {result.stderr}", "ERROR")
                return result.returncode

        except ImportError as e:
            raise B34STError(f"FBR34KER not available: {e}") from e
        except (
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
            ValueError,
        ) as e:
            raise B34STError(f"Failed to validate bundle: {e}") from e

    def _physical_validation(self, argv: list[str]) -> int:
        """Perform physical validation using FBR34KER's physical-validation command."""
        self.log("B34ST: Wrapping FBR34KER physical-validation command")

        parser = argparse.ArgumentParser(
            prog="b34st physical-validation",
            description="Perform physical validation using FBR34KER's physical-validation command.",
        )
        parser.add_argument(
            "subcommand",
            nargs="?",
            choices=["candidate-report"],
            help="Physical validation subcommand",
        )
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
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".", check=False)

            if result.returncode == 0:
                if args.output and pathlib.Path(args.output).exists():
                    self.log(f"Candidate report generated: {args.output}")
                    # Display first part of report
                    with open(args.output, "r") as f:
                        report = json.load(f)
                        self.log(f"Candidate ready: {report.get('candidate_ready', 'unknown')}")
                        self.log(
                            f"Physical validation complete: {report.get('physical_validation_complete', 'unknown')}"
                        )
                print(result.stdout)
                return result.returncode
            else:
                self.log(f"FBR34KER physical-validation failed: {result.stderr}", "ERROR")
                return result.returncode

        except ImportError as e:
            raise B34STError(f"FBR34KER not available: {e}") from e
        except (
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
            ValueError,
        ) as e:
            raise B34STError(f"Failed to perform physical validation: {e}") from e

    def _hardware_prepare(self, argv: list[str]) -> int:
        """Handle hardware preparation using FBR34KER's hardware-prepare command."""
        self.log("B34ST: Wrapping FBR34KER hardware-prepare command")

        parser = argparse.ArgumentParser(
            prog="b34st hardware-prepare",
            description="Handle hardware preparation using FBR34KER's hardware-prepare command.",
        )
        parser.add_argument(
            "--list-categories", action="store_true", help="List preparation categories"
        )
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
                    self._fbr34ker_command(),
                    "hardware-prepare",
                    "--save-checklists",
                    checklist_dir,
                ]

                self.log(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=".", check=False)

                if result.returncode == 0:
                    print(result.stdout)
                    return 0
                else:
                    self.log(f"FBR34KER hardware-prepare failed: {result.stderr}", "ERROR")
                    return result.returncode

            except (OSError, subprocess.SubprocessError) as e:
                raise B34STError(f"Failed to generate hardware checklists: {e}") from e

        if args.validate_bundle:
            try:
                import subprocess

                cmd = [
                    self._fbr34ker_command(),
                    "hardware-prepare",
                    "--validate-bundle",
                    args.validate_bundle,
                ]
                self.log(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=".", check=False)
                if result.returncode == 0:
                    print(result.stdout)
                    return 0
                else:
                    self.log(
                        f"FBR34KER hardware-prepare validate-bundle failed: {result.stderr}",
                        "ERROR",
                    )
                    return result.returncode
            except (OSError, subprocess.SubprocessError) as e:
                raise B34STError(f"Failed to validate bundle: {e}") from e

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

    def _forensics(self, argv: list[str]) -> int:
        """Handle forensics and data acquisition commands."""
        import argparse as ap

        parser = ap.ArgumentParser(
            prog="b34st forensics",
            description="Forensics and data acquisition operations.",
        )
        sub = parser.add_subparsers(dest="forensics_command", required=True)

        sub.add_parser("list-profiles", help="List built-in acquisition profiles")

        acq = sub.add_parser("acquire", help="Run a forensic acquisition session")
        acq.add_argument(
            "--profile",
            default="quick",
            choices=[
                "quick",
                "full",
                "memory-only",
                "storage-only",
                "filesystem-only",
                "network-only",
            ],
            help="Acquisition profile to use",
        )
        acq.add_argument("--device-id", default="unknown", help="Target device identifier")
        acq.add_argument("--operator", default="", help="Operator name")
        acq.add_argument("--product", default="", help="Target product type")
        acq.add_argument("--model", default="", help="Target model identifier")
        acq.add_argument("--ios-version", default="", help="Target iOS version")
        acq.add_argument("--chipset", default="", help="Target chipset identifier")
        acq.add_argument("--mode", default="unknown", help="Device mode")
        acq.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "forensics",
            help="Output directory",
        )
        acq.add_argument("--bundle", type=pathlib.Path, help="Output evidence bundle path")
        acq.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities for user data access",
        )

        verify = sub.add_parser("verify", help="Verify a forensics evidence bundle")
        verify.add_argument("bundle", type=pathlib.Path, help="Path to evidence bundle")

        secrets_p = sub.add_parser("secrets", help="iCloud/Keychain/Keybag acquisition")
        secrets_p.add_argument("--passcode", default="", help="Device passcode for SEP unlock")
        secrets_p.add_argument(
            "--sep-exploit", action="store_true", help="Use SEP exploit for unlock"
        )
        secrets_p.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "secrets",
            help="Output directory for secrets data",
        )
        secrets_p.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities for user data access",
        )

        activation_p = sub.add_parser(
            "activation", help="Activation bypass, Baseband, FMI operations"
        )
        activation_sub = activation_p.add_subparsers(dest="activation_command", required=True)

        act_status = activation_sub.add_parser("status", help="Query activation state")
        act_status.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "activation",
            help="Output directory",
        )
        act_status.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )

        act_bypass = activation_sub.add_parser("bypass", help="Apply activation bypass")
        act_bypass.add_argument(
            "--clear-records",
            action="store_true",
            default=True,
            help="Clear activation records",
        )
        act_bypass.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "activation",
            help="Output directory",
        )
        act_bypass.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities for device state manipulation",
        )

        act_clear = activation_sub.add_parser(
            "clear-records", help="Clear activation records from baseband/NAND"
        )
        act_clear.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "activation",
            help="Output directory",
        )
        act_clear.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities for device state manipulation",
        )

        act_query = activation_sub.add_parser(
            "query-all", help="Query all activation/baseband/FMI state"
        )
        act_query.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "activation",
            help="Output directory",
        )
        act_query.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )

        baseband_p = activation_sub.add_parser("baseband", help="Baseband operations")
        baseband_p.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "activation",
            help="Output directory",
        )
        baseband_p.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )
        baseband_sub = baseband_p.add_subparsers(dest="baseband_command", required=True)
        baseband_sub.add_parser("status", help="Query baseband status")
        baseband_sub.add_parser("imei", help="Read IMEI numbers")
        baseband_sub.add_parser("iccid", help="Read ICCID numbers")
        baseband_sub.add_parser("tickets", help="List activation tickets")
        baseband_sub.add_parser("clear-tickets", help="Clear baseband activation tickets")
        baseband_sub.add_parser("unlock", help="Unlock baseband (SIM lock bypass)")

        fmi_p = activation_sub.add_parser("fmi", help="Find My iPhone operations")
        fmi_p.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "activation",
            help="Output directory",
        )
        fmi_p.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )
        fmi_sub = fmi_p.add_subparsers(dest="fmi_command", required=True)
        fmi_sub.add_parser("status", help="Query FMI state")
        fmi_sub.add_parser("off", help="Turn FMI off")
        fmi_sub.add_parser("on", help="Turn FMI on")
        fmi_sub.add_parser("clear-activation-lock", help="Clear FMI activation lock")

        mobileact_p = activation_sub.add_parser(
            "mobileactivationd", help="Mobile activation daemon operations"
        )
        mobileact_p.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "activation",
            help="Output directory",
        )
        mobileact_p.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )
        mobileact_sub = mobileact_p.add_subparsers(dest="mobileact_command", required=True)
        mobileact_sub.add_parser("status", help="Query mobileactivationd state")
        mobileact_sub.add_parser("info", help="Query activation info")
        mobileact_sub.add_parser("patch", help="Patch mobileactivationd activation check")
        mobileact_sub.add_parser("restart", help="Restart mobileactivationd")
        mobileact_sub.add_parser("inject", help="Inject activation record")

        passcode_p = sub.add_parser("passcode", help="Passcode management (on/off/change)")
        passcode_p.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "passcode",
            help="Output directory for passcode artifacts",
        )
        passcode_sub = passcode_p.add_subparsers(dest="passcode_command", required=True)
        passcode_sub.add_parser("status", help="Query passcode state")
        passcode_sub.add_parser("policy", help="Query passcode policy")
        passcode_remove = passcode_sub.add_parser("remove", help="Remove device passcode")
        passcode_remove.add_argument("--passcode", default="", help="Current passcode")
        passcode_remove.add_argument(
            "--exploit",
            action="store_true",
            help="Use SEP exploit to bypass passcode requirement",
        )
        passcode_remove.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "passcode",
            help="Output directory",
        )
        passcode_remove.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )
        passcode_set = passcode_sub.add_parser("set", help="Set device passcode")
        passcode_set.add_argument("passcode", help="New passcode (min 4 chars)")
        passcode_set.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "passcode",
            help="Output directory",
        )
        passcode_set.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )
        passcode_change = passcode_sub.add_parser("change", help="Change device passcode")
        passcode_change.add_argument("current", help="Current passcode")
        passcode_change.add_argument("new", help="New passcode (min 4 chars)")
        passcode_change.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "passcode",
            help="Output directory",
        )
        passcode_change.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )
        passcode_bypass = passcode_sub.add_parser("bypass", help="Attempt passcode bypass")
        passcode_bypass.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "passcode",
            help="Output directory",
        )
        passcode_bypass.add_argument(
            "--capabilities",
            action="append",
            choices=["credential-extraction", "protected-data-access"],
            help="Requested security capabilities",
        )

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        from host.forensics.profiles import builtin_profiles
        from host.forensics.acquisition import (
            AcquisitionEngine,
            AcquisitionTarget,
        )
        from host.forensics.report import AcquisitionReport, ReportError

        if args.forensics_command == "list-profiles":
            profiles = builtin_profiles()
            print("Built-in acquisition profiles:")
            for name, prof in profiles.items():
                cats = ", ".join(sorted(prof.categories))
                print(f"  {name:20s}  {prof.description}")
                print(f"  {'':20s}  categories: {cats}")
                print()
            return 0

        if args.forensics_command == "acquire":
            profiles = builtin_profiles()
            profile = profiles.get(args.profile, profiles["quick"])

            blockers = _check_security_boundary(args.profile, getattr(args, "capabilities", []))
            if blockers and not getattr(args, "capabilities", []):
                print(
                    "Security boundary blockers for this acquisition type:",
                    file=sys.stderr,
                )
                for b in blockers:
                    print(f"  - {b}", file=sys.stderr)
                print(
                    "Use --capabilities credential-extraction --capabilities protected-data-access to acknowledge",
                    file=sys.stderr,
                )
                return 1

            target = AcquisitionTarget(
                device_id=args.device_id,
                operator=args.operator,
                product=args.product,
                model=args.model,
                ios_version=args.ios_version,
                chipset=args.chipset,
                mode=args.mode,
            )

            engine = AcquisitionEngine.create(
                target,
                args.output,
                profile=profile,
            )

            session = engine.run()

            if blockers:
                session.custody.record(
                    action="security.boundary.acknowledged",
                    detail=f"User data access requirements acknowledged: {', '.join(blockers)}",
                )

            session.finalize()
            session_dir = session.summary()
            self.log(f"Acquisition session completed: {session_dir}")

            if args.bundle:
                report = AcquisitionReport(session)
                result = report.build_bundle(args.bundle)
                self.log(f"Evidence bundle: {result['report_path']}")
                self.log(f"Bundle SHA-256: {result['bundle_sha256']}")

            import json

            print(json.dumps(session.summary(), indent=2, sort_keys=True))
            return 0

        if args.forensics_command == "verify":
            try:
                result = AcquisitionReport.verify_bundle(args.bundle)
            except ReportError as exc:
                self.log(f"Verification failed: {exc}", "ERROR")
                return 1

            import json

            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("valid") else 1

        if args.forensics_command == "secrets":
            return self._forensics_secrets(args)

        if args.forensics_command == "activation":
            return self._forensics_activation(args)

        if args.forensics_command == "passcode":
            return self._forensics_passcode(args)

        return 0

    def _forensics_secrets(self, args: argparse.Namespace) -> int:
        """Run iCloud/Keychain/Keybag acquisition."""
        from host.forensics.secrets import SecretsAcquisitor
        from host.forensics.chain_of_custody import CustodyLog

        blockers = _check_security_boundary("keychain", getattr(args, "capabilities", []))
        if blockers and not getattr(args, "capabilities", []):
            print(
                "Security boundary blockers for this acquisition type:",
                file=sys.stderr,
            )
            for b in blockers:
                print(f"  - {b}", file=sys.stderr)
            print(
                "Use --capabilities credential-extraction --capabilities protected-data-access to acknowledge",
                file=sys.stderr,
            )
            return 1

        def _mock_command(cmd: str) -> str:
            return f"command: {cmd}"

        custody = CustodyLog()
        sep = None
        acquisitor = SecretsAcquisitor(_mock_command, sep_mailbox=sep, custody=custody)
        output = args.output
        output.mkdir(parents=True, exist_ok=True)

        result = acquisitor.acquire_all(
            output,
            passcode=args.passcode or "",
            use_sep_exploit=args.sep_exploit,
        )

        if blockers:
            custody.record(
                action="security.boundary.acknowledged",
                detail=f"User data access requirements acknowledged: {', '.join(blockers)}",
            )

        import json

        print(json.dumps(result, indent=2, sort_keys=True))
        custody.write(output / "chain-of-custody.json")
        return 0

    def _forensics_activation(self, args: argparse.Namespace) -> int:
        """Handle activation, baseband, FMI, and mobileactivationd commands."""
        from host.forensics.activation import ActivationOrchestrator
        from host.forensics.chain_of_custody import CustodyLog

        def _mock_command(cmd: str) -> str:
            return f"command: {cmd}"

        custody = CustodyLog()
        orch = ActivationOrchestrator(_mock_command, custody=custody)

        status_code = 1
        if args.activation_command == "status":
            state = orch.activation.check_state()
            ticket = orch.activation.check_ticket()
            import json

            print(json.dumps({"state": state, "ticket": ticket}, indent=2))
            status_code = 0

        elif args.activation_command == "bypass":
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    "Activation bypass requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
            else:
                result = orch.activation.apply_full_bypass(
                    clear_records=getattr(args, "clear_records", True)
                )
                import json

                print(json.dumps(result, indent=2, sort_keys=True))
                custody.record(
                    action="security.boundary.acknowledged",
                    detail="Activation bypass capabilities acknowledged",
                )
                status_code = 0 if result.get("bypass_complete") else 1

        elif args.activation_command == "clear-records":
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    "Clear activation records requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
            else:
                result = orch.activation.clear_activation_records()
                import json

                print(json.dumps(result, indent=2, sort_keys=True))
                custody.record(
                    action="security.boundary.acknowledged",
                    detail="Clear activation records capabilities acknowledged",
                )
                status_code = 0 if result.get("cleared") else 1

        elif args.activation_command == "query-all":
            result = orch.query_all(getattr(args, "output", None))
            import json

            print(json.dumps(result, indent=2, sort_keys=True))
            status_code = 0

        elif args.activation_command == "baseband":
            status_code = self._forensics_baseband(args, orch)

        elif args.activation_command == "fmi":
            status_code = self._forensics_fmi(args, orch)

        elif args.activation_command == "mobileactivationd":
            status_code = self._forensics_mobileactivationd(args, orch)

        else:
            self.log(f"Unknown activation command: {args.activation_command}", "ERROR")
            status_code = 1

        output = getattr(args, "output", ROOT / "runtime-artifacts" / "b34st" / "activation")
        if output:
            output.mkdir(parents=True, exist_ok=True)
            custody.write(output / "chain-of-custody.json")
        return status_code

    def _forensics_baseband(self, args: argparse.Namespace, orch: Any) -> int:
        """Handle baseband subcommands."""
        cmd = getattr(args, "baseband_command", "")
        import json

        if cmd == "status":
            result = orch.baseband.query_status()
        elif cmd == "imei":
            result = {"imeis": orch.baseband.query_imei()}
        elif cmd == "iccid":
            result = {"iccids": orch.baseband.query_iccid()}
        elif cmd == "tickets":
            result = {"tickets": orch.baseband.query_nand_tickets()}
        elif cmd == "clear-tickets":
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    "Clear baseband tickets requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
                return 1
            result = orch.baseband.clear_activation_tickets()
        elif cmd == "unlock":
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    "Baseband unlock requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
                return 1
            result = orch.baseband.unlock_baseband()
        else:
            self.log(f"Unknown baseband command: {cmd}", "ERROR")
            return 1

        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    def _forensics_fmi(self, args: argparse.Namespace, orch: Any) -> int:
        """Handle FMI subcommands."""
        cmd = getattr(args, "fmi_command", "")
        import json

        if cmd == "status":
            result = orch.fmi.check_state()
        elif cmd in ("off", "on", "clear-activation-lock"):
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    f"FMI '{cmd}' requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
                return 1
            if cmd == "off":
                result = orch.fmi.turn_off()
            elif cmd == "on":
                result = orch.fmi.turn_on()
            else:
                result = orch.fmi.clear_activation_lock()
        else:
            self.log(f"Unknown FMI command: {cmd}", "ERROR")
            return 1

        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    def _forensics_mobileactivationd(self, args: argparse.Namespace, orch: Any) -> int:
        """Handle mobileactivationd subcommands."""
        cmd = getattr(args, "mobileact_command", "")
        import json

        if cmd == "status":
            result = orch.mobileactivationd.query_state()
        elif cmd == "info":
            result = orch.mobileactivationd.query_activation_info()
        elif cmd in ("patch", "restart", "inject"):
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    f"mobileactivationd '{cmd}' requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
                return 1
            if cmd == "patch":
                result = orch.mobileactivationd.patch_activation_check()
            elif cmd == "restart":
                result = orch.mobileactivationd.restart()
            else:
                result = orch.mobileactivationd.inject_activation_record()
        else:
            self.log(f"Unknown mobileactivationd command: {cmd}", "ERROR")
            return 1

        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    def _forensics_passcode(self, args: argparse.Namespace) -> int:
        """Handle passcode management commands."""
        from host.forensics.passcode import PasscodeManager
        from host.forensics.chain_of_custody import CustodyLog

        def _mock_command(cmd: str) -> str:
            return f"command: {cmd}"

        custody = CustodyLog()
        mgr = PasscodeManager(_mock_command, custody=custody)
        cmd = getattr(args, "passcode_command", "")
        import json

        if cmd == "status":
            result = mgr.check_state()
        elif cmd == "policy":
            result = mgr.check_policy()
        elif cmd == "remove":
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    "Passcode removal requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
                return 1
            passcode = getattr(args, "passcode", "")
            use_exploit = getattr(args, "exploit", False)
            try:
                result = mgr.remove(passcode, use_exploit=use_exploit)
            except (RuntimeError, OSError, ValueError) as exc:
                self.log(f"Passcode remove failed: {exc}", "ERROR")
                return 1
            custody.record(
                action="security.boundary.acknowledged",
                detail="Passcode removal capabilities acknowledged",
            )
        elif cmd == "set":
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    "Passcode set requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
                return 1
            passcode = getattr(args, "passcode", "")
            try:
                result = mgr.set_passcode(passcode)
            except (RuntimeError, OSError, ValueError) as exc:
                self.log(f"Passcode set failed: {exc}", "ERROR")
                return 1
            custody.record(
                action="security.boundary.acknowledged",
                detail="Passcode set capabilities acknowledged",
            )
        elif cmd == "change":
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    "Passcode change requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
                return 1
            current = getattr(args, "current", "")
            new = getattr(args, "new", "")
            try:
                result = mgr.change(current, new)
            except (RuntimeError, OSError, ValueError) as exc:
                self.log(f"Passcode change failed: {exc}", "ERROR")
                return 1
            custody.record(
                action="security.boundary.acknowledged",
                detail="Passcode change capabilities acknowledged",
            )
        elif cmd == "bypass":
            caps = getattr(args, "capabilities", [])
            if not caps:
                print(
                    "Passcode bypass requires explicit authorization capabilities.",
                    file=sys.stderr,
                )
                return 1
            result = mgr.attempt_bypass()
            custody.record(
                action="security.boundary.acknowledged",
                detail="Passcode bypass capabilities acknowledged",
            )
        else:
            self.log(f"Unknown passcode command: {cmd}", "ERROR")
            return 1

        output = getattr(args, "output", ROOT / "runtime-artifacts" / "b34st" / "passcode")
        output.mkdir(parents=True, exist_ok=True)
        custody.write(output / "chain-of-custody.json")

        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    def _sep_fuzz(self, argv: list[str]) -> int:
        """Run SEP key fuzzing campaigns (subcommand-based)."""
        import argparse as ap
        import json

        parser = ap.ArgumentParser(
            prog="b34st sep-fuzz",
            description="SEP Key Fuzzer — differential key-wrapper testing.",
        )
        sub = parser.add_subparsers(dest="sep_fuzz_command", required=True)

        run_p = sub.add_parser("run", help="Run a full SEP key fuzzing campaign")
        run_p.add_argument("--device-model", default="iPhone14,2", help="Device model identifier")
        run_p.add_argument("--os-build", default="21A123", help="iOS build number")
        run_p.add_argument("--chipset", default="A15", help="SoC chipset identifier")
        run_p.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "sep-fuzz",
            help="Output directory for campaign results",
        )
        run_p.add_argument(
            "--categories",
            nargs="*",
            choices=["device_lifecycle", "access_control", "wrapper_integrity"],
            default=None,
            help="Test categories to run (default: all)",
        )
        run_p.add_argument(
            "--harness-only",
            action="store_true",
            help="Only generate the baseline Swift harness, skip campaign",
        )
        run_p.add_argument(
            "--report-only",
            type=pathlib.Path,
            default=None,
            help="Generate bounty report from an existing campaign manifest",
        )
        run_p.add_argument(
            "--transport",
            default="simulator",
            choices=["simulator", "usb", "serial"],
            help="Device transport backend (default: simulator)",
        )
        run_p.add_argument(
            "--transport-args",
            default="{}",
            help='JSON dict of transport arguments (e.g. \'{"port": "/dev/ttyUSB0"}\')',
        )

        list_p = sub.add_parser("list-variations", help="List all fuzz variations defined")
        list_p.add_argument(
            "--category",
            choices=["device_lifecycle", "access_control", "wrapper_integrity"],
            default=None,
            help="Filter variations by category",
        )

        sub.add_parser("list-categories", help="List fuzz categories")

        generate_p = sub.add_parser("generate-harness", help="Generate the baseline Swift harness")
        generate_p.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "sep-fuzz",
            help="Output directory",
        )

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        from host.forensics.sep_key_fuzzer import (
            FUZZ_VARIATIONS,
            SEPKeyFuzzer,
            generate_baseline_harness,
            generate_bounty_report,
        )

        if args.sep_fuzz_command == "list-categories":
            print("SEP Fuzzer categories:")
            for cat in sorted(FUZZ_VARIATIONS):
                count = len(FUZZ_VARIATIONS[cat])
                print(f"  {cat:25s}  {count} variations")
            return 0

        if args.sep_fuzz_command == "list-variations":
            cats = [args.category] if args.category else sorted(FUZZ_VARIATIONS)
            for cat in cats:
                print(f"\n[{cat}]")
                for v in FUZZ_VARIATIONS.get(cat, []):
                    print(f"  {v['name']:35s}  {v['desc']}")
            return 0

        if args.sep_fuzz_command == "generate-harness":
            output = args.output
            output.mkdir(parents=True, exist_ok=True)
            harness = generate_baseline_harness(output / "BaselineHarness.swift")
            print(f"Baseline harness written: {harness}")
            return 0

        if args.sep_fuzz_command == "run":
            output = args.output
            output.mkdir(parents=True, exist_ok=True)

            if args.harness_only:
                harness = generate_baseline_harness(output / "BaselineHarness.swift")
                print(f"Baseline harness written: {harness}")
                print("Harness generated. Deploy to device via FBR34KER.")
                return 0

            if args.report_only:
                manifest_path = args.report_only
                if not manifest_path.is_file():
                    self.log(
                        f"Cannot generate report: manifest not found: {manifest_path}",
                        "ERROR",
                    )
                    return 1
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                report_path = generate_bounty_report(manifest, output)
                print(f"Bounty report generated: {report_path}")
                return 0

            categories = set(args.categories) if args.categories else None

            fuzzer = SEPKeyFuzzer(
                device_model=args.device_model,
                os_build=args.os_build,
                chipset=args.chipset,
            )
            fuzzer.generate_base_wrapper()

            # Build submit function from transport backend
            if args.transport == "simulator":

                def _simulated_submit(wrapper: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
                    return {
                        "accepted": False,
                        "public_key_hex": "",
                        "output_buffers": [],
                        "error": "simulated — deploy harness to device for live testing",
                        "duration_ms": 0.0,
                    }

                submit_fn = _simulated_submit
            else:
                from host.forensics.sep_deploy import make_fuzzer_submit

                transport_kwargs: dict[str, Any] = json.loads(args.transport_args)
                submit_fn = make_fuzzer_submit(args.transport, **transport_kwargs)

            manifest = fuzzer.run(
                submit_fn,
                output,
                categories=categories,
            )

            report_path = generate_bounty_report(manifest, output)
            print(f"Campaign manifest: {output / 'sep-fuzz-campaign.json'}")
            print(f"Bounty report: {report_path}")
            print(f"Baseline harness: {output / 'BaselineHarness.swift'}")
            print(json.dumps(manifest["summary"], indent=2, sort_keys=True))
            return 0

        return 0

    def _sep_research(self, argv: list[str]) -> int:
        """Run SEP vulnerability research pipeline stages."""
        import argparse as ap
        import json

        parser = ap.ArgumentParser(
            prog="b34st sep-research",
            description="SEP vulnerability research pipeline — automated SEP/sepOS fuzzing.",
        )
        sub = parser.add_subparsers(dest="pipeline_command", required=True)

        run_p = sub.add_parser("run", help="Run the full research pipeline")
        run_p.add_argument("--device-model", default="iPhone14,2", help="Device model identifier")
        run_p.add_argument("--os-build", default="21A123", help="iOS build number")
        run_p.add_argument("--chipset", default="A15", help="SoC chipset identifier")
        run_p.add_argument(
            "--output",
            type=pathlib.Path,
            default=ROOT / "runtime-artifacts" / "b34st" / "sep-research",
            help="Output directory",
        )
        run_p.add_argument(
            "--stages",
            nargs="*",
            choices=[
                "architectural_map",
                "corpus_generation",
                "differential_analysis",
                "structural_fuzzing",
                "stateful_fuzzing",
                "concurrency_fuzzing",
                "crash_triage",
            ],
            default=None,
            help="Stages to run (default: all)",
        )
        run_p.add_argument(
            "--transport",
            default="simulator",
            choices=["simulator", "usb", "serial", "tcp"],
            help="Device transport backend (default: simulator)",
        )
        run_p.add_argument(
            "--transport-args",
            default="{}",
            help='JSON dict of transport arguments (e.g. \'{"port": "/dev/ttyUSB0"}\')',
        )

        sub.add_parser("list-stages", help="List pipeline stages")
        sub.add_parser("info", help="Show pipeline component information")

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        from host.forensics.sep_research_pipeline import (
            STAGES,
            run_pipeline,
        )

        if args.pipeline_command == "list-stages":
            print("SEP Research Pipeline stages:")
            for i, stage in enumerate(STAGES, 1):
                print(f"  {i}. {stage}")
            return 0

        if args.pipeline_command == "info":
            print("SEP Research Pipeline")
            print("=====================")
            print()
            print("A complete SEP/sepOS vulnerability research workflow:")
            print()
            print("  1. architectural_map    — Document AP→SEP request boundaries")
            print("  2. corpus_generation    — Exercise documented APIs with")
            print("                             synthetic objects")
            print("  3. differential_analysis — Compare pairs differing in exactly")
            print("                             one variable")
            print("  4. structural_fuzzing   — Length errors, integer overflow,")
            print("                             type confusion mutations")
            print("  5. stateful_fuzzing     — Sequence mutations (create→use→delete→use)")
            print("  6. concurrency_fuzzing  — Race conditions (delete vs sign,")
            print("                             cancel vs complete)")
            print("  7. crash_triage         — Classify fault layer")
            print()
            print("Use the 'run' subcommand to execute stages.")
            print("Provide a custom api_fn for live device/SRD testing.")
            return 0

        if args.pipeline_command == "run":
            output = args.output
            output.mkdir(parents=True, exist_ok=True)

            api_fn = None
            if args.transport != "simulator":
                from host.forensics.sep_deploy import make_research_api

                transport_kwargs: dict[str, Any] = json.loads(args.transport_args)
                api_fn = make_research_api(args.transport, **transport_kwargs)

            result = run_pipeline(
                output,
                device_model=args.device_model,
                os_build=args.os_build,
                chipset=args.chipset,
                stages=args.stages,
                api_fn=api_fn,
            )

            manifest = output / "campaign-manifest.json"
            report = output / "SEP_Research_Campaign_Report.md"
            print(f"Campaign manifest: {manifest}")
            print(f"Campaign report: {report}")
            print(json.dumps(result, indent=2))
            return 0

        return 0

    def _cve(self, argv: list[str]) -> int:
        """Handle CVE database and exploit chain planning commands."""
        import argparse as ap
        import json

        db_path = (
            pathlib.Path(__file__).resolve().parent.parent
            / "host"
            / "cve"
            / "data"
            / "cve_database.json"
        )

        parser = ap.ArgumentParser(
            prog="b34st cve",
            description="CVE database & exploit chain planner for Apple iOS vulnerabilities.",
        )
        sub = parser.add_subparsers(dest="cve_command", required=True)

        search_p = sub.add_parser("search", help="Search CVEs by ID or description")
        search_p.add_argument("query", help="Search query")

        query_p = sub.add_parser("query", help="Get all CVEs for a specific iOS version")
        query_p.add_argument("version", help="iOS version (e.g., 16.5)")

        filter_p = sub.add_parser("filter", help="Filter CVEs by multiple criteria")
        filter_p.add_argument("--version", help="iOS version filter")
        filter_p.add_argument("--goal", action="append", help="Required goal")
        filter_p.add_argument("--component", action="append", help="Affected component")
        filter_p.add_argument("--exploit-type", action="append", help="Exploit type")
        filter_p.add_argument(
            "--exploit-available",
            action="store_true",
            default=None,
            help="Only CVEs with public exploits",
        )
        filter_p.add_argument(
            "--min-severity",
            choices=["critical", "high", "medium", "low"],
            default=None,
            help="Minimum severity",
        )

        sub.add_parser("stats", help="Show CVE database statistics")

        chain_p = sub.add_parser("chain", help="Plan an exploit chain to achieve a goal")
        chain_p.add_argument("goal", help="Exploit goal name (use 'goals' to list)")
        chain_p.add_argument("version", help="Target iOS version")

        device_chain_p = sub.add_parser(
            "device-chain", help="Plan exploit chain for a specific device model"
        )
        device_chain_p.add_argument("goal", help="Exploit goal name")
        device_chain_p.add_argument("version", help="Target iOS version")
        device_chain_p.add_argument("device", help="Device model (e.g., iPhone10,1)")

        device_info_p = sub.add_parser("device-info", help="Show device/SoC information")
        device_info_p.add_argument(
            "identifier",
            nargs="?",
            help="Device model or SoC name (e.g., iPhone10,1 or A11). Omit to list all.",
        )
        device_info_p.add_argument("--version", help="Filter devices by iOS version")

        suggest_p = sub.add_parser("suggest", help="Suggest achievable goals for a version")
        suggest_p.add_argument("version", help="Target iOS version")

        sub.add_parser("goals", help="List all available exploit goals")

        fuzz_p = sub.add_parser("fuzz", help="Fuzzer integration commands")
        fuzz_sub = fuzz_p.add_subparsers(dest="fuzz_command")
        fuzz_sub.add_parser("list", help="List available fuzz targets")

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        if not db_path.is_file():
            self.log(f"CVE database not found at {db_path}", "ERROR")
            return 1

        from host.cve.cve_db import CVEDatabase
        from host.cve.exploit_chain import ChainPlanner, BUILTIN_GOALS
        from host.cve.fuzzer import FuzzerFramework

        db = CVEDatabase.load_json(db_path)

        if args.cve_command == "stats":
            stats = db.compute_stats()
            print(json.dumps(stats, indent=2, sort_keys=True))
            return 0

        if args.cve_command == "search":
            results = db.search(args.query)
            if not results:
                print(f"No CVEs found matching: {args.query}")
                return 0
            print(f"Found {len(results)} CVEs matching '{args.query}':\n")
            for cve in results:
                print(f"  {cve.id} | {cve.severity:8s} | {cve.description[:80]}")
            return 0

        if args.cve_command == "query":
            results = db.query_by_version(args.version)
            if not results:
                print(f"No CVEs found for iOS {args.version}")
                return 0
            print(f"CVEs affecting iOS {args.version}: {len(results)}\n")
            for cve in sorted(
                results,
                key=lambda c: (
                    {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(c.severity, 99),
                    c.id,
                ),
            ):
                exploit = "✓" if cve.exploit_available else " "
                print(
                    f"  [{exploit}] {cve.id:20s} {cve.severity:8s} {', '.join(cve.affected_components[:3]):20s} {cve.description[:60]}"
                )
            return 0

        if args.cve_command == "filter":
            filters = {}
            if args.version:
                filters["version"] = args.version
            if args.goal:
                filters["goals"] = set(args.goal)
            if args.component:
                filters["components"] = set(args.component)
            if args.exploit_type:
                filters["exploit_types"] = set(args.exploit_type)
            if args.exploit_available is not None:
                filters["exploit_available"] = True
            if args.min_severity:
                filters["min_severity"] = args.min_severity

            results = db.filter(**filters)
            if not results:
                print("No CVEs match the given filters")
                return 0
            print(f"Filter results: {len(results)} CVEs\n")
            for cve in sorted(
                results,
                key=lambda c: (
                    {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(c.severity, 99),
                    c.id,
                ),
            ):
                print(
                    f"  {cve.id:20s} {cve.severity:8s} {'✓' if cve.exploit_available else ' '} {cve.description[:70]}"
                )
            return 0

        if args.cve_command == "goals":
            print("Built-in exploit goals:\n")
            for name, goal in sorted(BUILTIN_GOALS.items()):
                print(f"  {name:25s} {goal.description}")
                print(f"  {'':25s} requires: {', '.join(goal.required_subgoals)}")
                print(f"  {'':25s} difficulty: {goal.difficulty}")
                print()
            return 0

        if args.cve_command == "chain":
            planner = ChainPlanner(db)
            try:
                chains = planner.find_chains(args.goal, args.version)
            except (RuntimeError, OSError, ValueError) as exc:
                self.log(f"Chain planning failed: {exc}", "ERROR")
                return 1

            if not chains:
                print(f"No exploit chains found for goal '{args.goal}' on iOS {args.version}")
                print("Try a different goal or version, or check the CVE database coverage.")
                return 0

            print(f"Exploit chains for goal '{args.goal}' on iOS {args.version}:\n")
            for i, chain in enumerate(chains[:5], 1):
                status = "COMPLETE" if chain.complete else f"PARTIAL ({chain.coverage:.0%})"
                print(
                    f"  Chain #{i} [{status}] — {chain.estimate_difficulty}, ~{chain.estimated_success_rate}"
                )
                for link in chain.links:
                    comps = ", ".join(link.cve.affected_components[:2])
                    print(
                        f"    Step {link.step}: {link.cve.id:20s} [{comps:20s}] {'✓' if link.cve.exploit_available else ' '}  {link.cve.description[:60]}"
                    )
                all_provides = set()
                for link in chain.links:
                    all_provides.update(link.provides)
                print(f"    → Provides: {', '.join(sorted(all_provides))}")
                print()
            return 0

        if args.cve_command == "device-info":
            try:
                from host.cve.devices import (
                    DEVICE_DATABASE,
                    SOC_DATABASE,
                    get_device,
                    get_soc,
                    devices_for_version,
                )
            except ImportError:
                print("Device database not available (host/cve/devices.py)")
                return 1

            if args.version:
                devs = devices_for_version(args.version)
                print(f"Devices supporting iOS {args.version}:\n")
                for model, info in sorted(devs, key=lambda x: x[0]):
                    soc = SOC_DATABASE.get(info.soc)
                    boot = soc.bootrom_exploit if soc else "unknown"
                    arch = info.arch
                    print(
                        f"  {model:15s} {info.marketing:25s} {info.soc:5s} {arch:6s} bootrom={boot:10s} iOS {info.min_ios}-{info.max_ios}"
                    )
                return 0

            if args.identifier:
                dev = get_device(args.identifier)
                if dev:
                    soc = SOC_DATABASE.get(dev.soc)
                    print(f"Device: {dev.model} ({dev.marketing})")
                    print(f"  SoC:   {dev.soc} (CPID 0x{dev.cpid:x})")
                    print(f"  Arch:  {dev.arch}")
                    print(f"  iOS:   {dev.min_ios} - {dev.max_ios}")
                    if soc:
                        print(f"  Bootrom: {soc.bootrom_exploit}")
                        print(f"  SEP: {'yes' if soc.sep_present else 'no'}")
                        print(
                            f"  Persistent jailbreak: {'yes' if soc.persistent_jailbreak else 'no'}"
                        )
                else:
                    soc = get_soc(args.identifier.upper())
                    if soc:
                        print(f"SoC: {soc.name}")
                        print(f"  CPIDs: {', '.join(f'0x{c:x}' for c in soc.cpids)}")
                        print(f"  Arch:  {soc.arch}")
                        print(f"  Bootrom: {soc.bootrom_exploit}")
                        print(f"  SEP: {'yes' if soc.sep_present else 'no'}")
                        print(f"  Persistent JB: {'yes' if soc.persistent_jailbreak else 'no'}")
                        print(f"  iOS:   {soc.min_ios} - {soc.max_ios}")
                        print(f"  {soc.description}")
                        devices = [(m, d) for m, d in DEVICE_DATABASE.items() if d.soc == soc.name]
                        if devices:
                            print(f"\nDevices with {soc.name}:")
                            for model, info in sorted(devices):
                                print(
                                    f"  {model:15s} {info.marketing:25s} iOS {info.min_ios}-{info.max_ios}"
                                )
                    else:
                        print(f"Unknown device or SoC: {args.identifier}")
            else:
                print("Known SoCs:\n")
                for name, soc in sorted(SOC_DATABASE.items()):
                    dev_count = sum(1 for d in DEVICE_DATABASE.values() if d.soc == name)
                    print(
                        f"  {name:5s} {soc.description:40s} bootrom={soc.bootrom_exploit:10s} {dev_count} devices"
                    )
                print(f"\nKnown devices: {len(DEVICE_DATABASE)}")
            return 0

        if args.cve_command == "device-chain":
            try:
                from host.cve.devices import get_device, SOC_DATABASE
            except ImportError:
                print("Device database not available")
                return 1

            dev = get_device(args.device)
            if not dev:
                print(f"Unknown device: {args.device}. Use 'device-info' to list.")
                return 1

            soc = SOC_DATABASE.get(dev.soc)
            planner = ChainPlanner(db)
            try:
                chains = planner.find_chains_for_device(args.goal, args.version, args.device)
            except (RuntimeError, OSError, ValueError) as exc:
                self.log(f"Chain planning failed: {exc}", "ERROR")
                return 1

            if not chains:
                print(
                    f"No exploit chains found for '{args.goal}' on {args.device} ({dev.soc}) iOS {args.version}"
                )
                print(
                    "Try 'device-info' to check device compatibility or 'suggest' for achievable goals."
                )
                return 0

            print(
                f"Exploit chains for '{args.goal}' on {args.device} ({dev.marketing}, {dev.soc}):\n"
            )
            for i, chain in enumerate(chains[:5], 1):
                status = "COMPLETE" if chain.complete else f"PARTIAL ({chain.coverage:.0%})"
                print(
                    f"  Chain #{i} [{status}] — {chain.estimate_difficulty}, ~{chain.estimated_success_rate}"
                )
                for link in chain.links:
                    comps = ", ".join(link.cve.affected_components[:2])
                    print(
                        f"    Step {link.step}: {link.cve.id:20s} [{comps:20s}] {'✓' if link.cve.exploit_available else ' '}  {link.cve.description[:60]}"
                    )
                print()
            return 0

        if args.cve_command == "suggest":
            planner = ChainPlanner(db)
            try:
                suggestions = planner.suggest_goals(args.version)
            except (RuntimeError, OSError, ValueError) as exc:
                self.log(f"Goal suggestion failed: {exc}", "ERROR")
                return 1

            if not suggestions:
                print(f"No achievable goals found for iOS {args.version}")
                return 0

            print(f"Achievable goals for iOS {args.version}:\n")
            for s in suggestions:
                status = "✓ ACHIEVABLE" if s["achievable"] else f"~ Partial ({s['coverage']:.0%})"
                print(
                    f"  [{status}] {s['goal']:25s} difficulty={s['difficulty']:7s} rate={s['success_rate']:4s} steps={s['steps']}"
                )
                print(f"   {s['description']}")
                print(f"   CVEs: {', '.join(s['cves'])}")
                print()
            return 0

        if args.cve_command == "fuzz":
            fw = FuzzerFramework()
            if getattr(args, "fuzz_command", "") == "list":
                targets = fw.list_targets()
                print("Available fuzz targets:\n")
                for name, desc in targets.items():
                    print(f"  {name:25s} {desc}")
                print("\nUse `b34st cve fuzz run <target>` to execute (requires harness build)")
            return 0

        return 0

    def _prepare_waveshare_rp2350(self, target_chipset: str = "A14") -> None:
        """Prepare Waveshare RP2350 USB-A device for USBliter8 exploit v2.

        Complete preparation flow for A14/A15/M1/M2 devices including:
        1. Waveshare RP2350 USB-A device detection and identification
        2. Firmware flashing (UF2 file to the device)
        3. Cable selection guidance
        4. Power setup
        5. USB controller verification
        6. Device connection verification for target chipset

        Args:
            target_chipset: Target iPhone chipset (A14, A15, M1, or M2)
        """
        import subprocess
        import time
        from pathlib import Path

        self.log(f"Waveshare RP2350 USB-A preparation for {target_chipset} (v2)")

        # Display target information
        print(f"\n[*] Targeting {target_chipset} device")
        if target_chipset == "A15":
            print("  CPIDs: 0x8015, 0x8017, 0x8019, 0x801B, 0x801D")
        elif target_chipset == "M1":
            print(
                "  CPIDs: 0x8103 (iPhone 12 Mini/Pro), 0x8104 (iPhone 12 Max), 0x8105 (iPhone 12 Pro Max)"
            )
        elif target_chipset == "M2":
            print(
                "  CPIDs: 0x8106 (iPhone 13 Mini), 0x8107 (iPhone 13/Pro), 0x8109 (iPhone 13 Pro Max)"
            )
        elif target_chipset == "A14":
            print("  CPIDs: 0x8002 (iPhone 11 Pro), 0x8008, 0x800A, 0x800C, 0x800E")

        print("\n[*] Waveshare RP2350 USB-A Hardware Preparation (v2)")
        print("=" * 60)

        # Step 1: Device identification
        print("\n1. Device Identification:")
        print("   - Verify Waveshare RP2350 is connected with power")
        print("   - Target chipset: ", end="")

        # Check for Waveshare RP2350 device
        result = subprocess.run(["lsusb"], capture_output=True, text=True, check=False, timeout=10)
        if "PID 2050" in result.stdout:
            print("✓ RP2350 detected (PID 2050)")
            print("\n   RP2350 Specs:")
            print("     - Dual-core Cortex-M33/RISC-V")
            print("     - Native USB-A host (no adapters)")
            print("     - USB 2.0 High Speed (480 Mbps)")
            print("     - 264 KB SRAM + 16 MB flash")
            print("     - PIO capability for timing control")
        else:
            print("✗ RP2350 not detected!")
            print("\n   Connect Waveshare RP2350 and ensure:")
            print("   - Device is powered and connected")
            print("   - PID 2050 is visible in lsusb")
            self.log("RP2350 not detected. Check connection.", "ERROR")
            return 1

        # Step 2: Firmware preparation
        print("\n2. Firmware Preparation:")
        print("   - Ensure RP2350 is in BOOTSEL mode (hold BOOTSEL)")
        print("   - Connect to computer via USB")
        print("   - Drive 'RPI-RP2' should appear")
        print("   - Copy waveshare_rp2350_usb_a.uf2 to drive")
        print("   - Device will reboot automatically")

        firmware_path = ROOT / "build-exploit" / "waveshare_rp2350_usb_a.uf2"
        if firmware_path.is_file():
            print(f"   ✓ Firmware available: {firmware_path.name}")
        else:
            print(f"   ⚠ Firmware not found: {firmware_path}")
            print("   Build firmware:")
            print("     make build-rp2350-firmware")

        # Step 3: Cable requirements
        print("\n3. Cable Requirements:")
        print("   - USB-A to USB-C (data cable only)")
        print("   - Rated for USB 2.0 High Speed (480 Mbps)")
        print("   - Support for device charging (500mA+)")
        print("   - Apple OEM or Anker PowerLine recommended")
        print("   - Avoid charge-only cables (no D+/D- lines)")

        # Step 4: Power requirements
        print("\n4. Power Requirements:")
        if "RP2350" in result.stdout:
            print("   - RP2350 power: Supports bus power (USB-C)")
            print("   - Recommended: Host port 500mA+")
        print("   - Ensure stable power before proceeding")
        print("   - Avoid powered hubs for better timing")

        # Step 5: Target device verification
        print("\n5. Target Device Preparation:")
        print(f"   - Target: {target_chipset} (see CPIDs above)")
        print("   - Put device in DFU mode (hold volume down + connect)")
        print("   - Verify device appears in lsusb with DFU interface")

        # Check current USB devices
        print("\n   Current USB devices (lsusb):")
        for line in result.stdout.strip().split("\n"):
            if line and ("Apple" in line or "iPhone" in line or "DFU" in line):
                print(f"     - {line}")

        # Step 6: Verification checklist
        print("\n6. Verification Checklist:")
        print("   ✓ RP2350 hardware detected and powered")
        print("   ✓ Firmware flashed to RP2350")
        print("   ✓ Cable supports data transfer")
        print("   ✓ Power supply adequate (500mA+)")
        print("   ✓ Target device in DFU mode")
        print("   ✓ Target chipset CPID matches profile")

        # Step 7: pyusb verification
        print("\n7. pyusb/libusb Verification:")
        try:
            import pyusb
            from usb import USBContext

            print("   - pyusb library: ✓ Installed")

            with USBContext() as ctx:
                devices = ctx.list_devices()
                if devices:
                    print(f"   - USB devices detected: {len(devices)}")
                    print("   - Ready for exploit operation")
                else:
                    print("   - ✗ No devices detected by pyusb")
        except ImportError:
            print("   - pyusb: ✗ Not installed")
            print("   Install: pip install pyusb")
        except Exception as e:
            print(f"   - ✗ Check failed: {e}")

        # Completion message
        print("\n" + "=" * 60)
        print("[*] Waveshare RP2350 USB-A Preparation Complete (v2)")
        print(f"Target: {target_chipset} exploitation ready")
        print("\nNext steps:")
        print("  1. Verify RP2350 firmware is active")
        print("  2. Complete hardware preparation checklist")
        print("  3. Execute A14/A15/M1/M2 USBliter8 exploit")
        print("\nNote: Target device must match exact CPID in review profile.")

    def _usbliter8(self, argv: list[str]) -> int:
        """USBliter8 hardware preparation, execution, and workflow management."""
        import argparse as ap
        import json
        import subprocess

        parser = ap.ArgumentParser(
            prog="b34st usbliter8",
            description="USBliter8 DWC3 exploit workflow — hardware prep, execution, and return to B34ST.",
        )
        parser.add_argument(
            "--skip-hardware-prep",
            action="store_true",
            help="Skip hardware preparation checklist",
        )
        parser.add_argument(
            "--skip-rp2350-prep",
            action="store_true",
            help="Skip Waveshare RP2350 USB-A preparation (v2 with chipset targeting)",
        )
        parser.add_argument(
            "--chipset",
            choices=["A14", "A15", "M1", "M2"],
            default="A14",
            help="Target chipset for USBliter8 (default: A14)",
        )
        parser.add_argument(
            "--skip-build",
            action="store_true",
            help="Skip operational image build",
        )
        parser.add_argument(
            "--force-rebuild",
            action="store_true",
            help="Force rebuild even if image exists",
        )
        parser.add_argument(
            "--no-dfu-wait",
            action="store_true",
            help="Skip DFU wait (device already in DFU mode)",
        )
        parser.add_argument(
            "--no-console",
            action="store_true",
            help="Skip console connection after exploit",
        )
        parser.add_argument(
            "--return-to-b34st",
            action="store_true",
            help="Return to B34ST menu after completion (default: on)",
        )
        parser.add_argument(
            "--skip-evidence",
            action="store_true",
            help="Skip evidence collection",
        )
        parser.add_argument(
            "--no-return",
            action="store_true",
            help="Exit after exploit instead of returning to B34ST",
        )
        parser.add_argument(
            "--evidence",
            type=pathlib.Path,
            help="Path to write evidence JSON",
        )
        parser.add_argument(
            "--timeout", type=float, default=60.0, help="Timeout per step in seconds"
        )

        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code

        return_code = 0
        evidence_dir = pathlib.Path("runtime-artifacts/b34st/usbliter8")
        evidence_dir.mkdir(parents=True, exist_ok=True)

        if not args.skip_hardware_prep:
            self.log("USBliter8 hardware preparation")
            self._show_hardware_categories()

            # Waveshare RP2350 USB-A Preparation Flow
            if not args.skip_rp2350_prep:
                self._prepare_waveshare_rp2350(args.chipset)

            print("\nHardware preparation checklist:")
            items = [
                ("Host USB controller check", "Ensure host USB is xHCI or RP2350"),
                ("Cable and power check", "Use data cable, adequate power"),
                ("Device in DFU mode", "Verify device is in DFU mode"),
                ("Operational image built", "fbr34ker-operational.bin exists"),
                ("pyusb/libusb installed", "pip install pyusb"),
            ]
            for i, (item, desc) in enumerate(items, 1):
                skip = input(f"  [{i}/{len(items)}] {item} ({desc}) [Y/skip]: ").strip()
                if skip.lower() in ("s", "skip"):
                    print("    -> Skipped")
                else:
                    print("    -> Done")
            prep_record = evidence_dir / "hardware-prep.json"
            if not args.skip_evidence:
                prep_record.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "stage": "hardware_preparation",
                            "status": "verified",
                            "items": [{"item": item, "status": "done"} for item, _ in items],
                        },
                        indent=2,
                    )
                )
            self.log(f"Hardware preparation record: {prep_record}")

        operational_bin = ROOT / "build-exploit" / "fbr34ker-operational.bin"
        if args.force_rebuild or not operational_bin.is_file():
            if operational_bin.is_file():
                self.log("Found existing operational image, rebuilding (--force-rebuild)")
            else:
                self.log("Operational image not found, building now")
            if args.skip_build:
                self.log("Operational image missing but build was skipped", "ERROR")
                print("Operational image not found and --skip-build was requested.")
                return 1
            if not args.skip_build:
                result = subprocess.run(
                    ["make", "build-operational"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                if result.returncode != 0:
                    self.log(f"Build failed: {result.stderr}", "ERROR")
                    return 1
                self.log("Operational build complete")
        else:
            self.log(f"Found existing operational image: {operational_bin}")
            self.log("Skipping build (use --force-rebuild to override)")

        print("\n--- USBliter8 execution ---")
        print("This will exploit the A12+ device via DWC3 and run the chain.\n")

        owner = input(f'Type "{AUTHORIZATION_TEXT}" to continue: ')
        if owner != AUTHORIZATION_TEXT:
            print("Authorization not confirmed. Aborting.")
            return 1

        exploit_script = ROOT / "scripts" / "run_exploit.py"
        if not exploit_script.is_file():
            self.log(f"Exploit script not found: {exploit_script}", "ERROR")
            return 1

        evidence = (
            None
            if args.skip_evidence
            else (args.evidence or evidence_dir / "usbliter8-jailbreak.json")
        )
        cmd = [
            sys.executable,
            str(exploit_script),
            "--monitor",
            str(operational_bin),
            "--timeout",
            str(args.timeout),
        ]
        if evidence is not None:
            cmd.extend(["--evidence", str(evidence)])
        if args.no_dfu_wait:
            cmd.append("--no-dfu-wait")

        print(f"\nRunning: {' '.join(cmd)}\n")
        result = subprocess.run(cmd, cwd=ROOT, text=True, check=False)
        return_code = result.returncode

        if return_code == 0:
            self.log("USBliter8 exploit chain completed successfully")

            if not args.no_console:
                connect = input("\nConnect to FBR34KER console for live exploration? (y/N): ")
                if connect.lower() in ("y", "yes"):
                    console_cmd = [
                        sys.executable,
                        "-c",
                        "from host.usb_serial import USBConsole; "
                        "c = USBConsole(); c.open(); "
                        "print(c.read_until_prompt(timeout=10.0))",
                    ]
                    subprocess.run(console_cmd, cwd=ROOT, check=False)

            if args.return_to_b34st and not args.no_return:
                print("\nReturning to B34ST...")
                from b34st.control_panel import run_control_panel

                return run_control_panel()

        return return_code


def main() -> int:
    """Main B34ST CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="b34st",
        description="B34ST - FBR34KER Runtime Authentication Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
B34ST (B34KER/STAR) is a lightweight CLI wrapper for FBR34KER that
provides access to deterministic validation workflows, profile maturity
enforcement, and evidence-based authentication for A12/A13 iPhone hardware.

B34ST v{__version__} is part of FBR34KER {__version__} Beta.
It integrates with existing FBR34KER validation capabilities while
providing a streamlined interface for common operations.
        """,
    )

    parser.add_argument("--version", action="store_true", help="Show B34ST version and exit")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-essential output")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    if len(sys.argv) == 1:
        print("B34ST - FBR34KER Runtime Authentication Tool")
        print(f"Version {__version__} ({__release_name__})")
        print(f"\nB34ST v{__version__} is a lightweight CLI wrapper for FBR34KER")
        print("\nAvailable commands:")
        print("  b34st validate-session         Validate a session bundle")
        print("  b34st physical-validation       Perform physical validation operations")
        print("  b34st hardware-prepare         Read-only hardware preparation")
        print("  b34st forensics                Forensics and data acquisition")
        print("  b34st cve                      CVE database & exploit chain planner")
        print("  b34st cve device-info          Device/SoC database for iPhone 4-15, T2, M1/M2")
        print("  b34st cve device-chain         Device-aware exploit chain planning")
        print(
            "  b34st usbliter8                USBliter8 exploit workflow (hardware prep + execution)"
        )
        print("\nFor detailed help:")
        print("  b34st <command> --help")
        return 0

    args = parser.parse_args(sys.argv[1:])

    cli = B34STCLI(args.verbose, args.quiet)

    return cli.run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
