from __future__ import annotations

import pathlib
import unittest

from host.boot_image import load_profile
from host.irecovery_boot import DeviceInfo, RecoveryError, validate_target

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PhysicalProfileTests(unittest.TestCase):
    def test_exact_a13_iphone_profile(self):
        profile = load_profile(ROOT / "profiles/apple-a13-iphone-recovery.json")
        validate_target(
            profile, DeviceInfo(0x8020, "1", "DFU", "iPhone12,1", None, None, {})
        )
        with self.assertRaises(RecoveryError):
            validate_target(
                profile, DeviceInfo(0x8020, "1", "DFU", "iPad12,1", None, None, {})
            )

    def test_family_profile_remains_non_exact(self):
        profile = load_profile(ROOT / "profiles/apple-a13-recovery.json")
        self.assertFalse(profile["requires_exact_product"])


if __name__ == "__main__":
    unittest.main()
