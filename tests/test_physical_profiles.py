# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import pathlib
import json
import unittest

from host.boot_image import load_profile
from host.chipset_db import (
    CPID_A12,
    CPID_A12X,
    CPID_A12Z,
    CPID_A13,
    CPID_A14,
)
from host.irecovery_boot import DeviceInfo, RecoveryError, validate_target

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PhysicalProfileTests(unittest.TestCase):
    def test_exact_a13_iphone_profile(self):
        profile = load_profile(ROOT / "profiles/apple-a13-iphone-recovery.json")
        validate_target(
            profile, DeviceInfo(CPID_A13, "1", "DFU", "iPhone12,1", None, None, {})
        )
        with self.assertRaises(RecoveryError):
            validate_target(
                profile, DeviceInfo(CPID_A13, "1", "DFU", "iPad12,1", None, None, {})
            )

    def test_family_profile_remains_non_exact(self):
        profile = load_profile(ROOT / "profiles/apple-a13-recovery.json")
        self.assertFalse(profile["requires_exact_product"])

    def test_profile_cpids_match_canonical_chipset_database(self):
        expected = {
            "a12": {CPID_A12},
            "a12x": {CPID_A12X, CPID_A12Z},
            "a13": {CPID_A13},
            "a14": {CPID_A14},
        }
        for path in sorted((ROOT / "profiles").glob("apple-*-recovery.json")):
            profile = json.loads(path.read_text())
            family = profile["family"]
            if family not in expected:
                continue
            actual = {int(value, 16) for value in profile["cpids"]}
            self.assertEqual(actual, expected[family], path.name)


if __name__ == "__main__":
    unittest.main()
