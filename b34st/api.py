#!/usr/bin/env python3
"""B34ST API Interface Module

Provides FBR34KER-compatible CLI interface for B34ST validation operations.
Implements fbr34kctl.py with B34ST-specific commands and options.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from b34st.engine import B34STEngine


class APIError(Exception):
    pass


class B34STApi:
    """B34ST API interface with FBR34KER compatibility."""

    def __init__(self, verbose: bool = False):
        self.engine = B34STEngine(verbose=verbose)
        self.verbose = verbose

    def validate_session(self, args: argparse.Namespace) -> int:
        """Validate a session bundle."""
        return self.engine.handle_validate_session(args)

    def physical_validation(self, args: argparse.Namespace) -> int:
        """Handle physical validation commands."""
        return self.engine.handle_physical_validation(args)

    def hardware_prepare(self, args: argparse.Namespace) -> int:
        """Handle hardware preparation commands."""
        return self.engine.handle_hardware_prepare(args)

    def run_command(self, argv: list[str]) -> int:
        """Run B34ST command with API."""
        return self.engine.run(argv)


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

    for path, name in [(success, "success"), (failure, "failure"), (recovered, "recovered")]:
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

    parser.add_argument(
        "--version", action="store_true", help="Show version and exit"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress non-essential output"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )

    subparsers = parser.add_subparsers(
        dest="command", help="fbr34kctl subcommand", required=True
    )

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

    cr_parser = pv_subparsers.add_parser("candidate-report", help="Generate candidate report")
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

    if argv is None:
        argv = sys.argv[1:]

    args = parser.parse_args(argv)

    if args.version:
        print("B34ST 0.2.3 (FBR34KER Runtime Authentication Tool)")
        print("Physical Validation Candidate")
        return 0

    api = B34STApi(args.verbose)

    try:
        if args.command == "validate-bundle":
            return api.validate_session(args)
        elif args.command == "physical-validation":
            return api.physical_validation(args)
        elif args.command == "hardware-prepare":
            return api.hardware_prepare(args)
        else:
            parser.print_help()
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
