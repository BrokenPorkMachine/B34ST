from __future__ import annotations

import unittest

from host.chipset_db import (
    CPID_A12,
    CPID_A12X,
    CPID_A12Z,
    CPID_A13,
    CPID_A14,
    CPID_A15,
    CPID_M1,
    CPID_M2,
)
from host.usbliter8_payload import CPID_PATCH_MAP, SUPPORTED_CPIDS, get_cpid_name


class TargetIdentityTests(unittest.TestCase):
    def test_usbliter8_map_uses_canonical_cpids(self) -> None:
        expected = {
            CPID_A12,
            CPID_A12X,
            CPID_A12Z,
            CPID_A13,
            CPID_A14,
            CPID_A15,
            CPID_M1,
            CPID_M2,
        }
        self.assertEqual(SUPPORTED_CPIDS, expected)
        self.assertEqual(set(CPID_PATCH_MAP), expected)

    def test_generation_names_match_canonical_cpids(self) -> None:
        expected = {
            CPID_A12: "A12",
            CPID_A12X: "A12X",
            CPID_A12Z: "A12Z",
            CPID_A13: "A13",
            CPID_A14: "A14",
            CPID_A15: "A15",
            CPID_M1: "M1",
            CPID_M2: "M2",
        }
        for cpid, generation in expected.items():
            self.assertIn(generation, get_cpid_name(cpid))

    def test_a11_is_not_an_a12_plus_usbliter8_target(self) -> None:
        self.assertNotIn(0x8015, SUPPORTED_CPIDS)


if __name__ == "__main__":
    unittest.main()
