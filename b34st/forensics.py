#!/usr/bin/env python3
"""B34ST Forensics - Data acquisition and forensic evidence capabilities.

This module provides a B34ST CLI interface to the host.forensics package,
providing read-only forensic data acquisition for authorized iOS research
environments. It does not include exploitation, memory scraping, or access
to protected user data without explicit authorization.

User data access capabilities:
- `credential-extraction` - Requires unlocked SEP or passcode
- `protected-data-access` - Requires decrypted and mounted user data partition
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OWNER_ACK = "I OWN OR AM AUTHORIZED TO FORENSICALLY ACQUIRE FROM THIS DEVICE"
USER_DATA_ACK = "I HAVE EXPLICIT AUTHORIZATION FOR PROTECTED USER DATA ACCESS"


class ForensicsError(Exception):
    """Forensic operation error."""


# Acquisition types that require protected data access boundary
PROTECTED_DATA_ACQUISITION_TYPES = frozenset(
    ["keychain", "filesystem-only", "kernel-memory", "storage-only"]
)

# Acquisition types that require credential extraction boundary
CREDENTIAL_EXTRACTION_TYPES = frozenset(["keychain"])


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{label}{suffix}: ").strip() or default
    except (EOFError, KeyboardInterrupt):
        return ""


def _yes(label: str) -> bool:
    return _prompt(f"{label} (y/N)").lower() in {"y", "yes"}


def _check_security_boundary(
    profile_name: str,
    requested_capabilities: list[str] | None,
) -> list[str]:
    """Validate security boundary for acquisition types.

    Returns a list of blockers that must be acknowledged before proceeding.
    """
    blockers = []

    has_user_data = "protected-data-access" in (requested_capabilities or [])
    has_creds = "credential-extraction" in (requested_capabilities or [])

    if profile_name in PROTECTED_DATA_ACQUISITION_TYPES or has_user_data:
        blockers.append("The user data partition must be decrypted and mounted.")
        blockers.append("File Data Protection class granularity must be accounted for.")

    if profile_name in CREDENTIAL_EXTRACTION_TYPES or has_creds:
        blockers.append("Keychain data requires the passcode or an unlocked SEP.")
        blockers.append("Extraction may trigger iCloud remote lock; isolate network.")

    return blockers


def guided_acquisition(args: argparse.Namespace) -> int:
    """Run the interactive forensic acquisition orchestrator."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ForensicsError("guided acquisition requires an interactive TTY")

    from host.forensics.acquisition import AcquisitionEngine, AcquisitionTarget
    from host.forensics.profiles import builtin_profiles

    if _prompt(f'Type "{OWNER_ACK}" to continue') != OWNER_ACK:
        raise ForensicsError("owner authorization was not accepted")

    profiles = builtin_profiles()
    print("\nAvailable acquisition profiles:")
    for name, prof in profiles.items():
        print(f"  {name:20s}  {prof.description}")

    profile_name = _prompt("Acquisition profile", "quick")
    profile = profiles.get(profile_name, profiles["quick"])

    # Check if this profile requires protected data boundary
    blockers = _check_security_boundary(profile_name, args.capabilities)
    if blockers:
        print("\nSecurity boundary blockers for this acquisition type:")
        for b in blockers:
            print(f"  - {b}")
        if not _yes("Acknowledge these requirements"):
            raise ForensicsError("protected data access requirements not acknowledged")

    target = AcquisitionTarget(
        device_id=_prompt("Device ID", "unknown"),
        operator=_prompt("Operator name", ""),
        product=_prompt("Product", ""),
        model=_prompt("Model", ""),
        ios_version=_prompt("iOS version", ""),
        chipset=_prompt("Chipset", ""),
        mode=_prompt("Device mode", "unknown"),
    )

    engine = AcquisitionEngine.create(
        target,
        args.output or ROOT / "runtime-artifacts" / "b34st" / "forensics",
        profile=profile,
    )

    session = engine.run()
    session.finalize()

    print(f"\nAcquisition session: {session.session_dir}")
    summary = session.summary()
    print(f"Operations: {summary['summary']['total_operations']}")
    print(f"Passed: {summary['summary']['passed']}")
    print(f"Failed: {summary['summary']['failed']}")

    return 0


def acquire_cmd(args: argparse.Namespace) -> int:
    """Run a forensic acquisition session non-interactively."""
    from host.forensics.acquisition import AcquisitionEngine, AcquisitionTarget
    from host.forensics.profiles import builtin_profiles
    from host.forensics.report import AcquisitionReport

    profiles = builtin_profiles()
    profile = profiles.get(args.profile, profiles["quick"])

    # Security boundary check - warn if accessing protected data without capabilities
    blockers = _check_security_boundary(args.profile, getattr(args, "capabilities", []))
    if blockers and not getattr(args, "capabilities", []):
        print("Security boundary blockers for this acquisition type:", file=sys.stderr)
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

    # Record security boundary acknowledgments in custody log
    if blockers:
        session.custody.record(
            action="security.boundary.acknowledged",
            detail=f"User data access requirements acknowledged: {', '.join(blockers)}",
        )

    session.finalize()

    if args.bundle:
        report = AcquisitionReport(session)
        result = report.build_bundle(args.bundle)
        print(f"Bundle created: {result['report_path']}")
        print(f"Bundle SHA-256: {result['bundle_sha256']}")

    print(json.dumps(session.summary(), indent=2, sort_keys=True))
    return 0


def verify_cmd(args: argparse.Namespace) -> int:
    """Verify a forensic evidence bundle."""
    from host.forensics.report import AcquisitionReport, ReportError

    try:
        result = AcquisitionReport.verify_bundle(args.bundle)
    except ReportError as exc:
        raise ForensicsError(f"verification failed: {exc}")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("valid") else 1


def list_profiles_cmd(args: argparse.Namespace) -> int:
    """List built-in acquisition profiles."""
    from host.forensics.profiles import builtin_profiles

    profiles = builtin_profiles()
    for name, prof in profiles.items():
        print(f"  {name:20s}  {prof.description}")
        print(f"  {'':20s}  categories: {', '.join(sorted(prof.categories))}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="B34ST forensic data acquisition and evidence capabilities",
    )
    sub = root.add_subparsers(dest="command")

    guided_parser = sub.add_parser(
        "guided", help="interactive acquisition orchestrator"
    )
    guided_parser.add_argument("--output", type=pathlib.Path)
    guided_parser.add_argument(
        "--capabilities",
        action="append",
        choices=["credential-extraction", "protected-data-access"],
        help="requested security capabilities",
    )

    acquire_parser = sub.add_parser("acquire", help="run acquisition session")
    acquire_parser.add_argument(
        "--profile",
        choices=[
            "quick",
            "full",
            "memory-only",
            "storage-only",
            "filesystem-only",
            "network-only",
        ],
        default="quick",
        help="acquisition profile",
    )
    acquire_parser.add_argument(
        "--device-id", default="unknown", help="device identifier"
    )
    acquire_parser.add_argument("--operator", default="", help="operator name")
    acquire_parser.add_argument("--product", default="", help="target product")
    acquire_parser.add_argument("--model", default="", help="target model")
    acquire_parser.add_argument("--ios-version", default="", help="iOS version")
    acquire_parser.add_argument("--chipset", default="", help="chipset")
    acquire_parser.add_argument("--mode", default="unknown", help="device mode")
    acquire_parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "runtime-artifacts" / "b34st" / "forensics",
        help="output directory",
    )
    acquire_parser.add_argument(
        "--bundle", type=pathlib.Path, help="output bundle path"
    )
    acquire_parser.add_argument(
        "--capabilities",
        action="append",
        choices=["credential-extraction", "protected-data-access"],
        help="requested security capabilities for user data access",
    )

    verify_parser = sub.add_parser("verify", help="verify evidence bundle")
    verify_parser.add_argument("bundle", type=pathlib.Path)

    sub.add_parser("list-profiles", help="list acquisition profiles")

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in {None, "guided"}:
            return guided_acquisition(args)
        if args.command == "acquire":
            return acquire_cmd(args)
        if args.command == "verify":
            return verify_cmd(args)
        if args.command == "list-profiles":
            return list_profiles_cmd(args)
        return 0
    except ForensicsError as exc:
        print(f"forensics error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
