#!/usr/bin/env python3
"""B34ST API Interface Module

Provides FBR34KER-compatible CLI interface for B34ST validation operations.
Implements fbr34kctl.py with B34ST-specific commands and options.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Any

from b34st.engine import B34STCLI
from b34st.version import __version__

ROOT = pathlib.Path(__file__).resolve().parent.parent


class APIError(Exception):
    pass


class B34STApi:
    """B34ST API interface with FBR34KER compatibility."""

    def __init__(self, verbose: bool = False):
        self.engine = B34STCLI(verbose=verbose)
        self.verbose = verbose

    def validate_session(self, args: argparse.Namespace) -> int:
        """Validate a session bundle."""
        argv = ["--bundle", str(args.bundle)]
        if getattr(args, "profile", None):
            argv.extend(["--profile", str(args.profile)])
        return self.engine._validate_session(argv)

    def physical_validation(self, args: argparse.Namespace) -> int:
        """Handle physical validation commands."""
        argv = [
            "candidate-report",
            "--success",
            str(args.success),
            "--failure",
            str(args.failure),
            "--recovered",
            str(args.recovered),
        ]
        if getattr(args, "qemu_summary", None):
            argv.extend(["--qemu-summary", str(args.qemu_summary)])
        if getattr(args, "output", None):
            argv.extend(["--output", str(args.output)])
        return self.engine._physical_validation(argv)

    def hardware_prepare(self, args: argparse.Namespace) -> int:
        """Handle hardware preparation commands."""
        argv: list[str] = []
        if getattr(args, "list_categories", False):
            argv.append("--list-categories")
        if getattr(args, "save_checklists", None):
            argv.extend(["--save-checklists", str(args.save_checklists)])
        if getattr(args, "validate_bundle", None):
            argv.extend(["--validate-bundle", str(args.validate_bundle)])
        return self.engine._hardware_prepare(argv)

    def forensics_acquire(self, args: argparse.Namespace) -> int:
        """Run a forensic acquisition session."""
        argv = ["acquire", "--profile", args.profile, "--device-id", args.device_id]
        if args.operator:
            argv.extend(["--operator", args.operator])
        if args.product:
            argv.extend(["--product", args.product])
        if args.output:
            argv.extend(["--output", str(args.output)])
        if args.bundle:
            argv.extend(["--bundle", str(args.bundle)])
        for cap in getattr(args, "capabilities", []) or []:
            argv.extend(["--capabilities", cap])
        return self.engine._forensics(argv)

    def forensics_verify(self, bundle_path: pathlib.Path) -> int:
        """Verify a forensics evidence bundle."""
        return self.engine._forensics(["verify", str(bundle_path)])

    def forensics_list_profiles(self) -> int:
        """List built-in acquisition profiles."""
        return self.engine._forensics(["list-profiles"])

    def run_command(self, argv: list[str]) -> int:
        """Run B34ST command with API."""
        return self.engine.run(argv)

    def cve_search(self, query: str) -> int:
        """Search CVE database."""
        return self.engine._cve(["search", query])

    def cve_query(self, version: str) -> int:
        """Get CVEs for an iOS version."""
        return self.engine._cve(["query", version])

    def cve_filter(self, **kwargs: Any) -> int:
        """Filter CVEs by criteria. Pass kwargs as --key=value style args."""
        argv = ["filter"]
        for key, val in kwargs.items():
            if isinstance(val, bool):
                if val:
                    argv.append(f"--{key.replace('_', '-')}")
            elif isinstance(val, list):
                for v in val:
                    argv.extend([f"--{key.replace('_', '-')}", str(v)])
            else:
                argv.extend([f"--{key.replace('_', '-')}", str(val)])
        return self.engine._cve(argv)

    def cve_stats(self) -> int:
        """Show CVE database statistics."""
        return self.engine._cve(["stats"])

    def cve_chain(self, goal: str, version: str) -> int:
        """Plan exploit chain for goal on version."""
        return self.engine._cve(["chain", goal, version])

    def cve_suggest(self, version: str) -> int:
        """Suggest achievable goals for version."""
        return self.engine._cve(["suggest", version])

    def cve_goals(self) -> int:
        """List all built-in exploit goals."""
        return self.engine._cve(["goals"])

    def cve_fuzz_list(self) -> int:
        """List available fuzz targets."""
        return self.engine._cve(["fuzz", "list"])

    # ------------------------------------------------------------------
    # SEP Key Fuzzer API
    # ------------------------------------------------------------------

    def sep_fuzz_run(
        self,
        *,
        device_model: str = "iPhone14,2",
        os_build: str = "21A123",
        chipset: str = "A15",
        output_dir: pathlib.Path | None = None,
        categories: list[str] | None = None,
        harness_only: bool = False,
        transport: str = "simulator",
        transport_args: str = "{}",
    ) -> int:
        """Run a SEP key fuzzing campaign."""
        argv = ["run"]
        argv.extend(["--device-model", device_model])
        argv.extend(["--os-build", os_build])
        argv.extend(["--chipset", chipset])
        if output_dir:
            argv.extend(["--output", str(output_dir)])
        if categories:
            argv.extend(["--categories", *categories])
        if harness_only:
            argv.append("--harness-only")
        argv.extend(["--transport", transport])
        argv.extend(["--transport-args", transport_args])
        return self.engine._sep_fuzz(argv)

    def sep_fuzz_list_categories(self) -> int:
        """List available fuzz categories."""
        return self.engine._sep_fuzz(["list-categories"])

    def sep_fuzz_list_variations(
        self, category: str | None = None
    ) -> int:
        """List fuzz variations, optionally filtered by category."""
        argv = ["list-variations"]
        if category:
            argv.extend(["--category", category])
        return self.engine._sep_fuzz(argv)

    def sep_fuzz_generate_harness(
        self, output_dir: pathlib.Path | None = None
    ) -> int:
        """Generate the baseline Swift harness."""
        argv = ["generate-harness"]
        if output_dir:
            argv.extend(["--output", str(output_dir)])
        return self.engine._sep_fuzz(argv)

    # ------------------------------------------------------------------
    # SEP Research Pipeline API
    # ------------------------------------------------------------------

    def sep_research_run(
        self,
        *,
        device_model: str = "iPhone14,2",
        os_build: str = "21A123",
        chipset: str = "A15",
        output_dir: pathlib.Path | None = None,
        stages: list[str] | None = None,
        transport: str = "simulator",
        transport_args: str = "{}",
    ) -> int:
        """Run the SEP vulnerability research pipeline."""
        argv = ["run"]
        argv.extend(["--device-model", device_model])
        argv.extend(["--os-build", os_build])
        argv.extend(["--chipset", chipset])
        if output_dir:
            argv.extend(["--output", str(output_dir)])
        if stages:
            argv.extend(["--stages", *stages])
        argv.extend(["--transport", transport])
        argv.extend(["--transport-args", transport_args])
        return self.engine._sep_research(argv)

    def sep_research_list_stages(self) -> int:
        """List available pipeline stages."""
        return self.engine._sep_research(["list-stages"])

    def sep_research_info(self) -> int:
        """Show pipeline component information."""
        return self.engine._sep_research(["info"])


# Global API instance
_api = B34STApi()


def validate_bundle(path: pathlib.Path) -> dict[str, Any]:
    """Validate a session bundle - FBR34KER compatible API."""
    from b34st.engine import B34STError

    if not path.exists():
        raise B34STError(f"Bundle file not found: {path}")

    from host.physical_validation import validate_bundle as fv

    return fv(path)


def candidate_report(
    success: pathlib.Path,
    failure: pathlib.Path,
    recovered: pathlib.Path,
    qemu_summary: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Generate candidate report - FBR34KER compatible API."""
    from b34st.engine import B34STError

    for path, name in [
        (success, "success"),
        (failure, "failure"),
        (recovered, "recovered"),
    ]:
        if not path.exists():
            raise B34STError(f"{name} bundle not found: {path}")

    from host.physical_validation import candidate_report as cr

    return cr(success, failure, recovered, qemu_summary)


def main(argv: list[str] | None = None) -> int:
    """B34ST API main entry point - FBR34KER compatible."""
    parser = argparse.ArgumentParser(
        prog="fbr34kctl.py",
        description="FBR34kER control utility with B34ST extension",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\nAvailable commands:\n  validate-bundle     Validate a session bundle\n  physical-validation  Perform physical validation operations\n  hardware-prepare    Read-only hardware preparation\n  help               Show help information\n        """,
    )

    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress non-essential output"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    subparsers = parser.add_subparsers(dest="command", help="fbr34kctl subcommand")

    # Validate bundle command
    vb_parser = subparsers.add_parser(
        "validate-bundle", help="Validate a session bundle"
    )
    vb_parser.add_argument("bundle", help="Path to session bundle")
    vb_parser.add_argument(
        "--profile",
        default="profiles/apple-a13-iphone-recovery.json",
        help="Device profile",
    )

    # Physical validation command
    pv_parser = subparsers.add_parser(
        "physical-validation", help="Perform physical validation"
    )
    pv_subparsers = pv_parser.add_subparsers(
        dest="pv_command", help="Physical validation subcommand", required=True
    )

    cr_parser = pv_subparsers.add_parser(
        "candidate-report", help="Generate candidate report"
    )
    cr_parser.add_argument("--success", required=True, help="Successful bundle path")
    cr_parser.add_argument("--failure", required=True, help="Failure bundle path")
    cr_parser.add_argument("--recovered", required=True, help="Recovered bundle path")
    cr_parser.add_argument("--qemu-summary", help="QEMU summary path")
    cr_parser.add_argument("--output", help="Output report path")

    # Hardware prepare command
    hp_parser = subparsers.add_parser(
        "hardware-prepare", help="Read-only hardware preparation"
    )
    hp_parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List preparation categories",
    )
    hp_parser.add_argument("--save-checklists", help="Save checklists to directory")
    hp_parser.add_argument("--validate-bundle", help="Validate existing bundle")

    # Forensics acquisition command
    fx_parser = subparsers.add_parser(
        "forensics", help="Forensics and data acquisition"
    )
    fx_sub = fx_parser.add_subparsers(
        dest="fx_command", help="Forensics subcommand", required=True
    )

    fx_sub.add_parser(
        "list-profiles", help="List built-in acquisition profiles"
    )

    fx_acq = fx_sub.add_parser("acquire", help="Run a forensic acquisition session")
    fx_acq.add_argument(
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
    )
    fx_acq.add_argument("--device-id", default="unknown")
    fx_acq.add_argument("--operator", default="")
    fx_acq.add_argument("--product", default="")
    fx_acq.add_argument("--output", type=pathlib.Path)
    fx_acq.add_argument("--bundle", type=pathlib.Path)
    fx_acq.add_argument(
        "--capabilities",
        action="append",
        choices=["credential-extraction", "protected-data-access"],
        help="security capabilities for user data access",
    )

    fx_vfy = fx_sub.add_parser("verify", help="Verify a forensics evidence bundle")
    fx_vfy.add_argument("bundle", type=pathlib.Path)

    # SEP Key Fuzzer command
    sep_fuzz_parser = subparsers.add_parser(
        "sep-fuzz", help="SEP Key Fuzzer — differential SEP key-wrapper testing"
    )
    sep_fuzz_sub = sep_fuzz_parser.add_subparsers(
        dest="sep_fuzz_command", help="SEP fuzzer subcommand", required=True
    )

    sf_run = sep_fuzz_sub.add_parser(
        "run", help="Run a full SEP key fuzzing campaign"
    )
    sf_run.add_argument(
        "--device-model", default="iPhone14,2", help="Device model identifier"
    )
    sf_run.add_argument("--os-build", default="21A123", help="iOS build number")
    sf_run.add_argument(
        "--chipset", default="A15", help="SoC chipset identifier"
    )
    sf_run.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "runtime-artifacts" / "b34st" / "sep-fuzz",
        help="Output directory",
    )
    sf_run.add_argument(
        "--categories",
        nargs="*",
        choices=["device_lifecycle", "access_control", "wrapper_integrity"],
        default=None,
        help="Test categories to run (default: all)",
    )
    sf_run.add_argument(
        "--harness-only",
        action="store_true",
        help="Only generate baseline Swift harness",
    )

    sep_fuzz_sub.add_parser(
        "list-categories", help="List fuzz categories"
    )
    sf_list_vars = sep_fuzz_sub.add_parser(
        "list-variations", help="List fuzz variations"
    )
    sf_list_vars.add_argument(
        "--category",
        choices=["device_lifecycle", "access_control", "wrapper_integrity"],
        default=None,
        help="Filter by category",
    )
    sf_gen = sep_fuzz_sub.add_parser(
        "generate-harness", help="Generate baseline Swift harness"
    )
    sf_gen.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "runtime-artifacts" / "b34st" / "sep-fuzz",
        help="Output directory",
    )

    # SEP Research Pipeline command
    sep_research_parser = subparsers.add_parser(
        "sep-research",
        help="SEP Research Pipeline — automated SEP/sepOS vulnerability fuzzing",
    )
    sep_research_sub = sep_research_parser.add_subparsers(
        dest="sep_research_command",
        help="Pipeline subcommand",
        required=True,
    )

    sr_run = sep_research_sub.add_parser(
        "run", help="Run the full research pipeline"
    )
    sr_run.add_argument(
        "--device-model", default="iPhone14,2", help="Device model identifier"
    )
    sr_run.add_argument("--os-build", default="21A123", help="iOS build number")
    sr_run.add_argument(
        "--chipset", default="A15", help="SoC chipset identifier"
    )
    sr_run.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "runtime-artifacts" / "b34st" / "sep-research",
        help="Output directory",
    )
    sr_run.add_argument(
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

    sep_research_sub.add_parser(
        "list-stages", help="List pipeline stages"
    )
    sep_research_sub.add_parser(
        "info", help="Show pipeline component information"
    )

    # CVE database command
    cve_parser = subparsers.add_parser(
        "cve", help="CVE database & exploit chain planner"
    )
    cve_sub = cve_parser.add_subparsers(
        dest="cve_command", help="CVE subcommand", required=True
    )
    cve_search = cve_sub.add_parser("search", help="Search CVEs by ID or description")
    cve_search.add_argument("query", help="Search query")
    cve_query = cve_sub.add_parser("query", help="Get CVEs for an iOS version")
    cve_query.add_argument("version", help="iOS version")
    cve_sub.add_parser("stats", help="Database statistics")
    cve_chain = cve_sub.add_parser("chain", help="Plan exploit chain")
    cve_chain.add_argument("goal")
    cve_chain.add_argument("version")
    cve_suggest = cve_sub.add_parser("suggest", help="Suggest achievable goals")
    cve_suggest.add_argument("version")
    cve_sub.add_parser("goals", help="List exploit goals")

    if argv is None:
        argv = sys.argv[1:]

    args = parser.parse_args(argv)

    if args.version:
        print(f"B34ST {__version__} (FBR34KER Runtime Authentication Tool)")
        print("Beta")
        return 0
    if args.command is None:
        parser.print_help()
        return 1

    api = B34STApi(args.verbose)

    try:
        if args.command == "validate-bundle":
            return api.validate_session(args)
        elif args.command == "physical-validation":
            return api.physical_validation(args)
        elif args.command == "hardware-prepare":
            return api.hardware_prepare(args)
        elif args.command == "forensics":
            if args.fx_command == "list-profiles":
                return api.forensics_list_profiles()
            elif args.fx_command == "acquire":
                return api.forensics_acquire(args)
            elif args.fx_command == "verify":
                return api.forensics_verify(args.bundle)
            else:
                parser.print_help()
                return 1
        elif args.command == "sep-fuzz":
            if args.sep_fuzz_command == "run":
                return api.sep_fuzz_run(
                    device_model=args.device_model,
                    os_build=args.os_build,
                    chipset=args.chipset,
                    output_dir=args.output,
                    categories=args.categories,
                    harness_only=args.harness_only,
                )
            elif args.sep_fuzz_command == "list-categories":
                return api.sep_fuzz_list_categories()
            elif args.sep_fuzz_command == "list-variations":
                return api.sep_fuzz_list_variations(
                    category=args.category
                )
            elif args.sep_fuzz_command == "generate-harness":
                return api.sep_fuzz_generate_harness(
                    output_dir=args.output
                )
            else:
                parser.print_help()
                return 1
        elif args.command == "sep-research":
            if args.sep_research_command == "run":
                return api.sep_research_run(
                    device_model=args.device_model,
                    os_build=args.os_build,
                    chipset=args.chipset,
                    output_dir=args.output,
                    stages=args.stages,
                )
            elif args.sep_research_command == "list-stages":
                return api.sep_research_list_stages()
            elif args.sep_research_command == "info":
                return api.sep_research_info()
            else:
                parser.print_help()
                return 1
        elif args.command == "cve":
            if args.cve_command == "search":
                return api.cve_search(args.query)
            elif args.cve_command == "query":
                return api.cve_query(args.version)
            elif args.cve_command == "stats":
                return api.cve_stats()
            elif args.cve_command == "chain":
                return api.cve_chain(args.goal, args.version)
            elif args.cve_command == "suggest":
                return api.cve_suggest(args.version)
            elif args.cve_command == "goals":
                return api.cve_goals()
            else:
                parser.print_help()
                return 1
        else:
            parser.print_help()
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
