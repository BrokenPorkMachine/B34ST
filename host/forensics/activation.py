"""Activation, baseband, mobileactivationd, and FMI (Find My) operations.

Provides activation lock bypass, baseband management (unlock/IMEI),
mobileactivationd interaction, and FMI state control via the
FBR34KER exploit chain and SEP communication.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from typing import Any, Callable

from host.forensics.chain_of_custody import CustodyLog


class ActivationError(RuntimeError):
    pass


class ActivationBypass:
    """iCloud Activation Lock bypass operations.

    Activation lock is enforced by a combination of:
    - Baseband records (activation ticket storage)
    - NAND-based activation records
    - Mobileactivationd daemon state
    - SEP nonce/efuse checks

    Bypass strategies:
    1. Clear baseband activation records
    2. Patch mobileactivationd to accept offline activation
    3. Inject forged activation ticket
    4. Modify NAND activation records
    5. SEP efuse bypass (requires exploit)
    """

    def __init__(
        self,
        command_fn: Callable[[str], str],
        *,
        custody: CustodyLog | None = None,
    ):
        self._command = command_fn
        self.custody = custody or CustodyLog()

    def check_state(self) -> dict[str, Any]:
        raw = self._command("activation-status")
        result: dict[str, Any] = {
            "is_activated": False,
            "activation_locked": True,
        }
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "activated" in str(result).lower():
            result["is_activated"] = True
            result["activation_locked"] = False
        return result

    def check_ticket(self) -> dict[str, Any]:
        raw = self._command("activation-ticket-status")
        result: dict[str, Any] = {"ticket_present": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "present" in str(result).lower() or "found" in str(result).lower():
            result["ticket_present"] = True
        return result

    def clear_activation_records(self) -> dict[str, Any]:
        self.custody.record("activation.clear", "Clearing activation records")
        raw = self._command("activation-clear-records")
        result: dict[str, Any] = {"cleared": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["cleared"] = True
        self.custody.record(
            "activation.clear.result",
            f"Records cleared: {result.get('cleared')}",
        )
        return result

    def patch_mobileactivationd(self) -> dict[str, Any]:
        self.custody.record("activation.patch", "Patching mobileactivationd")
        raw = self._command("activation-patch-daemon")
        result: dict[str, Any] = {"patched": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["patched"] = True
        self.custody.record(
            "activation.patch.result",
            f"mobileactivationd patched: {result.get('patched')}",
        )
        return result

    def inject_forged_ticket(self, ticket_path: str = "") -> dict[str, Any]:
        self.custody.record("activation.inject_ticket", "Injecting activation ticket")
        cmd = "activation-inject-ticket"
        if ticket_path:
            cmd += f" {ticket_path}"
        raw = self._command(cmd)
        result: dict[str, Any] = {"injected": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["injected"] = True
        self.custody.record(
            "activation.inject_ticket.result",
            f"Ticket injected: {result.get('injected')}",
        )
        return result

    def apply_full_bypass(self, *, clear_records: bool = True) -> dict[str, Any]:
        self.custody.record(
            "activation.bypass.start", "Starting full activation bypass"
        )
        results: dict[str, Any] = {"bypass_complete": False}
        state = self.check_state()
        results["initial_state"] = state

        if state.get("is_activated"):
            results["bypass_complete"] = True
            results["reason"] = "Device is already activated"
            self.custody.record("activation.bypass", "Device already activated")
            return results

        if clear_records:
            clear = self.clear_activation_records()
            results["records_cleared"] = clear.get("cleared", False)

        patch = self.patch_mobileactivationd()
        results["mobileactivationd_patched"] = patch.get("patched", False)

        ticket_status = self.check_ticket()
        if not ticket_status.get("ticket_present"):
            inject = self.inject_forged_ticket()
            results["ticket_injected"] = inject.get("injected", False)

        final_state = self.check_state()
        results["final_state"] = final_state
        results["bypass_complete"] = final_state.get("is_activated", False)

        self.custody.record(
            "activation.bypass.result",
            f"Bypass {'succeeded' if results['bypass_complete'] else 'failed'}",
        )
        return results

    def query_efuse(self) -> dict[str, Any]:
        raw = self._command("efuse-status")
        result: dict[str, Any] = {}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return result


class BasebandManager:
    """Baseband management operations.

    Baseband (BP) operations include:
    - Querying baseband firmware version and state
    - Reading IMEI and ICCID
    - Clearing activation tickets from baseband NAND
    - Baseband unlock (SIM lock bypass)
    """

    def __init__(self, command_fn: Callable[[str], str]):
        self._command = command_fn

    def query_status(self) -> dict[str, Any]:
        raw = self._command("baseband-status")
        result: dict[str, Any] = {"baseband_present": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "present" in str(result).lower() and "not" not in str(result).lower():
            result["baseband_present"] = True
        return result

    def query_imei(self) -> list[str]:
        raw = self._command("baseband-imei")
        imeis: list[str] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if line and len(line) >= 15 and line.isdigit():
                imeis.append(line)
        return imeis

    def query_iccid(self) -> list[str]:
        raw = self._command("baseband-iccid")
        iccids: list[str] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if line and len(line) >= 10:
                iccids.append(line)
        return iccids

    def query_nand_tickets(self) -> list[dict[str, Any]]:
        raw = self._command("baseband-tickets")
        tickets: list[dict[str, Any]] = []
        for line in raw.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 1:
                tickets.append({
                    "identifier": parts[0],
                    "type": parts[1] if len(parts) > 1 else "",
                    "valid": parts[2] if len(parts) > 2 else "",
                })
        return tickets

    def clear_activation_tickets(self) -> dict[str, Any]:
        raw = self._command("baseband-clear-tickets")
        result: dict[str, Any] = {"cleared": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["cleared"] = True
        return result

    def unlock_baseband(self) -> dict[str, Any]:
        raw = self._command("baseband-unlock")
        result: dict[str, Any] = {"unlocked": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower() or "unlocked" in str(result).lower():
            result["unlocked"] = True
        return result

    def query_all(self, output_dir: pathlib.Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        bp_dir = output_dir / "baseband"
        bp_dir.mkdir(exist_ok=True)

        status = self.query_status()
        imeis = self.query_imei()
        iccids = self.query_iccid()
        tickets = self.query_nand_tickets()

        manifest = {
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            "status": status,
            "imeis": imeis,
            "iccids": iccids,
            "activation_tickets": tickets,
        }

        manifest_path = bp_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest


class MobileActivationManager:
    """mobileactivationd interaction and manipulation.

    mobileactivationd is the daemon responsible for device activation.
    Operations include querying its state, injecting activation records,
    patching its code to bypass activation checks, and managing
    activation-data stored on the device.
    """

    def __init__(self, command_fn: Callable[[str], str]):
        self._command = command_fn

    def query_state(self) -> dict[str, Any]:
        raw = self._command("mobileactivationd-status")
        result: dict[str, Any] = {"running": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "running" in str(result).lower():
            result["running"] = True
        return result

    def query_activation_info(self) -> dict[str, Any]:
        raw = self._command("mobileactivationd-info")
        result: dict[str, Any] = {}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return result

    def inject_activation_record(self, record_path: str = "") -> dict[str, Any]:
        cmd = "mobileactivationd-inject"
        if record_path:
            cmd += f" {record_path}"
        raw = self._command(cmd)
        result: dict[str, Any] = {"injected": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["injected"] = True
        return result

    def patch_activation_check(self) -> dict[str, Any]:
        raw = self._command("mobileactivationd-patch")
        result: dict[str, Any] = {"patched": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["patched"] = True
        return result

    def restart(self) -> dict[str, Any]:
        raw = self._command("mobileactivationd-restart")
        result: dict[str, Any] = {"restarted": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["restarted"] = True
        return result

    def query_all(self, output_dir: pathlib.Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        mad_dir = output_dir / "mobileactivationd"
        mad_dir.mkdir(exist_ok=True)

        state = self.query_state()
        info = self.query_activation_info()

        manifest = {
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            "state": state,
            "activation_info": info,
        }

        manifest_path = mad_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest


class FmiManager:
    """Find My iPhone (FMI) state control.

    FMI state is stored in:
    - NAND activation records
    - Baseband ticket records
    - iCloud account state
    - SEP nonce

    Operations expose current FMI state and allow toggling via
    available exploit infrastructure.
    """

    def __init__(self, command_fn: Callable[[str], str]):
        self._command = command_fn

    def check_state(self) -> dict[str, Any]:
        raw = self._command("fmi-status")
        result: dict[str, Any] = {
            "fmi_on": False,
            "fmi_off": True,
        }
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        lower_str = str(result).lower()
        if "on" in lower_str or "enabled" in lower_str or "locked" in lower_str:
            result["fmi_on"] = True
            result["fmi_off"] = False
        return result

    def turn_off(self) -> dict[str, Any]:
        raw = self._command("fmi-off")
        result: dict[str, Any] = {"fmi_on": True, "fmi_off_requested": True}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower() or "off" in str(result).lower():
            result["fmi_on"] = False
            result["fmi_off"] = True
        return result

    def turn_on(self) -> dict[str, Any]:
        raw = self._command("fmi-on")
        result: dict[str, Any] = {"fmi_on": False, "fmi_on_requested": True}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower() or "on" in str(result).lower():
            result["fmi_on"] = True
            result["fmi_off"] = False
        return result

    def clear_activation_lock(self) -> dict[str, Any]:
        raw = self._command("fmi-clear-activation-lock")
        result: dict[str, Any] = {"cleared": False}
        for line in raw.strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        if "ok" in str(result).lower():
            result["cleared"] = True
        return result

    def query_all(self, output_dir: pathlib.Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        fmi_dir = output_dir / "fmi"
        fmi_dir.mkdir(exist_ok=True)

        state = self.check_state()

        manifest = {
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            "state": state,
        }

        manifest_path = fmi_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest


class ActivationOrchestrator:
    """Coordinates activation, baseband, mobileactivationd, and FMI operations."""

    def __init__(
        self,
        command_fn: Callable[[str], str],
        *,
        custody: CustodyLog | None = None,
    ):
        self._command = command_fn
        self.custody = custody or CustodyLog()
        self.activation = ActivationBypass(command_fn, custody=self.custody)
        self.baseband = BasebandManager(command_fn)
        self.mobileactivationd = MobileActivationManager(command_fn)
        self.fmi = FmiManager(command_fn)

    def query_all(self, output_dir: pathlib.Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        activation_dir = output_dir / "activation"
        activation_dir.mkdir(exist_ok=True)

        activation_state = self.activation.check_state()
        activation_ticket = self.activation.check_ticket()
        activation_efuse = self.activation.query_efuse()
        baseband_status = self.baseband.query_status()
        imeis = self.baseband.query_imei()
        iccids = self.baseband.query_iccid()
        mad_state = self.mobileactivationd.query_state()
        mad_info = self.mobileactivationd.query_activation_info()
        fmi_state = self.fmi.check_state()

        manifest = {
            "acquisition": {
                "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            "activation": {
                "state": activation_state,
                "ticket": activation_ticket,
                "efuse": activation_efuse,
            },
            "baseband": {
                "status": baseband_status,
                "imeis": imeis,
                "iccids": iccids,
            },
            "mobileactivationd": {
                "state": mad_state,
                "activation_info": mad_info,
            },
            "fmi": fmi_state,
        }

        manifest_path = activation_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest
