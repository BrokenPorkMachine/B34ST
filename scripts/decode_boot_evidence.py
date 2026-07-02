#!/usr/bin/env python3

"""Decode a raw FBR34KER .boot_evidence memory record."""
# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
import zlib

MAGIC = 0x46424556
VERSION = 1
RECORD = struct.Struct("<IHHI6I4xQQ")
STAGES = {
    0: "reset",
    1: "context",
    2: "platform",
    3: "runtime",
    4: "architecture",
    5: "interactive",
    6: "shutdown",
    7: "fault",
}


def decode(data: bytes) -> dict[str, object]:
    if len(data) < RECORD.size:
        raise ValueError(f"record is {len(data)} bytes; expected at least {RECORD.size}")
    raw = data[: RECORD.size]
    values = RECORD.unpack(raw)
    (magic, version, size, checksum, boot_count, previous_stage,
     current_stage, previous_clean, clean_shutdown, last_error,
     last_value, stage_sequence) = values
    check = bytearray(raw)
    check[8:12] = b"\0\0\0\0"
    calculated = zlib.crc32(check) & 0xFFFFFFFF
    valid = (
        magic == MAGIC
        and version == VERSION
        and size == RECORD.size
        and checksum == calculated
        and previous_stage in STAGES
        and current_stage in STAGES
    )
    return {
        "schema": 1,
        "valid": valid,
        "magic": f"0x{magic:08x}",
        "version": version,
        "size": size,
        "checksum": f"0x{checksum:08x}",
        "calculated_checksum": f"0x{calculated:08x}",
        "boot_count": boot_count,
        "previous_stage": STAGES.get(previous_stage, f"unknown-{previous_stage}"),
        "previous_clean": bool(previous_clean),
        "current_stage": STAGES.get(current_stage, f"unknown-{current_stage}"),
        "clean_shutdown": bool(clean_shutdown),
        "last_error": f"0x{last_error:08x}",
        "last_value": f"0x{last_value:016x}",
        "stage_sequence": stage_sequence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=pathlib.Path,
                        help="raw 56-byte .boot_evidence memory dump")
    parser.add_argument("--pretty", action="store_true",
                        help="indent JSON output")
    args = parser.parse_args()
    try:
        result = decode(args.record.read_bytes())
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
