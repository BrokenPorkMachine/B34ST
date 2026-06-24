from __future__ import annotations

import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_help_and_short_flags_are_documented(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("--build", result.stdout)
        self.assertIn("--run", result.stdout)
        self.assertIn("--clean", result.stdout)
        self.assertIn("-b", result.stdout)
        self.assertIn("-r", result.stdout)
        self.assertIn("-c", result.stdout)
        self.assertIn("--package", result.stdout)
        self.assertIn("--permissions", result.stdout)


    def test_version_matches_runtime_architecture(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "--version"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "FBR34KER 0.2.3")

    def test_unknown_flag_is_rejected(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "--not-a-real-option"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown option", result.stderr)


if __name__ == "__main__":
    unittest.main()
