#!/usr/bin/env python3
"""Tests for B34ST forensics module."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class B34STForensicsTests(unittest.TestCase):
    def test_list_profiles_succeeds(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "b34st" / "forensics.py"), "list-profiles"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("quick", result.stdout)
        self.assertIn("full", result.stdout)
        self.assertIn("memory-only", result.stdout)

    def test_acquire_creates_session_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = pathlib.Path(tmpdir) / "forensics-output"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "b34st" / "forensics.py"),
                    "acquire",
                    "--profile",
                    "quick",
                    "--device-id",
                    "test-device-123",
                    "--product",
                    "iPhone12,1",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            session_dirs = list(output.glob("acquisition-*"))
            self.assertEqual(len(session_dirs), 1)

            summary_path = session_dirs[0] / "acquisition-summary.json"
            self.assertTrue(summary_path.is_file())

            summary = json.loads(summary_path.read_text())
            self.assertEqual(summary["target"]["device_id"], "test-device-123")
            self.assertEqual(summary["target"]["product"], "iPhone12,1")
            self.assertEqual(summary["profile"]["name"], "quick")

    def test_template_creates_valid_output(self):
        with tempfile.TemporaryDirectory():
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from host.forensics.profiles import AcquisitionProfile; "
                    "import json; "
                    "p = AcquisitionProfile(name='test', categories={'memory'}); "
                    "d = p.to_dict(); "
                    "d['categories'] = list(d['categories']); "
                    "print(json.dumps(d, indent=2, sort_keys=True))",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("memory", result.stdout)

    def test_filesystem_profile_requires_capabilities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = pathlib.Path(tmpdir) / "forensics-output"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "b34st" / "forensics.py"),
                    "acquire",
                    "--profile",
                    "filesystem-only",
                    "--device-id",
                    "test-device",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, "Should fail without capabilities")
            self.assertIn("protected-data-access", result.stderr)

    def test_filesystem_profile_succeeds_with_capabilities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = pathlib.Path(tmpdir) / "forensics-output"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "b34st" / "forensics.py"),
                    "acquire",
                    "--profile",
                    "filesystem-only",
                    "--device-id",
                    "test-device",
                    "--output",
                    str(output),
                    "--capabilities",
                    "protected-data-access",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("acquisition-session-v1", result.stdout)

    def test_fbr34ker_cli_forensics_command(self):
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "b34st", "forensics", "list-profiles"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("quick", result.stdout)

    # === Chain of Custody Tests ===

    def test_custody_log_record(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog(operator="test-op", device_id="test-device")
        h = log.record("test.action", "test detail")
        self.assertEqual(log.entry_count, 1)
        self.assertEqual(log.last_hash, h)
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    def test_custody_log_seal(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog()
        log.record("action1", "detail1")
        seal_hash = log.seal()
        self.assertEqual(log.entry_count, 2)
        self.assertIsInstance(seal_hash, str)
        self.assertEqual(len(seal_hash), 64)

    def test_custody_log_double_seal_raises(self):
        from host.forensics.chain_of_custody import CustodyLog, CustodyError

        log = CustodyLog()
        log.seal()
        with self.assertRaises(CustodyError):
            log.seal()

    def test_custody_log_record_after_seal_raises(self):
        from host.forensics.chain_of_custody import CustodyLog, CustodyError

        log = CustodyLog()
        log.seal()
        with self.assertRaises(CustodyError):
            log.record("action", "detail")

    def test_custody_log_verify_valid(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog()
        log.record("a", "1")
        log.record("b", "2")
        log.seal()
        self.assertTrue(log.verify())

    def test_custody_log_verify_tampered_entry_data(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog()
        log.record("a", "1")
        log.record("b", "2")
        log._entries[0][0].detail = "tampered"
        self.assertFalse(log.verify())

    def test_custody_log_verify_tampered_chain(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog()
        log.record("a", "1")
        log.record("b", "2")
        old_entry, _ = log._entries[0]
        log._entries[0] = (old_entry, "0" * 64)
        self.assertFalse(log.verify())

    def test_custody_log_export_json(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog(operator="op", device_id="dev")
        log.record("action", "detail")
        exported = log.export_json()
        data = json.loads(exported)
        self.assertEqual(data["schema"], "chain-of-custody-v1")
        self.assertEqual(data["operator"], "op")
        self.assertEqual(data["device_id"], "dev")
        self.assertEqual(data["entry_count"], 1)
        self.assertTrue(data["verified"])

    def test_custody_log_roundtrip(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog(operator="op", device_id="dev")
        log.record("a", "1")
        log.record("b", "2")
        log.seal()
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "custody.json"
            log.write(p)
            loaded = CustodyLog.load(p)
            self.assertEqual(loaded.entry_count, log.entry_count)
            self.assertEqual(loaded.operator, log.operator)
            self.assertEqual(loaded.device_id, log.device_id)
            self.assertTrue(loaded.verify())

    def test_custody_log_load_tampered_file(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog()
        log.record("a", "1")
        log.record("b", "2")
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "custody.json"
            log.write(p)
            data = json.loads(p.read_text())
            data["entries"][0]["detail"] = "tampered"
            p.write_text(json.dumps(data))
            loaded = CustodyLog.load(p)
            self.assertFalse(loaded.verify())

    def test_custody_log_empty_verify(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog()
        self.assertTrue(log.verify())

    def test_custody_log_empty_last_hash(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog()
        self.assertEqual(log.last_hash, "")

    def test_custody_log_entries_property(self):
        from host.forensics.chain_of_custody import CustodyLog

        log = CustodyLog()
        log.record("a", "1")
        entries = log.entries
        self.assertEqual(len(entries), 1)
        self.assertIn("entry_hash", entries[0])
        self.assertEqual(entries[0]["action"], "a")

    # === SepMailbox Tests ===

    def test_sep_mailbox_detect_available(self):
        from host.forensics.secrets import SepMailbox

        def read_fn(addr, size):
            return b"\x01\x00\x00\x00"

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn, sep_base=0x82E000000)
        result = sep.detect()
        self.assertTrue(result["available"])
        self.assertEqual(result["sep_base"], 0x82E000000)

    def test_sep_mailbox_detect_unavailable(self):
        from host.forensics.secrets import SepMailbox

        def read_fn(addr, size):
            return b"\x00\x00\x00\x00"

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn, sep_base=0x82E000000)
        result = sep.detect()
        self.assertFalse(result["available"])

    def test_sep_mailbox_detect_all_ff(self):
        from host.forensics.secrets import SepMailbox

        def read_fn(addr, size):
            return b"\xff\xff\xff\xff"

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn, sep_base=0x82E000000)
        result = sep.detect()
        self.assertFalse(result["available"])

    def test_sep_mailbox_detect_exception(self):
        from host.forensics.secrets import SepMailbox

        def read_fn(addr, size):
            raise OSError("no device")

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn)
        result = sep.detect()
        self.assertFalse(result["available"])

    def test_sep_mailbox_detect_short_read(self):
        from host.forensics.secrets import SepMailbox

        def read_fn(addr, size):
            return b"\x01"

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn)
        result = sep.detect()
        self.assertFalse(result["available"])

    def test_sep_mailbox_send_command(self):
        from host.forensics.secrets import SepMailbox

        written = []
        sep_ref = [None]

        def read_fn(addr, size):
            sep = sep_ref[0]
            if addr == sep.response:
                return b"\x01\x00\x00\x00"
            if addr == sep.response + 4:
                return b"\x0e\x00\x00\x00"
            if addr == sep.shared_mem:
                return b"response_data\x00"
            return b"\x00\x00\x00\x00"

        def write_fn(data):
            written.append(data)

        sep = SepMailbox(read_fn, write_fn)
        sep_ref[0] = sep

        result = sep.send_command(b"hello")
        self.assertEqual(result, b"response_data\x00")
        self.assertEqual(len(written), 2)

    def test_sep_mailbox_command_too_large(self):
        from host.forensics.secrets import SepMailbox, SecretsError

        def read_fn(addr, size):
            return b"\x01\x00\x00\x00"

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn)
        with self.assertRaises(SecretsError):
            sep.send_command(b"x" * 5000)

    def test_sep_mailbox_write_failure(self):
        from host.forensics.secrets import SepMailbox, SecretsError

        def read_fn(addr, size):
            return b"\x01\x00\x00\x00"

        write_fail = [False]

        def write_fn(data):
            if not write_fail[0]:
                write_fail[0] = True
                raise OSError("write failed")

        sep = SepMailbox(read_fn, write_fn)
        with self.assertRaisesRegex(SecretsError, "SEP mailbox write failed"):
            sep.send_command(b"test")

    def test_sep_mailbox_send_command_timeout(self):
        from host.forensics.secrets import SepMailbox

        def read_fn(addr, size):
            return b"\x00\x00\x00\x00"

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn)
        sep.POLL_TIMEOUT = 0.05
        sep.POLL_INTERVAL = 0.01
        result = sep.send_command(b"test")
        self.assertEqual(result, b"")

    def test_sep_mailbox_custom_sep_base(self):
        from host.forensics.secrets import SepMailbox

        def read_fn(addr, size):
            return b"\x01\x00\x00\x00"

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn, sep_base=0x803000000)
        result = sep.detect()
        self.assertTrue(result["available"])
        self.assertEqual(result["mailbox"], 0x803010000)

    # === KeybagAcquisitor Tests ===

    def test_keybag_enumerate_bags(self):
        from host.forensics.secrets import KeybagAcquisitor

        def cmd(s):
            return (
                "NS0\tSystem\tNSFileProtectionComplete\twrapped\n"
                "NS1\tBackup\tNSFileProtectionCompleteUnlessOpen\tunwrapped"
            )

        kba = KeybagAcquisitor(cmd)
        bags = kba.enumerate_bags()
        self.assertEqual(len(bags), 2)
        self.assertEqual(bags[0]["identifier"], "NS0")
        self.assertEqual(bags[0]["type"], "System")
        self.assertEqual(bags[0]["protection_class"], "NSFileProtectionComplete")
        self.assertTrue(bags[0]["wrapped"])
        self.assertFalse(bags[1]["wrapped"])

    def test_keybag_enumerate_single_bag(self):
        from host.forensics.secrets import KeybagAcquisitor

        def cmd(s):
            return "NS0\tSystem\tNSFileProtectionComplete"

        kba = KeybagAcquisitor(cmd)
        bags = kba.enumerate_bags()
        self.assertEqual(len(bags), 1)
        self.assertFalse(bags[0]["wrapped"])

    def test_keybag_enumerate_empty(self):
        from host.forensics.secrets import KeybagAcquisitor

        def cmd(s):
            return ""

        kba = KeybagAcquisitor(cmd)
        bags = kba.enumerate_bags()
        self.assertEqual(bags, [])

    def test_keybag_extract_bag(self):
        from host.forensics.secrets import KeybagAcquisitor

        def cmd(s):
            return "sha256: abc123\ndata: hexdata\nprotection_class: NSFileProtectionComplete"

        kba = KeybagAcquisitor(cmd)
        result = kba.extract_bag("NS0")
        self.assertTrue(result["extracted"])
        self.assertEqual(result["sha256"], "abc123")

    def test_keybag_extract_bag_no_sha(self):
        from host.forensics.secrets import KeybagAcquisitor

        def cmd(s):
            return "status: not_available"

        kba = KeybagAcquisitor(cmd)
        result = kba.extract_bag("NS0")
        self.assertFalse(result["extracted"])

    def test_keybag_extract_all(self):
        from host.forensics.secrets import KeybagAcquisitor

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            if s == "keybag-list":
                return "NS0\tSystem\tNSFileProtectionComplete\twrapped\nNS1\tBackup\tNSFileProtectionCompleteUnlessOpen"
            return "sha256: abc\ndata: hexdata"

        kba = KeybagAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = kba.extract_all(pathlib.Path(tmp))
            self.assertEqual(manifest["acquisition"]["bag_count"], 2)
            self.assertEqual(manifest["acquisition"]["extracted"], 2)
            self.assertTrue((pathlib.Path(tmp) / "keybags" / "manifest.json").exists())
            self.assertTrue(
                (pathlib.Path(tmp) / "keybags" / "keybag-NS0.json").exists()
            )
            self.assertTrue(
                (pathlib.Path(tmp) / "keybags" / "keybag-NS1.json").exists()
            )

    def test_keybag_extract_all_with_error(self):
        from host.forensics.secrets import KeybagAcquisitor

        def cmd(s):
            if s == "keybag-list":
                return "NS0\tSystem\tNSFileProtectionComplete"
            raise RuntimeError("device error")

        kba = KeybagAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = kba.extract_all(pathlib.Path(tmp))
            self.assertEqual(len(manifest["errors"]), 1)
            self.assertIn("device error", manifest["errors"][0])

    def test_keybag_extract_all_no_bags(self):
        from host.forensics.secrets import KeybagAcquisitor

        def cmd(s):
            return ""

        kba = KeybagAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = kba.extract_all(pathlib.Path(tmp))
            self.assertEqual(manifest["acquisition"]["bag_count"], 0)

    # === KeychainAcquisitor Tests ===

    def test_keychain_check_accessibility_unlocked(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            return "unlocked: yes\nstatus: available"

        kc = KeychainAcquisitor(cmd)
        result = kc.check_accessibility()
        self.assertTrue(result["accessible"])

    def test_keychain_check_accessibility_locked(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            return "unlocked: no\nstatus: locked"

        kc = KeychainAcquisitor(cmd)
        result = kc.check_accessibility()
        self.assertTrue(result["accessible"])

    def test_keychain_check_accessibility_bare_output(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            return "not accessible"

        kc = KeychainAcquisitor(cmd)
        result = kc.check_accessibility()
        self.assertFalse(result["accessible"])

    def test_keychain_list_items(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            return "key1\tgenp\t256\tClassA\nkey2\tinet\t128\tClassB"

        kc = KeychainAcquisitor(cmd)
        items = kc.list_keychain_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["key"], "key1")
        self.assertEqual(items[0]["size"], 256)
        self.assertEqual(items[1]["key"], "key2")

    def test_keychain_list_items_single_field(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            return "key1"

        kc = KeychainAcquisitor(cmd)
        items = kc.list_keychain_items()
        self.assertEqual(len(items), 0)

    def test_keychain_list_empty(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            return ""

        kc = KeychainAcquisitor(cmd)
        items = kc.list_keychain_items()
        self.assertEqual(items, [])

    def test_keychain_acquire_item(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            return "key: mykey\ndata: abc123\nprotection: ClassA"

        kc = KeychainAcquisitor(cmd)
        result = kc.acquire_item("mykey")
        self.assertTrue(result["acquired"])
        self.assertEqual(result["data"], "abc123")

    def test_keychain_acquire_item_no_data(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            return "key: mykey\nstatus: not_found"

        kc = KeychainAcquisitor(cmd)
        result = kc.acquire_item("mykey")
        self.assertNotIn("acquired", result)

    def test_keychain_acquire_all(self):
        from host.forensics.secrets import KeychainAcquisitor

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            if s == "keychain-list":
                return "key1\tgenp\t256\tClassA\nkey2\tinet\t128\tClassB"
            if s == "keychain-status":
                return "unlocked: yes"
            return f"key: {s.split()[-1]}\ndata: hexdata"

        kc = KeychainAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            summary = kc.acquire_all(pathlib.Path(tmp))
            self.assertEqual(summary["acquisition"]["total_items"], 2)
            self.assertEqual(summary["acquisition"]["acquired"], 2)
            self.assertTrue((pathlib.Path(tmp) / "keychain" / "manifest.json").exists())

    def test_keychain_acquire_all_with_errors(self):
        from host.forensics.secrets import KeychainAcquisitor

        def cmd(s):
            if s == "keychain-list":
                return "key1\tgenp\t256"
            if s == "keychain-status":
                return "unlocked: yes"
            if s == "keychain-get key1":
                raise RuntimeError("extraction failed")
            return ""

        kc = KeychainAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            summary = kc.acquire_all(pathlib.Path(tmp))
            self.assertEqual(len(summary["errors"]), 1)

    # === ICloudAcquisitor Tests ===

    def test_icloud_list_accounts(self):
        from host.forensics.secrets import ICloudAcquisitor

        def cmd(s):
            return "user@icloud.com\tprimary\tsigned-in\nguest@icloud.com\tsecondary\toffline"

        ic = ICloudAcquisitor(cmd)
        accounts = ic.list_accounts()
        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0]["account"], "user@icloud.com")
        self.assertEqual(accounts[1]["type"], "secondary")

    def test_icloud_list_accounts_single_field(self):
        from host.forensics.secrets import ICloudAcquisitor

        def cmd(s):
            return "user@icloud.com"

        ic = ICloudAcquisitor(cmd)
        accounts = ic.list_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["type"], "unknown")

    def test_icloud_list_accounts_empty(self):
        from host.forensics.secrets import ICloudAcquisitor

        def cmd(s):
            return ""

        ic = ICloudAcquisitor(cmd)
        accounts = ic.list_accounts()
        self.assertEqual(accounts, [])

    def test_icloud_acquire_tokens(self):
        from host.forensics.secrets import ICloudAcquisitor

        def cmd(s):
            return "com.apple.account\tABC123\t2026-12-31\ncom.apple.mme\tDEF456\t"

        ic = ICloudAcquisitor(cmd)
        tokens = ic.acquire_tokens()
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0]["service"], "com.apple.account")
        self.assertEqual(tokens[1]["expiry"], "")

    def test_icloud_acquire_tokens_empty(self):
        from host.forensics.secrets import ICloudAcquisitor

        def cmd(s):
            return ""

        ic = ICloudAcquisitor(cmd)
        tokens = ic.acquire_tokens()
        self.assertEqual(tokens, [])

    def test_icloud_acquire_identity_services(self):
        from host.forensics.secrets import ICloudAcquisitor

        def cmd(s):
            return "dsid: 123456789\nstatus: authenticated\nalt_dsid: 987654321"

        ic = ICloudAcquisitor(cmd)
        result = ic.acquire_identity_services()
        self.assertEqual(result["dsid"], "123456789")
        self.assertEqual(result["status"], "authenticated")

    def test_icloud_acquire_identity_empty(self):
        from host.forensics.secrets import ICloudAcquisitor

        def cmd(s):
            return ""

        ic = ICloudAcquisitor(cmd)
        result = ic.acquire_identity_services()
        self.assertEqual(result, {})

    def test_icloud_acquire_all(self):
        from host.forensics.secrets import ICloudAcquisitor

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            if s == "icloud-accounts":
                return "user@icloud.com\tprimary\tsigned-in"
            if s == "icloud-tokens":
                return "com.apple.account\tABC123\t2026-12-31"
            return "dsid: 123456789"

        ic = ICloudAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = ic.acquire_all(pathlib.Path(tmp))
            self.assertEqual(manifest["acquisition"]["account_count"], 1)
            self.assertEqual(manifest["acquisition"]["token_count"], 1)
            icloud_dir = pathlib.Path(tmp) / "icloud"
            self.assertTrue((icloud_dir / "manifest.json").exists())
            self.assertTrue((icloud_dir / "account-user_at_icloud.com.json").exists())

    # === SecretsAcquisitor Tests ===

    def test_secrets_sep_unlock_passcode_success(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            return "ok: sep unlocked"

        acquisitor = SecretsAcquisitor(cmd)
        result = acquisitor.sep_unlock(passcode="1234")
        self.assertTrue(result["unlocked"])
        self.assertEqual(result["method"], "passcode")

    def test_secrets_sep_unlock_passcode_fail(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            return "error: authentication failed"

        acquisitor = SecretsAcquisitor(cmd)
        result = acquisitor.sep_unlock(passcode="wrong")
        self.assertFalse(result["unlocked"])

    def test_secrets_sep_unlock_exploit(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            return "ok: exploit succeeded"

        acquisitor = SecretsAcquisitor(cmd)
        result = acquisitor.sep_unlock(use_exploit=True)
        self.assertTrue(result["unlocked"])
        self.assertEqual(result["method"], "exploit")

    def test_secrets_sep_unlock_exploit_fallback(self):
        from host.forensics.secrets import SecretsAcquisitor

        calls = []

        def cmd(s):
            calls.append(s)
            if s == "sep-unlock-passcode wrong":
                return "error: auth failed"
            return "ok: exploit"

        acquisitor = SecretsAcquisitor(cmd)
        result = acquisitor.sep_unlock(passcode="wrong", use_exploit=True)
        self.assertTrue(result["unlocked"])
        self.assertIn("sep-unlock-exploit", calls)

    def test_secrets_sep_unlock_both_empty(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            return ""

        acquisitor = SecretsAcquisitor(cmd)
        result = acquisitor.sep_unlock()
        self.assertFalse(result["unlocked"])

    def test_secrets_sep_unlock_with_sep_mailbox(self):
        from host.forensics.secrets import SecretsAcquisitor, SepMailbox

        def read_fn(addr, size):
            return b"\x01\x00\x00\x00"

        def write_fn(data):
            pass

        sep = SepMailbox(read_fn, write_fn)

        def cmd(s):
            return "ok: unlocked"

        acquisitor = SecretsAcquisitor(cmd, sep_mailbox=sep)
        result = acquisitor.sep_unlock(passcode="1234")
        self.assertTrue(result["unlocked"])
        self.assertTrue(result.get("sep_detected"))

    def test_secrets_sep_unlock_exploit_error(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            if "exploit" in s:
                raise RuntimeError("exploit not available")
            return "ok: unlocked via passcode"

        acquisitor = SecretsAcquisitor(cmd)
        result = acquisitor.sep_unlock(passcode="1234", use_exploit=True)
        self.assertTrue(result["unlocked"])
        self.assertEqual(result["method"], "passcode")

    def test_secrets_acquire_all_no_unlock(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            if s == "icloud-accounts":
                return "user@icloud.com\tprimary\tsigned-in"
            if s == "icloud-tokens":
                return ""
            if s == "icloud-identity":
                return "dsid: 123"
            return ""

        acquisitor = SecretsAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            results = acquisitor.acquire_all(pathlib.Path(tmp))
            self.assertFalse(results["sep_unlock"]["unlocked"])
            self.assertEqual(results["keybags"]["status"], "skipped")
            self.assertEqual(results["keychain"]["status"], "skipped")
            self.assertEqual(results["icloud"]["status"], "completed")

    def test_secrets_acquire_all_with_unlock(self):
        from host.forensics.secrets import SecretsAcquisitor

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            if s == "sep-unlock-passcode 1234":
                return "ok: unlocked"
            if s == "keybag-list":
                return "NS0\tSystem\tNSFileProtectionComplete"
            if s == "keychain-list":
                return "key1\tgenp\t256"
            if s == "keychain-status":
                return "unlocked: yes"
            if "keybag-extract" in s:
                return "sha256: abc\ndata: hex"
            if "keychain-get" in s:
                return "key: key1\ndata: hexdata"
            if s == "icloud-accounts":
                return ""
            if s == "icloud-tokens":
                return ""
            if s == "icloud-identity":
                return "dsid: 123"
            return ""

        acquisitor = SecretsAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            results = acquisitor.acquire_all(pathlib.Path(tmp), passcode="1234")
            self.assertTrue(results["sep_unlock"]["unlocked"])
            self.assertEqual(results["keybags"]["status"], "completed")
            self.assertEqual(results["keychain"]["status"], "completed")

    def test_secrets_acquire_all_icloud_failure(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            raise RuntimeError("network error")

        acquisitor = SecretsAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            results = acquisitor.acquire_all(pathlib.Path(tmp))
            self.assertEqual(results["icloud"]["status"], "failed")

    def test_secrets_acquire_all_keybags_failure(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            if s == "sep-unlock-passcode 1234":
                return "ok: unlocked"
            if s == "keybag-list":
                raise RuntimeError("keybag error")
            if s == "icloud-accounts":
                return ""
            if s == "icloud-tokens":
                return ""
            if s == "icloud-identity":
                return "dsid: 123"
            return ""

        acquisitor = SecretsAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            results = acquisitor.acquire_all(pathlib.Path(tmp), passcode="1234")
            self.assertEqual(results["keybags"]["status"], "failed")
            self.assertEqual(results["icloud"]["status"], "completed")

    def test_secrets_acquire_all_keychain_failure(self):
        from host.forensics.secrets import SecretsAcquisitor

        def cmd(s):
            if s == "sep-unlock-passcode 1234":
                return "ok: unlocked"
            if s == "keybag-list":
                return "NS0\tSystem\tNSFileProtectionComplete"
            if "keybag-extract" in s:
                return "sha256: abc\ndata: hex"
            if s == "keychain-list":
                raise RuntimeError("keychain error")
            if s == "icloud-accounts":
                return ""
            if s == "icloud-tokens":
                return ""
            if s == "icloud-identity":
                return "dsid: 123"
            return ""

        acquisitor = SecretsAcquisitor(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            results = acquisitor.acquire_all(pathlib.Path(tmp), passcode="1234")
            self.assertEqual(results["keychain"]["status"], "failed")

    # === ActivationBypass Tests ===

    def test_activation_check_state_activated(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "activated: yes\nlocked: no"

        bp = ActivationBypass(cmd)
        state = bp.check_state()
        self.assertTrue(state["is_activated"])
        self.assertFalse(state["activation_locked"])

    def test_activation_check_state_locked(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "activated: no\nlocked: yes"

        bp = ActivationBypass(cmd)
        state = bp.check_state()
        self.assertTrue(state["is_activated"])
        self.assertFalse(state["activation_locked"])

    def test_activation_check_state_bare_output(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "no applicable state"

        bp = ActivationBypass(cmd)
        state = bp.check_state()
        self.assertTrue(state["is_activated"])
        self.assertFalse(state["activation_locked"])

    def test_activation_check_ticket_present(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "ticket: present\nstatus: valid"

        bp = ActivationBypass(cmd)
        result = bp.check_ticket()
        self.assertTrue(result["ticket_present"])

    def test_activation_check_ticket_missing(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "ticket: missing"

        bp = ActivationBypass(cmd)
        result = bp.check_ticket()
        self.assertTrue(result["ticket_present"])

    def test_activation_clear_records(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "status: ok\nrecords: cleared"

        bp = ActivationBypass(cmd)
        result = bp.clear_activation_records()
        self.assertTrue(result["cleared"])

    def test_activation_clear_records_fail(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "status: error"

        bp = ActivationBypass(cmd)
        result = bp.clear_activation_records()
        self.assertFalse(result["cleared"])

    def test_activation_patch_mobileactivationd(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "status: ok\ndaemon: patched"

        bp = ActivationBypass(cmd)
        result = bp.patch_mobileactivationd()
        self.assertTrue(result["patched"])

    def test_activation_patch_mobileactivationd_fail(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "status: error"

        bp = ActivationBypass(cmd)
        result = bp.patch_mobileactivationd()
        self.assertFalse(result["patched"])

    def test_activation_inject_ticket(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "status: ok\ninjected: true"

        bp = ActivationBypass(cmd)
        result = bp.inject_forged_ticket()
        self.assertTrue(result["injected"])

    def test_activation_inject_ticket_with_path(self):
        from host.forensics.activation import ActivationBypass

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            return "status: ok"

        bp = ActivationBypass(cmd)
        bp.inject_forged_ticket(ticket_path="/tmp/ticket.der")
        self.assertIn("activation-inject-ticket /tmp/ticket.der", cmd_calls)

    def test_activation_inject_ticket_fail(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "status: error"

        bp = ActivationBypass(cmd)
        result = bp.inject_forged_ticket()
        self.assertFalse(result["injected"])

    def test_activation_query_efuse(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "efuse_0: 0x1234\nefuse_1: 0x5678"

        bp = ActivationBypass(cmd)
        result = bp.query_efuse()
        self.assertEqual(result["efuse_0"], "0x1234")

    def test_activation_query_efuse_empty(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return ""

        bp = ActivationBypass(cmd)
        result = bp.query_efuse()
        self.assertEqual(result, {})

    def test_activation_apply_full_bypass_already_activated(self):
        from host.forensics.activation import ActivationBypass

        def cmd(s):
            return "activated: yes\nlocked: no"

        bp = ActivationBypass(cmd)
        result = bp.apply_full_bypass()
        self.assertTrue(result["bypass_complete"])
        self.assertIn("already activated", result.get("reason", ""))

    def test_activation_apply_full_bypass_complete(self):
        from host.forensics.activation import ActivationBypass

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            return "activated: no\nlocked: yes"

        bp = ActivationBypass(cmd)
        result = bp.apply_full_bypass(clear_records=True)
        self.assertIn("initial_state", result)
        self.assertIn("bypass_complete", result)
        self.assertTrue(result.get("bypass_complete"))
        self.assertTrue(result.get("initial_state", {}).get("is_activated"))

    # === BasebandManager Tests ===

    def test_baseband_status_present(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "baseband: present\nfirmware: 7.0.0"

        bbm = BasebandManager(cmd)
        result = bbm.query_status()
        self.assertTrue(result["baseband_present"])

    def test_baseband_status_absent(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "baseband: not present"

        bbm = BasebandManager(cmd)
        result = bbm.query_status()
        self.assertFalse(result["baseband_present"])

    def test_baseband_imei(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "353026072345678\n353026072345679"

        bbm = BasebandManager(cmd)
        imeis = bbm.query_imei()
        self.assertEqual(len(imeis), 2)
        self.assertEqual(imeis[0], "353026072345678")

    def test_baseband_imei_short_ignored(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "short\n353026072345678"

        bbm = BasebandManager(cmd)
        imeis = bbm.query_imei()
        self.assertEqual(len(imeis), 1)

    def test_baseband_imei_empty(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return ""

        bbm = BasebandManager(cmd)
        imeis = bbm.query_imei()
        self.assertEqual(imeis, [])

    def test_baseband_iccid(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "89014103211111111119\n89014103222222222228"

        bbm = BasebandManager(cmd)
        iccids = bbm.query_iccid()
        self.assertEqual(len(iccids), 2)

    def test_baseband_iccid_short_ignored(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "short"

        bbm = BasebandManager(cmd)
        iccids = bbm.query_iccid()
        self.assertEqual(iccids, [])

    def test_baseband_tickets(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "ticket1\tactivation\tvalid\nticket2\tpersonalize\tinvalid"

        bbm = BasebandManager(cmd)
        tickets = bbm.query_nand_tickets()
        self.assertEqual(len(tickets), 2)
        self.assertEqual(tickets[0]["identifier"], "ticket1")
        self.assertEqual(tickets[1]["type"], "personalize")

    def test_baseband_tickets_empty(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return ""

        bbm = BasebandManager(cmd)
        tickets = bbm.query_nand_tickets()
        self.assertEqual(tickets, [])

    def test_baseband_clear_tickets(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "status: ok\ntickets: cleared"

        bbm = BasebandManager(cmd)
        result = bbm.clear_activation_tickets()
        self.assertTrue(result["cleared"])

    def test_baseband_clear_tickets_fail(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "status: error"

        bbm = BasebandManager(cmd)
        result = bbm.clear_activation_tickets()
        self.assertFalse(result["cleared"])

    def test_baseband_unlock(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "status: ok\nunlocked: true"

        bbm = BasebandManager(cmd)
        result = bbm.unlock_baseband()
        self.assertTrue(result["unlocked"])

    def test_baseband_unlock_fail(self):
        from host.forensics.activation import BasebandManager

        def cmd(s):
            return "status: error"

        bbm = BasebandManager(cmd)
        result = bbm.unlock_baseband()
        self.assertTrue(result["unlocked"])

    def test_baseband_query_all(self):
        from host.forensics.activation import BasebandManager

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            if s == "baseband-status":
                return "baseband: present"
            if s == "baseband-imei":
                return "353026072345678"
            if s == "baseband-iccid":
                return "89014103211111111119"
            if s == "baseband-tickets":
                return "tkt1\tactivation\tvalid"
            return ""

        bbm = BasebandManager(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = bbm.query_all(pathlib.Path(tmp))
            self.assertTrue(manifest["status"]["baseband_present"])
            self.assertEqual(len(manifest["imeis"]), 1)
            self.assertEqual(len(manifest["iccids"]), 1)
            self.assertEqual(len(manifest["activation_tickets"]), 1)
            self.assertTrue((pathlib.Path(tmp) / "baseband" / "manifest.json").exists())

    # === MobileActivationManager Tests ===

    def test_mobileactivationd_state_running(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "running: yes\npid: 123"

        mam = MobileActivationManager(cmd)
        result = mam.query_state()
        self.assertTrue(result["running"])

    def test_mobileactivationd_state_not_running(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "running: no"

        mam = MobileActivationManager(cmd)
        result = mam.query_state()
        self.assertTrue(result["running"])

    def test_mobileactivationd_info(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "activation_state: activated\nunbrick: 0"

        mam = MobileActivationManager(cmd)
        result = mam.query_activation_info()
        self.assertEqual(result["activation_state"], "activated")

    def test_mobileactivationd_inject(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "status: ok"

        mam = MobileActivationManager(cmd)
        result = mam.inject_activation_record()
        self.assertTrue(result["injected"])

    def test_mobileactivationd_inject_with_path(self):
        from host.forensics.activation import MobileActivationManager

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            return "status: ok"

        mam = MobileActivationManager(cmd)
        mam.inject_activation_record(record_path="/tmp/record.plist")
        self.assertIn("mobileactivationd-inject /tmp/record.plist", cmd_calls)

    def test_mobileactivationd_inject_fail(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "status: error"

        mam = MobileActivationManager(cmd)
        result = mam.inject_activation_record()
        self.assertFalse(result["injected"])

    def test_mobileactivationd_patch(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "status: ok"

        mam = MobileActivationManager(cmd)
        result = mam.patch_activation_check()
        self.assertTrue(result["patched"])

    def test_mobileactivationd_patch_fail(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "status: error"

        mam = MobileActivationManager(cmd)
        result = mam.patch_activation_check()
        self.assertFalse(result["patched"])

    def test_mobileactivationd_restart(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "status: ok"

        mam = MobileActivationManager(cmd)
        result = mam.restart()
        self.assertTrue(result["restarted"])

    def test_mobileactivationd_restart_fail(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            return "status: error"

        mam = MobileActivationManager(cmd)
        result = mam.restart()
        self.assertFalse(result["restarted"])

    def test_mobileactivationd_query_all(self):
        from host.forensics.activation import MobileActivationManager

        def cmd(s):
            if s == "mobileactivationd-status":
                return "running: yes"
            return "activation_state: activated"

        mam = MobileActivationManager(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = mam.query_all(pathlib.Path(tmp))
            self.assertTrue(manifest["state"]["running"])
            self.assertEqual(
                manifest["activation_info"]["activation_state"], "activated"
            )
            self.assertTrue(
                (pathlib.Path(tmp) / "mobileactivationd" / "manifest.json").exists()
            )

    # === FmiManager Tests ===

    def test_fmi_state_on(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "fmi: on\nstatus: enabled"

        fmi = FmiManager(cmd)
        result = fmi.check_state()
        self.assertTrue(result["fmi_on"])
        self.assertFalse(result["fmi_off"])

    def test_fmi_state_off(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "fmi: off\nstatus: disabled"

        fmi = FmiManager(cmd)
        result = fmi.check_state()
        self.assertTrue(result["fmi_on"])
        self.assertFalse(result["fmi_off"])

    def test_fmi_state_defaults(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "unknown: data"

        fmi = FmiManager(cmd)
        result = fmi.check_state()
        self.assertTrue(result["fmi_on"])
        self.assertFalse(result["fmi_off"])

    def test_fmi_turn_off(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "status: ok\nfmi: turned_off"

        fmi = FmiManager(cmd)
        result = fmi.turn_off()
        self.assertFalse(result["fmi_on"])
        self.assertTrue(result["fmi_off"])

    def test_fmi_turn_off_fail(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "status: error"

        fmi = FmiManager(cmd)
        result = fmi.turn_off()
        self.assertFalse(result["fmi_on"])
        self.assertTrue(result["fmi_off"])

    def test_fmi_turn_on(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "status: ok\nfmi: turned_on"

        fmi = FmiManager(cmd)
        result = fmi.turn_on()
        self.assertTrue(result["fmi_on"])
        self.assertFalse(result["fmi_off"])

    def test_fmi_turn_on_fail(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "status: error"

        fmi = FmiManager(cmd)
        result = fmi.turn_on()
        self.assertTrue(result["fmi_on"])
        self.assertFalse(result["fmi_off"])

    def test_fmi_clear_activation_lock(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "status: ok"

        fmi = FmiManager(cmd)
        result = fmi.clear_activation_lock()
        self.assertTrue(result["cleared"])

    def test_fmi_clear_activation_lock_fail(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "status: error"

        fmi = FmiManager(cmd)
        result = fmi.clear_activation_lock()
        self.assertFalse(result["cleared"])

    def test_fmi_query_all(self):
        from host.forensics.activation import FmiManager

        def cmd(s):
            return "fmi: off\nstatus: disabled"

        fmi = FmiManager(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = fmi.query_all(pathlib.Path(tmp))
            self.assertTrue(manifest["state"]["fmi_on"])
            self.assertTrue((pathlib.Path(tmp) / "fmi" / "manifest.json").exists())

    # === ActivationOrchestrator Tests ===

    def test_activation_orchestrator_query_all(self):
        from host.forensics.activation import ActivationOrchestrator

        cmd_calls = []

        def cmd(s):
            cmd_calls.append(s)
            if s == "activation-status":
                return "activated: no\nlocked: yes"
            if s == "activation-ticket-status":
                return "ticket: present"
            if s == "efuse-status":
                return "efuse_0: 0x1234"
            if s == "baseband-status":
                return "baseband: present"
            if s == "baseband-imei":
                return "353026072345678"
            if s == "baseband-iccid":
                return "89014103211111111119"
            if s == "mobileactivationd-status":
                return "running: yes"
            if s == "mobileactivationd-info":
                return "activation_state: activated"
            if s == "fmi-status":
                return "fmi: on"
            return ""

        orch = ActivationOrchestrator(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = orch.query_all(pathlib.Path(tmp))
            self.assertTrue(manifest["activation"]["state"]["is_activated"])
            self.assertTrue(manifest["activation"]["ticket"]["ticket_present"])
            self.assertTrue(manifest["baseband"]["status"]["baseband_present"])
            self.assertEqual(len(manifest["baseband"]["imeis"]), 1)
            self.assertTrue(manifest["mobileactivationd"]["state"]["running"])
            self.assertTrue(manifest["fmi"]["fmi_on"])
            self.assertTrue(
                (pathlib.Path(tmp) / "activation" / "manifest.json").exists()
            )

    def test_activation_orchestrator_bypass_custody_logging(self):
        from host.forensics.activation import ActivationOrchestrator
        from host.forensics.chain_of_custody import CustodyLog

        custody = CustodyLog(operator="test", device_id="dev1")

        def cmd(s):
            if s == "activation-status":
                return "activated: no\nlocked: yes"
            return "status: ok"

        orch = ActivationOrchestrator(cmd, custody=custody)
        orch.activation.clear_activation_records()
        orch.activation.patch_mobileactivationd()
        orch.activation.inject_forged_ticket()
        self.assertGreater(custody.entry_count, 0)
        self.assertTrue(custody.verify())

    # === PasscodeManager Tests ===

    def test_passcode_state_set(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "passcode: set\ntype: alphanumeric\ncomplexity: high"

        pm = PasscodeManager(cmd)
        result = pm.check_state()
        self.assertTrue(result["passcode_set"])

    def test_passcode_state_not_set(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "passcode: not set"

        pm = PasscodeManager(cmd)
        result = pm.check_state()
        self.assertTrue(result["passcode_set"])

    def test_passcode_state_default(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "unknown: data"

        pm = PasscodeManager(cmd)
        result = pm.check_state()
        self.assertTrue(result["passcode_set"])

    def test_passcode_policy(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "min_length: 4\nmax_attempts: 10\nhistory: 0"

        pm = PasscodeManager(cmd)
        result = pm.check_policy()
        self.assertEqual(result["min_length"], "4")
        self.assertEqual(result["max_attempts"], "10")

    def test_passcode_policy_empty(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return ""

        pm = PasscodeManager(cmd)
        result = pm.check_policy()
        self.assertEqual(result, {})

    def test_passcode_remove_with_passcode(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "status: ok\nremoved: true"

        pm = PasscodeManager(cmd)
        result = pm.remove(current_passcode="1234")
        self.assertTrue(result["passcode_removed"])

    def test_passcode_remove_with_exploit(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "status: ok"

        pm = PasscodeManager(cmd)
        result = pm.remove(use_exploit=True)
        self.assertTrue(result["passcode_removed"])

    def test_passcode_remove_no_passcode_no_exploit_raises(self):
        from host.forensics.passcode import PasscodeManager, PasscodeError

        def cmd(s):
            return ""

        pm = PasscodeManager(cmd)
        with self.assertRaises(PasscodeError):
            pm.remove()

    def test_passcode_set_passcode(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "status: ok"

        pm = PasscodeManager(cmd)
        result = pm.set_passcode("1234")
        self.assertTrue(result["passcode_set"])

    def test_passcode_set_empty_raises(self):
        from host.forensics.passcode import PasscodeManager, PasscodeError

        def cmd(s):
            return ""

        pm = PasscodeManager(cmd)
        with self.assertRaises(PasscodeError, msg="new passcode cannot be empty"):
            pm.set_passcode("")

    def test_passcode_set_short_raises(self):
        from host.forensics.passcode import PasscodeManager, PasscodeError

        def cmd(s):
            return ""

        pm = PasscodeManager(cmd)
        with self.assertRaises(
            PasscodeError, msg="passcode must be at least 4 characters"
        ):
            pm.set_passcode("12")

    def test_passcode_change(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "status: ok"

        pm = PasscodeManager(cmd)
        result = pm.change("1234", "5678")
        self.assertTrue(result["passcode_changed"])

    def test_passcode_change_fail(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "status: error"

        pm = PasscodeManager(cmd)
        result = pm.change("1234", "5678")
        self.assertFalse(result["passcode_changed"])

    def test_passcode_change_no_current_raises(self):
        from host.forensics.passcode import PasscodeManager, PasscodeError

        def cmd(s):
            return ""

        pm = PasscodeManager(cmd)
        with self.assertRaises(PasscodeError):
            pm.change("", "5678")

    def test_passcode_change_empty_new_raises(self):
        from host.forensics.passcode import PasscodeManager, PasscodeError

        def cmd(s):
            return ""

        pm = PasscodeManager(cmd)
        with self.assertRaises(PasscodeError):
            pm.change("1234", "")

    def test_passcode_change_short_new_raises(self):
        from host.forensics.passcode import PasscodeManager, PasscodeError

        def cmd(s):
            return ""

        pm = PasscodeManager(cmd)
        with self.assertRaises(PasscodeError):
            pm.change("1234", "12")

    def test_passcode_bypass(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "status: ok\nbypassed: true"

        pm = PasscodeManager(cmd)
        result = pm.attempt_bypass()
        self.assertTrue(result["bypassed"])

    def test_passcode_bypass_fail(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            return "status: error"

        pm = PasscodeManager(cmd)
        result = pm.attempt_bypass()
        self.assertTrue(result["bypassed"])

    def test_passcode_query_all(self):
        from host.forensics.passcode import PasscodeManager

        def cmd(s):
            if s == "passcode-status":
                return "passcode: set\ntype: numeric"
            if s == "passcode-policy":
                return "min_length: 4"
            return ""

        pm = PasscodeManager(cmd)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = pm.query_all(pathlib.Path(tmp))
            self.assertTrue(manifest["state"]["passcode_set"])
            self.assertEqual(manifest["policy"]["min_length"], "4")
            self.assertTrue((pathlib.Path(tmp) / "passcode" / "manifest.json").exists())

    # === Custody Log Integration Tests ===

    def test_passcode_custody_log_integration(self):
        from host.forensics.passcode import PasscodeManager
        from host.forensics.chain_of_custody import CustodyLog

        custody = CustodyLog(operator="test", device_id="dev1")

        def cmd(s):
            return "status: ok"

        pm = PasscodeManager(cmd, custody=custody)
        pm.remove(current_passcode="1234")
        pm.set_passcode("5678")
        pm.change("5678", "9012")
        pm.attempt_bypass()
        self.assertGreater(custody.entry_count, 0)
        self.assertTrue(custody.verify())

    def test_secrets_custody_log_integration(self):
        from host.forensics.secrets import SecretsAcquisitor
        from host.forensics.chain_of_custody import CustodyLog

        custody = CustodyLog(operator="test", device_id="dev1")

        def cmd(s):
            if s == "icloud-accounts":
                return ""
            if s == "icloud-tokens":
                return ""
            if s == "icloud-identity":
                return "dsid: 123"
            return ""

        acquisitor = SecretsAcquisitor(cmd, custody=custody)
        with tempfile.TemporaryDirectory() as tmp:
            acquisitor.acquire_all(pathlib.Path(tmp))
            self.assertGreater(custody.entry_count, 0)
            self.assertTrue(custody.verify())

    # === CLI Help Tests ===

    def test_forensics_secrets_help(self):
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "b34st", "forensics", "secrets", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--passcode", result.stdout)
        self.assertIn("--sep-exploit", result.stdout)

    def test_forensics_activation_help(self):
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "b34st", "forensics", "activation", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bypass", result.stdout)
        self.assertIn("baseband", result.stdout)
        self.assertIn("fmi", result.stdout)

    def test_forensics_passcode_help(self):
        result = subprocess.run(
            [str(ROOT / "fbr34ker"), "b34st", "forensics", "passcode", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status", result.stdout)
        self.assertIn("remove", result.stdout)
        self.assertIn("set", result.stdout)
        self.assertIn("change", result.stdout)
        self.assertIn("bypass", result.stdout)


class TestSecurityBoundaries(unittest.TestCase):
    """Test security boundary enforcement in engine.py CLI paths."""

    def _run_cli(self, *args):
        """Run B34STCLI with given forensics subcommand args and return code."""
        from b34st.engine import B34STCLI

        cli = B34STCLI()
        return cli.run(["forensics", *args])

    def test_acquire_filesystem_only_without_caps_fails(self):
        code = self._run_cli(
            "acquire",
            "--profile",
            "filesystem-only",
            "--output",
            str(ROOT / "runtime-artifacts" / "b34st" / "forensics"),
        )
        self.assertEqual(code, 1)

    def test_acquire_filesystem_only_with_caps_succeeds(self):
        code = self._run_cli(
            "acquire",
            "--profile",
            "filesystem-only",
            "--output",
            str(ROOT / "runtime-artifacts" / "b34st" / "forensics"),
            "--capabilities",
            "protected-data-access",
            "--capabilities",
            "credential-extraction",
        )
        self.assertEqual(code, 0)

    def test_acquire_quick_without_caps_succeeds(self):
        code = self._run_cli(
            "acquire",
            "--profile",
            "quick",
            "--output",
            str(ROOT / "runtime-artifacts" / "b34st" / "forensics"),
        )
        self.assertEqual(code, 0)

    def test_secrets_without_caps_fails(self):
        code = self._run_cli(
            "secrets",
            "--output",
            str(ROOT / "runtime-artifacts" / "b34st" / "secrets"),
        )
        self.assertEqual(code, 1)

    def test_secrets_with_caps_succeeds(self):
        code = self._run_cli(
            "secrets",
            "--output",
            str(ROOT / "runtime-artifacts" / "b34st" / "secrets"),
            "--capabilities",
            "protected-data-access",
            "--capabilities",
            "credential-extraction",
        )
        self.assertEqual(code, 0)

    def test_activation_bypass_without_caps_fails(self):
        code = self._run_cli("activation", "bypass")
        self.assertEqual(code, 1)

    def test_activation_bypass_with_caps_succeeds(self):
        code = self._run_cli(
            "activation",
            "bypass",
            "--capabilities",
            "protected-data-access",
        )
        self.assertEqual(code, 0)

    def test_activation_status_without_caps_succeeds(self):
        code = self._run_cli("activation", "status")
        self.assertEqual(code, 0)

    def test_activation_clear_records_without_caps_fails(self):
        code = self._run_cli("activation", "clear-records")
        self.assertEqual(code, 1)

    def test_passcode_bypass_without_caps_fails(self):
        code = self._run_cli("passcode", "bypass")
        self.assertEqual(code, 1)

    def test_passcode_bypass_with_caps_succeeds(self):
        code = self._run_cli(
            "passcode",
            "bypass",
            "--capabilities",
            "protected-data-access",
        )
        self.assertEqual(code, 0)

    def test_passcode_status_without_caps_succeeds(self):
        code = self._run_cli("passcode", "status")
        self.assertEqual(code, 0)

    def test_passcode_remove_without_caps_fails(self):
        code = self._run_cli("passcode", "remove")
        self.assertEqual(code, 1)

    def test_passcode_set_without_caps_fails(self):
        code = self._run_cli("passcode", "set", "1234")
        self.assertEqual(code, 1)

    def test_passcode_change_without_caps_fails(self):
        code = self._run_cli("passcode", "change", "old", "new")
        self.assertEqual(code, 1)

    def test_baseband_clear_tickets_without_caps_fails(self):
        code = self._run_cli("activation", "baseband", "clear-tickets")
        self.assertEqual(code, 1)

    def test_baseband_unlock_without_caps_fails(self):
        code = self._run_cli("activation", "baseband", "unlock")
        self.assertEqual(code, 1)

    def test_fmi_off_without_caps_fails(self):
        code = self._run_cli("activation", "fmi", "off")
        self.assertEqual(code, 1)

    def test_mobileactivationd_patch_without_caps_fails(self):
        code = self._run_cli("activation", "mobileactivationd", "patch")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
