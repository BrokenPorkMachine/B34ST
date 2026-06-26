from __future__ import annotations

import json
import pathlib
import plistlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

from host.ipsw_manager import inspect_ipsw, normalize_catalog, select_firmware

ROOT = pathlib.Path(__file__).resolve().parents[1]


class IPSWManagerTests(unittest.TestCase):
    def ipsw(self, root: pathlib.Path) -> pathlib.Path:
        path = root / "iPhone12,1_17.6.1_21G93_Restore.ipsw"
        restore = {
            "ProductVersion": "17.6.1",
            "ProductBuildVersion": "21G93",
            "SupportedProductTypes": ["iPhone12,1"],
        }
        manifest = {
            "ProductVersion": "17.6.1",
            "ProductBuildVersion": "21G93",
            "SupportedProductTypes": ["iPhone12,1"],
            "BuildIdentities": [],
        }
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Restore.plist", plistlib.dumps(restore))
            archive.writestr("BuildManifest.plist", plistlib.dumps(manifest))
        return path

    def catalog(self, root: pathlib.Path, *, signed: bool) -> pathlib.Path:
        value = {
            "name": "iPhone 11",
            "identifier": "iPhone12,1",
            "firmwares": [{
                "identifier": "iPhone12,1",
                "version": "17.6.1",
                "buildid": "21G93",
                "signed": signed,
                "url": "https://updates.cdn-apple.com/test/iPhone12,1_17.6.1_21G93_Restore.ipsw",
                "releasedate": "2024-08-07T00:00:00Z",
            }],
        }
        path = root / "catalog.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_catalog_normalization_and_selection(self) -> None:
        value = json.loads(self.catalog(pathlib.Path(tempfile.mkdtemp()), signed=True).read_text())
        catalog = normalize_catalog(value, "iPhone12,1")
        selected = select_firmware(
            catalog,
            version="17.6.1",
            build=None,
            signed_only=True,
        )
        self.assertEqual(selected["build"], "21G93")
        self.assertTrue(selected["signed"])

    def test_ipsw_inspection_extracts_target_and_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = inspect_ipsw(self.ipsw(pathlib.Path(directory)))
            self.assertEqual(result["product_version"], "17.6.1")
            self.assertEqual(result["product_build"], "21G93")
            self.assertIn("iPhone12,1", result["supported_products"])

    def test_signed_upgrade_plans_with_no_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    "host/ipsw_manager.py",
                    "--catalog",
                    str(self.catalog(root, signed=True)),
                    "upgrade",
                    "--product",
                    "iPhone12,1",
                    "--ipsw",
                    str(self.ipsw(root)),
                    "--idevicerestore",
                    "/usr/bin/true",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsigned_firmware_is_tethered_plan_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    "host/ipsw_manager.py",
                    "--catalog",
                    str(self.catalog(root, signed=False)),
                    "tethered-downgrade",
                    "--product",
                    "iPhone12,1",
                    "--ipsw",
                    str(self.ipsw(root)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertTrue(plan["tethered"])
            self.assertFalse(plan["persistent"])
            self.assertTrue(plan["requires_external_first_stage"])


if __name__ == "__main__":
    unittest.main()
