#!/usr/bin/env python3
"""Offline FBR34KER handoff-v4 loader simulator and conformance checker.

The simulator parses the generic AArch64 ELF, validates a handoff design,
constructs packed handoff tables in sparse simulated memory, and emits a
machine-readable report. It does not exploit, patch, or deliver code to a
device.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import struct
from dataclasses import dataclass, asdict
from typing import Any, Iterable

try:
    from .handoff_schema import load_and_validate
    from .project_version import RELEASE_VERSION
except ImportError:
    from handoff_schema import load_and_validate
    from project_version import RELEASE_VERSION

ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
PROGRAM_HEADER = struct.Struct("<IIQQQQQQ")
PT_LOAD = 1
EM_AARCH64 = 183
PF_X, PF_W, PF_R = 1, 2, 4
FDT_MAGIC = 0xD00DFEED
MAX_DTB_SIZE = 4 * 1024 * 1024
MAX_BOOT_MODULE_SIZE = 64 * 1024
HANDOFF_MAGIC = 0x464F524745484F46
HANDOFF_SIZE = 284
SERVICE_TABLE_SIZE = 128
REGION_ENTRY_SIZE = 24
MODULE_ENTRY_SIZE = 24

REGION_TYPE_IDS = {
    "usable": 1,
    "reserved": 2,
    "mmio": 3,
    "monitor": 4,
    "framebuffer": 5,
}
ATTR_BITS = {"read": 1, "write": 2, "execute": 4, "device": 8, "dma": 16}
SERVICE_BITS = {
    "console-write": 1 << 0,
    "console-read": 1 << 1,
    "console-flush": 1 << 2,
    "framebuffer-flush": 1 << 3,
    "interrupt-controller": 1 << 4,
    "watchdog-configure": 1 << 5,
    "watchdog-kick": 1 << 6,
}
MODULE_CAP_BITS = {"console": 1, "log": 2, "time": 4, "dt": 8, "state": 16, "host": 32}
HANDOFF_FLAGS = {
    "device-tree": 1 << 1,
    "framebuffer": 1 << 2,
    "runtime-input": 1 << 3,
    "timer": 1 << 4,
    "power": 1 << 5,
    "platform-services": 1 << 6,
    "module-policy": 1 << 7,
}
STATUS_VALUES = {"supported", "unsupported", "invalid", "unsafe", "not-tested"}


class LoaderSimulationError(ValueError):
    """Raised when the loader plan cannot be constructed safely."""


def _number(value: int | str) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ElfSegment:
    index: int
    offset: int
    virtual_address: int
    physical_address: int
    file_size: int
    memory_size: int
    flags: int
    alignment: int
    sha256: str

    @property
    def load_address(self) -> int:
        return self.physical_address or self.virtual_address


@dataclass(frozen=True)
class Placement:
    name: str
    kind: str
    base: int
    size: int
    sha256: str
    source: str | None = None


@dataclass(frozen=True)
class Check:
    identifier: str
    status: str
    summary: str
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.status not in STATUS_VALUES:
            raise ValueError(f"invalid conformance status {self.status}")


class ElfImage:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.data = path.read_bytes()
        if len(self.data) < ELF_HEADER.size:
            raise LoaderSimulationError("generic image is smaller than an ELF header")
        values = ELF_HEADER.unpack_from(self.data)
        ident = values[0]
        if ident[:4] != b"\x7fELF" or ident[4] != 2 or ident[5] != 1:
            raise LoaderSimulationError("generic image must be little-endian ELF64")
        self.elf_type = values[1]
        self.machine = values[2]
        self.entry = values[4]
        phoff, phentsize, phnum = values[5], values[9], values[10]
        if self.machine != EM_AARCH64:
            raise LoaderSimulationError("generic image is not AArch64")
        if phentsize != PROGRAM_HEADER.size or phnum == 0:
            raise LoaderSimulationError(
                "generic image has an unsupported program-header table"
            )
        if phoff > len(self.data) or phnum > (len(self.data) - phoff) // phentsize:
            raise LoaderSimulationError("generic image program headers are truncated")
        segments: list[ElfSegment] = []
        for index in range(phnum):
            fields = PROGRAM_HEADER.unpack_from(self.data, phoff + index * phentsize)
            p_type, flags, offset, vaddr, paddr, filesz, memsz, alignment = fields
            if p_type != PT_LOAD:
                continue
            if (
                memsz < filesz
                or offset > len(self.data)
                or filesz > len(self.data) - offset
            ):
                raise LoaderSimulationError(f"ELF load segment {index} is malformed")
            payload = self.data[offset : offset + filesz]
            segments.append(
                ElfSegment(
                    index,
                    offset,
                    vaddr,
                    paddr,
                    filesz,
                    memsz,
                    flags,
                    alignment,
                    _sha256(payload),
                )
            )
        if not segments:
            raise LoaderSimulationError("generic image contains no loadable segments")
        self.segments = tuple(segments)
        executable = [
            s
            for s in segments
            if s.flags & PF_X
            and s.load_address <= self.entry < s.load_address + s.memory_size
        ]
        if not executable:
            raise LoaderSimulationError(
                "ELF entry point is outside executable load segments"
            )


class SparseAllocator:
    def __init__(
        self, regions: list[dict[str, Any]], occupied: Iterable[tuple[int, int]]
    ):
        self.regions = regions
        self.occupied = sorted(list(occupied))

    def allocate(
        self,
        size: int,
        *,
        alignment: int = 16,
        allowed_types: tuple[str, ...] = ("usable", "reserved"),
    ) -> int:
        if size <= 0:
            raise LoaderSimulationError("cannot allocate an empty simulated object")
        for region in self.regions:
            if region["type"] not in allowed_types:
                continue
            attrs = set(region["attributes"])
            if not {"read", "write"}.issubset(attrs):
                continue
            start = _align(_number(region["base"]), alignment)
            end = _number(region["base"]) + _number(region["size"])
            while start + size <= end:
                collision = next(
                    (
                        (a, b)
                        for a, b in self.occupied
                        if start < b and a < start + size
                    ),
                    None,
                )
                if collision is None:
                    self.occupied.append((start, start + size))
                    self.occupied.sort()
                    return start
                start = _align(collision[1], alignment)
        raise LoaderSimulationError(f"no granted writable region can hold {size} bytes")


def _region_cover(
    regions: list[dict[str, Any]],
    base: int,
    size: int,
    required: set[str],
    types: set[str] | None = None,
) -> bool:
    end = base + size
    for region in regions:
        rb = _number(region["base"])
        re = rb + _number(region["size"])
        if rb <= base and end <= re and required.issubset(set(region["attributes"])):
            if types is None or region["type"] in types:
                return True
    return False


def _validate_dtb(path: pathlib.Path) -> bytes:
    data = path.read_bytes()
    if len(data) < 40 or len(data) > MAX_DTB_SIZE:
        raise LoaderSimulationError("DTB must contain 40 bytes to 4 MiB")
    magic, total_size = struct.unpack_from(">II", data)
    if magic != FDT_MAGIC or total_size < 40 or total_size > len(data):
        raise LoaderSimulationError("DTB header or total size is invalid")
    return data[:total_size]


def _callback_names(document: dict[str, Any]) -> list[str]:
    names: list[str] = []
    mapping = {
        "console-write": ("console_write",),
        "console-read": ("console_read",),
        "console-flush": ("console_flush",),
        "framebuffer-flush": ("framebuffer_flush",),
        "interrupt-controller": (
            "interrupt_ack",
            "interrupt_complete",
            "interrupt_set_enabled",
        ),
        "watchdog-configure": ("watchdog_configure",),
        "watchdog-kick": ("watchdog_kick",),
    }
    for service in document.get("services", []):
        names.extend(mapping[service])
    runtime = set(document.get("runtime_callbacks", []))
    if "input" in runtime:
        names.append("runtime_getc")
    if "timer" in runtime:
        names.extend(("timer_read", "timer_frequency"))
    if "power" in runtime:
        names.extend(("reboot", "halt"))
    return names


def _pack_services(document: dict[str, Any], callbacks: dict[str, int]) -> bytes:
    services = document.get("services", [])
    capability_mask = sum(SERVICE_BITS[name] for name in services)
    values = [
        1,
        SERVICE_TABLE_SIZE,
        capability_mask,
        0,
        callbacks.get("console_write", 0),
        callbacks.get("console_read", 0),
        callbacks.get("console_flush", 0),
        0,
        callbacks.get("framebuffer_flush", 0),
        0,
        callbacks.get("interrupt_ack", 0),
        callbacks.get("interrupt_complete", 0),
        callbacks.get("interrupt_set_enabled", 0),
        0,
        callbacks.get("watchdog_configure", 0),
        callbacks.get("watchdog_kick", 0),
        0,
    ]
    data = struct.pack("<IIQQ" + "Q" * 13, *values)
    if len(data) != SERVICE_TABLE_SIZE:
        raise AssertionError("platform service table size mismatch")
    return data


def _pack_handoff(
    document: dict[str, Any],
    pointers: dict[str, int],
    callback: dict[str, int],
    module_count: int,
) -> bytes:
    monitor = document["monitor"]
    runtime = set(document.get("runtime_callbacks", []))
    flags = 0
    if pointers.get("dtb"):
        flags |= HANDOFF_FLAGS["device-tree"]
    if document.get("framebuffer") is not None:
        flags |= HANDOFF_FLAGS["framebuffer"]
    if "input" in runtime:
        flags |= HANDOFF_FLAGS["runtime-input"]
    if "timer" in runtime:
        flags |= HANDOFF_FLAGS["timer"]
    if "power" in runtime:
        flags |= HANDOFF_FLAGS["power"]
    if document.get("services"):
        flags |= HANDOFF_FLAGS["platform-services"]
    if document.get("module_policy") is not None:
        flags |= HANDOFF_FLAGS["module-policy"]

    framebuffer = document.get("framebuffer") or {}
    policy = document.get("module_policy") or {}
    data = bytearray()
    data += struct.pack(
        "<QIIQQQIIQQQQ",
        HANDOFF_MAGIC,
        4,
        HANDOFF_SIZE,
        _number(monitor["base"]),
        _number(monitor["size"]),
        pointers["regions"],
        len(document["regions"]),
        0,
        pointers.get("dtb", 0),
        pointers.get("dtb_size", 0),
        0,
        0,
    )
    data += struct.pack(
        "<QQIIQIIIIQ",
        flags,
        pointers.get("modules", 0),
        module_count,
        0,
        _number(framebuffer.get("base", 0)),
        framebuffer.get("width", 0),
        framebuffer.get("height", 0),
        framebuffer.get("pixels_per_row", 0),
        framebuffer.get("pixel_format_id", 0),
        0x46425233344B4552,
    )
    data += struct.pack(
        "<" + "Q" * 9,
        callback.get("runtime_getc", 0),
        0,
        callback.get("timer_read", 0),
        callback.get("timer_frequency", 0),
        0,
        callback.get("reboot", 0),
        callback.get("halt", 0),
        0,
        0x41524D363447454E,
    )
    data += struct.pack(
        "<QIIIIQIIIHHIQQQ",
        pointers.get("services", 0),
        SERVICE_TABLE_SIZE if pointers.get("services") else 0,
        document["entry_exception_level"],
        document["page_granule"],
        document["boot_cpu_id"],
        _number(framebuffer.get("size", 0)),
        framebuffer.get("bytes_per_pixel", 0),
        framebuffer.get("rotation", 0),
        policy.get("allowed_capability_mask", 0),
        policy.get("dynamic_slots", 0),
        0,
        policy.get("instruction_budget", 0),
        _number(document["firmware_revision"]),
        0,
        0,
    )
    if len(data) != HANDOFF_SIZE:
        raise AssertionError(f"handoff size mismatch: {len(data)}")
    return bytes(data)


def _write_blob(output: pathlib.Path, name: str, data: bytes) -> dict[str, Any]:
    path = output / name
    path.write_bytes(data)
    return {"path": name, "size": len(data), "sha256": _sha256(data)}


def simulate_loader(
    handoff_path: pathlib.Path,
    image_path: pathlib.Path,
    output: pathlib.Path,
    *,
    dtb_path: pathlib.Path | None = None,
    module_paths: Iterable[pathlib.Path] = (),
) -> dict[str, Any]:
    document = load_and_validate(handoff_path)
    image = ElfImage(image_path)
    output.mkdir(parents=True, exist_ok=True)
    regions = document["regions"]
    monitor_base = _number(document["monitor"]["base"])
    monitor_size = _number(document["monitor"]["size"])
    monitor_end = monitor_base + monitor_size

    checks: list[Check] = [
        Check("handoff-schema", "supported", "handoff-v4 design validated"),
        Check(
            "elf-architecture",
            "supported",
            "ELF64 little-endian AArch64 image validated",
            {"entry": f"0x{image.entry:x}", "segments": len(image.segments)},
        ),
    ]
    occupied: list[tuple[int, int]] = []
    placements: list[Placement] = []
    max_segment_end = monitor_base
    for segment in image.segments:
        base = segment.load_address
        end = base + segment.memory_size
        if base < monitor_base or end > monitor_end:
            raise LoaderSimulationError(
                f"ELF segment {segment.index} is outside the monitor allocation"
            )
        required = {"read"}
        if segment.flags & PF_W:
            required.add("write")
        if segment.flags & PF_X:
            required.add("execute")
        if not _region_cover(regions, base, segment.memory_size, required, {"monitor"}):
            raise LoaderSimulationError(
                f"ELF segment {segment.index} lacks matching monitor-region permissions"
            )
        occupied.append((base, end))
        max_segment_end = max(max_segment_end, end)
        placements.append(
            Placement(
                f"elf-segment-{segment.index}",
                "monitor-segment",
                base,
                segment.memory_size,
                segment.sha256,
                image_path.name,
            )
        )
    checks.append(
        Check(
            "monitor-placement",
            "supported",
            "all ELF load segments fit the executable monitor region",
        )
    )

    callback_names = _callback_names(document)
    callbacks: dict[str, int] = {}
    callback_blob = bytearray()
    if callback_names:
        callback_base = _align(max_segment_end, 16)
        for name in callback_names:
            callbacks[name] = callback_base + len(callback_blob)
            callback_blob += struct.pack(
                "<II", 0xD421E240, 0xD65F03C0
            )  # brk #0xf12; ret
        if callback_base + len(callback_blob) > monitor_end:
            raise LoaderSimulationError(
                "monitor region has no room for synthetic callback stubs"
            )
        occupied.append((callback_base, callback_base + len(callback_blob)))
        placements.append(
            Placement(
                "callback-stubs",
                "synthetic-executable-stubs",
                callback_base,
                len(callback_blob),
                _sha256(callback_blob),
                None,
            )
        )
        checks.append(
            Check(
                "callback-materialization",
                "not-tested",
                "synthetic trap callbacks were materialized for offline structure validation",
                {"count": len(callback_names), "base": f"0x{callback_base:x}"},
            )
        )
    else:
        checks.append(
            Check(
                "callback-materialization",
                "unsupported",
                "handoff design declares no callback services",
            )
        )

    allocator = SparseAllocator(regions, occupied)
    region_blob = b"".join(
        struct.pack(
            "<QQII",
            _number(item["base"]),
            _number(item["size"]),
            REGION_TYPE_IDS[item["type"]],
            item["attribute_mask"],
        )
        for item in regions
    )
    region_address = allocator.allocate(len(region_blob), alignment=8)
    placements.append(
        Placement(
            "memory-regions",
            "handoff-metadata",
            region_address,
            len(region_blob),
            _sha256(region_blob),
            None,
        )
    )

    dtb = b""
    dtb_address = 0
    if dtb_path is not None:
        dtb = _validate_dtb(dtb_path)
        dtb_address = allocator.allocate(len(dtb), alignment=8)
        placements.append(
            Placement(
                "device-tree", "fdt", dtb_address, len(dtb), _sha256(dtb), dtb_path.name
            )
        )
        checks.append(
            Check(
                "device-tree",
                "supported",
                "DTB header, size, and placement validated",
                {"base": f"0x{dtb_address:x}", "size": len(dtb)},
            )
        )
    else:
        checks.append(
            Check("device-tree", "not-tested", "no DTB was supplied to the simulator")
        )

    module_records: list[tuple[pathlib.Path, bytes, int]] = []
    for raw_path in module_paths:
        path = pathlib.Path(raw_path)
        payload = path.read_bytes()
        if not payload or len(payload) > MAX_BOOT_MODULE_SIZE:
            raise LoaderSimulationError(
                f"boot module {path} must contain 1..{MAX_BOOT_MODULE_SIZE} bytes"
            )
        address = allocator.allocate(len(payload), alignment=16)
        module_records.append((path, payload, address))
        placements.append(
            Placement(
                path.name,
                "boot-module",
                address,
                len(payload),
                _sha256(payload),
                path.name,
            )
        )
    if module_records:
        checks.append(
            Check(
                "boot-modules",
                "supported",
                "boot modules fit granted readable memory",
                {"count": len(module_records)},
            )
        )
    else:
        checks.append(
            Check("boot-modules", "not-tested", "no boot modules were supplied")
        )

    module_blob = b"".join(
        struct.pack("<QQII", address, len(payload), 1, 0)
        for _, payload, address in module_records
    )
    module_address = (
        allocator.allocate(len(module_blob), alignment=8) if module_blob else 0
    )
    if module_blob:
        placements.append(
            Placement(
                "boot-module-table",
                "handoff-metadata",
                module_address,
                len(module_blob),
                _sha256(module_blob),
                None,
            )
        )

    service_blob = (
        _pack_services(document, callbacks) if document.get("services") else b""
    )
    service_address = (
        allocator.allocate(len(service_blob), alignment=8) if service_blob else 0
    )
    if service_blob:
        placements.append(
            Placement(
                "platform-services",
                "handoff-metadata",
                service_address,
                len(service_blob),
                _sha256(service_blob),
                None,
            )
        )

    handoff_address = allocator.allocate(HANDOFF_SIZE, alignment=16)
    pointers = {
        "regions": region_address,
        "modules": module_address,
        "services": service_address,
        "dtb": dtb_address,
        "dtb_size": len(dtb),
    }
    handoff_blob = _pack_handoff(document, pointers, callbacks, len(module_records))
    placements.append(
        Placement(
            "handoff-v4",
            "handoff-structure",
            handoff_address,
            len(handoff_blob),
            _sha256(handoff_blob),
            None,
        )
    )

    artifacts = [
        _write_blob(output, "handoff-v4.bin", handoff_blob),
        _write_blob(output, "memory-regions.bin", region_blob),
    ]
    if callback_blob:
        artifacts.append(
            _write_blob(output, "callback-stubs.bin", bytes(callback_blob))
        )
    if service_blob:
        artifacts.append(_write_blob(output, "platform-services.bin", service_blob))
    if module_blob:
        artifacts.append(_write_blob(output, "boot-modules.bin", module_blob))
    if dtb:
        artifacts.append(_write_blob(output, "device-tree.dtb", dtb))
    for path, payload, address in module_records:
        artifacts.append(
            _write_blob(output, f"module-{address:016x}-{path.name}", payload)
        )

    for region in regions:
        attrs = set(region["attributes"])
        if region["type"] in {"usable", "mmio"} and "execute" in attrs:
            checks.append(
                Check(
                    "writable-executable-regions",
                    "unsafe",
                    f"{region['type']} region is executable",
                    {"base": region["base"], "size": region["size"]},
                )
            )
            break
    else:
        checks.append(
            Check(
                "writable-executable-regions",
                "supported",
                "no usable or MMIO region is executable",
            )
        )

    runtime = set(document.get("runtime_callbacks", []))
    for feature in ("input", "timer", "power"):
        checks.append(
            Check(
                f"runtime-{feature}",
                "not-tested" if feature in runtime else "unsupported",
                (
                    "callback structure materialized but not executed"
                    if feature in runtime
                    else "callback not declared by the loader design"
                ),
            )
        )
    if "interrupt-controller" in document.get("services", []):
        checks.append(
            Check(
                "interrupt-controller",
                "not-tested",
                "IRQ callbacks materialized; delivery requires a runtime target",
            )
        )
    else:
        checks.append(
            Check(
                "interrupt-controller",
                "unsupported",
                "loader design has no interrupt-controller service",
            )
        )

    normalized_path = output / "normalized-handoff.json"
    normalized_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts.append(
        {
            "path": normalized_path.name,
            "size": normalized_path.stat().st_size,
            "sha256": _sha256(normalized_path.read_bytes()),
        }
    )
    sparse_plan = {
        "schema_version": 1,
        "address_space": "AArch64 physical",
        "regions": document["regions"],
        "placements": [
            asdict(item) | {"base": f"0x{item.base:x}"}
            for item in sorted(placements, key=lambda value: value.base)
        ],
    }
    sparse_path = output / "sparse-memory.json"
    sparse_path.write_text(
        json.dumps(sparse_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts.append(
        {
            "path": sparse_path.name,
            "size": sparse_path.stat().st_size,
            "sha256": _sha256(sparse_path.read_bytes()),
        }
    )

    invalid_or_unsafe = [
        item for item in checks if item.status in {"invalid", "unsafe"}
    ]
    report = {
        "schema_version": 1,
        "project": "FBR34KER",
        "version": RELEASE_VERSION,
        "result": "fail" if invalid_or_unsafe else "pass",
        "offline_only": True,
        "entry_point": f"0x{image.entry:x}",
        "handoff_address": f"0x{handoff_address:x}",
        "image": {
            "path": str(image_path),
            "sha256": _sha256(image.data),
            "segments": [asdict(item) for item in image.segments],
        },
        "placements": [
            asdict(item) | {"base": f"0x{item.base:x}"}
            for item in sorted(placements, key=lambda value: value.base)
        ],
        "checks": [asdict(item) for item in checks],
        "artifacts": artifacts,
    }
    report_path = output / "loader-conformance.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def format_report(report: dict[str, Any]) -> str:
    rows = [f"FBR34KER loader conformance: {report.get('result', 'unknown').upper()}"]
    rows.append(f"Entry point: {report.get('entry_point', 'unknown')}")
    rows.append(f"Handoff: {report.get('handoff_address', 'unknown')}")
    for check in report.get("checks", []):
        rows.append(f"[{check['status']:11}] {check['identifier']}: {check['summary']}")
    return "\n".join(rows) + "\n"


def load_report(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LoaderSimulationError(f"cannot read loader report: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("checks"), list):
        raise LoaderSimulationError("loader report has an invalid schema")
    for check in value["checks"]:
        if not isinstance(check, dict) or check.get("status") not in STATUS_VALUES:
            raise LoaderSimulationError("loader report contains an invalid check")
    return value
