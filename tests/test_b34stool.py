from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import b34stool

ROOT = pathlib.Path(__file__).resolve().parents[1]


class B34SToolTests(unittest.TestCase):
    def test_sixteen_categories_are_registered(self) -> None:
        self.assertEqual(len(b34stool.CATEGORIES), 16)
        self.assertIn("forensics.acquire", b34stool.ACTION_MAP)
        self.assertIn("forensics.verify", b34stool.ACTION_MAP)
        self.assertIn("research-runtime.validate-evidence", b34stool.ACTION_MAP)
        guided = b34stool.ACTION_MAP["ipsw.tethered-downgrade"]
        self.assertIn("tethered-downgrade-guide", guided.command)
        self.assertTrue(guided.interactive)
        self.assertIn("ramdisk.guide", b34stool.ACTION_MAP)
        self.assertIn("ramdisk.load", b34stool.ACTION_MAP)
        self.assertTrue(b34stool.ACTION_MAP["ramdisk.guide"].interactive)

    def test_noninteractive_command_writes_session_log_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_dir = pathlib.Path(directory) / "session"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "b34stool.py"),
                    "--session-dir",
                    str(session_dir),
                    "--command",
                    "system.version",
                    "--json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((session_dir / "session.log").is_file())
            evidence_path = session_dir / "evidence" / "001-system.version.json"
            self.assertTrue(evidence_path.is_file())
            evidence = json.loads(evidence_path.read_text())
            self.assertEqual(evidence["schema_version"], 1)
            self.assertEqual(evidence["operation"], "system.version")
            self.assertEqual(evidence["exit_code"], 0)
            self.assertIn("duration_ms", evidence)
            summary = json.loads(result.stdout.splitlines()[-1])
            self.assertTrue(summary["ok"])
            self.assertEqual(pathlib.Path(summary["session"]), session_dir)

    def test_root_launcher_passes_arguments_through(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "b34stool", "--list"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("System:", result.stdout)
        self.assertIn("b34st.environment-plan", result.stdout)


if __name__ == "__main__":
    unittest.main()
