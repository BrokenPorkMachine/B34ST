from __future__ import annotations

import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class BuildModeTests(unittest.TestCase):
    def test_operational_recipe_enables_security_model(self) -> None:
        result = subprocess.run(
            ["make", "-n", "-B", "build-operational"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-c kernel/kernel_patches.c", result.stdout)
        self.assertIn("-DFBR34KER_ENABLE_SECURITY_MODEL", result.stdout)

    def test_default_recipe_omits_security_model(self) -> None:
        result = subprocess.run(
            ["make", "-n", "-B", "all"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("-DFBR34KER_ENABLE_SECURITY_MODEL", result.stdout)


if __name__ == "__main__":
    unittest.main()
