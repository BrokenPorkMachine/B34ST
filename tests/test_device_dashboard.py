# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import argparse
import json
import pathlib
import plistlib
import tempfile
import unittest

from host.device_dashboard import build_snapshot, query_normal_device


class DeviceDashboardTests(unittest.TestCase):
    def catalog(self, root: pathlib.Path) -> pathlib.Path:
        value = {
            "identifier": "iPhone12,1",
            "firmwares": [
                {
                    "identifier": "iPhone12,1",
                    "version": "18.5",
                    "buildid": "22F76",
                    "signed": True,
                    "url": "https://updates.cdn-apple.com/test/latest.ipsw",
                },
                {
                    "identifier": "iPhone12,1",
                    "version": "17.6.1",
                    "buildid": "21G93",
                    "signed": False,
                    "url": "https://updates.cdn-apple.com/test/old.ipsw",
                },
            ],
        }
        path = root / "catalog.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def fixture(self, root: pathlib.Path) -> pathlib.Path:
        path = root / "device.json"
        path.write_text(json.dumps({
            "cpid": "0x8030",
            "ecid": "1234",
            "mode": "DFU",
            "product": "iPhone12,1",
            "model": "N104AP",
        }), encoding="utf-8")
        return path

    def test_recovery_snapshot_includes_launch_latest_and_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            args = argparse.Namespace(
                device_info=self.fixture(root),
                recovery_only=True,
                udid=None,
                ecid=None,
                ideviceinfo="missing",
                idevice_id="missing",
                irecovery="missing",
                catalog=str(self.catalog(root)),
                timeout=1.0,
                catalog_timeout=1.0,
            )
            snapshot = build_snapshot(args)
            self.assertTrue(snapshot["connected"])
            self.assertEqual(snapshot["device"]["launch_version"], "13.0")
            self.assertIsNone(snapshot["device"]["current_version"])
            self.assertEqual(snapshot["firmware"]["latest_signed"]["version"], "18.5")
            actions = {item["id"]: item for item in snapshot["actions"]}
            self.assertTrue(actions["research-runtime"]["available"])
            self.assertTrue(actions["tethered-downgrade"]["available"])
            self.assertEqual(
                actions["tethered-downgrade"]["title"],
                "Guided tethered downgrade",
            )
            self.assertIn(
                "separately installed external tether adapter",
                actions["tethered-downgrade"]["reason"],
            )
            self.assertTrue(actions["ramdisk"]["available"])
            self.assertEqual(
                actions["ramdisk"]["title"], "Guided ramdisk maker / loader"
            )
            self.assertIn(
                "target/build-specific adapter", actions["ramdisk"]["reason"]
            )

    def test_normal_mode_reports_current_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            info = root / "ideviceinfo"
            identifier = root / "idevice_id"
            plist = plistlib.dumps({
                "UniqueDeviceID": "udid",
                "UniqueChipID": 1234,
                "ProductType": "iPhone12,1",
                "HardwareModel": "N104AP",
                "DeviceName": "Test Phone",
                "ProductVersion": "17.6.1",
                "BuildVersion": "21G93",
            })
            info.write_text(
                "#!/usr/bin/env python3\nimport sys\nsys.stdout.buffer.write(" +
                repr(plist) + ")\n",
                encoding="utf-8",
            )
            identifier.write_text("#!/bin/sh\necho udid\n", encoding="utf-8")
            info.chmod(0o755)
            identifier.chmod(0o755)
            result = query_normal_device(
                ideviceinfo=str(info),
                idevice_id=str(identifier),
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["current_version"], "17.6.1")
            self.assertEqual(result["mode"], "Normal")


if __name__ == "__main__":
    unittest.main()
