from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from deployment_profile import ProfileError, load_profile, validate_profile  # noqa: E402


class DeploymentProfileTests(unittest.TestCase):
    def test_release_profile(self) -> None:
        profile = load_profile(ROOT / "profiles/qemu-virt-deployment.json")
        region = profile.region_for(0x80000000, 4096, "monitor")
        self.assertEqual(region.name, "payload")

    def test_overlap_rejected(self) -> None:
        with self.assertRaisesRegex(ProfileError, "overlap"):
            validate_profile({
                "schema_version": 1,
                "name": "bad",
                "board_compatible": ["test,bad"],
                "deployment_regions": [
                    {"name": "one", "base": 0x1000, "size": 0x2000,
                     "artifact_kinds": ["monitor"]},
                    {"name": "two", "base": 0x2000, "size": 0x2000,
                     "artifact_kinds": ["module"]},
                ],
            })


if __name__ == "__main__":
    unittest.main()
