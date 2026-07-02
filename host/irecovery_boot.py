#!/usr/bin/env python3

"""Query and send FBR34KER boot images through an authorized irecovery session."""
# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
from typing import Sequence

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
try:
    from .boot_image import BootImageError, inspect_image, load_profile, parse_int
    from .project_version import RELEASE_VERSION
except ImportError:
    from boot_image import BootImageError, inspect_image, load_profile, parse_int  # noqa: E402
    from project_version import RELEASE_VERSION  # noqa: E402

QUERY_TOKEN = re.compile(r"\b([A-Za-z][A-Za-z0-9_-]{1,15})\s*:\s*([^\s]+)")
MAX_EVIDENCE_SIZE = 512 * 1024
BOOT_COMMANDS = {"bootx", "go", "memboot"}


class RecoveryError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class DeviceInfo:
    cpid: int
    ecid: str | None
    mode: str
    product: str | None
    model: str | None
    board_id: str | None
    raw: dict[str, str]

    def public_dict(self) -> dict[str, object]:
        return {
            "cpid": f"0x{self.cpid:04x}",
            "ecid": self.ecid,
            "mode": self.mode,
            "product": self.product,
            "model": self.model,
            "board_id": self.board_id,
        }


def hash_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_query(output: str) -> DeviceInfo:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().upper().replace(" ", "_")
            value = value.strip()
            if key and value:
                values[key] = value
        for match in QUERY_TOKEN.finditer(line):
            values.setdefault(match.group(1).upper(), match.group(2))
    cpid_raw = values.get("CPID")
    if cpid_raw is None:
        raise RecoveryError("irecovery query did not report CPID")
    try:
        cpid = int(cpid_raw, 0) if cpid_raw.lower().startswith("0x") else int(cpid_raw, 16)
    except ValueError as exc:
        raise RecoveryError(f"invalid CPID from irecovery: {cpid_raw}") from exc
    mode = values.get("MODE", values.get("DEVICE_MODE", "unknown"))
    return DeviceInfo(
        cpid=cpid,
        ecid=values.get("ECID"),
        mode=mode,
        product=values.get("PRODUCT") or values.get("PRODUCT_TYPE"),
        model=values.get("MODEL") or values.get("HARDWARE_MODEL"),
        board_id=values.get("BDID") or values.get("BOARD_ID"),
        raw=values,
    )


def load_device_info(path: pathlib.Path) -> DeviceInfo:
    if not path.is_file() or path.stat().st_size > MAX_EVIDENCE_SIZE:
        raise RecoveryError("invalid device-info JSON")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"invalid device-info JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RecoveryError("device-info JSON must be an object")
    cpid = parse_int(value.get("cpid"), field="cpid")
    return DeviceInfo(
        cpid=cpid,
        ecid=str(value["ecid"]) if value.get("ecid") is not None else None,
        mode=str(value.get("mode", "unknown")),
        product=str(value["product"]) if value.get("product") is not None else None,
        model=str(value["model"]) if value.get("model") is not None else None,
        board_id=str(value["board_id"]) if value.get("board_id") is not None else None,
        raw={str(k).upper(): str(v) for k, v in value.items()},
    )


def run_tool(tool: str, arguments: Sequence[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            [tool, *arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RecoveryError(f"irecovery executable not found: {tool}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RecoveryError(f"irecovery timed out after {timeout:g}s") from exc
    if result.returncode != 0:
        detail = result.stdout.strip() or f"exit={result.returncode}"
        raise RecoveryError(f"irecovery failed: {detail}")
    return result


def query_device(tool: str, ecid: str | None, timeout: float) -> DeviceInfo:
    args: list[str] = []
    if ecid:
        args += ["-i", ecid]
    args.append("-q")
    return parse_query(run_tool(tool, args, timeout=timeout).stdout)


def normalize_mode(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def validate_target(profile: dict[str, object], device: DeviceInfo) -> None:
    allowed_cpids = {parse_int(value, field="CPID") for value in profile["cpids"]}
    if device.cpid not in allowed_cpids:
        expected = ", ".join(f"0x{value:04x}" for value in sorted(allowed_cpids))
        raise RecoveryError(f"device CPID 0x{device.cpid:04x} does not match profile ({expected})")
    allowed_modes = profile.get("allowed_modes", ["DFU", "Recovery"])
    if not isinstance(allowed_modes, list):
        raise RecoveryError("profile allowed_modes is invalid")
    normalized = normalize_mode(device.mode)
    if normalized != "unknown" and normalized not in {normalize_mode(str(value)) for value in allowed_modes}:
        raise RecoveryError(f"device mode {device.mode!r} is not allowed by profile")
    products = profile.get("product_types", [])
    if products:
        if device.product is None:
            if profile.get("requires_exact_product", False):
                raise RecoveryError("device query did not report a product type required by this profile")
        elif device.product not in {str(value) for value in products}:
            raise RecoveryError(f"device product {device.product!r} does not match profile")
    boards = profile.get("board_configurations", [])
    if boards:
        observed = device.model or device.board_id
        if observed is None:
            raise RecoveryError("device query did not report a board configuration required by this profile")
        if observed not in {str(value) for value in boards}:
            raise RecoveryError(f"device board configuration {observed!r} does not match profile")


def validate_image(path: pathlib.Path, profile: dict[str, object], allow_raw: bool) -> dict[str, object]:
    if not path.is_file():
        raise RecoveryError(f"boot image does not exist: {path}")
    size = path.stat().st_size
    maximum = int(profile.get("max_image_size", 64 * 1024 * 1024))
    if size <= 0 or size > maximum:
        raise RecoveryError("boot image size is outside the profile limit")
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic == b"FBRI":
        try:
            info = inspect_image(path)
        except BootImageError as exc:
            raise RecoveryError(str(exc)) from exc
        if info["family"] != profile["family"]:
            raise RecoveryError("boot image family does not match recovery profile")
        return {"format": "fbri-v1", "family": info["family"], "size": size,
                "sha256": info["sha256"], "component_count": info["component_count"]}
    if not allow_raw:
        raise RecoveryError("raw payload requires --allow-raw")
    return {"format": "raw", "family": profile["family"], "size": size,
            "sha256": hash_file(path), "component_count": 1}


def write_evidence(path: pathlib.Path, value: dict[str, object]) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > MAX_EVIDENCE_SIZE:
        raise RecoveryError("evidence record is unexpectedly large")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def _tool_args(ecid: str | None, *tail: str) -> list[str]:
    result: list[str] = []
    if ecid:
        result += ["-i", ecid]
    result += tail
    return result


def send_image(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    device = load_device_info(args.device_info) if args.device_info else query_device(args.irecovery, args.ecid, args.timeout)
    validate_target(profile, device)
    image = validate_image(args.image, profile, args.allow_raw)
    command = args.boot_command or str(profile.get("default_boot_command", "bootx"))
    if command not in BOOT_COMMANDS:
        raise RecoveryError(f"unsupported boot command: {command}")
    if args.execute and not args.authorized_session:
        raise RecoveryError("--execute requires --authorized-session")
    if args.execute and not args.acknowledge_unsigned_code:
        raise RecoveryError("--execute requires --acknowledge-unsigned-code")
    if not args.dry_run and not args.authorized_session:
        raise RecoveryError("sending requires --authorized-session")

    ecid = args.ecid or device.ecid
    send_arguments = _tool_args(ecid, "-f", str(args.image.resolve()))
    command_arguments = _tool_args(ecid, "-c", command)
    sent = False
    executed = False
    started = time.monotonic()
    if not args.dry_run:
        run_tool(args.irecovery, send_arguments, timeout=args.timeout)
        sent = True
        if args.execute:
            run_tool(args.irecovery, command_arguments, timeout=args.timeout)
            executed = True
    evidence = {
        "schema_version": 1,
        "project": "FBR34KER",
        "release_version": RELEASE_VERSION,
        "operation": "irecovery-send",
        "profile_id": profile["profile_id"],
        "device": device.public_dict(),
        "image": image,
        "dry_run": args.dry_run,
        "authorized_session_acknowledged": bool(args.authorized_session),
        "execute_requested": bool(args.execute),
        "sent": sent,
        "executed": executed,
        "boot_command": command if args.execute else None,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "security_boundary": "No exploit, signature bypass, or DFU-entry mechanism is included.",
    }
    if args.evidence:
        write_evidence(args.evidence, evidence)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    query = sub.add_parser("query", help="query a connected recovery/DFU device")
    query.add_argument("--irecovery", default=shutil.which("irecovery") or "irecovery")
    query.add_argument("--ecid")
    query.add_argument("--timeout", type=float, default=15.0)
    verify = sub.add_parser("verify", help="query and verify a device against a recovery profile")
    verify.add_argument("--irecovery", default=shutil.which("irecovery") or "irecovery")
    verify.add_argument("--profile", type=pathlib.Path, required=True)
    verify.add_argument("--device-info", type=pathlib.Path,
                        help="offline device query JSON for tests and diagnostics")
    verify.add_argument("--ecid")
    verify.add_argument("--timeout", type=float, default=15.0)
    verify.add_argument("--evidence", type=pathlib.Path)
    send = sub.add_parser("send", help="validate and send an image; execution is optional")
    send.add_argument("--irecovery", default=shutil.which("irecovery") or "irecovery")
    send.add_argument("--profile", type=pathlib.Path, required=True)
    send.add_argument("--image", type=pathlib.Path, required=True)
    send.add_argument("--device-info", type=pathlib.Path,
                      help="offline device query JSON for dry-runs and tests")
    send.add_argument("--ecid")
    send.add_argument("--timeout", type=float, default=60.0)
    send.add_argument("--allow-raw", action="store_true")
    send.add_argument("--authorized-session", action="store_true",
                      help="confirm the connected device/session is yours and authorized")
    send.add_argument("--execute", action="store_true",
                      help="issue the profile boot command after upload")
    send.add_argument("--acknowledge-unsigned-code", action="store_true",
                      help="confirm that stock iBoot will normally reject unsigned code")
    send.add_argument("--boot-command", choices=sorted(BOOT_COMMANDS))
    send.add_argument("--dry-run", action="store_true")
    send.add_argument("--evidence", type=pathlib.Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.timeout <= 0 or args.timeout > 300:
            raise RecoveryError("timeout must be in the range 0..300 seconds")
        if args.command == "query":
            device = query_device(args.irecovery, args.ecid, args.timeout)
            print(json.dumps(device.public_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "verify":
            profile = load_profile(args.profile)
            device = load_device_info(args.device_info) if args.device_info else query_device(args.irecovery, args.ecid, args.timeout)
            validate_target(profile, device)
            evidence = {
                "schema_version": 1,
                "project": "FBR34KER",
                "release_version": RELEASE_VERSION,
                "operation": "irecovery-verify",
                "passed": True,
                "profile_id": profile["profile_id"],
                "profile_maturity": profile.get("maturity", "unverified"),
                "device": device.public_dict(),
                "security_boundary": "Read-only query and profile matching; no transfer or execution.",
            }
            if args.evidence:
                write_evidence(args.evidence, evidence)
            print(json.dumps(evidence, indent=2, sort_keys=True))
            return 0
        return send_image(args)
    except (RecoveryError, BootImageError, OSError, ValueError) as exc:
        print(f"irecovery error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
