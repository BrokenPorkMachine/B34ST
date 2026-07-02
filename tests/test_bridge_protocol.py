# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

from host.boot_image import Component, build_image
from host.first_stage_adapter import AdapterError, BridgeFirstStageAdapter

ROOT = pathlib.Path(__file__).resolve().parents[1]


class BridgeProtocolTests(unittest.TestCase):
    def fixture(self, root: pathlib.Path):
        device = root / "device.json"
        device.write_text(
            json.dumps(
                {
                    "cpid": "0x8030",
                    "mode": "DFU",
                    "ecid": "abc",
                    "product": "iPhone12,1",
                }
            )
        )
        monitor = root / "monitor.bin"
        monitor.write_bytes(b"Z" * 8192)
        image = root / "boot.img"
        build_image(
            image,
            ROOT / "profiles/apple-a13-iphone-recovery.json",
            [Component("monitor", monitor, 0x80000000, 0x80000000)],
        )
        command = [
            sys.executable,
            str(ROOT / "host/reference_bridge.py"),
            "--state-dir",
            str(root / "state"),
            "--device-info",
            str(device),
        ]
        return device, image, command

    def test_persistent_chunked_bridge_session(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _, image, command = self.fixture(root)
            adapter = BridgeFirstStageAdapter(command, timeout=10, chunk_size=1024)
            try:
                identity = adapter.identify()
                self.assertIn("chunked-upload", identity.capabilities)
                adapter.authorize("authorized-bridge-session")
                uploaded = adapter.upload(image)
                self.assertEqual(
                    uploaded["sha256"],
                    adapter.verify_image(image)["image"]["sha256"],
                )
                adapter.start()
                adapter.probe_stage("console")
                console = adapter.read_console(0)
                self.assertTrue(console["lines"])
                reset = adapter.reset("authorized-bridge-session")
                self.assertFalse(reset["authorized"])
                with self.assertRaises(AdapterError):
                    adapter.start()
            finally:
                adapter.close()

    def test_bridge_rejects_bad_chunk_size(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _, _, command = self.fixture(root)
            with self.assertRaises(AdapterError):
                BridgeFirstStageAdapter(command, chunk_size=999999)


if __name__ == "__main__":
    unittest.main()
