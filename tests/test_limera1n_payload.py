from __future__ import annotations

import unittest

ROOT = None

try:
    from host.limera1n_payload import (
        LIMERA1N_EXPLOIT_SIZE,
        LOAD_ADDR_A4,
        LOAD_ADDR_A5,
        SUPPORTED_CPIDS,
        build_payload,
        get_cpid_name,
        get_exploit_transfers,
        get_load_addr,
        get_supported_cpids,
        is_cpid_supported,
    )
except ImportError:
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "host"))
    from limera1n_payload import (
        LIMERA1N_EXPLOIT_SIZE,
        LOAD_ADDR_A4,
        LOAD_ADDR_A5,
        SUPPORTED_CPIDS,
        build_payload,
        get_cpid_name,
        get_exploit_transfers,
        get_load_addr,
        get_supported_cpids,
        is_cpid_supported,
    )


class Limera1nPayloadTests(unittest.TestCase):
    def test_is_cpid_supported_a4(self) -> None:
        self.assertTrue(is_cpid_supported(0x8930))

    def test_is_cpid_supported_a5(self) -> None:
        self.assertTrue(is_cpid_supported(0x8940))

    def test_is_cpid_supported_a5r2(self) -> None:
        self.assertTrue(is_cpid_supported(0x8942))

    def test_is_cpid_supported_a5r3(self) -> None:
        self.assertTrue(is_cpid_supported(0x8945))

    def test_is_cpid_supported_a6_returns_false(self) -> None:
        self.assertFalse(is_cpid_supported(0x8950))

    def test_is_cpid_supported_a7_returns_false(self) -> None:
        self.assertFalse(is_cpid_supported(0x8960))

    def test_is_cpid_supported_unknown_returns_false(self) -> None:
        self.assertFalse(is_cpid_supported(0xDEAD))

    def test_get_supported_cpids_sorted(self) -> None:
        cpids = get_supported_cpids()
        self.assertEqual(cpids, sorted(cpids))
        self.assertGreater(len(cpids), 0)

    def test_get_supported_cpids_contains_expected(self) -> None:
        cpids = get_supported_cpids()
        for expected in (0x8930, 0x8940, 0x8942, 0x8945):
            self.assertIn(expected, cpids)

    def test_get_cpid_name_a4(self) -> None:
        self.assertIn("A4", get_cpid_name(0x8930))

    def test_get_cpid_name_a5(self) -> None:
        self.assertIn("A5", get_cpid_name(0x8940))

    def test_get_cpid_name_unknown(self) -> None:
        self.assertIn("Unknown", get_cpid_name(0xBEEF))

    def test_get_load_addr_a4(self) -> None:
        self.assertEqual(get_load_addr(0x8930), LOAD_ADDR_A4)
        self.assertEqual(LOAD_ADDR_A4, 0x22000000)

    def test_get_load_addr_a5(self) -> None:
        self.assertEqual(get_load_addr(0x8940), LOAD_ADDR_A5)
        self.assertEqual(LOAD_ADDR_A5, 0x28000000)

    def test_get_load_addr_a5r2(self) -> None:
        self.assertEqual(get_load_addr(0x8942), LOAD_ADDR_A5)

    def test_get_load_addr_a5r3(self) -> None:
        self.assertEqual(get_load_addr(0x8945), LOAD_ADDR_A5)

    def test_get_exploit_transfers_returns_list(self) -> None:
        for cpid in (0x8930, 0x8940, 0x8942, 0x8945):
            with self.subTest(cpid=hex(cpid)):
                transfers = get_exploit_transfers(cpid)
                self.assertIsInstance(transfers, list)
                self.assertGreater(len(transfers), 0)

    def test_get_exploit_transfers_elements_are_5tuples(self) -> None:
        for cpid in (0x8930, 0x8940):
            for t in get_exploit_transfers(cpid):
                self.assertIsInstance(t, tuple)
                self.assertEqual(len(t), 5)
                bmrt, breq, wval, widx, data = t
                self.assertIsInstance(bmrt, int)
                self.assertIsInstance(breq, int)
                self.assertIsInstance(wval, int)
                self.assertIsInstance(widx, int)
                self.assertIsInstance(data, bytes)

    def test_get_exploit_transfers_first_is_oversized_write(self) -> None:
        for cpid in (0x8930, 0x8940):
            with self.subTest(cpid=hex(cpid)):
                first = get_exploit_transfers(cpid)[0]
                bmrt, breq, wval, widx, data = first
                self.assertEqual(breq, 0)
                self.assertEqual(len(data), LIMERA1N_EXPLOIT_SIZE)

    def test_build_payload_wraps_data_a4(self) -> None:
        payload = b"\x01\x02\x03\x04"
        wrapped = build_payload(payload, 0x8930)
        self.assertIsInstance(wrapped, bytes)
        self.assertEqual(len(wrapped), LIMERA1N_EXPLOIT_SIZE + 12)

    def test_build_payload_wraps_data_a5(self) -> None:
        payload = b"\xde\xad\xbe\xef"
        wrapped = build_payload(payload, 0x8940)
        self.assertIsInstance(wrapped, bytes)
        self.assertEqual(len(wrapped), LIMERA1N_EXPLOIT_SIZE + 12)

    def test_build_payload_contains_load_addr_a4(self) -> None:
        wrapped = build_payload(b"\xff" * 16, 0x8930)
        header_addr = int.from_bytes(wrapped[:8], "little")
        self.assertEqual(header_addr, LOAD_ADDR_A4)

    def test_build_payload_contains_load_addr_a5(self) -> None:
        wrapped = build_payload(b"\xff" * 16, 0x8940)
        header_addr = int.from_bytes(wrapped[:8], "little")
        self.assertEqual(header_addr, LOAD_ADDR_A5)

    def test_build_payload_contains_size(self) -> None:
        wrapped = build_payload(b"\xaa" * 100, 0x8930)
        stored_size = int.from_bytes(wrapped[8:12], "little")
        self.assertEqual(stored_size, 100)

    def test_build_payload_too_large_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_payload(b"\x00" * (LIMERA1N_EXPLOIT_SIZE + 1), 0x8930)

    def test_build_payload_max_size_ok(self) -> None:
        wrapped = build_payload(b"\x00" * LIMERA1N_EXPLOIT_SIZE, 0x8940)
        self.assertEqual(len(wrapped), LIMERA1N_EXPLOIT_SIZE + 12)

    def test_supported_cpids_set_constant(self) -> None:
        self.assertIsInstance(SUPPORTED_CPIDS, set)
        for cpid in SUPPORTED_CPIDS:
            self.assertIsInstance(cpid, int)

    def test_addresses_are_aligned(self) -> None:
        self.assertEqual(LOAD_ADDR_A4 % 0x1000, 0)
        self.assertEqual(LOAD_ADDR_A5 % 0x1000, 0)

    def test_exploit_size_is_reasonable(self) -> None:
        self.assertGreaterEqual(LIMERA1N_EXPLOIT_SIZE, 0x1000)
        self.assertLessEqual(LIMERA1N_EXPLOIT_SIZE, 0x100000)
