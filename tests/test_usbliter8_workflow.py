# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import pathlib
import tempfile
import types
import unittest
from unittest import mock

import b34st.engine as engine
from scripts import run_exploit


class USBLiter8WorkflowTests(unittest.TestCase):
    def _fake_root(self, root: pathlib.Path, with_image: bool = True) -> pathlib.Path:
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / "run_exploit.py").write_text("#!/usr/bin/env python3\n")
        (root / "build-exploit").mkdir(parents=True, exist_ok=True)
        if with_image:
            (root / "build-exploit" / "fbr34ker-operational.bin").write_bytes(b"MON")
        return root

    def test_usbliter8_skip_hardware_prep_uses_existing_monitor_without_auto_build(self) -> None:
        cli = engine.B34STCLI(quiet=True)
        with tempfile.TemporaryDirectory() as directory:
            fake_root = self._fake_root(pathlib.Path(directory))
            calls: list[list[str]] = []

            def fake_run(cmd, **kwargs):
                calls.append([str(part) for part in cmd])
                return types.SimpleNamespace(returncode=0)

            with (
                mock.patch.object(engine, "ROOT", fake_root),
                mock.patch("subprocess.run", side_effect=fake_run),
                mock.patch("builtins.input", side_effect=["I OWN OR AM AUTHORIZED TO TEST THIS DEVICE"]),
            ):
                result = cli._usbliter8([
                    "--skip-hardware-prep",
                    "--skip-build",
                    "--no-console",
                    "--no-return",
                    "--no-dfu-wait",
                ])

        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)
        command = calls[0]
        self.assertIn("--monitor", command)
        self.assertIn(str(fake_root / "build-exploit" / "fbr34ker-operational.bin"), command)
        self.assertIn("--no-dfu-wait", command)
        self.assertNotIn("--auto", command)

    def test_usbliter8_skip_build_fails_when_operational_image_missing(self) -> None:
        cli = engine.B34STCLI(quiet=True)
        with tempfile.TemporaryDirectory() as directory:
            fake_root = self._fake_root(pathlib.Path(directory), with_image=False)
            with mock.patch.object(engine, "ROOT", fake_root):
                result = cli._usbliter8([
                    "--skip-hardware-prep",
                    "--skip-build",
                    "--no-console",
                    "--no-return",
                ])

        self.assertEqual(result, 1)

    def test_run_exploit_accepts_no_dfu_wait_and_propagates_it(self) -> None:
        fake_chain = mock.MagicMock()
        fake_chain.__enter__.return_value = fake_chain
        fake_chain.run_all.return_value = {
            "device_found": True,
            "chipset_detected": True,
            "dwc_exploited": True,
            "monitor_sent": True,
            "monitor_executed": True,
            "console_connected": True,
            "exploit_chain": True,
            "jailbreak_chain": True,
            "kernel_booted": True,
        }
        fake_chain.dev.chipset_name = "A12"
        fake_chain.dev.chipset = {"name": "A12"}

        with tempfile.TemporaryDirectory() as directory:
            monitor = pathlib.Path(directory) / "monitor.bin"
            monitor.write_bytes(b"MON")
            with (
                mock.patch.object(run_exploit, "HAS_USB", True),
                mock.patch.object(run_exploit, "build_operational", return_value=str(monitor)),
                mock.patch.object(run_exploit, "BootChain", return_value=fake_chain),
                mock.patch("sys.argv", ["run_exploit.py", "--auto", "--no-dfu-wait"]),
            ):
                result = run_exploit.main()

        self.assertEqual(result, 0)
        self.assertTrue(fake_chain.skip_dfu_wait)


if __name__ == "__main__":
    unittest.main()
