# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import pathlib
import runpy
import subprocess
import unittest
from unittest import mock

from b34st.version import __version__

ROOT = pathlib.Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_guided_tool_arguments_cancel_on_empty_input(self) -> None:
        namespace = runpy.run_path(str(ROOT / "fbr34ker"))
        with mock.patch("builtins.input", return_value=""):
            self.assertIsNone(namespace["_tool_arguments"]("module-status"))

    def test_guided_tool_arguments_preserve_quoted_values(self) -> None:
        namespace = runpy.run_path(str(ROOT / "fbr34ker"))
        with mock.patch(
            "builtins.input",
            return_value='command "hello world"',
        ):
            self.assertEqual(
                namespace["_tool_arguments"]("module-status"),
                ["command", "hello world"],
            )

    def test_help_and_short_flags_are_documented(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("--build", result.stdout)
        self.assertIn("--run", result.stdout)
        self.assertIn("--clean", result.stdout)
        self.assertIn("-b", result.stdout)
        self.assertIn("-r", result.stdout)
        self.assertIn("-c", result.stdout)
        self.assertIn("--package", result.stdout)
        self.assertIn("--permissions", result.stdout)
        self.assertIn("menu", result.stdout)


    def test_version_matches_runtime_architecture(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "--version"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), f"FBR34KER {__version__}")

    def test_unknown_flag_is_rejected(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "--not-a-real-option"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown option", result.stderr)

    def test_root_invocation_routes_to_interactive_menu(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("B34ST control panel requires an interactive TTY", result.stderr)

    def test_menu_flag_alias_routes_to_interactive_menu(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "--menu"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Interactive menu requires a TTY", result.stderr)

    def test_control_panel_requires_tty(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "control-panel"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("B34ST control panel requires an interactive TTY", result.stderr)

    def test_b34st_version_is_available_through_root_launcher(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "b34st", "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"B34ST {__version__}", result.stdout)

    def test_canonical_source_tree_b34st_launcher(self) -> None:
        result = subprocess.run(
            [str(ROOT / "scripts" / "B34ST"), "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"B34ST {__version__}", result.stdout)

    def test_b34st_backend_passthrough(self) -> None:
        result = subprocess.run(
            [str(ROOT / "scripts" / "B34ST"), "fbr34ker", "version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"FBR34KER {__version__}", result.stdout)

    def test_control_panel_forensics_alias(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "forensics", "list-profiles"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Built-in acquisition profiles", result.stdout)
        self.assertIn("quick", result.stdout)

    def test_control_panel_cve_alias(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "cve", "stats"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"total_cves"', result.stdout)

    def test_installed_launcher_forensics_alias(self) -> None:
        result = subprocess.run(
            [
                "python3",
                str(ROOT / "host" / "fbr34ker_cli.py"),
                "forensics",
                "list-profiles",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Built-in acquisition profiles", result.stdout)

    def test_installed_launcher_cve_alias(self) -> None:
        result = subprocess.run(
            ["python3", str(ROOT / "host" / "fbr34ker_cli.py"), "cve", "stats"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"total_cves"', result.stdout)

    def test_ramdisk_targets_are_available_through_root_launcher(self) -> None:
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "ramdisk", "list-targets", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"device_class": "iphone"', result.stdout)
        self.assertIn('"device_class": "ipad"', result.stdout)
        self.assertIn('"device_class": "mac"', result.stdout)

    def test_ramdisk_targets_are_available_through_installed_launcher(self) -> None:
        result = subprocess.run(
            [
                "python3",
                str(ROOT / "host" / "fbr34ker_cli.py"),
                "ramdisk",
                "list-targets",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"target_count"', result.stdout)


if __name__ == "__main__":
    unittest.main()
