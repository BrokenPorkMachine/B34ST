from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class DeploymentCliTests(unittest.TestCase):
    def test_version(self) -> None:
        result = subprocess.run([sys.executable, "host/fbr34kdeploy.py", "--version"],
                                cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0.4.0", result.stdout)

    def test_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            monitor = pathlib.Path(temporary) / "monitor.bin"
            monitor.write_bytes(b"x" * 4096)
            result = subprocess.run([
                sys.executable, "host/fbr34kdeploy.py", "plan",
                "--profile", "profiles/qemu-virt-deployment.json",
                "--artifact", f"monitor:monitor:{monitor}@0x80000000",
            ], cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"status": "valid"', result.stdout)

    def test_deploy_dry_run_does_not_create_target_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            monitor = root / "monitor.bin"
            state = root / "state"
            monitor.write_bytes(b"x" * 4096)
            result = subprocess.run([
                sys.executable, "host/fbr34kdeploy.py", "deploy",
                "--profile", "profiles/qemu-virt-deployment.json",
                "--simulator-state", str(state), "--dry-run",
                "--artifact", f"monitor:monitor:{monitor}@0x80000000",
            ], cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"status": "dry-run-valid"', result.stdout)
            self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main()
