#!/usr/bin/env python3
"""Build and inspect deterministic FBR34KER recovery boot-image bundles."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import shutil
import struct
import sys
from typing import Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAGIC = b"FBRI"
FORMAT_VERSION = 1
HEADER_SIZE = 128
MANIFEST_CAPACITY = 16 * 1024
ALIGNMENT = 4096
HEADER = struct.Struct("<4sHHIIIIQQQQQ32s32s")
FAMILY_IDS = {"generic": 0, "a12": 1, "a12x": 2, "a13": 3, "a14": 4, "m1": 5, "a15": 6, "m2": 7}
ID_FAMILIES = {value: key for key, value in FAMILY_IDS.items()}
MAX_PROFILE_SIZE = 256 * 1024
MAX_COMPONENTS = 8
MAX_IMAGE_SIZE = 64 * 1024 * 1024
MAX_COMPONENT_SIZE = 32 * 1024 * 1024
UINT64_MAX = (1 << 64) - 1
ROLE_PATTERN = __import__("re").compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
HASH_PATTERN = __import__("re").compile(r"^[0-9a-f]{64}$")


class BootImageError(ValueError):
    pass


def align(value: int, boundary: int = ALIGNMENT) -> int:
    if value < 0 or boundary <= 0 or boundary & (boundary - 1):
        raise BootImageError("invalid alignment request")
    return (value + boundary - 1) & ~(boundary - 1)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_int(value: str | int | None, *, field: str) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        result = value
    else:
        try:
            result = int(value, 0)
        except ValueError as exc:
            raise BootImageError(f"{field} must be an integer") from exc
    if result < 0 or result > 0xFFFFFFFFFFFFFFFF:
        raise BootImageError(f"{field} is outside uint64 range")
    return result


def load_profile(path: pathlib.Path) -> dict[str, object]:
    if not path.is_file():
        raise BootImageError(f"profile does not exist: {path}")
    if path.stat().st_size > MAX_PROFILE_SIZE:
        raise BootImageError("profile is too large")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BootImageError(f"invalid profile: {exc}") from exc
    if not isinstance(profile, dict) or profile.get("schema_version") != 1:
        raise BootImageError("unsupported recovery profile schema")
    family = profile.get("family")
    if family not in FAMILY_IDS or family == "generic":
        raise BootImageError(f"profile family must be one of {', '.join(f for f in FAMILY_IDS if f != 'generic')}")
    cpids = profile.get("cpids")
    if not isinstance(cpids, list) or not cpids:
        raise BootImageError("profile must contain at least one CPID")
    for value in cpids:
        parse_int(value, field="CPID")
    max_size = profile.get("max_image_size", MAX_IMAGE_SIZE)
    if not isinstance(max_size, int) or max_size <= 0 or max_size > MAX_IMAGE_SIZE:
        raise BootImageError("invalid max_image_size")
    adapter_abi = profile.get("adapter_abi", 1)
    if adapter_abi != 1:
        raise BootImageError("unsupported first-stage adapter ABI")
    maturity = profile.get("maturity", "simulated")
    allowed_maturity = {
        "unverified", "simulator-validated", "hardware-observed", "hardware-verified",
        "simulated", "qemu-verified", "bridge-verified", "console-verified",
        "boot-evidence-verified", "physical-runtime-verified",
    }
    if maturity not in allowed_maturity:
        raise BootImageError("invalid profile maturity")
    if profile.get("physical_execution_verified", False) not in {True, False}:
        raise BootImageError("physical_execution_verified must be boolean")
    stages = profile.get("required_bringup_stages", [])
    allowed_stages = {"console", "board-inventory", "memory-map", "timer", "interrupts", "watchdog", "boot-evidence", "reboot"}
    if not isinstance(stages, list) or not all(isinstance(value, str) and value in allowed_stages for value in stages):
        raise BootImageError("invalid required_bringup_stages")
    products = profile.get("product_types", [])
    if not isinstance(products, list) or not all(isinstance(value, str) and value and len(value) <= 32 for value in products):
        raise BootImageError("invalid product_types")
    boards = profile.get("board_configurations", [])
    if not isinstance(boards, list) or not all(isinstance(value, str) and value and len(value) <= 32 for value in boards):
        raise BootImageError("invalid board_configurations")
    exact = profile.get("requires_exact_product", False)
    if not isinstance(exact, bool) or (exact and not products):
        raise BootImageError("exact product profiles require product_types")
    memory_policy = profile.get("memory_policy", "adapter-reported-only")
    if memory_policy not in {"adapter-reported-only"}:
        raise BootImageError("unsupported memory_policy")
    transports = profile.get("console_transports", [])
    if not isinstance(transports, list) or not all(isinstance(value, str) and value for value in transports):
        raise BootImageError("invalid console_transports")
    return profile


@dataclasses.dataclass(frozen=True)
class Component:
    role: str
    path: pathlib.Path
    load_address: int = 0
    entry_address: int = 0


def _component_record(component: Component, offset: int, data: bytes) -> dict[str, object]:
    if not component.role or len(component.role) > 32:
        raise BootImageError("component role must be 1..32 characters")
    return {
        "role": component.role,
        "name": component.path.name,
        "offset": offset,
        "size": len(data),
        "sha256": sha256_bytes(data),
        "load_address": component.load_address,
        "entry_address": component.entry_address,
    }


def build_image(
    output: pathlib.Path,
    profile_path: pathlib.Path,
    components: Iterable[Component],
    *,
    raw_output: pathlib.Path | None = None,
) -> dict[str, object]:
    profile = load_profile(profile_path)
    items = list(components)
    if not 1 <= len(items) <= MAX_COMPONENTS:
        raise BootImageError(f"component count must be 1..{MAX_COMPONENTS}")
    role_names = [item.role for item in items]
    if len(set(role_names)) != len(role_names):
        raise BootImageError("component roles must be unique")

    payload_offset = align(HEADER_SIZE + MANIFEST_CAPACITY)
    cursor = payload_offset
    data_items: list[tuple[Component, bytes, int]] = []
    records: list[dict[str, object]] = []
    for item in items:
        if not ROLE_PATTERN.fullmatch(item.role):
            raise BootImageError("component role must match [a-z0-9][a-z0-9._-]{0,31}")
        if item.load_address < 0 or item.load_address > UINT64_MAX:
            raise BootImageError(f"{item.role} load address is outside uint64 range")
        if item.entry_address < 0 or item.entry_address > UINT64_MAX:
            raise BootImageError(f"{item.role} entry address is outside uint64 range")
        path = item.path.resolve()
        if not path.is_file():
            raise BootImageError(f"component does not exist: {item.path}")
        data = path.read_bytes()
        if not data:
            raise BootImageError(f"component is empty: {item.path}")
        if len(data) > MAX_COMPONENT_SIZE:
            raise BootImageError(f"component exceeds {MAX_COMPONENT_SIZE} bytes: {item.path}")
        if item.load_address and item.load_address + len(data) > UINT64_MAX + 1:
            raise BootImageError(f"{item.role} load range overflows uint64")
        if item.entry_address and not (item.load_address <= item.entry_address < item.load_address + len(data)):
            raise BootImageError(f"{item.role} entry address is outside its load range")
        cursor = align(cursor)
        data_items.append((item, data, cursor))
        records.append(_component_record(item, cursor, data))
        cursor += len(data)
    total_size = align(cursor)
    if total_size > int(profile.get("max_image_size", MAX_IMAGE_SIZE)):
        raise BootImageError("boot image exceeds profile max_image_size")

    manifest: dict[str, object] = {
        "schema_version": 1,
        "format": "fbri-v1",
        "project": "FBR34KER",
        "release_version": "0.3.0",
        "profile_id": profile["profile_id"],
        "family": profile["family"],
        "cpids": profile["cpids"],
        "execution_contract": profile.get("execution_contract", "external-authorized-loader"),
        "direct_stock_iboot_compatible": False,
        "alignment": ALIGNMENT,
        "image_size": total_size,
        "components": records,
    }
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    if len(manifest_bytes) > MANIFEST_CAPACITY:
        raise BootImageError("manifest exceeds fixed capacity")

    image = bytearray(total_size)
    image[HEADER_SIZE:HEADER_SIZE + len(manifest_bytes)] = manifest_bytes
    for item, data, offset in data_items:
        del item
        image[offset:offset + len(data)] = data
    payload_size = total_size - payload_offset
    payload_hash = hashlib.sha256(image[payload_offset:]).digest()
    manifest_hash = hashlib.sha256(manifest_bytes).digest()
    header = HEADER.pack(
        MAGIC,
        FORMAT_VERSION,
        HEADER_SIZE,
        0,
        FAMILY_IDS[str(profile["family"])],
        len(records),
        MANIFEST_CAPACITY,
        total_size,
        HEADER_SIZE,
        len(manifest_bytes),
        payload_offset,
        payload_size,
        manifest_hash,
        payload_hash,
    )
    if len(header) != HEADER_SIZE:
        raise AssertionError("boot image header size mismatch")
    image[:HEADER_SIZE] = header

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(image)
    temporary.replace(output)

    sidecar = output.with_suffix(output.suffix + ".json")
    sidecar.write_text(json.dumps({
        **manifest,
        "image_sha256": sha256_file(output),
        "profile_sha256": sha256_file(profile_path),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if raw_output is not None:
        monitor = next((item for item in items if item.role == "monitor"), None)
        if monitor is None:
            raise BootImageError("--raw-output requires a monitor component")
        raw_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(monitor.path, raw_output)
        raw_sidecar = raw_output.with_suffix(raw_output.suffix + ".json")
        raw_sidecar.write_text(json.dumps({
            "schema_version": 1,
            "format": "raw-aarch64-payload",
            "family": profile["family"],
            "profile_id": profile["profile_id"],
            "payload": raw_output.name,
            "size": raw_output.stat().st_size,
            "sha256": sha256_file(raw_output),
            "execution_contract": "external-authorized-loader",
            "direct_stock_iboot_compatible": False,
            "load_address": monitor.load_address,
            "entry_address": monitor.entry_address,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return inspect_image(output)


def inspect_image(path: pathlib.Path) -> dict[str, object]:
    if not path.is_file():
        raise BootImageError(f"image does not exist: {path}")
    size = path.stat().st_size
    if size < HEADER_SIZE or size > MAX_IMAGE_SIZE:
        raise BootImageError("invalid boot image size")
    data = path.read_bytes()
    try:
        (magic, version, header_size, flags, family_id, count, manifest_capacity,
         total_size, manifest_offset, manifest_size, payload_offset, payload_size,
         manifest_hash, payload_hash) = HEADER.unpack_from(data)
    except struct.error as exc:
        raise BootImageError("truncated boot image header") from exc
    if magic != MAGIC or version != FORMAT_VERSION or header_size != HEADER_SIZE:
        raise BootImageError("unsupported boot image header")
    if flags != 0:
        raise BootImageError("unknown boot image flags")
    if family_id not in ID_FAMILIES:
        raise BootImageError("unknown boot image family")
    if count < 1 or count > MAX_COMPONENTS:
        raise BootImageError("invalid component count")
    if manifest_capacity != MANIFEST_CAPACITY:
        raise BootImageError("unexpected manifest capacity")
    if total_size != len(data) or total_size % ALIGNMENT:
        raise BootImageError("invalid total image size")
    if manifest_offset != HEADER_SIZE or manifest_size <= 0 or manifest_size > manifest_capacity:
        raise BootImageError("invalid manifest bounds")
    if manifest_offset + manifest_size > HEADER_SIZE + manifest_capacity:
        raise BootImageError("manifest range overflows its fixed capacity")
    if payload_offset != align(HEADER_SIZE + manifest_capacity):
        raise BootImageError("invalid payload offset")
    if payload_size != total_size - payload_offset:
        raise BootImageError("invalid payload size")
    manifest_bytes = data[manifest_offset:manifest_offset + manifest_size]
    if hashlib.sha256(manifest_bytes).digest() != manifest_hash:
        raise BootImageError("manifest hash mismatch")
    if hashlib.sha256(data[payload_offset:]).digest() != payload_hash:
        raise BootImageError("payload hash mismatch")
    try:
        manifest = json.loads(manifest_bytes.decode("ascii"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BootImageError("invalid manifest JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != "fbri-v1":
        raise BootImageError("invalid embedded manifest")
    required_manifest = {"schema_version", "format", "project", "release_version", "profile_id", "family", "cpids", "execution_contract", "direct_stock_iboot_compatible", "alignment", "image_size", "components"}
    if set(manifest) != required_manifest:
        raise BootImageError("manifest has missing or unknown fields")
    if manifest.get("schema_version") != 1 or manifest.get("project") != "FBR34KER":
        raise BootImageError("invalid manifest identity")
    if not isinstance(manifest.get("release_version"), str) or len(manifest["release_version"]) > 32:
        raise BootImageError("invalid manifest release version")
    if not isinstance(manifest.get("profile_id"), str) or not manifest["profile_id"] or len(manifest["profile_id"]) > 96:
        raise BootImageError("invalid manifest profile id")
    if not isinstance(manifest.get("cpids"), list) or not manifest["cpids"]:
        raise BootImageError("invalid manifest CPID list")
    for value in manifest["cpids"]:
        parse_int(value, field="manifest CPID")
    if manifest.get("direct_stock_iboot_compatible") is not False:
        raise BootImageError("stock iBoot compatibility flag must remain false")
    if manifest.get("alignment") != ALIGNMENT or manifest.get("image_size") != total_size:
        raise BootImageError("manifest layout metadata mismatch")
    if any(data[manifest_offset + manifest_size:payload_offset]):
        raise BootImageError("non-zero bytes in reserved manifest capacity")
    if manifest.get("family") != ID_FAMILIES[family_id]:
        raise BootImageError("family mismatch between header and manifest")
    components = manifest.get("components")
    if not isinstance(components, list) or len(components) != count:
        raise BootImageError("component table mismatch")
    occupied: list[tuple[int, int]] = []
    roles: set[str] = set()
    expected_fields = {"role", "name", "offset", "size", "sha256", "load_address", "entry_address"}
    for record in components:
        if not isinstance(record, dict) or set(record) != expected_fields:
            raise BootImageError("invalid component record")
        role = record.get("role")
        name = record.get("name")
        digest = record.get("sha256")
        if not isinstance(role, str) or not ROLE_PATTERN.fullmatch(role) or role in roles:
            raise BootImageError("invalid or duplicate component role")
        roles.add(role)
        if (not isinstance(name, str) or not name or len(name) > 128 or
                "/" in name or "\\" in name or name in {".", ".."} or
                pathlib.PurePath(name).name != name):
            raise BootImageError("invalid component name")
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            raise BootImageError("invalid component hash")
        offset = record.get("offset")
        length = record.get("size")
        if not isinstance(offset, int) or not isinstance(length, int) or length <= 0 or length > MAX_COMPONENT_SIZE:
            raise BootImageError("invalid component bounds")
        end = offset + length
        if offset < payload_offset or end > total_size or offset % ALIGNMENT:
            raise BootImageError("component is outside the payload area")
        if any(offset < existing_end and end > existing_start for existing_start, existing_end in occupied):
            raise BootImageError("overlapping components")
        load_address = record.get("load_address")
        entry_address = record.get("entry_address")
        if not isinstance(load_address, int) or not 0 <= load_address <= UINT64_MAX:
            raise BootImageError("invalid component load address")
        if not isinstance(entry_address, int) or not 0 <= entry_address <= UINT64_MAX:
            raise BootImageError("invalid component entry address")
        if load_address and load_address + length > UINT64_MAX + 1:
            raise BootImageError("component load range overflows uint64")
        if entry_address and not (load_address <= entry_address < load_address + length):
            raise BootImageError("component entry address is outside its load range")
        occupied.append((offset, end))
        if sha256_bytes(data[offset:end]) != digest:
            raise BootImageError(f"component hash mismatch: {role}")
    if "monitor" not in roles:
        raise BootImageError("boot image has no monitor component")
    for (_, end), (next_start, _) in zip(sorted(occupied), sorted(occupied)[1:]):
        if any(data[end:next_start]):
            raise BootImageError("non-zero bytes in component alignment padding")
    if occupied and any(data[max(end for _, end in occupied):total_size]):
        raise BootImageError("non-zero bytes after final component")
    return {
        "path": str(path),
        "size": len(data),
        "sha256": sha256_file(path),
        "family": ID_FAMILIES[family_id],
        "component_count": count,
        "manifest": manifest,
    }


def _component(role: str, path: pathlib.Path | None, load: str | None = None,
               entry: str | None = None) -> Component | None:
    if path is None:
        return None
    return Component(role, path, parse_int(load, field=f"{role} load address"),
                     parse_int(entry, field=f"{role} entry address"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="create a deterministic boot.img bundle")
    build.add_argument("--profile", type=pathlib.Path, required=True)
    build.add_argument("--monitor", type=pathlib.Path, required=True)
    build.add_argument("--monitor-load")
    build.add_argument("--monitor-entry")
    build.add_argument("--handoff", type=pathlib.Path)
    build.add_argument("--module", type=pathlib.Path)
    build.add_argument("--dtb", type=pathlib.Path)
    build.add_argument("--stage0", type=pathlib.Path,
                       help="optional externally supplied authorized first-stage payload")
    build.add_argument("--output", type=pathlib.Path, required=True)
    build.add_argument("--raw-output", type=pathlib.Path)
    inspect = sub.add_parser("inspect", help="validate and display a boot image")
    inspect.add_argument("image", type=pathlib.Path)
    inspect.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            components = [
                _component("stage0", args.stage0),
                _component("monitor", args.monitor, args.monitor_load, args.monitor_entry),
                _component("handoff", args.handoff),
                _component("dtb", args.dtb),
                _component("module", args.module),
            ]
            result = build_image(args.output, args.profile,
                                 [item for item in components if item is not None],
                                 raw_output=args.raw_output)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        result = inspect_image(args.image)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"FBR34KER boot image: {args.image}")
            print(f"family: {result['family']}")
            print(f"size: {result['size']}")
            print(f"sha256: {result['sha256']}")
            for component in result["manifest"]["components"]:
                print(f"- {component['role']}: offset={component['offset']} size={component['size']} sha256={component['sha256']}")
        return 0
    except (BootImageError, OSError) as exc:
        print(f"boot image error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
