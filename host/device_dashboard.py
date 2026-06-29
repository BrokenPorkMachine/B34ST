#!/usr/bin/env python3
"""Build a B34ST device-specific capability and firmware dashboard."""

from __future__ import annotations

import argparse
import json
import pathlib
import plistlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "host"))

from b34st.device_catalog import device_metadata  # noqa: E402
from boot_image import BootImageError, load_profile  # noqa: E402
from ipsw_manager import DEFAULT_CATALOG, IPSWError, fetch_catalog  # noqa: E402
from irecovery_boot import RecoveryError, load_device_info, query_device  # noqa: E402


class DashboardError(RuntimeError):
    pass


def _run(arguments: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            arguments,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DashboardError(str(exc)) from exc


def query_normal_device(
    *,
    udid: str | None = None,
    ideviceinfo: str = "ideviceinfo",
    idevice_id: str = "idevice_id",
    timeout: float = 10.0,
) -> dict[str, Any] | None:
    info_tool = shutil.which(ideviceinfo)
    id_tool = shutil.which(idevice_id)
    if not info_tool:
        return None
    selected = udid
    if selected is None and id_tool:
        identifiers = _run([id_tool, "-l"], timeout).stdout.decode("utf-8", "replace").split()
        selected = identifiers[0] if identifiers else None
    command = [info_tool, "--xml"]
    if selected:
        command += ["--udid", selected]
    result = _run(command, timeout)
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        value = plistlib.loads(result.stdout)
    except plistlib.InvalidFileException as exc:
        raise DashboardError(f"ideviceinfo returned invalid plist: {exc}") from exc
    if not isinstance(value, dict):
        raise DashboardError("ideviceinfo result is not a dictionary")
    return {
        "source": "lockdown",
        "mode": "Normal",
        "udid": selected or value.get("UniqueDeviceID"),
        "ecid": str(value.get("UniqueChipID")) if value.get("UniqueChipID") is not None else None,
        "product": value.get("ProductType"),
        "model": value.get("HardwareModel"),
        "device_name": value.get("DeviceName"),
        "current_version": value.get("ProductVersion"),
        "current_build": value.get("BuildVersion"),
        "serial": value.get("SerialNumber"),
    }


def query_recovery_device(
    *,
    fixture: pathlib.Path | None = None,
    irecovery: str = "irecovery",
    ecid: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any] | None:
    try:
        device = load_device_info(fixture) if fixture else query_device(
            shutil.which(irecovery) or irecovery,
            ecid,
            timeout,
        )
    except (RecoveryError, OSError):
        return None
    value = device.public_dict()
    value["source"] = "fixture" if fixture else "irecovery"
    value["current_version"] = None
    value["current_build"] = None
    return value


def matching_profiles(product: str | None) -> list[dict[str, Any]]:
    if not product:
        return []
    matches = []
    for path in sorted((ROOT / "profiles").glob("apple-*-recovery.json")):
        try:
            profile = load_profile(path)
        except (BootImageError, OSError, ValueError):
            continue
        if product not in profile.get("product_types", []):
            continue
        matches.append({
            "profile_id": profile["profile_id"],
            "path": str(path.relative_to(ROOT)),
            "exact": bool(profile.get("requires_exact_product")),
            "family": profile["family"],
            "maturity": profile.get("maturity", "unverified"),
        })
    return sorted(matches, key=lambda item: (not item["exact"], item["profile_id"]))


def _version_key(value: str) -> tuple[int, ...]:
    parts = []
    for item in value.split("."):
        digits = "".join(character for character in item if character.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def firmware_summary(
    product: str | None,
    *,
    catalog_source: str,
    timeout: float,
) -> dict[str, Any]:
    if not product:
        return {"available": False, "error": "product identifier unavailable"}
    try:
        catalog = fetch_catalog(product, catalog_source, timeout)
    except IPSWError as exc:
        return {"available": False, "error": str(exc)}
    signed = [item for item in catalog["firmwares"] if item["signed"]]
    latest = max(signed, key=lambda item: _version_key(item["version"])) if signed else None
    unsigned = [item for item in catalog["firmwares"] if not item["signed"]]
    return {
        "available": True,
        "latest_signed": latest,
        "signed_count": len(signed),
        "unsigned_count": len(unsigned),
        "catalog": catalog,
    }


def assess_capabilities(
    device: dict[str, Any],
    firmware: dict[str, Any],
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mode = str(device.get("mode") or "unknown").lower()
    current = device.get("current_version")
    latest = (firmware.get("latest_signed") or {}).get("version")
    exact_profile = any(item["exact"] for item in profiles)
    normal = mode == "normal"
    recovery = any(token in mode for token in ("dfu", "recovery"))
    upgrade_needed = not current or not latest or _version_key(str(latest)) > _version_key(str(current))
    actions = [
        {
            "id": "inspect",
            "available": True,
            "title": "Inspect device and firmware compatibility",
            "reason": "Read-only device and profile inspection is always safe.",
        },
        {
            "id": "download-latest",
            "available": bool(firmware.get("latest_signed")),
            "title": "Download latest signed IPSW",
            "reason": "A signed Apple firmware record is available." if firmware.get("latest_signed")
            else "The signed firmware catalog is unavailable.",
        },
        {
            "id": "upgrade",
            "available": bool(firmware.get("latest_signed")) and (normal or recovery) and upgrade_needed,
            "title": "Upgrade using signed IPSW",
            "reason": (
                f"Current {current or 'version unknown'}; latest signed {latest}."
                if latest and upgrade_needed
                else f"Device is already on {current}, which is not older than latest signed {latest}."
                if latest and current
                else "No signed firmware record is available."
            ),
        },
        {
            "id": "signed-restore",
            "available": bool(firmware.get("latest_signed")) and (normal or recovery),
            "title": "Erase and restore signed firmware",
            "reason": (
                "Supported through idevicerestore; this erases user data."
                if firmware.get("latest_signed") and (normal or recovery)
                else "Requires a signed firmware record and a normal/recovery/DFU connection."
            ),
        },
        {
            "id": "research-runtime",
            "available": recovery and exact_profile,
            "title": "Authorized external first-stage / research runtime",
            "reason": (
                "Device is in recovery/DFU and an exact project profile exists."
                if recovery and exact_profile
                else "Requires DFU/recovery mode and an exact reviewed profile."
            ),
        },
        {
            "id": "tethered-downgrade",
            "available": recovery and exact_profile and firmware.get("unsigned_count", 0) > 0,
            "title": "Guided tethered downgrade",
            "reason": (
                "Unsigned historical firmware exists. The guide validates the "
                "IPSW and creates a plan; execution additionally requires a "
                "separately installed external tether adapter."
                if recovery and exact_profile and firmware.get("unsigned_count", 0) > 0
                else "Requires unsigned catalog firmware, DFU/recovery mode, and an exact profile."
            ),
        },
        {
            "id": "ramdisk",
            "available": recovery and exact_profile,
            "title": "Guided ramdisk maker / loader",
            "reason": (
                "An exact profile exists and the device is in DFU/recovery. "
                "B34ST can build and verify a bundle; physical loading requires "
                "a separately installed target/build-specific adapter."
                if recovery and exact_profile
                else "Requires DFU/recovery mode and an exact reviewed product profile."
            ),
        },
        {
            "id": "runtime-console",
            "available": False,
            "title": "Attach B34ST/FBR34KER runtime console",
            "reason": "Requires evidence that an authorized monitor or tether stage is currently running.",
        },
    ]
    return actions


def required_materials(action: str) -> list[str]:
    common = ["Known-good USB data cable", "Stable host power", "A recent device backup"]
    values = {
        "download-latest": ["Internet access", "At least 15 GB free disk space"],
        "upgrade": common + ["Latest signed IPSW", "idevicerestore", "Device passcode/trust when requested"],
        "signed-restore": common + ["Latest signed IPSW", "idevicerestore", "Find My disabled where required"],
        "research-runtime": common + [
            "Exact recovery profile",
            "Reviewed external first-stage adapter or bridge",
            "Validated FBRI monitor image",
            "Explicit owner authorization",
        ],
        "tethered-downgrade": common + [
            "Exact unsigned target IPSW",
            "Reviewed external tether adapter for execution (not bundled)",
            "A compatible boot chain for every restart",
            "Evidence/rollback storage",
        ],
        "ramdisk": common + [
            "Prepared target/build-specific ramdisk, kernelcache, and DeviceTree",
            "Optional matching trust cache and boot-chain components",
            "Reviewed external ramdisk adapter for physical loading (not bundled)",
            "Exact product identifier, OS version, and build",
            "Evidence storage and explicit owner authorization",
        ],
        "runtime-console": ["Running FBR34KER monitor", "USB CDC or configured bridge endpoint"],
    }
    return values.get(action, ["No additional materials"])


def procedure(action: str) -> list[str]:
    values = {
        "download-latest": [
            "Confirm the detected product identifier.",
            "Query the signed firmware catalog.",
            "Download from the Apple CDN with resume enabled.",
            "Verify ZIP structure, BuildManifest, target product, and SHA-256.",
        ],
        "upgrade": [
            "Create and verify a backup.",
            "Download and inspect the latest signed IPSW.",
            "Run idevicerestore in no-action mode and review its plan.",
            "Accept the owner and restore confirmations.",
            "Execute the update restore and wait for device activation.",
            "Return to B34ST and refresh device information.",
        ],
        "signed-restore": [
            "Back up any required data and confirm erase intent.",
            "Disable Find My when Apple requires it.",
            "Verify the selected signed IPSW matches the product.",
            "Run idevicerestore erase restore.",
            "Complete activation, then return to B34ST and refresh.",
        ],
        "research-runtime": [
            "Place the device in the required DFU/recovery mode.",
            "Validate exact profile, boot image, memory map, and adapter identity.",
            "Authorize the current adapter generation.",
            "Upload and start the monitor as separate confirmed operations.",
            "Collect console, boot evidence, reset, and reauthorization proof.",
            "Return to the B34ST dashboard for next-stage actions.",
        ],
        "tethered-downgrade": [
            "Open the guide and choose a local IPSW or an Apple catalog download.",
            "B34ST validates the product, version, build, manifest, and SHA-256.",
            "Provide a reviewed external tether adapter, or stop safely after planning.",
            "Review the human-readable plan and resolve every readiness blocker.",
            "Authorize execution; B34ST passes one JSON request to the adapter.",
            "Preserve the structured result and return to B34ST.",
            "Repeat the tethered boot after every device restart.",
        ],
        "ramdisk": [
            "Open the guide and confirm the exact product, OS version, and build.",
            "Review the exact-profile compatibility plan and its unverified items.",
            "Provide prepared ramdisk, kernelcache, DeviceTree, and optional components.",
            "Build the deterministic FBRD bundle and verify every component hash.",
            "Generate a plan-only adapter request; no device data is sent by default.",
            "Configure a reviewed target/build-specific adapter.",
            "Authorize execution separately and preserve the adapter JSON evidence.",
        ],
        "runtime-console": [
            "Confirm the monitor or tethered runtime is active.",
            "Open the logged B34ST console.",
            "Run bounded inspection or module commands.",
            "Exit with Ctrl-D and return to the dashboard.",
        ],
    }
    return values.get(action, ["Review the device dashboard and select an available action."])


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    normal = None if args.recovery_only else query_normal_device(
        udid=args.udid,
        ideviceinfo=args.ideviceinfo,
        idevice_id=args.idevice_id,
        timeout=args.timeout,
    )
    device = normal or query_recovery_device(
        fixture=args.device_info,
        irecovery=args.irecovery,
        ecid=args.ecid,
        timeout=args.timeout,
    )
    if device is None:
        return {
            "schema_version": 1,
            "connected": False,
            "device": None,
            "firmware": {"available": False, "error": "no connected device detected"},
            "profiles": [],
            "actions": [],
        }
    product = device.get("product")
    metadata = device_metadata(product)
    if metadata:
        device.update(metadata)
    profiles = matching_profiles(product)
    firmware = firmware_summary(product, catalog_source=args.catalog, timeout=args.catalog_timeout)
    return {
        "schema_version": 1,
        "connected": True,
        "device": device,
        "firmware": firmware,
        "profiles": profiles,
        "actions": assess_capabilities(device, firmware, profiles),
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--device-info", type=pathlib.Path)
    root.add_argument("--recovery-only", action="store_true")
    root.add_argument("--udid")
    root.add_argument("--ecid")
    root.add_argument("--ideviceinfo", default="ideviceinfo")
    root.add_argument("--idevice-id", default="idevice_id")
    root.add_argument("--irecovery", default="irecovery")
    root.add_argument("--catalog", default=DEFAULT_CATALOG)
    root.add_argument("--timeout", type=float, default=10.0)
    root.add_argument("--catalog-timeout", type=float, default=5.0)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        snapshot = build_snapshot(args)
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 0 if snapshot["connected"] else 1
    except (DashboardError, IPSWError, OSError, ValueError) as exc:
        print(f"device dashboard error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
