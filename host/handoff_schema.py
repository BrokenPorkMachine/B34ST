#!/usr/bin/env python3
"""Validate hardware-neutral FBR34KER handoff-v4 design documents.

This utility validates metadata only. It does not deliver a payload, alter a
boot chain, or contain device-specific offsets.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

REGION_TYPES = {
    "usable": 1,
    "reserved": 2,
    "mmio": 3,
    "monitor": 4,
    "framebuffer": 5,
}
REGION_ATTRIBUTES = {
    "read": 1 << 0,
    "write": 1 << 1,
    "execute": 1 << 2,
    "device": 1 << 3,
    "dma": 1 << 4,
}
RUNTIME_CALLBACK_NAMES = {"input", "timer", "power"}
SERVICE_NAMES = {
    "console-write",
    "console-read",
    "console-flush",
    "framebuffer-flush",
    "interrupt-controller",
    "watchdog-configure",
    "watchdog-kick",
}
MODULE_CAPABILITIES = {
    "console": 1 << 0,
    "log": 1 << 1,
    "time": 1 << 2,
    "dt": 1 << 3,
    "state": 1 << 4,
    "host": 1 << 5,
}
PAGE_GRANULES = {4096, 16384, 65536}
PIXEL_FORMATS = {"xrgb8888": (0, 4), "argb8888": (1, 4),
                 "bgra8888": (2, 4), "rgb565": (3, 2)}
U64_MAX = (1 << 64) - 1


class HandoffSchemaError(ValueError):
    """Raised when a handoff design document violates the v4 contract."""


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise HandoffSchemaError(f"{field} must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError as exc:
            raise HandoffSchemaError(f"{field} is not an integer") from exc
    else:
        raise HandoffSchemaError(f"{field} must be an integer or 0x string")
    if not 0 <= result <= U64_MAX:
        raise HandoffSchemaError(f"{field} is outside the unsigned 64-bit range")
    return result


def _range(base: int, size: int, field: str) -> tuple[int, int]:
    if size <= 0 or base > U64_MAX - size:
        raise HandoffSchemaError(f"{field} is empty or overflows")
    return base, base + size


def _mask(values: Any, names: dict[str, int], field: str) -> int:
    if isinstance(values, int) and not isinstance(values, bool):
        supported = sum(names.values())
        if values & ~supported:
            raise HandoffSchemaError(f"{field} contains unsupported bits")
        return values
    if not isinstance(values, list):
        raise HandoffSchemaError(f"{field} must be a list")
    result = 0
    for value in values:
        if value not in names:
            raise HandoffSchemaError(f"{field} contains unknown value {value!r}")
        result |= names[value]
    return result


def _covered(regions: list[dict[str, Any]], base: int, size: int,
             allowed_types: set[int], required_attributes: int) -> bool:
    end = base + size
    return any(
        region["type_id"] in allowed_types
        and region["base"] <= base
        and end <= region["end"]
        and region["attribute_mask"] & required_attributes == required_attributes
        for region in regions
    )


def template() -> dict[str, Any]:
    return {
        "version": 4,
        "entry_exception_level": 1,
        "page_granule": 16384,
        "boot_cpu_id": 0,
        "firmware_revision": "0x0",
        "monitor": {"base": "0x80000000", "size": "0x00800000"},
        "regions": [
            {
                "base": "0x80000000",
                "size": "0x00800000",
                "type": "monitor",
                "attributes": ["read", "write", "execute"],
            },
            {
                "base": "0x80800000",
                "size": "0x07800000",
                "type": "usable",
                "attributes": ["read", "write"],
            },
        ],
        "services": ["console-write", "console-read", "console-flush"],
        "runtime_callbacks": ["input", "timer", "power"],
        "module_policy": {
            "allowed_capabilities": ["console", "log", "time", "dt"],
            "dynamic_slots": 2,
            "instruction_budget": 2048,
        },
    }


def validate_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise HandoffSchemaError("handoff document must be a JSON object")
    if _integer(document.get("version"), "version") != 4:
        raise HandoffSchemaError("version must be 4")
    entry_el = _integer(document.get("entry_exception_level"),
                        "entry_exception_level")
    if entry_el not in {1, 2, 3}:
        raise HandoffSchemaError("entry_exception_level must be 1, 2, or 3")
    granule = _integer(document.get("page_granule"), "page_granule")
    if granule not in PAGE_GRANULES:
        raise HandoffSchemaError("page_granule must be 4096, 16384, or 65536")
    boot_cpu = _integer(document.get("boot_cpu_id", 0), "boot_cpu_id")
    firmware = _integer(document.get("firmware_revision", 0),
                        "firmware_revision")

    monitor = document.get("monitor")
    if not isinstance(monitor, dict):
        raise HandoffSchemaError("monitor must be an object")
    monitor_base = _integer(monitor.get("base"), "monitor.base")
    monitor_size = _integer(monitor.get("size"), "monitor.size")
    _range(monitor_base, monitor_size, "monitor")

    raw_regions = document.get("regions")
    if not isinstance(raw_regions, list) or not 1 <= len(raw_regions) <= 128:
        raise HandoffSchemaError("regions must contain between 1 and 128 entries")
    regions: list[dict[str, Any]] = []
    previous_end = 0
    for index, raw in enumerate(raw_regions):
        if not isinstance(raw, dict):
            raise HandoffSchemaError(f"regions[{index}] must be an object")
        base = _integer(raw.get("base"), f"regions[{index}].base")
        size = _integer(raw.get("size"), f"regions[{index}].size")
        _, end = _range(base, size, f"regions[{index}]")
        type_name = raw.get("type")
        if type_name not in REGION_TYPES:
            raise HandoffSchemaError(f"regions[{index}].type is unsupported")
        attributes = _mask(raw.get("attributes", []), REGION_ATTRIBUTES,
                           f"regions[{index}].attributes")
        if index and base < previous_end:
            raise HandoffSchemaError("regions must be sorted and non-overlapping")
        previous_end = end
        if type_name == "mmio" and not attributes & REGION_ATTRIBUTES["device"]:
            raise HandoffSchemaError("MMIO regions require the device attribute")
        regions.append({
            "base": base, "size": size, "end": end,
            "type": type_name, "type_id": REGION_TYPES[type_name],
            "attributes": raw.get("attributes", []),
            "attribute_mask": attributes,
        })

    monitor_required = (REGION_ATTRIBUTES["read"] |
                        REGION_ATTRIBUTES["write"] |
                        REGION_ATTRIBUTES["execute"])
    if not _covered(regions, monitor_base, monitor_size,
                    {REGION_TYPES["monitor"]}, monitor_required):
        raise HandoffSchemaError(
            "monitor range must be covered by an executable monitor region"
        )

    services = document.get("services", [])
    if not isinstance(services, list) or any(value not in SERVICE_NAMES
                                             for value in services):
        raise HandoffSchemaError("services contains an unsupported service")
    if len(set(services)) != len(services):
        raise HandoffSchemaError("services contains duplicates")

    runtime_callbacks = document.get("runtime_callbacks", [])
    if (not isinstance(runtime_callbacks, list) or
            any(value not in RUNTIME_CALLBACK_NAMES for value in runtime_callbacks)):
        raise HandoffSchemaError("runtime_callbacks contains an unsupported callback")
    if len(set(runtime_callbacks)) != len(runtime_callbacks):
        raise HandoffSchemaError("runtime_callbacks contains duplicates")

    framebuffer = document.get("framebuffer")
    normalized_framebuffer = None
    if framebuffer is not None:
        if not isinstance(framebuffer, dict):
            raise HandoffSchemaError("framebuffer must be an object")
        base = _integer(framebuffer.get("base"), "framebuffer.base")
        size = _integer(framebuffer.get("size"), "framebuffer.size")
        width = _integer(framebuffer.get("width"), "framebuffer.width")
        height = _integer(framebuffer.get("height"), "framebuffer.height")
        stride = _integer(framebuffer.get("pixels_per_row"),
                          "framebuffer.pixels_per_row")
        format_name = framebuffer.get("pixel_format")
        if format_name not in PIXEL_FORMATS:
            raise HandoffSchemaError("framebuffer.pixel_format is unsupported")
        format_id, bytes_per_pixel = PIXEL_FORMATS[format_name]
        rotation = _integer(framebuffer.get("rotation", 0),
                            "framebuffer.rotation")
        if rotation not in {0, 90, 180, 270}:
            raise HandoffSchemaError("framebuffer.rotation is unsupported")
        if width == 0 or height == 0 or stride < width:
            raise HandoffSchemaError("framebuffer geometry is invalid")
        needed = stride * height * bytes_per_pixel
        if needed > U64_MAX or size < needed:
            raise HandoffSchemaError("framebuffer.size is smaller than its geometry")
        _range(base, size, "framebuffer")
        rw = REGION_ATTRIBUTES["read"] | REGION_ATTRIBUTES["write"]
        if not _covered(regions, base, size,
                        {REGION_TYPES["reserved"], REGION_TYPES["mmio"],
                         REGION_TYPES["framebuffer"]}, rw):
            raise HandoffSchemaError(
                "framebuffer must be covered by a readable/writable region"
            )
        normalized_framebuffer = {
            "base": f"0x{base:x}", "size": f"0x{size:x}",
            "width": width, "height": height, "pixels_per_row": stride,
            "pixel_format": format_name, "pixel_format_id": format_id,
            "bytes_per_pixel": bytes_per_pixel, "rotation": rotation,
        }
    if "framebuffer-flush" in services and normalized_framebuffer is None:
        raise HandoffSchemaError(
            "framebuffer-flush requires a framebuffer descriptor"
        )

    module_policy = document.get("module_policy")
    normalized_policy = None
    if module_policy is not None:
        if not isinstance(module_policy, dict):
            raise HandoffSchemaError("module_policy must be an object")
        allowed = _mask(module_policy.get("allowed_capabilities", []),
                        MODULE_CAPABILITIES,
                        "module_policy.allowed_capabilities")
        slots = _integer(module_policy.get("dynamic_slots", 0),
                         "module_policy.dynamic_slots")
        budget = _integer(module_policy.get("instruction_budget", 0),
                          "module_policy.instruction_budget")
        if slots > 4:
            raise HandoffSchemaError("module_policy.dynamic_slots exceeds 4")
        if slots and not 1 <= budget <= 4096:
            raise HandoffSchemaError(
                "module_policy.instruction_budget must be 1..4096 when slots are enabled"
            )
        normalized_policy = {
            "allowed_capabilities": sorted(module_policy.get(
                "allowed_capabilities", [])),
            "allowed_capability_mask": allowed,
            "dynamic_slots": slots,
            "instruction_budget": budget,
        }

    return {
        "version": 4,
        "entry_exception_level": entry_el,
        "page_granule": granule,
        "boot_cpu_id": boot_cpu,
        "firmware_revision": f"0x{firmware:x}",
        "monitor": {"base": f"0x{monitor_base:x}",
                    "size": f"0x{monitor_size:x}"},
        "regions": [
            {"base": f"0x{item['base']:x}", "size": f"0x{item['size']:x}",
             "type": item["type"], "attributes": item["attributes"],
             "attribute_mask": item["attribute_mask"]}
            for item in regions
        ],
        "services": sorted(services),
        "runtime_callbacks": sorted(runtime_callbacks),
        "framebuffer": normalized_framebuffer,
        "module_policy": normalized_policy,
    }


def load_and_validate(path: pathlib.Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffSchemaError(f"cannot read handoff document: {exc}") from exc
    return validate_document(document)


def write_template(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
