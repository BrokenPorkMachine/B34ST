# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import importlib.util
import pathlib
import struct
import unittest
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "decode_boot_evidence", ROOT / "scripts" / "decode_boot_evidence.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BootEvidenceDecoderTests(unittest.TestCase):
    def test_valid_record(self) -> None:
        record = bytearray(MODULE.RECORD.pack(
            MODULE.MAGIC, 1, MODULE.RECORD.size, 0,
            3, 5, 4, 0, 0, 0x12, 0x3456, 8,
        ))
        checksum = zlib.crc32(record) & 0xFFFFFFFF
        struct.pack_into("<I", record, 8, checksum)
        result = MODULE.decode(bytes(record))
        self.assertTrue(result["valid"])
        self.assertEqual(result["current_stage"], "architecture")
        self.assertEqual(result["boot_count"], 3)

    def test_short_record_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.decode(b"short")


if __name__ == "__main__":
    unittest.main()
