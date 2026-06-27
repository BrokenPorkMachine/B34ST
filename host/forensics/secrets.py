"""iCloud, Keychain, and Keybag acquisition via SEP and kernel exploit.

Provides iCloud token extraction, encrypted Keychain dump, Keybag
(protection-class key) extraction via SEP mailbox communication,
and SEP unlock operations through the FBR34KER exploit chain.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
from typing import Any, Callable

from host.forensics.chain_of_custody import CustodyLog

SEP_BASES = {
    "A12": 0x82D000000,
    "A12X": 0x82D000000,
    "A12Z": 0x82D000000,
    "A13": 0x82E000000,
    "A14": 0x803000000,
    "A15": 0x811000000,
    "M1": 0x810300000,
    "M2": 0x811200000,
}

_SEP_BASE_DEFAULT = 0x82E000000


class SecretsError(RuntimeError):
    pass


class SepMailbox:
    """SEP mailbox communication primitives.

    Uses the caller-provided vendor read/write functions to communicate
    with the Secure Enclave via its MMIO mailbox region. The SEP mailbox
    protocol requires:

    1. Writing a command packet to sep_mailbox + shared memory area
    2. Triggering SEP via doorbell (write to sep_base + doorbell offset)
    3. Polling sep_response for completion
    4. Reading response data from shared memory
    """

    MAILBOX_OFFSET = 0x10000
    RESPONSE_OFFSET = 0x20000
    DOORBELL_OFFSET = 0x08000
    SHARED_MEM_OFFSET = 0x30000
    SHARED_MEM_SIZE = 0x10000
    MAX_COMMAND_SIZE = 4096
    POLL_INTERVAL = 0.01
    POLL_TIMEOUT = 5.0

    def __init__(
        self,
        read_fn: Callable[[int, int], bytes],
        write_fn: Callable[[bytes], None],
        sep_base: int = _SEP_BASE_DEFAULT,
    ):
        self._read = read_fn
        self._write = write_fn
        self.sep_base = sep_base
        self.mailbox = sep_base + self.MAILBOX_OFFSET
        self.response = sep_base + self.RESPONSE_OFFSET
        self.doorbell = sep_base + self.DOORBELL_OFFSET
        self.shared_mem = sep_base + self.SHARED_MEM_OFFSET

    def detect(self) -> dict[str, Any]:
        import struct

        try:
            test = self._read(self.sep_base, 4)
            val = struct.unpack("<I", test)[0] if len(test) >= 4 else 0
            available = val != 0 and val != 0xFFFFFFFF
        except Exception:
            available = False
        return {
            "sep_base": self.sep_base,
            "mailbox": self.mailbox,
            "response": self.response,
            "doorbell": self.doorbell,
            "available": available,
        }

    def send_command(self, command: bytes) -> bytes:
        import struct
        import time

        if len(command) > self.MAX_COMMAND_SIZE:
            raise SecretsError(f"SEP command exceeds {self.MAX_COMMAND_SIZE} bytes")

        cmd_packet = struct.pack("<I", len(command)) + command
        cmd_packet = cmd_packet.ljust(256, b"\x00")

        try:
            self._write(cmd_packet)
        except Exception as exc:
            raise SecretsError(f"SEP mailbox write failed: {exc}") from exc

        doorbell_val = struct.pack("<I", 1)
        try:
            self._write(doorbell_val)
        except Exception as exc:
            raise SecretsError(f"SEP doorbell trigger failed: {exc}") from exc

        deadline = time.monotonic() + self.POLL_TIMEOUT
        response = b""
        while time.monotonic() < deadline:
            try:
                status_word = self._read(self.response, 4)
                if len(status_word) >= 4:
                    status = struct.unpack("<I", status_word)[0]
                    if status & 0x1:
                        resp_size = self._read(self.response + 4, 4)
                        if len(resp_size) >= 4:
                            sz = struct.unpack("<I", resp_size)[0]
                            if sz > 0 and sz <= self.SHARED_MEM_SIZE:
                                response = self._read(self.shared_mem, sz)
                                break
            except Exception:
                pass
            time.sleep(self.POLL_INTERVAL)

        return response


class KeybagAcquisitor:
    """Extracts Keybag (protection-class keys) from SEP.

    Keybags contain the wrapped class keys used for Data Protection.
    Extraction requires either an unlocked SEP or a passcode to unlock it.
    """

    def __init__(
        self,
        command_fn: Callable[[str], str],
        sep_mailbox: SepMailbox | None = None,
    ):
        self._command = command_fn
        self._sep = sep_mailbox

    def enumerate_bags(self) -> list[dict[str, Any]]:
        raw = self._command("keybag-list")
        bags: list[dict[str, Any]] = []
        for line in raw.strip().splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            bag = {
                "identifier": parts[0] if len(parts) > 0 else "",
                "type": parts[1] if len(parts) > 1 else "unknown",
                "protection_class": parts[2] if len(parts) > 2 else "",
                "wrapped": len(parts) > 3 and parts[3] == "wrapped",
            }
            bags.append(bag)
        return bags

    def extract_bag(self, bag_id: str) -> dict[str, Any]:
        raw = self._command(f"keybag-extract {bag_id}")
        result: dict[str, Any] = {
            "bag_id": bag_id,
            "extracted": False,
        }
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "sha256" in result:
            result["extracted"] = True
        return result

    def extract_all(self, output_dir: pathlib.Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        keybags_dir = output_dir / "keybags"
        keybags_dir.mkdir(exist_ok=True)

        bags = self.enumerate_bags()
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        sha256_all = hashlib.sha256()

        for bag in bags:
            try:
                result = self.extract_bag(bag["identifier"])
                if result.get("extracted"):
                    sha256_all.update(
                        json.dumps(result, sort_keys=True).encode("utf-8")
                    )
                results.append(result)
            except Exception as exc:
                errors.append(f"bag {bag['identifier']}: {exc}")
                result = {"bag_id": bag["identifier"], "error": str(exc)}
                results.append(result)

            bag_file = keybags_dir / f"keybag-{bag['identifier']}.json"
            bag_file.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        manifest = {
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "bag_count": len(bags),
                "extracted": sum(1 for r in results if r.get("extracted")),
                "errors": len(errors),
                "sha256": sha256_all.hexdigest(),
            },
            "bags": results,
            "errors": errors,
        }

        manifest_path = keybags_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest


class KeychainAcquisitor:
    """Acquires Keychain items from the device.

    Keychain access requires the SEP to be unlocked (passcode entered
    after boot) or a passcode bypass. Items are extracted with their
    attributes and encrypted data blobs.
    """

    def __init__(self, command_fn: Callable[[str], str]):
        self._command = command_fn

    def check_accessibility(self) -> dict[str, Any]:
        raw = self._command("keychain-status")
        result: dict[str, Any] = {"accessible": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "unlocked" in str(result).lower():
            result["accessible"] = True
        return result

    def list_keychain_items(self) -> list[dict[str, Any]]:
        raw = self._command("keychain-list")
        items: list[dict[str, Any]] = []
        for line in raw.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                items.append({
                    "key": parts[0],
                    "class": parts[1] if len(parts) > 1 else "",
                    "size": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
                    "protection": parts[3] if len(parts) > 3 else "",
                })
        return items

    def acquire_item(self, item_key: str) -> dict[str, Any]:
        raw = self._command(f"keychain-get {item_key}")
        result: dict[str, Any] = {"key": item_key}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "data" in result:
            result["acquired"] = True
        return result

    def acquire_all(self, output_dir: pathlib.Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        keychain_dir = output_dir / "keychain"
        keychain_dir.mkdir(exist_ok=True)

        items = self.list_keychain_items()
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        sha256_all = hashlib.sha256()

        for item in items:
            try:
                result = self.acquire_item(item["key"])
                if result.get("acquired"):
                    sha256_all.update(
                        json.dumps(result, sort_keys=True).encode("utf-8")
                    )
                results.append(result)
            except Exception as exc:
                errors.append(f"item {item['key']}: {exc}")
                result = {"key": item["key"], "error": str(exc)}
                results.append(result)

            item_file = keychain_dir / f"item-{item['key'].replace('/', '_')}.json"
            item_file.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        summary = {
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "total_items": len(items),
                "acquired": sum(1 for r in results if r.get("acquired")),
                "errors": len(errors),
                "sha256": sha256_all.hexdigest(),
            },
            "accessibility": self.check_accessibility(),
            "items": results,
            "errors": errors,
        }

        manifest_path = keychain_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return summary


class ICloudAcquisitor:
    """Acquires iCloud tokens and authentication artifacts.

    Extracts iCloud authentication tokens, identity service artifacts,
    and account-related data from the Keychain and filesystem via
    the FBR34KER runtime exploit.
    """

    def __init__(self, command_fn: Callable[[str], str]):
        self._command = command_fn

    def list_accounts(self) -> list[dict[str, Any]]:
        raw = self._command("icloud-accounts")
        accounts: list[dict[str, Any]] = []
        for line in raw.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 1:
                accounts.append({
                    "account": parts[0],
                    "type": parts[1] if len(parts) > 1 else "unknown",
                    "status": parts[2] if len(parts) > 2 else "unknown",
                })
        return accounts

    def acquire_tokens(self) -> list[dict[str, Any]]:
        raw = self._command("icloud-tokens")
        tokens: list[dict[str, Any]] = []
        for line in raw.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                tokens.append({
                    "service": parts[0],
                    "token_hash": parts[1],
                    "expiry": parts[2] if len(parts) > 2 else "",
                })
        return tokens

    def acquire_identity_services(self) -> dict[str, Any]:
        raw = self._command("icloud-identity")
        result: dict[str, Any] = {}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return result

    def acquire_all(self, output_dir: pathlib.Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        icloud_dir = output_dir / "icloud"
        icloud_dir.mkdir(exist_ok=True)

        accounts = self.list_accounts()
        tokens = self.acquire_tokens()
        identity = self.acquire_identity_services()

        manifest = {
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "account_count": len(accounts),
                "token_count": len(tokens),
            },
            "accounts": accounts,
            "tokens": tokens,
            "identity_services": identity,
        }

        manifest_path = icloud_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        for acct in accounts:
            acct_file = icloud_dir / f"account-{acct['account'].replace('@', '_at_')}.json"
            acct_file.write_text(
                json.dumps(acct, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        return manifest


class SecretsAcquisitor:
    """Orchestrates iCloud, Keychain, and Keybag acquisition.

    Coordinates all three acquisitors with chain-of-custody logging
    and integrated SEP mailbox operations.
    """

    def __init__(
        self,
        command_fn: Callable[[str], str],
        *,
        sep_mailbox: SepMailbox | None = None,
        custody: CustodyLog | None = None,
    ):
        self._command = command_fn
        self._sep = sep_mailbox
        self.custody = custody or CustodyLog()
        self.icloud = ICloudAcquisitor(command_fn)
        self.keychain = KeychainAcquisitor(command_fn)
        self.keybags = KeybagAcquisitor(command_fn, sep_mailbox)

    def sep_unlock(
        self,
        passcode: str = "",
        *,
        use_exploit: bool = False,
    ) -> dict[str, Any]:
        """Attempt to unlock the SEP.

        Args:
            passcode: Device passcode (if known) for SEP unlock via ESB.
            use_exploit: If True, attempt SEP exploit-based unlock.

        Returns:
            SEP unlock result with status.
        """
        result: dict[str, Any] = {"unlocked": False}

        if self._sep:
            status = self._sep.detect()
            result["sep_detected"] = status["available"]

        if passcode:
            try:
                raw = self._command(f"sep-unlock-passcode {passcode}")
                result["method"] = "passcode"
                result["raw"] = raw
                if "ok" in raw.lower():
                    result["unlocked"] = True
            except Exception as exc:
                result["error"] = str(exc)

        if use_exploit and not result["unlocked"]:
            try:
                raw = self._command("sep-unlock-exploit")
                result["method"] = "exploit"
                result["raw"] = raw
                if "ok" in raw.lower():
                    result["unlocked"] = True
            except Exception as exc:
                result["error"] = str(exc)
                if "not" in result.get("error", ""):
                    result["error_exploit"] = str(exc)

        return result

    def acquire_all(
        self,
        output_dir: pathlib.Path,
        *,
        passcode: str = "",
        use_sep_exploit: bool = False,
    ) -> dict[str, Any]:
        """Acquire all secrets with SEP unlock if needed."""
        output_dir.mkdir(parents=True, exist_ok=True)

        self.custody.record(
            "secrets.acquire.start",
            f"Starting secrets acquisition (passcode={'provided' if passcode else 'none'}, "
            f"sep_exploit={use_sep_exploit})",
        )

        unlock_result = self.sep_unlock(
            passcode, use_exploit=use_sep_exploit
        )
        sep_unlocked = unlock_result.get("unlocked", False)
        self.custody.record("secrets.sep_unlock", f"SEP unlock: {unlock_result}")

        results: dict[str, Any] = {
            "sep_unlock": unlock_result,
            "keybags": {"status": "skipped", "reason": "SEP not unlocked"},
            "keychain": {"status": "skipped", "reason": "SEP not unlocked"},
        }

        if sep_unlocked:
            try:
                bag_result = self.keybags.extract_all(output_dir)
                results["keybags"] = {
                    "status": "completed",
                    "bags": bag_result["acquisition"]["bag_count"],
                    "extracted": bag_result["acquisition"]["extracted"],
                }
                self.custody.record(
                    "secrets.keybags",
                    f"Extracted {bag_result['acquisition']['extracted']} keybags",
                )
            except Exception as exc:
                results["keybags"] = {"status": "failed", "error": str(exc)}
                self.custody.record("secrets.keybags", f"Failed: {exc}")

            try:
                kc_result = self.keychain.acquire_all(output_dir)
                results["keychain"] = {
                    "status": "completed",
                    "items": kc_result["acquisition"]["total_items"],
                    "acquired": kc_result["acquisition"]["acquired"],
                }
                self.custody.record(
                    "secrets.keychain",
                    f"Acquired {kc_result['acquisition']['acquired']} keychain items",
                )
            except Exception as exc:
                results["keychain"] = {"status": "failed", "error": str(exc)}
                self.custody.record("secrets.keychain", f"Failed: {exc}")

        try:
            ic_result = self.icloud.acquire_all(output_dir)
            results["icloud"] = {
                "status": "completed",
                "accounts": ic_result["acquisition"]["account_count"],
                "tokens": ic_result["acquisition"]["token_count"],
            }
            self.custody.record(
                "secrets.icloud",
                f"Found {ic_result['acquisition']['account_count']} accounts, "
                f"{ic_result['acquisition']['token_count']} tokens",
            )
        except Exception as exc:
            results["icloud"] = {"status": "failed", "error": str(exc)}
            self.custody.record("secrets.icloud", f"Failed: {exc}")

        return results
