"""Storage acquisition for forensic capture of NAND and partition data.

# SPDX-License-Identifier: BSD-2-Clause
Supports partition enumeration and block-level imaging with integrity
hashing via wire protocol commands.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import pathlib
from typing import Any, Callable


class StorageAcquisitionError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class StoragePartition:
    """Describes a storage partition to acquire."""

    name: str
    device: str
    size: int
    offset: int = 0
    fs_type: str = ""
    description: str = ""
    critical: bool = False


class StorageAcquisitor:
    """Acquires storage/partition data with block-level integrity verification.

    Uses a caller-provided read function that abstracts the transport
    (wire protocol commands or vendor requests).
    """

    BLOCK_SIZE = 65536

    def __init__(
        self,
        read_fn: Callable[[str, int, int], bytes],
        *,
        enumerate_fn: Callable[[], list[StoragePartition]] | None = None,
    ):
        self._read_fn = read_fn
        self._enumerate_fn = enumerate_fn

    def enumerate_partitions(self) -> list[StoragePartition]:
        if self._enumerate_fn is not None:
            return self._enumerate_fn()
        return []

    def acquire_partition(
        self,
        partition: StoragePartition,
        output_dir: pathlib.Path,
        *,
        compress: bool = False,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        part_dir = output_dir / f"storage-{partition.name}"
        part_dir.mkdir(exist_ok=True)

        blocks: list[dict[str, Any]] = []
        sha256_all = hashlib.sha256()
        total_read = 0
        errors: list[str] = []
        block_size = self.BLOCK_SIZE
        offset = 0

        while offset < partition.size:
            chunk_size = min(block_size, partition.size - offset)
            try:
                data = self._read_fn(partition.device, offset, chunk_size)
                if not data:
                    errors.append(f"empty read at offset 0x{offset:x}")
                    offset += chunk_size
                    continue
            except (OSError, RuntimeError) as exc:
                errors.append(f"read error at offset 0x{offset:x}: {exc}")
                offset += chunk_size
                continue

            sha256_all.update(data)
            block_hash = hashlib.sha256(data).hexdigest()
            block_file = part_dir / f"block-0x{offset:016x}.bin"
            block_file.write_bytes(data)

            blocks.append(
                {
                    "offset": offset,
                    "size": len(data),
                    "sha256": block_hash,
                    "file": block_file.name,
                }
            )
            total_read += len(data)
            offset += chunk_size

        manifest = {
            "partition": {
                "name": partition.name,
                "device": partition.device,
                "size": partition.size,
                "offset": partition.offset,
                "fs_type": partition.fs_type,
                "description": partition.description,
                "critical": partition.critical,
            },
            "acquisition": {
                "timestamp": dt.datetime.now()
                .astimezone()
                .isoformat(timespec="seconds"),
                "total_bytes": total_read,
                "block_count": len(blocks),
                "error_count": len(errors),
                "block_size": block_size,
                "full_sha256": sha256_all.hexdigest(),
            },
            "blocks": blocks,
            "errors": errors,
        }

        manifest_path = part_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest

    def acquire_partition_list(
        self,
        partitions: list[StoragePartition],
        output_dir: pathlib.Path,
    ) -> list[dict[str, Any]]:
        results = []
        for part in partitions:
            try:
                result = self.acquire_partition(part, output_dir)
                results.append(result)
            except (OSError, RuntimeError) as exc:
                results.append(
                    {
                        "partition": {"name": part.name, "device": part.device},
                        "error": str(exc),
                    }
                )
        return results
