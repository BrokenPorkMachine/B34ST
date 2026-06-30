"""Forensic imaging with per-block integrity hashing and sparse support.

Produces sector-level images with cryptographic hash chains suitable
for court-admissible evidence acquisition.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import pathlib
import zlib
from typing import Any, Callable


class ImagingError(RuntimeError):
    pass


@dataclasses.dataclass
class ImagingOptions:
    """Options for forensic imaging operations."""
    block_size: int = 65536
    compress: bool = False
    sparse: bool = True
    verify_on_write: bool = True
    max_size: int = 0


class ForensicImage:
    """Creates and manages a forensic disk/memory image with integrity tracking.

    Each block is individually hashed (SHA-256) and the overall image
    has a chain-of-custody hash for tamper evidence.
    """

    def __init__(
        self,
        name: str,
        read_fn: Callable[[int, int], bytes],
        total_size: int,
        options: ImagingOptions | None = None,
    ):
        self.name = name
        self._read_fn = read_fn
        self.total_size = total_size
        self.options = options or ImagingOptions()

    def create(
        self,
        output_dir: pathlib.Path,
        *,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        image_dir = output_dir / f"image-{self.name}"
        image_dir.mkdir(exist_ok=True)

        blocks: list[dict[str, Any]] = []
        sha256_all = hashlib.sha256()
        total_read = 0
        errors: list[str] = []
        block_size = self.options.block_size
        max_size = self.options.max_size or self.total_size
        limit = min(self.total_size, max_size)
        offset = 0

        while offset < limit:
            chunk_size = min(block_size, limit - offset)

            try:
                data = self._read_fn(offset, chunk_size)
                if not data:
                    errors.append(f"empty read at offset 0x{offset:x}")
                    offset += chunk_size
                    continue
            except Exception as exc:
                errors.append(f"read error at offset 0x{offset:x}: {exc}")
                offset += chunk_size
                continue

            all_zero = all(b == 0 for b in data)
            if self.options.sparse and all_zero:
                blocks.append({
                    "offset": offset,
                    "size": chunk_size,
                    "sparse": True,
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
                sha256_all.update(data)
                total_read += chunk_size
                offset += chunk_size
                if progress_cb:
                    progress_cb(total_read, limit)
                continue

            sha256_all.update(data)
            block_hash = hashlib.sha256(data).hexdigest()
            block_data = data

            if self.options.compress:
                block_data = zlib.compress(data)
                stored_size = len(block_data)
            else:
                stored_size = len(block_data)

            block_file = image_dir / f"block-0x{offset:016x}.bin"
            if self.options.compress:
                block_file = block_file.with_suffix(".zlib")
            block_file.write_bytes(block_data)

            if self.options.verify_on_write:
                written = block_file.read_bytes()
                if self.options.compress:
                    written = zlib.decompress(written)
                if written != data:
                    errors.append(
                        f"verify failed at offset 0x{offset:x}"
                    )

            blocks.append({
                "offset": offset,
                "size": chunk_size,
                "stored_size": stored_size,
                "sparse": False,
                "compressed": self.options.compress,
                "sha256": block_hash,
                "file": block_file.name,
            })
            total_read += chunk_size
            offset += chunk_size

            if progress_cb:
                progress_cb(total_read, limit)

        digest = sha256_all.hexdigest()
        image_file = image_dir / f"{self.name}.sha256"
        image_file.write_text(digest + "\n", encoding="utf-8")

        manifest = {
            "image": {
                "name": self.name,
                "total_size": self.total_size,
                "acquired_size": limit,
                "sparse": self.options.sparse,
                "compress": self.options.compress,
                "block_size": block_size,
            },
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "total_bytes_read": total_read,
                "block_count": len(blocks),
                "error_count": len(errors),
                "full_sha256": digest,
            },
            "blocks": blocks,
            "errors": errors,
        }

        manifest_path = image_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest

    @staticmethod
    def verify_image(image_dir: pathlib.Path) -> dict[str, Any]:
        manifest_path = image_dir / "manifest.json"
        if not manifest_path.is_file():
            raise ImagingError(f"manifest not found: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sha256_all = hashlib.sha256()
        failures: list[str] = []
        verified_blocks = 0

        for block in manifest.get("blocks", []):
            if block.get("sparse"):
                bytes(block["size"])
            else:
                block_file = image_dir / block["file"]
                if not block_file.is_file():
                    failures.append(f"missing block file: {block['file']}")
                    continue
                data = block_file.read_bytes()
                if block.get("compressed"):
                    try:
                        data = zlib.decompress(data)
                    except zlib.error as exc:
                        failures.append(
                            f"decompress fail at offset 0x{block['offset']:x}: {exc}"
                        )
                        continue
                stored_hash = hashlib.sha256(data).hexdigest()
                if stored_hash != block["sha256"]:
                    failures.append(
                        f"hash mismatch at offset 0x{block['offset']:x}: "
                        f"expected {block['sha256']}, got {stored_hash}"
                    )
                sha256_all.update(data)
            verified_blocks += 1

        full_hash = sha256_all.hexdigest()
        expected_hash = manifest["acquisition"]["full_sha256"]

        return {
            "image": manifest["image"]["name"],
            "verified": not failures and full_hash == expected_hash,
            "block_count": len(manifest.get("blocks", [])),
            "verified_blocks": verified_blocks,
            "failures": failures,
            "full_sha256": full_hash,
            "expected_sha256": expected_hash,
            "hash_match": full_hash == expected_hash,
        }
