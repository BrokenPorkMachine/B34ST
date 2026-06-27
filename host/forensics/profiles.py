"""Acquisition profiles defining forensic data collection scope.

Pre-built profiles for common scenarios (quick triage, full acquisition,
memory-only, storage-only) and profile loading/serialization.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
from typing import Any


class ProfileError(RuntimeError):
    pass


@dataclasses.dataclass
class AcquisitionProfile:
    """Defines the scope and categories of a forensic acquisition."""
    name: str = "default"
    description: str = "Default acquisition profile"
    categories: set[str] = dataclasses.field(default_factory=lambda: {
        "memory", "filesystem", "network",
    })
    memory_regions: list[str] = dataclasses.field(default_factory=list)
    filesystem_paths: list[str] = dataclasses.field(default_factory=list)
    storage_partitions: list[str] = dataclasses.field(default_factory=list)
    network_capture: bool = True
    compress: bool = False
    sparse: bool = True
    max_bytes: int = 0
    operator_required: bool = True
    authorization_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcquisitionProfile:
        data = dict(data)
        if "categories" in data:
            data["categories"] = set(data["categories"])
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


def builtin_profiles() -> dict[str, AcquisitionProfile]:
    return {
        "quick": AcquisitionProfile(
            name="quick",
            description="Quick triage: filesystem listing and network state only",
            categories={"filesystem", "network"},
            filesystem_paths=["/", "/etc", "/var"],
            network_capture=True,
            max_bytes=16 * 1024 * 1024,
        ),
        "full": AcquisitionProfile(
            name="full",
            description="Full forensic acquisition: memory, storage, filesystem, network",
            categories={"memory", "storage", "filesystem", "network"},
            filesystem_paths=["/", "/etc", "/var", "/System", "/usr"],
            network_capture=True,
            compress=True,
            sparse=True,
        ),
        "memory-only": AcquisitionProfile(
            name="memory-only",
            description="Memory-only acquisition: capture RAM contents with page hashing",
            categories={"memory"},
            memory_regions=["all"],
            network_capture=False,
        ),
        "storage-only": AcquisitionProfile(
            name="storage-only",
            description="Storage-only acquisition: partition imaging with block hashing",
            categories={"storage"},
            storage_partitions=["all"],
            network_capture=False,
            compress=True,
            sparse=True,
        ),
        "filesystem-only": AcquisitionProfile(
            name="filesystem-only",
            description="Filesystem-only acquisition: recursive file listing and extraction",
            categories={"filesystem"},
            filesystem_paths=["/", "/etc", "/var", "/System", "/usr"],
            network_capture=False,
        ),
        "network-only": AcquisitionProfile(
            name="network-only",
            description="Network state capture: interfaces, connections, routing, DNS",
            categories={"network"},
            network_capture=True,
        ),
    }


def load_profile(path: pathlib.Path) -> AcquisitionProfile:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ProfileError(f"failed to load profile {path}: {exc}") from exc
    return AcquisitionProfile.from_dict(data)


def save_profile(profile: AcquisitionProfile, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
