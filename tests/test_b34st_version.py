from __future__ import annotations

import unittest

from b34st.version import B34STVersion, VersionError, __version__


class B34STVersionTests(unittest.TestCase):
    def test_current_beta_version_is_valid(self) -> None:
        self.assertEqual(__version__, "0.5.0b")
        self.assertTrue(B34STVersion.validate_version())

    def test_supported_release_version_forms(self) -> None:
        for version in ("0.4.3", "0.4.3a", "0.4.3b", "0.4.3rc1"):
            with self.subTest(version=version):
                self.assertTrue(B34STVersion.validate_version(version))
        for version in ("0.4", "0.4.3beta", "v0.4.3", "01.4.3"):
            with self.subTest(version=version):
                self.assertFalse(B34STVersion.validate_version(version))

    def test_compare_versions_orders_prereleases(self) -> None:
        self.assertLess(B34STVersion.compare_versions("0.4.3b", "0.4.3"), 0)
        self.assertGreater(B34STVersion.compare_versions("0.4.3b", "0.4.2"), 0)
        self.assertLess(B34STVersion.compare_versions("0.4.3b", "0.4.3rc1"), 0)
        self.assertEqual(B34STVersion.compare_versions("0.4.3b", "0.4.3b"), 0)

    def test_compare_versions_rejects_invalid_input(self) -> None:
        with self.assertRaises(VersionError):
            B34STVersion.compare_versions("0.4.3beta", "0.4.3")


if __name__ == "__main__":
    unittest.main()
