from __future__ import annotations

import pathlib
import tempfile
import unittest

from host.boot_image import Component, build_image
from host.first_stage_adapter import AdapterError, SimulatorFirstStageAdapter

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FirstStageAdapterTests(unittest.TestCase):
    def make_image(self, root: pathlib.Path, load=0x80000000):
        monitor = root / "monitor.bin"
        monitor.write_bytes(b"A" * 4096)
        image = root / "boot.img"
        build_image(
            image,
            ROOT / "profiles/apple-a13-recovery.json",
            [Component("monitor", monitor, load, load)],
        )
        return image

    def adapter(self, root, inject=None):
        return SimulatorFirstStageAdapter(
            root / "state",
            {"cpid": "0x8030", "mode": "DFU", "ecid": "1"},
            inject_failure=inject,
        )

    def test_upload_requires_authorization(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = self.adapter(root)
            image = self.make_image(root)
            with self.assertRaises(AdapterError):
                a.upload(image)

    def test_region_validation_rejects_outside_monitor(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = self.adapter(root)
            image = self.make_image(root, 0x90000000)
            a.authorize("authorized-test-session")
            with self.assertRaises(AdapterError):
                a.upload(image)

    def test_reset_invalidates_authorization(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = self.adapter(root)
            image = self.make_image(root)
            a.authorize("authorized-test-session")
            a.upload(image)
            a.start()
            result = a.reset("authorized-test-session")
            self.assertFalse(result["authorized"])
            with self.assertRaises(AdapterError):
                a.start()

    def test_injected_failure_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = self.adapter(root, "timer")
            image = self.make_image(root)
            a.authorize("authorized-test-session")
            a.upload(image)
            a.start()
            with self.assertRaises(AdapterError):
                a.probe_stage("timer")
            self.assertEqual(a.collect()["state"]["previous_failure"], "timer")


if __name__ == "__main__":
    unittest.main()
