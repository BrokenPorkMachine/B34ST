from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from host.boot_image import Component, build_image
from host.irecovery_boot import RecoveryError, parse_query, validate_target
from host.boot_image import load_profile

ROOT = pathlib.Path(__file__).resolve().parents[1]


class IRecoveryBootTests(unittest.TestCase):
    def test_query_parser_accepts_standard_fields(self) -> None:
        info = parse_query("CPID: 0x8030\nECID: 1234\nMODE: Recovery Mode\nPRODUCT: iPhone12,1\nMODEL: N104AP\n")
        self.assertEqual(info.cpid, 0x8030)
        self.assertEqual(info.product, "iPhone12,1")
        self.assertEqual(info.mode, "Recovery Mode")

    def test_profile_rejects_wrong_family(self) -> None:
        info = parse_query("CPID: 0x8030\nMODE: DFU\n")
        with self.assertRaises(RecoveryError):
            validate_target(load_profile(ROOT / "profiles/apple-a12-recovery.json"), info)

    def test_send_requires_authorized_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            monitor = root / "monitor.bin"
            monitor.write_bytes(b"M" * 4096)
            image = root / "boot.img"
            build_image(image, ROOT / "profiles/apple-a12-recovery.json",
                        [Component("monitor", monitor)])
            device = root / "device.json"
            device.write_text(json.dumps({"cpid": "0x8020", "mode": "DFU", "ecid": "1"}))
            result = subprocess.run(
                [sys.executable, "host/irecovery_boot.py", "send",
                 "--profile", "profiles/apple-a12-recovery.json",
                 "--image", str(image), "--device-info", str(device)],
                cwd=ROOT, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("--authorized-session", result.stderr)

    def test_fake_irecovery_send_and_execute(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            monitor = root / "monitor.bin"
            monitor.write_bytes(b"N" * 4096)
            image = root / "boot.img"
            build_image(image, ROOT / "profiles/apple-a13-recovery.json",
                        [Component("monitor", monitor)])
            device = root / "device.json"
            device.write_text(json.dumps({"cpid": "0x8030", "mode": "DFU", "ecid": "abcd"}))
            log = root / "irecovery.log"
            fake = root / "irecovery"
            fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FBR_TEST_LOG\"\nexit 0\n")
            fake.chmod(0o755)
            evidence = root / "evidence.json"
            env = os.environ.copy(); env["FBR_TEST_LOG"] = str(log)
            result = subprocess.run(
                [sys.executable, "host/irecovery_boot.py", "send",
                 "--irecovery", str(fake),
                 "--profile", "profiles/apple-a13-recovery.json",
                 "--image", str(image), "--device-info", str(device),
                 "--authorized-session", "--execute", "--acknowledge-unsigned-code",
                 "--evidence", str(evidence)],
                cwd=ROOT, env=env, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = log.read_text().splitlines()
            self.assertEqual(len(calls), 2)
            self.assertIn("-f", calls[0])
            self.assertIn("-c bootx", calls[1])
            record = json.loads(evidence.read_text())
            self.assertTrue(record["sent"])
            self.assertTrue(record["executed"])

    def test_verify_is_read_only_and_records_profile_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            device = root / "device.json"
            device.write_text(json.dumps({"cpid": "0x8030", "mode": "DFU", "ecid": "abcd"}))
            evidence = root / "verify.json"
            result = subprocess.run(
                [sys.executable, "host/irecovery_boot.py", "verify",
                 "--profile", "profiles/apple-a13-recovery.json",
                 "--device-info", str(device), "--evidence", str(evidence)],
                cwd=ROOT, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(evidence.read_text())
            self.assertTrue(value["passed"])
            self.assertEqual(value["operation"], "irecovery-verify")


if __name__ == "__main__":
    unittest.main()
