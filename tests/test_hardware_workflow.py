# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from host.boot_image import Component, build_image

ROOT = pathlib.Path(__file__).resolve().parents[1]


class HardwareWorkflowTests(unittest.TestCase):
    def test_prepare_is_read_only_and_reports_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            monitor = root / "monitor.bin"
            monitor.write_bytes(b"P" * 4096)
            image = root / "boot.img"
            build_image(image, ROOT / "profiles/apple-a13-iphone-recovery.json",
                        [Component("monitor", monitor, 0x80000000, 0x80000000)])
            device = root / "device.json"
            device.write_text(json.dumps({"cpid": "0x8030", "mode": "DFU",
                                          "ecid": "abcd", "product": "iPhone12,1"}))
            result = subprocess.run([
                sys.executable, "host/hardware_workflow.py", "prepare",
                "--profile", "profiles/apple-a13-iphone-recovery.json",
                "--device-info", str(device), "--image", str(image),
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertTrue(value["ready"])
            self.assertFalse(value["mutation_performed"])

    def test_checklist_is_available_from_unified_cli(self):
        result = subprocess.run([
            "./fbr34ker", "hardware", "checklist",
            "profiles/apple-a13-iphone-recovery.json",
        ], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["checks"]), 8)


if __name__ == "__main__":
    unittest.main()
