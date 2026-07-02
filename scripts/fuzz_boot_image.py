#!/usr/bin/env python3

"""Run a deterministic malformed-FBRI corpus against the strict parser."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random
import struct
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.boot_image import (
    BootImageError,
    Component,
    HEADER,
    HEADER_SIZE,
    MANIFEST_CAPACITY,
    build_image,
    inspect_image,
)


def rewrite_manifest(data: bytearray, mutate) -> None:
    """Apply a mutation function to the JSON manifest inside an FBRI image."""
    fields = list(HEADER.unpack_from(data))
    size = fields[9]
    manifest = json.loads(
        bytes(data[HEADER_SIZE : HEADER_SIZE + size]).decode("ascii")
    )
    mutate(manifest)
    encoded = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    if len(encoded) > MANIFEST_CAPACITY:
        raise RuntimeError("mutated manifest too large")
    data[HEADER_SIZE : HEADER_SIZE + MANIFEST_CAPACITY] = b"\0" * MANIFEST_CAPACITY
    data[HEADER_SIZE : HEADER_SIZE + len(encoded)] = encoded
    fields[9] = len(encoded)
    fields[12] = hashlib.sha256(encoded).digest()
    fields[13] = hashlib.sha256(data[fields[10] :]).digest()
    data[:HEADER_SIZE] = HEADER.pack(*fields)


def main(argv: list[str] | None = None) -> int:
    """Build a deterministic corpus of malformed FBRI images and validate rejects."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--iterations", type=int, default=64)
    a = p.parse_args(argv)

    if a.iterations < 1 or a.iterations > 1024:
        p.error("iterations must be 1..1024")

    rejected = 0

    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        monitor = root / "monitor.bin"
        monitor.write_bytes(b"F" * 8192)
        image = root / "boot.img"

        build_image(
            image,
            pathlib.Path("profiles/apple-a13-recovery.json"),
            [Component("monitor", monitor, 0x80000000, 0x80000000)],
        )
        original = image.read_bytes()
        corpus: list[bytes] = []

        corpus.append(original[:64])

        v = bytearray(original)
        struct.pack_into("<I", v, 8, 1)
        corpus.append(bytes(v))

        v = bytearray(original)
        rewrite_manifest(
            v,
            lambda m: m["components"][0].update({"entry_address": 0x90000000}),
        )
        corpus.append(bytes(v))

        v = bytearray(original)
        rewrite_manifest(v, lambda m: m.update({"unknown": 1}))
        corpus.append(bytes(v))

        rng = random.Random(0xF34)
        for _ in range(a.iterations):
            v = bytearray(original)
            index = rng.randrange(len(v))
            v[index] ^= 1 << rng.randrange(8)
            corpus.append(bytes(v))

        for index, value in enumerate(corpus):
            candidate = root / f"bad-{index}.img"
            candidate.write_bytes(value)
            try:
                inspect_image(candidate)
            except BootImageError:
                rejected += 1
            else:
                raise RuntimeError(f"malformed corpus item {index} was accepted")

    print(f"FBRI malformed corpus rejected ({rejected} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
