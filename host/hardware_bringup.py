#!/usr/bin/env python3
"""Run and collect authorized A12/A13 first-stage bring-up sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shlex
import sys
from typing import Any

from boot_image import BootImageError, load_profile
from first_stage_adapter import (
    AdapterError,
    BridgeFirstStageAdapter,
    CommandFirstStageAdapter,
    SimulatorFirstStageAdapter,
)
from irecovery_boot import DeviceInfo, RecoveryError, load_device_info, validate_target
from session_bundle import SessionBundleError, write_session_bundle

RELEASE_VERSION = "0.6.1b"
DEFAULT_STAGES = (
    "console",
    "board-inventory",
    "memory-map",
    "timer",
    "interrupts",
    "watchdog",
    "boot-evidence",
)


class BringupError(RuntimeError):
    pass


def _adapter(args: argparse.Namespace, device: DeviceInfo):
    if getattr(args, "bridge_command", None):
        return BridgeFirstStageAdapter(
            shlex.split(args.bridge_command), timeout=args.timeout
        )
    if args.adapter_command:
        return CommandFirstStageAdapter(
            shlex.split(args.adapter_command), timeout=args.timeout
        )
    regions = None
    if args.memory_map:
        value = json.loads(args.memory_map.read_text(encoding="utf-8"))
        regions = value.get("memory_regions") if isinstance(value, dict) else value
    return SimulatorFirstStageAdapter(
        args.state_dir,
        device.public_dict(),
        regions=regions,
        inject_failure=getattr(args, "inject_failure", None),
    )


def _external(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "bridge_command", None) or args.adapter_command)


def _adapter_transport(args: argparse.Namespace) -> str:
    if getattr(args, "bridge_command", None):
        return "persistent-bridge"
    if args.adapter_command:
        return "one-shot-command"
    return "simulator"


def _transcript(collected: dict[str, object]) -> list[dict[str, object]]:
    state = collected.get("state") if isinstance(collected, dict) else None
    values = (
        state.get("transcript", [])
        if isinstance(state, dict)
        else collected.get("transcript", [])
    )
    return (
        [dict(item) for item in values if isinstance(item, dict)]
        if isinstance(values, list)
        else []
    )


def _console(adapter, collected: dict[str, object]) -> list[str]:
    try:
        value = adapter.read_console(0)
        lines = value.get("lines", [])
        if isinstance(lines, list):
            return [str(line) for line in lines]
    except AdapterError:
        pass
    state = collected.get("state") if isinstance(collected, dict) else None
    values = state.get("console", []) if isinstance(state, dict) else []
    return [str(line) for line in values] if isinstance(values, list) else []


def _bundle_values(
    summary: dict[str, object],
    profile: dict[str, object],
    image: dict[str, object],
    collected: dict[str, object],
    console_lines: list[str],
) -> dict[str, Any]:
    transcript = _transcript(collected)
    transfer_log = "".join(
        json.dumps(item, sort_keys=True) + "\n" for item in transcript
    )
    boot = next(
        (
            item.get("details", {})
            for item in summary.get("stages", [])
            if isinstance(item, dict) and item.get("stage") == "boot-evidence"
        ),
        {},
    )
    crash = (
        {
            "schema_version": 1,
            "failure": summary.get("failure"),
            "profile_id": summary.get("profile_id"),
            "device": summary.get("device"),
        }
        if summary.get("failure")
        else {}
    )
    return {
        "session.json": summary,
        "summary.json": summary,
        "device.json": summary.get("device", {}),
        "profile.json": profile,
        "image-manifest.json": image.get("manifest", image),
        "transfer.log": transfer_log,
        "console.log": "".join(line + "\n" for line in console_lines),
        "boot-evidence.json": boot,
        "trace.json": {"schema_version": 1, "records": transcript},
        "crash-report.json": crash,
    }


def run_session(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    device = load_device_info(args.device_info)
    validate_target(profile, device)
    if (
        _external(args)
        and not profile.get("requires_exact_product", False)
        and not args.allow_family_profile
    ):
        raise BringupError(
            "external hardware sessions require an exact product profile; use --allow-family-profile only for controlled development"
        )
    if not args.authorized_session:
        raise BringupError("bring-up mutation requires --authorized-session")
    if not args.acknowledge_unsigned_code:
        raise BringupError(
            "starting an external monitor requires --acknowledge-unsigned-code"
        )
    adapter = _adapter(args, device)
    stages: list[dict[str, object]] = []
    failed: str | None = None
    failed_stage: str | None = None
    recovery = None
    collected: dict[str, object] = {}
    try:
        identity = adapter.identify()
        adapter_device = identity.device
        adapter_cpid = int(str(adapter_device.get("cpid", "0")), 0)
        if adapter_cpid != device.cpid:
            raise BringupError("adapter and selected device CPIDs differ")
        if (
            profile.get("requires_exact_product")
            and adapter_device.get("product") != device.product
        ):
            raise BringupError("adapter and selected device product types differ")
        authorization = adapter.authorize(args.authorization_id)
        verified = adapter.verify_image(args.image)
        if verified["image"]["family"] != profile["family"]:
            raise BringupError("image family does not match the selected profile")
        uploaded = adapter.upload(args.image)
        started = adapter.start()
        for stage in profile.get("required_bringup_stages", DEFAULT_STAGES):
            failed_stage = str(stage)
            try:
                stages.append(adapter.probe_stage(str(stage)))
            except AdapterError as exc:
                failed = str(exc)
                stages.append(
                    {"stage": failed_stage, "status": "failed", "detail": failed}
                )
                break
        failed_stage = None if failed is None else failed_stage
        if failed and args.recover_on_failure:
            recovery = adapter.reset(args.authorization_id)
        collected = adapter.collect()
        console_lines = _console(adapter, collected)
        image_public = dict(verified["image"])
        image_public["path"] = args.image.name
        session_material = "|".join(
            [
                str(profile["profile_id"]),
                str(device.ecid or "unknown"),
                str(image_public["sha256"]),
                str(identity.session_generation),
            ]
        )
        summary = {
            "schema_version": 1,
            "project": "FBR34KER",
            "release_version": RELEASE_VERSION,
            "operation": "authorized-physical-integration-preview",
            "session_id": hashlib.sha256(session_material.encode("utf-8")).hexdigest()[
                :24
            ],
            "profile_id": profile["profile_id"],
            "profile_maturity": profile.get("maturity", "unverified"),
            "device": device.public_dict(),
            "adapter": identity.public_dict(),
            "adapter_transport": _adapter_transport(args),
            "authorization": authorization,
            "image": image_public,
            "placements": verified["placements"],
            "upload": uploaded,
            "start": started,
            "stages": stages,
            "passed": failed is None,
            "failure": failed,
            "failed_stage": failed_stage,
            "recovery": recovery,
            "authorization_invalidated_after_recovery": bool(recovery),
            "physical_execution_verified": False,
            "evidence_boundary": "Simulator or operator-supplied authorized first-stage bridge; no exploit or signature bypass included.",
        }
        if args.evidence:
            write_session_bundle(
                args.evidence,
                _bundle_values(
                    summary, profile, image_public, collected, console_lines
                ),
            )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if failed is None else 1
    finally:
        try:
            adapter.close()
        except AdapterError:
            if sys.exc_info()[0] is None:
                raise


def collect_session(args: argparse.Namespace) -> int:
    device = load_device_info(args.device_info)
    adapter = _adapter(args, device)
    try:
        collected = adapter.collect()
        console_lines = _console(adapter, collected)
        summary = {
            "schema_version": 1,
            "project": "FBR34KER",
            "release_version": RELEASE_VERSION,
            "operation": "bringup-collect",
            "session_id": hashlib.sha256(
                json.dumps(collected, sort_keys=True).encode()
            ).hexdigest()[:24],
            "device": device.public_dict(),
            "profile_id": None,
            "passed": True,
            "stages": [],
            "collected": collected,
        }
        write_session_bundle(
            args.output, _bundle_values(summary, {}, {}, collected, console_lines)
        )
        print(args.output)
        return 0
    finally:
        adapter.close()


def recover_session(args: argparse.Namespace) -> int:
    if not args.authorized_session:
        raise BringupError("recovery requires --authorized-session")
    device = load_device_info(args.device_info)
    adapter = _adapter(args, device)
    try:
        result = adapter.reset(args.authorization_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    finally:
        adapter.close()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--state-dir", type=pathlib.Path, required=True)
    common.add_argument("--device-info", type=pathlib.Path, required=True)
    adapters = common.add_mutually_exclusive_group()
    adapters.add_argument(
        "--adapter-command",
        help="one-shot authorized adapter executable; JSON request on stdin",
    )
    adapters.add_argument(
        "--bridge-command",
        help="persistent authorized bridge command using JSON-lines protocol v1",
    )
    common.add_argument(
        "--memory-map",
        type=pathlib.Path,
        help="simulator memory-map JSON; ignored by external adapters",
    )
    common.add_argument("--timeout", type=float, default=30.0)
    run = sub.add_parser("run", parents=[common])
    run.add_argument("--profile", type=pathlib.Path, required=True)
    run.add_argument("--image", type=pathlib.Path, required=True)
    run.add_argument("--authorized-session", action="store_true")
    run.add_argument("--authorization-id", default="authorized-local-session")
    run.add_argument("--acknowledge-unsigned-code", action="store_true")
    run.add_argument("--allow-family-profile", action="store_true")
    run.add_argument(
        "--inject-failure", choices=["verify-image", "upload", "start", *DEFAULT_STAGES]
    )
    run.add_argument(
        "--recover-on-failure", action=argparse.BooleanOptionalAction, default=True
    )
    run.add_argument("--evidence", type=pathlib.Path)
    collect = sub.add_parser("collect", parents=[common])
    collect.add_argument("--output", type=pathlib.Path, required=True)
    recover = sub.add_parser("recover", parents=[common])
    recover.add_argument("--authorized-session", action="store_true")
    recover.add_argument("--authorization-id", default="authorized-local-session")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.timeout <= 0 or args.timeout > 300:
            raise BringupError("timeout must be in the range 0..300 seconds")
        if args.command == "run":
            return run_session(args)
        if args.command == "collect":
            return collect_session(args)
        return recover_session(args)
    except (
        BringupError,
        AdapterError,
        RecoveryError,
        BootImageError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        SessionBundleError,
    ) as exc:
        print(f"bringup error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
