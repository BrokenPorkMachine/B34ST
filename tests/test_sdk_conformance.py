from __future__ import annotations

import pathlib
import tempfile
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from handoff_binary import build_blob  # noqa: E402
from sdk_conformance import check  # noqa: E402


class SDKConformanceTests(unittest.TestCase):
    def test_reference_design_is_partial_not_failed(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "h.fbhb"
            p.write_bytes(build_blob(ROOT / "examples/handoff-v4.json"))
            report = check(p, profile_path=ROOT / "examples/hardware-profile.json")
            self.assertEqual(report["result"], "partial")
            states = {x["feature"]: x["state"] for x in report["matrix"]}
            self.assertEqual(states["ABI layout"], "PASS")
            self.assertEqual(states["Callback containment"], "NOT TESTED")


if __name__ == "__main__":
    unittest.main()
