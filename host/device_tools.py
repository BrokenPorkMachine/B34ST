#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""List, watch, and diagnose authorized A12/A13 recovery-mode devices."""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import shutil
import subprocess
import sys
import time

from boot_image import BootImageError, load_profile
from irecovery_boot import (
    DeviceInfo,
    RecoveryError,
    load_device_info,
    query_device,
    validate_target,
)


def tool_version(path: str) -> str:
    try:
        result = subprocess.run(
            [path, "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            check=False,
        )
        return (result.stdout.strip().splitlines() or [f"exit={result.returncode}"])[0]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)


def executable_path(value: str) -> str | None:
    return (
        shutil.which(value)
        if pathlib.Path(value).name == value
        else (value if pathlib.Path(value).is_file() else None)
    )


def discover_profiles(
    directory: pathlib.Path, device: DeviceInfo
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    if not directory.is_dir():
        return matches
    for path in sorted(directory.glob("apple-*-recovery.json")):
        try:
            profile = load_profile(path)
            validate_target(profile, device)
        except (BootImageError, RecoveryError, OSError, ValueError):
            continue
        matches.append(
            {
                "profile_id": profile["profile_id"],
                "path": str(path),
                "exact": bool(profile.get("requires_exact_product", False)),
                "maturity": profile.get("maturity", "unverified"),
            }
        )
    return sorted(
        matches, key=lambda item: (not bool(item["exact"]), str(item["profile_id"]))
    )


def read_devices(args: argparse.Namespace) -> list[DeviceInfo]:
    if args.device_info:
        return [load_device_info(path) for path in args.device_info]
    executable = executable_path(args.irecovery)
    if not executable:
        raise RecoveryError(f"irecovery executable not found: {args.irecovery}")
    return [query_device(executable, args.ecid, args.timeout)]


def list_devices(args: argparse.Namespace) -> int:
    try:
        devices = read_devices(args)
    except RecoveryError:
        if not args.allow_empty:
            raise
        devices = []
    values = []
    for device in devices:
        public = device.public_dict()
        public["profile_matches"] = discover_profiles(args.profiles_dir, device)
        values.append(public)
    exact = sum(
        1
        for value in values
        for profile in value["profile_matches"]
        if profile["exact"]
    )
    output = {
        "schema_version": 1,
        "count": len(values),
        "exact_profile_matches": exact,
        "devices": values,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if values or args.allow_empty else 1


def watch_devices(args: argparse.Namespace) -> int:
    previous: dict[str, object] | None = None
    fixture_index = 0
    for iteration in range(args.iterations):
        try:
            if args.device_info:
                path = args.device_info[min(fixture_index, len(args.device_info) - 1)]
                device = load_device_info(path)
                fixture_index += 1
            else:
                executable = executable_path(args.irecovery)
                if not executable:
                    raise RecoveryError("irecovery executable not found")
                device = query_device(executable, args.ecid, args.timeout)
            current: dict[str, object] | None = device.public_dict()
        except RecoveryError:
            current = None
        if current != previous:
            event = (
                "connected"
                if previous is None and current
                else "disconnected"
                if current is None
                else "changed"
            )
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "iteration": iteration + 1,
                        "event": event,
                        "device": current,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        previous = current
        if iteration + 1 < args.iterations:
            time.sleep(args.interval)
    return 0


def doctor_device(args: argparse.Namespace) -> int:
    executable = executable_path(args.irecovery)
    checks = [
        {
            "name": "host-macos",
            "ok": platform.system() == "Darwin",
            "required": False,
            "detail": platform.platform(),
        },
        {
            "name": "irecovery",
            "ok": bool(executable),
            "required": not args.device_info,
            "detail": tool_version(executable) if executable else "not installed",
        },
    ]
    device = (
        load_device_info(args.device_info[0])
        if args.device_info
        else (query_device(executable, args.ecid, args.timeout) if executable else None)
    )
    profile = load_profile(args.profile) if args.profile else None
    if profile and device:
        validate_target(profile, device)
    matches = discover_profiles(args.profiles_dir, device) if device else []
    checks.append(
        {
            "name": "device-query",
            "ok": device is not None,
            "required": True,
            "detail": device.public_dict() if device else "no device evidence",
        }
    )
    checks.append(
        {
            "name": "profile-match",
            "ok": profile is not None and device is not None,
            "required": bool(args.profile),
            "detail": profile.get("profile_id") if profile else "profile not requested",
        }
    )
    checks.append(
        {
            "name": "exact-profile-available",
            "ok": any(item["exact"] for item in matches),
            "required": False,
            "detail": matches,
        }
    )
    passed = all(item["ok"] for item in checks if item["required"])
    print(
        json.dumps(
            {
                "schema_version": 1,
                "passed": passed,
                "checks": checks,
                "device": device.public_dict() if device else None,
                "profile": profile.get("profile_id") if profile else None,
                "profile_matches": matches,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device-info", type=pathlib.Path, action="append")
    parser.add_argument("--irecovery", default=shutil.which("irecovery") or "irecovery")
    parser.add_argument("--ecid")
    parser.add_argument("--timeout", type=float, default=15.0)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor")
    add_common(doctor)
    doctor.add_argument("--profile", type=pathlib.Path)
    doctor.add_argument(
        "--profiles-dir", type=pathlib.Path, default=pathlib.Path("profiles")
    )
    listing = sub.add_parser("list")
    add_common(listing)
    listing.add_argument(
        "--profiles-dir", type=pathlib.Path, default=pathlib.Path("profiles")
    )
    listing.add_argument("--allow-empty", action="store_true")
    watch = sub.add_parser("watch")
    add_common(watch)
    watch.add_argument("--iterations", type=int, default=20)
    watch.add_argument("--interval", type=float, default=1.0)
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.timeout <= 0 or args.timeout > 300:
            raise RecoveryError("timeout must be in the range 0..300 seconds")
        if args.command == "doctor":
            return doctor_device(args)
        if args.command == "list":
            return list_devices(args)
        if (
            args.iterations < 1
            or args.iterations > 10000
            or args.interval < 0
            or args.interval > 300
        ):
            raise RecoveryError("invalid watch limits")
        return watch_devices(args)
    except (OSError, ValueError, RecoveryError, BootImageError) as exc:
        print(f"device {args.command} error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
