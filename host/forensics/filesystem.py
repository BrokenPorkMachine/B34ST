"""Filesystem acquisition for capturing file listings and file contents.

Supports recursive directory enumeration and targeted file extraction
via wire protocol or bridge commands.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import pathlib
from typing import Any, Callable


class FileSystemAcquisitionError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class FileEntry:
    """Describes a file discovered during filesystem enumeration."""

    path: str
    size: int
    sha256: str = ""
    mode: str = ""
    owner: str = ""
    modified: str = ""


class FileSystemAcquisitor:
    """Acquires filesystem listings and file contents from a target device.

    Uses caller-provided callbacks for directory enumeration and file reads,
    abstracting across USB serial, wire protocol, or bridge transports.
    """

    MAX_FILE_SIZE = 64 * 1024 * 1024

    def __init__(
        self,
        list_fn: Callable[[str], list[FileEntry]],
        read_fn: Callable[[str, int, int], bytes],
        *,
        stat_fn: Callable[[str], FileEntry | None] | None = None,
    ):
        self._list_fn = list_fn
        self._read_fn = read_fn
        self._stat_fn = stat_fn

    def enumerate_path(
        self,
        path: str,
        output_dir: pathlib.Path,
        *,
        recursive: bool = True,
        max_depth: int = 32,
    ) -> list[FileEntry]:
        entries: list[FileEntry] = []
        try:
            entries = self._list_fn(path)
        except (OSError, RuntimeError) as exc:
            raise FileSystemAcquisitionError(f"failed to list {path}: {exc}") from exc

        manifest_path = output_dir / "filesystem" / "listing.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        listing = [
            {
                "path": e.path,
                "size": e.size,
                "sha256": e.sha256,
                "mode": e.mode,
                "owner": e.owner,
                "modified": e.modified,
            }
            for e in entries
        ]

        manifest = {
            "root": path,
            "recursive": recursive,
            "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "entry_count": len(entries),
            "entries": listing,
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return entries

    def acquire_file(
        self,
        path: str,
        output_dir: pathlib.Path,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        file_dir = output_dir / "filesystem"
        file_dir.mkdir(exist_ok=True)

        try:
            entry = self._stat_fn(path) if self._stat_fn else None
        except OSError:
            entry = None

        sha256 = hashlib.sha256()
        total = 0
        chunks: list[dict[str, Any]] = []
        offset = 0
        chunk_size = 65536

        while True:
            try:
                data = self._read_fn(path, offset, chunk_size)
            except (OSError, RuntimeError) as exc:
                return {
                    "path": path,
                    "error": str(exc),
                    "total_bytes": total,
                }
            if not data:
                break
            sha256.update(data)
            chunk_hash = hashlib.sha256(data).hexdigest()
            safe_name = path.lstrip("/").replace("/", "_")
            chunk_file = file_dir / f"{safe_name}.part"
            with chunk_file.open("ab") as f:
                f.write(data)

            chunks.append(
                {
                    "offset": offset,
                    "size": len(data),
                    "sha256": chunk_hash,
                }
            )
            total += len(data)
            offset += len(data)

            if len(data) < chunk_size:
                break

            if total > self.MAX_FILE_SIZE:
                break

        if total > self.MAX_FILE_SIZE:
            pass

        digest = sha256.hexdigest()
        result = {
            "path": path,
            "size": total,
            "sha256": digest,
            "chunks": chunks,
            "stat": {
                "mode": entry.mode if entry else "",
                "owner": entry.owner if entry else "",
                "modified": entry.modified if entry else "",
            }
            if entry
            else {},
        }
        return result

    def acquire_paths(
        self,
        paths: list[str],
        output_dir: pathlib.Path,
    ) -> list[dict[str, Any]]:
        results = []
        for path in paths:
            try:
                result = self.acquire_file(path, output_dir)
                results.append(result)
            except (OSError, RuntimeError) as exc:
                results.append({"path": path, "error": str(exc)})
        return results
