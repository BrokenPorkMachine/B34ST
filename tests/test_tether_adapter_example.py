# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "tether_adapter_contract_example.py"


class TetherAdapterExampleTests(unittest.TestCase):
    def test_description_cannot_be_mistaken_for_a_real_adapter(self) -> None:
        result = subprocess.run(
            [sys.executable, str(EXAMPLE), "--describe"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        description = json.loads(result.stdout)
        self.assertFalse(description["performs_device_io"])
        self.assertFalse(description["execution_supported"])
        self.assertEqual(description["device_support"], [])

    def test_valid_request_is_rejected_as_contract_only(self) -> None:
        request = {
            "schema_version": 1,
            "operation": "tethered-downgrade",
            "arguments": {
                "product": "iPhone12,1",
                "ipsw_path": "/tmp/target.ipsw",
                "ipsw_sha256": "a" * 64,
                "version": "17.6.1",
                "build": "21G93",
                "ecid": "1234",
                "tethered": True,
            },
        }
        result = subprocess.run(
            [sys.executable, str(EXAMPLE)],
            cwd=ROOT,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        response = json.loads(result.stdout)
        self.assertFalse(response["ok"])
        self.assertFalse(response["performs_device_io"])
        self.assertIn("contract example only", response["error"])
        self.assertEqual(response["validated_target"]["product"], "iPhone12,1")

    def test_unknown_argument_is_rejected(self) -> None:
        request = {
            "schema_version": 1,
            "operation": "tethered-downgrade",
            "arguments": {
                "product": "iPhone12,1",
                "ipsw_path": "/tmp/target.ipsw",
                "ipsw_sha256": "a" * 64,
                "version": "17.6.1",
                "build": "21G93",
                "tethered": True,
                "unexpected": True,
            },
        }
        result = subprocess.run(
            [sys.executable, str(EXAMPLE)],
            cwd=ROOT,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown arguments", json.loads(result.stdout)["error"])


if __name__ == "__main__":
    unittest.main()
