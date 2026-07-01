from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class DeviceToolsTests(unittest.TestCase):
    def test_offline_doctor_validates_profile(self):
        with tempfile.TemporaryDirectory() as d:
            device = pathlib.Path(d) / "device.json"
            device.write_text(
                json.dumps({"cpid": "0x8030", "mode": "DFU", "ecid": "1"})
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "host/device_tools.py",
                    "doctor",
                    "--profile",
                    "profiles/apple-a13-recovery.json",
                    "--device-info",
                    str(device),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertTrue(value["passed"])

    def test_list_finds_exact_profile(self):
        with tempfile.TemporaryDirectory() as d:
            device = pathlib.Path(d) / "device.json"
            device.write_text(
                json.dumps(
                    {
                        "cpid": "0x8030",
                        "mode": "DFU",
                        "ecid": "1",
                        "product": "iPhone12,1",
                    }
                )
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "host/device_tools.py",
                    "list",
                    "--device-info",
                    str(device),
                    "--profiles-dir",
                    "profiles",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertGreaterEqual(value["exact_profile_matches"], 1)

    def test_watch_emits_change(self):
        with tempfile.TemporaryDirectory() as d:
            first = pathlib.Path(d) / "first.json"
            second = pathlib.Path(d) / "second.json"
            first.write_text(
                json.dumps(
                    {
                        "cpid": "0x8030",
                        "mode": "DFU",
                        "ecid": "1",
                        "product": "iPhone12,1",
                    }
                )
            )
            second.write_text(
                json.dumps(
                    {
                        "cpid": "0x8030",
                        "mode": "Recovery",
                        "ecid": "1",
                        "product": "iPhone12,1",
                    }
                )
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "host/device_tools.py",
                    "watch",
                    "--device-info",
                    str(first),
                    "--device-info",
                    str(second),
                    "--iterations",
                    "2",
                    "--interval",
                    "0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(result.stdout.splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
