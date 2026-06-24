#!/usr/bin/env python3
"""Validation of declarative FBR34KER deployment profiles."""
from __future__ import annotations

import dataclasses
import json
import pathlib
import re
from typing import Any

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ALLOWED_KINDS = {"loader", "monitor", "dtb", "module", "configuration"}
MAX_REGIONS = 16
MAX_REGION_SIZE = 512 * 1024 * 1024
MAX_ARTIFACT_SIZE = 64 * 1024 * 1024


class ProfileError(ValueError):
    """Raised when a deployment profile violates the bounded schema."""


def parse_integer(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ProfileError(f"{field} must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError as exc:
            raise ProfileError(f"{field} is not an integer") from exc
    else:
        raise ProfileError(f"{field} must be an integer or numeric string")
    if not 0 <= result <= 0xFFFFFFFFFFFFFFFF:
        raise ProfileError(f"{field} exceeds 64-bit address space")
    return result


@dataclasses.dataclass(frozen=True)
class DeploymentRegion:
    name: str
    base: int
    size: int
    kinds: frozenset[str]

    @property
    def end(self) -> int:
        return self.base + self.size

    def contains(self, address: int, size: int, kind: str) -> bool:
        if kind not in self.kinds or size < 0:
            return False
        end = address + size
        return address >= self.base and end >= address and end <= self.end


@dataclasses.dataclass(frozen=True)
class DeploymentProfile:
    name: str
    board_compatible: tuple[str, ...]
    max_artifact_size: int
    max_total_size: int
    entry_alignment: int
    regions: tuple[DeploymentRegion, ...]

    def region_for(self, address: int, size: int, kind: str) -> DeploymentRegion:
        matches = [region for region in self.regions if region.contains(address, size, kind)]
        if len(matches) != 1:
            raise ProfileError(
                f"{kind} artifact range 0x{address:x}+0x{size:x} is not contained "
                "in exactly one permitted deployment region"
            )
        return matches[0]


def _require_name(value: object, field: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ProfileError(f"{field} must match {_NAME.pattern}")
    return value


def validate_profile(data: Any) -> DeploymentProfile:
    if not isinstance(data, dict):
        raise ProfileError("deployment profile root must be an object")
    allowed = {
        "schema_version", "name", "board_compatible", "max_artifact_size",
        "max_total_size", "entry_alignment", "deployment_regions",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ProfileError("unknown deployment profile fields: " + ", ".join(unknown))
    if data.get("schema_version") != 1:
        raise ProfileError("deployment profile schema_version must be 1")
    name = _require_name(data.get("name"), "name")
    compatibles = data.get("board_compatible")
    if not isinstance(compatibles, list) or not compatibles or len(compatibles) > 16:
        raise ProfileError("board_compatible must contain 1 to 16 strings")
    compatible_values: list[str] = []
    for index, value in enumerate(compatibles):
        if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 127:
            raise ProfileError(f"board_compatible[{index}] is invalid")
        compatible_values.append(value)
    max_artifact = parse_integer(data.get("max_artifact_size", MAX_ARTIFACT_SIZE),
                                 "max_artifact_size")
    if not 1 <= max_artifact <= MAX_ARTIFACT_SIZE:
        raise ProfileError(f"max_artifact_size must be 1..{MAX_ARTIFACT_SIZE}")
    max_total = parse_integer(data.get("max_total_size", MAX_ARTIFACT_SIZE),
                              "max_total_size")
    if not max_artifact <= max_total <= MAX_ARTIFACT_SIZE * 4:
        raise ProfileError("max_total_size must be >= max_artifact_size and bounded")
    alignment = parse_integer(data.get("entry_alignment", 4), "entry_alignment")
    if alignment == 0 or alignment > 65536 or alignment & (alignment - 1):
        raise ProfileError("entry_alignment must be a power of two no greater than 65536")
    regions_data = data.get("deployment_regions")
    if not isinstance(regions_data, list) or not 1 <= len(regions_data) <= MAX_REGIONS:
        raise ProfileError(f"deployment_regions must contain 1 to {MAX_REGIONS} entries")
    regions: list[DeploymentRegion] = []
    for index, raw in enumerate(regions_data):
        if not isinstance(raw, dict):
            raise ProfileError(f"deployment_regions[{index}] must be an object")
        unknown_region = sorted(set(raw) - {"name", "base", "size", "artifact_kinds"})
        if unknown_region:
            raise ProfileError(f"deployment_regions[{index}] has unknown fields: " +
                               ", ".join(unknown_region))
        region_name = _require_name(raw.get("name"), f"deployment_regions[{index}].name")
        base = parse_integer(raw.get("base"), f"deployment_regions[{index}].base")
        size = parse_integer(raw.get("size"), f"deployment_regions[{index}].size")
        if not 1 <= size <= MAX_REGION_SIZE or base + size > 0x10000000000000000:
            raise ProfileError(f"deployment_regions[{index}] range is invalid")
        kinds_raw = raw.get("artifact_kinds")
        if not isinstance(kinds_raw, list) or not kinds_raw:
            raise ProfileError(f"deployment_regions[{index}].artifact_kinds must be non-empty")
        kinds = frozenset(kinds_raw)
        if not all(isinstance(kind, str) for kind in kinds) or not kinds <= ALLOWED_KINDS:
            raise ProfileError(f"deployment_regions[{index}] contains unsupported artifact kinds")
        regions.append(DeploymentRegion(region_name, base, size, kinds))
    for left_index, left in enumerate(regions):
        for right in regions[left_index + 1:]:
            if left.base < right.end and right.base < left.end:
                raise ProfileError(f"deployment regions {left.name} and {right.name} overlap")
    return DeploymentProfile(
        name=name,
        board_compatible=tuple(compatible_values),
        max_artifact_size=max_artifact,
        max_total_size=max_total,
        entry_alignment=alignment,
        regions=tuple(regions),
    )


def load_profile(path: pathlib.Path) -> DeploymentProfile:
    try:
        if path.stat().st_size > 128 * 1024:
            raise ProfileError("deployment profile exceeds 131072 bytes")
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProfileError(f"cannot read deployment profile: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"deployment profile is not valid JSON: {exc}") from exc
    return validate_profile(data)
