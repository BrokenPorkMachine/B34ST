"""Passcode management: on/off/change via SEP and exploit chain.

# SPDX-License-Identifier: BSD-2-Clause
Provides passcode state query, passcode removal, passcode setting,
and passcode change operations through the FBR34KER exploit
infrastructure and SEP communication.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from typing import Any, Callable

from host.forensics.chain_of_custody import CustodyLog
from host.forensics.secrets import SepMailbox


class PasscodeError(RuntimeError):
    pass


class PasscodeManager:
    """Passcode state control on the target device.

    Passcode operations require SEP interaction:
    - Querying passcode state (on/off, type, complexity)
    - Removing the passcode (requires passcode or SEP exploit)
    - Setting a new passcode
    - Changing the passcode (requires current passcode)
    - Bypassing passcode for keychain extraction
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

    def check_state(self) -> dict[str, Any]:
        raw = self._command("passcode-status")
        result: dict[str, Any] = {
            "passcode_set": False,
        }
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        lower_str = str(result).lower()
        if "set" in lower_str or "enabled" in lower_str or "on" in lower_str:
            result["passcode_set"] = True
        return result

    def check_policy(self) -> dict[str, Any]:
        raw = self._command("passcode-policy")
        result: dict[str, Any] = {}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return result

    def remove(self, current_passcode: str = "", *, use_exploit: bool = False) -> dict[str, Any]:
        """Remove the device passcode.

        Args:
            current_passcode: Current passcode (required unless exploit used).
            use_exploit: If True, attempt SEP exploit to bypass passcode requirement.

        Returns:
            Passcode removal result.
        """
        self.custody.record(
            "passcode.remove.start",
            f"Attempting passcode removal (exploit={use_exploit})",
        )

        result: dict[str, Any] = {
            "passcode_removed": False,
        }

        if current_passcode:
            raw = self._command(f"passcode-remove {current_passcode}")
        elif use_exploit:
            raw = self._command("passcode-remove-exploit")
        else:
            raise PasscodeError(
                "current passcode required (or use exploit)"
            )

        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower() or "removed" in str(result).lower():
            result["passcode_removed"] = True
        else:
            result["error"] = raw.strip()

        self.custody.record(
            "passcode.remove.result",
            f"Removed: {result.get('passcode_removed')}",
        )
        return result

    def set_passcode(self, new_passcode: str) -> dict[str, Any]:
        if not new_passcode:
            raise PasscodeError("new passcode cannot be empty")
        if len(new_passcode) < 4:
            raise PasscodeError("passcode must be at least 4 characters")

        self.custody.record(
            "passcode.set.start", "Setting new device passcode"
        )
        raw = self._command(f"passcode-set {new_passcode}")
        result: dict[str, Any] = {"passcode_set": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["passcode_set"] = True
        self.custody.record(
            "passcode.set.result",
            f"Set: {result.get('passcode_set')}",
        )
        return result

    def change(self, current_passcode: str, new_passcode: str) -> dict[str, Any]:
        if not current_passcode:
            raise PasscodeError("current passcode required")
        if not new_passcode:
            raise PasscodeError("new passcode cannot be empty")
        if len(new_passcode) < 4:
            raise PasscodeError("passcode must be at least 4 characters")

        self.custody.record(
            "passcode.change.start", "Changing device passcode"
        )
        raw = self._command(
            f"passcode-change {current_passcode} {new_passcode}"
        )
        result: dict[str, Any] = {"passcode_changed": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["passcode_changed"] = True
        self.custody.record(
            "passcode.change.result",
            f"Changed: {result.get('passcode_changed')}",
        )
        return result

    def attempt_bypass(self) -> dict[str, Any]:
        self.custody.record(
            "passcode.bypass.start", "Attempting passcode bypass"
        )
        raw = self._command("passcode-bypass")
        result: dict[str, Any] = {"bypassed": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower() or "bypassed" in str(result).lower():
            result["bypassed"] = True
        self.custody.record(
            "passcode.bypass.result",
            f"Bypassed: {result.get('bypassed')}",
        )
        return result

    def query_all(self, output_dir: pathlib.Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        passcode_dir = output_dir / "passcode"
        passcode_dir.mkdir(exist_ok=True)

        state = self.check_state()
        policy = self.check_policy()

        manifest = {
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            "state": state,
            "policy": policy,
        }

        manifest_path = passcode_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest
