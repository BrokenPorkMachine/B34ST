"""Memory acquisition for forensic capture of RAM contents.

Supports region-based acquisition with page-level hashing via
USB vendor requests or wire protocol commands.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import pathlib
from typing import Any, Callable


class MemoryAcquisitionError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class MemoryRegion:
    """Describes a memory region to acquire."""

    name: str
    base: int
    size: int
    description: str = ""
    critical: bool = False


class MemoryAcquisitor:
    """Acquires memory regions from a target device with integrity verification.

    Uses a caller-provided read function that abstracts the transport
    (USB vendor requests, wire protocol, serial console commands).
    """

    BLOCK_SIZE = 4096

    def __init__(
        self,
        read_fn: Callable[[int, int], bytes],
        *,
        max_chunk: int = 0x8000,
    ):
        self._read_fn = read_fn
        self._max_chunk = max_chunk

    def acquire_region(
        self,
        region: MemoryRegion,
        output_dir: pathlib.Path,
        *,
        compress: bool = False,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        region_dir = output_dir / f"memory-{region.name}"
        region_dir.mkdir(exist_ok=True)

        pages: list[dict[str, Any]] = []
        sha256_all = hashlib.sha256()
        total_read = 0
        errors: list[str] = []
        base = region.base
        size = region.size

        offset = 0
        while offset < size:
            chunk_size = min(self._max_chunk, size - offset)
            try:
                data = self._read_fn(base + offset, chunk_size)
                if not data:
                    errors.append(f"empty read at offset 0x{offset:x}")
                    offset += chunk_size
                    continue
            except (OSError, RuntimeError) as exc:
                errors.append(f"read error at offset 0x{offset:x}: {exc}")
                offset += chunk_size
                continue

            sha256_all.update(data)
            page_hash = hashlib.sha256(data).hexdigest()
            page_file = region_dir / f"page-0x{base + offset:016x}-{chunk_size}.bin"
            page_file.write_bytes(data)

            pages.append(
                {
                    "offset": offset,
                    "address": base + offset,
                    "size": len(data),
                    "sha256": page_hash,
                    "file": page_file.name,
                }
            )
            total_read += len(data)
            offset += chunk_size

        manifest = {
            "region": {
                "name": region.name,
                "base": region.base,
                "size": region.size,
                "description": region.description,
                "critical": region.critical,
            },
            "acquisition": {
                "timestamp": dt.datetime.now()
                .astimezone()
                .isoformat(timespec="seconds"),
                "total_bytes": total_read,
                "page_count": len(pages),
                "error_count": len(errors),
                "block_size": self.BLOCK_SIZE,
                "max_chunk": self._max_chunk,
                "full_sha256": sha256_all.hexdigest(),
            },
            "pages": pages,
            "errors": errors,
        }

        manifest_path = region_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest

    def acquire_region_list(
        self,
        regions: list[MemoryRegion],
        output_dir: pathlib.Path,
    ) -> list[dict[str, Any]]:
        results = []
        for region in regions:
            try:
                result = self.acquire_region(region, output_dir)
                results.append(result)
            except (OSError, RuntimeError) as exc:
                results.append(
                    {
                        "region": {
                            "name": region.name,
                            "base": region.base,
                            "size": region.size,
                        },
                        "error": str(exc),
                    }
                )
        return results
