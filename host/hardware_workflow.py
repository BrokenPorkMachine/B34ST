#!/usr/bin/env python3
"""Operator-facing FBR34KER physical-validation workflow."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

from boot_image import BootImageError, inspect_image, load_profile
from irecovery_boot import RecoveryError, load_device_info, validate_target
from physical_validation import checklist, explain_failure, validate_bundle

ROOT = pathlib.Path(__file__).resolve().parents[1]


class HardwareWorkflowError(RuntimeError):
    pass


def prepare(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    device = load_device_info(args.device_info)
    validate_target(profile, device)
    image = inspect_image(args.image)
    if image.get("family") != profile.get("family"):
        raise HardwareWorkflowError("image family does not match profile")
    result = {
        "schema_version": 1,
        "project": "FBR34KER",
        "release_version": "0.4.0",
        "operation": "physical-validation-prepare",
        "ready": True,
        "mutation_performed": False,
        "device": device.public_dict(),
        "profile_id": profile.get("profile_id"),
        "profile_maturity": profile.get("maturity", "simulated"),
        "image": {key: image.get(key) for key in ("family", "sha256", "size", "component_count")},
        "requirements": checklist(args.profile)["checks"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def forward(module: str, arguments: list[str]) -> int:
    return subprocess.run([sys.executable, str(ROOT / "host" / module), *arguments],
                          cwd=ROOT, check=False).returncode


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--profile", type=pathlib.Path, required=True)
    prep.add_argument("--device-info", type=pathlib.Path, required=True)
    prep.add_argument("--image", type=pathlib.Path, required=True)
    for command in ("run", "collect", "recover"):
        item = sub.add_parser(command)
        item.add_argument("arguments", nargs=argparse.REMAINDER)
    doctor = sub.add_parser("doctor"); doctor.add_argument("arguments", nargs=argparse.REMAINDER)
    check = sub.add_parser("checklist"); check.add_argument("profile", type=pathlib.Path)
    explain = sub.add_parser("explain-failure"); explain.add_argument("bundle", type=pathlib.Path)
    validate = sub.add_parser("validate"); validate.add_argument("bundle", type=pathlib.Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "prepare": return prepare(args)
        if args.command in {"run", "collect", "recover"}:
            return forward("hardware_bringup.py", [args.command, *args.arguments])
        if args.command == "doctor": return forward("device_tools.py", ["doctor", *args.arguments])
        if args.command == "checklist": result = checklist(args.profile)
        elif args.command == "explain-failure": result = explain_failure(args.bundle)
        else:
            result = validate_bundle(args.bundle)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["valid"] else 1
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, HardwareWorkflowError,
            BootImageError, RecoveryError) as exc:
        print(f"hardware workflow error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
