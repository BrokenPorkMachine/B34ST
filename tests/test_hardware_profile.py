import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

import hardware_profile  # noqa: E402


class HardwareProfileTests(unittest.TestCase):
    def test_template_validates(self) -> None:
        normalized = hardware_profile.validate_profile(hardware_profile.template_profile())
        self.assertEqual(normalized["architecture"], "arm64")
        self.assertIn("memory_map", normalized["required_services"])

    def test_rejects_unknown_or_non_arm64_profile(self) -> None:
        profile = hardware_profile.template_profile()
        profile["architecture"] = "x86_64"
        with self.assertRaises(hardware_profile.HardwareProfileError):
            hardware_profile.validate_profile(profile)
        profile = hardware_profile.template_profile()
        profile["unexpected"] = True
        with self.assertRaises(hardware_profile.HardwareProfileError):
            hardware_profile.validate_profile(profile)

    def test_compatibility_matrix_from_metadata_only_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            records = {
                "handoff-info": "Version: 4\n",
                "exception-level": "Current exception level: EL1\n",
                "console-services": "Primary console: callback\n",
                "timer-test": "timer-test: frequency=24000000 monotonic=yes\n",
                "memory-check": "memory map: ok\nhandoff:    ok\nheap:       ok\nstack:      ok\n",
                "device-tree-summary": "FDT: validated\n",
                "services": "console output: yes\ntimer: yes\n",
                "irq-controller": "GICv3 delivery: masked\n",
                "watchdog-services": "configure: unavailable\nkick: unavailable\n",
                "framebuffer-info": "No framebuffer\n",
                "probe-status": "Modules:         LOCKED\n",
                "compatibility": "Modules LOCKED\n",
            }
            for name, text in records.items():
                (root / f"{name}.txt").write_text(text, encoding="utf-8")
            profile = hardware_profile.template_profile()
            profile["required_services"] = ["console_write", "monotonic_time", "memory_map"]
            report = hardware_profile.check_profile(profile, root)
            self.assertEqual(report["result"], "partial")
            self.assertFalse(any(item["state"] == "FAIL" for item in report["matrix"]))
            self.assertEqual(report["diagnostics"], root.name)
            formatted = hardware_profile.format_matrix(report)
            self.assertIn("Boot handoff", formatted)
            self.assertIn("LOCKED", formatted)

    def test_profile_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "board.json"
            hardware_profile.write_profile_template(path)
            loaded = hardware_profile.load_profile(path)
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)
            self.assertEqual(loaded["name"], "example-arm64-board")


if __name__ == "__main__":
    unittest.main()
