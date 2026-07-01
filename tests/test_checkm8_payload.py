from __future__ import annotations

import unittest

ROOT = None

try:
    from host.checkm8_payload import (
        CHECKM8_PAYLOAD_ADDR,
        CHECKM8_PAYLOAD_SIZE,
        SUPPORTED_CPIDS,
        build_payload,
        get_cpid_name,
        get_exploit_transfers,
        get_supported_cpids,
        is_cpid_supported,
    )
except ImportError:
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "host"))
    from checkm8_payload import (
        CHECKM8_PAYLOAD_ADDR,
        CHECKM8_PAYLOAD_SIZE,
        SUPPORTED_CPIDS,
        build_payload,
        get_cpid_name,
        get_exploit_transfers,
        get_supported_cpids,
        is_cpid_supported,
    )


class Checkm8PayloadTests(unittest.TestCase):
    def test_is_cpid_supported_a7(self) -> None:
        self.assertTrue(is_cpid_supported(0x8960))

    def test_is_cpid_supported_a8(self) -> None:
        self.assertTrue(is_cpid_supported(0x7000))

    def test_is_cpid_supported_a9(self) -> None:
        self.assertTrue(is_cpid_supported(0x8000))

    def test_is_cpid_supported_a10(self) -> None:
        self.assertTrue(is_cpid_supported(0x8010))

    def test_is_cpid_supported_a11(self) -> None:
        self.assertTrue(is_cpid_supported(0x8015))

    def test_is_cpid_supported_t2(self) -> None:
        self.assertTrue(is_cpid_supported(0x8012))

    def test_is_cpid_supported_a4_returns_false(self) -> None:
        self.assertFalse(is_cpid_supported(0x8930))

    def test_is_cpid_supported_a12_returns_false(self) -> None:
        self.assertFalse(is_cpid_supported(0x8020))

    def test_is_cpid_supported_unknown_returns_false(self) -> None:
        self.assertFalse(is_cpid_supported(0xDEAD))

    def test_get_supported_cpids_sorted(self) -> None:
        cpids = get_supported_cpids()
        self.assertEqual(cpids, sorted(cpids))
        self.assertGreater(len(cpids), 0)

    def test_get_supported_cpids_contains_expected(self) -> None:
        cpids = get_supported_cpids()
        for expected in (0x7000, 0x8000, 0x8010, 0x8015, 0x8960):
            self.assertIn(expected, cpids)

    def test_get_cpid_name_a7(self) -> None:
        self.assertIn("A7", get_cpid_name(0x8960))

    def test_get_cpid_name_a8(self) -> None:
        self.assertIn("A8", get_cpid_name(0x7000))

    def test_get_cpid_name_a11(self) -> None:
        self.assertIn("A11", get_cpid_name(0x8015))

    def test_get_cpid_name_unknown(self) -> None:
        self.assertIn("Unknown", get_cpid_name(0xBEEF))

    def test_get_exploit_transfers_returns_list(self) -> None:
        transfers = get_exploit_transfers()
        self.assertIsInstance(transfers, list)
        self.assertGreater(len(transfers), 0)

    def test_get_exploit_transfers_elements_are_5tuples(self) -> None:
        for t in get_exploit_transfers():
            self.assertIsInstance(t, tuple)
            self.assertEqual(len(t), 5)
            bmrt, breq, wval, widx, data = t
            self.assertIsInstance(bmrt, int)
            self.assertIsInstance(breq, int)
            self.assertIsInstance(wval, int)
            self.assertIsInstance(widx, int)
            self.assertIsInstance(data, bytes)

    def test_get_exploit_transfers_has_overflow_larger_than_zero(self) -> None:
        for t in get_exploit_transfers():
            if t[1] == 6 and t[3] == 0x0100:
                if len(t[4]) >= 4:
                    size = int.from_bytes(t[4][:4], "little")
                    self.assertGreater(size, 0x1000)

    def test_build_payload_wraps_data(self) -> None:
        payload = b"\x01\x02\x03\x04"
        wrapped = build_payload(payload)
        self.assertIsInstance(wrapped, bytes)
        self.assertEqual(len(wrapped), CHECKM8_PAYLOAD_SIZE + 12)

    def test_build_payload_contains_load_addr(self) -> None:
        wrapped = build_payload(b"\xff" * 16)
        header_addr = int.from_bytes(wrapped[:8], "little")
        self.assertEqual(header_addr, CHECKM8_PAYLOAD_ADDR)

    def test_build_payload_contains_size(self) -> None:
        wrapped = build_payload(b"\xaa" * 100)
        stored_size = int.from_bytes(wrapped[8:12], "little")
        self.assertEqual(stored_size, 100)

    def test_build_payload_too_large_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_payload(b"\x00" * (CHECKM8_PAYLOAD_SIZE + 1))

    def test_build_payload_max_size_ok(self) -> None:
        wrapped = build_payload(b"\x00" * CHECKM8_PAYLOAD_SIZE)
        self.assertEqual(len(wrapped), CHECKM8_PAYLOAD_SIZE + 12)

    def test_supported_cpids_set_constant(self) -> None:
        self.assertIsInstance(SUPPORTED_CPIDS, set)
        for cpid in SUPPORTED_CPIDS:
            self.assertIsInstance(cpid, int)

    def test_payload_addr_is_aligned(self) -> None:
        self.assertEqual(CHECKM8_PAYLOAD_ADDR % 0x1000, 0)

    def test_payload_size_is_reasonable(self) -> None:
        self.assertGreaterEqual(CHECKM8_PAYLOAD_SIZE, 0x1000)
        self.assertLessEqual(CHECKM8_PAYLOAD_SIZE, 0x100000)
