# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class EvidenceCompareTests(unittest.TestCase):
    def test_reports_stage_change(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = root / "a.json"
            b = root / "b.json"
            base = {
                "profile_id": "x",
                "device": {"cpid": "0x8030"},
                "image": {"sha256": "a"},
                "passed": True,
                "failure": None,
                "stages": [{"stage": "timer", "status": "passed"}],
            }
            a.write_text(json.dumps(base))
            changed = {
                **base,
                "passed": False,
                "failure": "timer",
                "stages": [{"stage": "timer", "status": "failed"}],
            }
            b.write_text(json.dumps(changed))
            result = subprocess.run(
                [sys.executable, "host/evidence_compare.py", str(a), str(b)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertFalse(value["equal"])
            self.assertTrue(any(x["field"] == "stage:timer" for x in value["changes"]))


if __name__ == "__main__":
    unittest.main()
