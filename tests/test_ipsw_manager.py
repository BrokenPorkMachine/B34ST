# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import argparse
import json
import os
import pathlib
import plistlib
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

from host.ipsw_manager import (
    _select_unsigned_firmware,
    inspect_ipsw,
    normalize_catalog,
    select_firmware,
)

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

    def test_catalog_can_list_unsigned_targets_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    "host/ipsw_manager.py",
                    "--catalog",
                    str(self.catalog(root, signed=False)),
                    "catalog",
                    "--product",
                    "iPhone12,1",
                    "--unsigned-only",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            catalog = json.loads(result.stdout)
            self.assertEqual(len(catalog["firmwares"]), 1)
            self.assertFalse(catalog["firmwares"][0]["signed"])

    def test_guide_can_select_an_exact_unsigned_download_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            args = argparse.Namespace(
                product="iPhone12,1",
                catalog=str(self.catalog(root, signed=False)),
                timeout=1.0,
                version="17.6.1",
                build=None,
            )
            with mock.patch("builtins.input") as input_mock:
                selected = _select_unsigned_firmware(args)
            self.assertEqual(selected["version"], "17.6.1")
            self.assertEqual(selected["build"], "21G93")
            input_mock.assert_not_called()

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
            self.assertFalse(plan["execution_readiness"]["ready"])
            self.assertIn(
                "separately installed, target-specific executable",
                plan["adapter_contract"]["definition"],
            )
            self.assertIn(
                "The IPSW file",
                plan["adapter_contract"]["not_an_adapter"],
            )
            self.assertIn(
                "None is a verified drop-in adapter",
                plan["adapter_contract"]["public_compatibility"],
            )
            self.assertIn(
                "No external tether adapter",
                plan["execution_readiness"]["blockers"][0],
            )

    def test_guided_plan_is_human_readable_and_writes_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "plan.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "host/ipsw_manager.py",
                    "--catalog",
                    str(self.catalog(root, signed=False)),
                    "tethered-downgrade-guide",
                    "--product",
                    "iPhone12,1",
                    "--ipsw",
                    str(self.ipsw(root)),
                    "--plan-only",
                    "--evidence",
                    str(evidence),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("What is the tether adapter?", result.stdout)
            self.assertIn(
                "separately installed, target-specific executable",
                result.stdout,
            )
            self.assertIn("It is not the IPSW", result.stdout)
            self.assertIn(
                "None is a verified drop-in adapter",
                result.stdout,
            )
            self.assertIn("Tethered downgrade plan", result.stdout)
            self.assertIn("Execution:   PLAN ONLY", result.stdout)
            self.assertIn("Stopped after planning", result.stdout)
            self.assertTrue(evidence.is_file())

    def test_external_adapter_contract_executes_and_records_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            adapter = root / "adapter.py"
            adapter.write_text(
                "import json, sys\n"
                "request = json.load(sys.stdin)\n"
                "print(json.dumps({'ok': request['operation'] == "
                "'tethered-downgrade'}))\n",
                encoding="utf-8",
            )
            evidence = root / "execution.json"
            adapter_command = (
                f"{shlex.quote(sys.executable)} {shlex.quote(str(adapter))}"
            )
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
                    "--adapter-command",
                    adapter_command,
                    "--execute",
                    "--owner-authorization",
                    "I OWN OR AM AUTHORIZED TO RESTORE THIS DEVICE",
                    "--confirm",
                    "START TETHERED DOWNGRADE",
                    "--evidence",
                    str(evidence),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertTrue(recorded["adapter_response"]["ok"])
            self.assertEqual(recorded["exit_code"], 0)

    def test_missing_adapter_error_explains_configuration(self) -> None:
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
                    "--execute",
                    "--owner-authorization",
                    "I OWN OR AM AUTHORIZED TO RESTORE THIS DEVICE",
                    "--confirm",
                    "START TETHERED DOWNGRADE",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env={"PATH": os.environ.get("PATH", "")},
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("B34ST_TETHER_ADAPTER", result.stderr)

    def test_guide_rejects_an_explicit_invalid_adapter_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "plan.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "host/ipsw_manager.py",
                    "--catalog",
                    str(self.catalog(root, signed=False)),
                    "tethered-downgrade-guide",
                    "--product",
                    "iPhone12,1",
                    "--ipsw",
                    str(self.ipsw(root)),
                    "--adapter-command",
                    "/missing/tether-adapter",
                    "--evidence",
                    str(evidence),
                ],
                cwd=ROOT,
                text=True,
                input="",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("not found or is not executable", result.stderr)
            self.assertTrue(evidence.is_file())


if __name__ == "__main__":
    unittest.main()
