# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from hardware_profile import load_profile, import_probe_results, validate_profile  # noqa: E402


class ProfileImportTests(unittest.TestCase):
    def test_import_never_promotes_untested_services(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            records = {
                "handoff-info": "Version:        4\n",
                "exception-level": "Current exception level: EL1\n",
                "console-services": "Primary console: loader service callback\n",
                "services": "console output: yes\nconsole input: no\ntimer: yes\n",
                "timer-test": "timer-test: frequency=1000000 elapsed=10ms\n",
                "memory-check": "memory map: ok\nhandoff:    ok\nheap:       ok\nstack:      ok\n",
                "irq-controller": "polling-only\n",
                "probe-status": "Modules:         LOCKED\n",
            }
            for name, text in records.items():
                (d / f"{name}.txt").write_text(text)
            reviewed = import_probe_results(
                load_profile(ROOT / "examples/hardware-profile.json"), d
            )
            review = reviewed["review"]
            self.assertIn("console_write", review["supported_services"])
            self.assertIn("memory_map", review["supported_services"])
            self.assertNotIn("console_read", review["supported_services"])
            validate_profile(reviewed)


if __name__ == "__main__":
    unittest.main()
