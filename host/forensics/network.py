"""Network state acquisition for forensic capture of network configuration.

# SPDX-License-Identifier: BSD-2-Clause
Captures interface information, active connections, routing tables,
and network stack state via wire protocol or console commands.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib
from typing import Any, Callable


class NetworkAcquisitionError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class NetworkInterfaceInfo:
    """Describes a network interface on the target."""

    name: str
    type: str
    mac: str = ""
    ipv4: str = ""
    ipv6: str = ""
    mtu: int = 0
    flags: str = ""
    state: str = ""
    description: str = ""


class NetworkAcquisitor:
    """Captures network state from a target device.

    Uses caller-provided command execution to query network
    interfaces, connections, routing, and DNS configuration.
    """

    def __init__(
        self,
        command_fn: Callable[[str], str],
    ):
        self._command_fn = command_fn

    def _run(self, command: str) -> str:
        try:
            return self._command_fn(command)
        except RuntimeError as exc:
            raise NetworkAcquisitionError(f"command failed: {command}: {exc}") from exc

    def capture_interfaces(self) -> list[NetworkInterfaceInfo]:
        raw = self._run("network-interfaces")
        interfaces: list[NetworkInterfaceInfo] = []
        for line in raw.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 1:
                interfaces.append(
                    NetworkInterfaceInfo(
                        name=parts[0],
                        type=parts[1] if len(parts) > 1 else "",
                        mac=parts[2] if len(parts) > 2 else "",
                        ipv4=parts[3] if len(parts) > 3 else "",
                        state=parts[4] if len(parts) > 4 else "",
                    )
                )
        return interfaces

    def capture_connections(self) -> str:
        return self._run("network-connections")

    def capture_routing(self) -> str:
        return self._run("network-routing")

    def capture_dns(self) -> str:
        return self._run("network-dns")

    def capture_arp(self) -> str:
        return self._run("network-arp")

    def capture_all(
        self,
        output_dir: pathlib.Path,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        net_dir = output_dir / "network"
        net_dir.mkdir(exist_ok=True)

        captures: dict[str, Any] = {}
        errors: list[str] = []

        for name, method in [
            ("interfaces", self.capture_interfaces),
            ("connections", self.capture_connections),
            ("routing", self.capture_routing),
            ("dns", self.capture_dns),
            ("arp", self.capture_arp),
        ]:
            try:
                result = method()
                if isinstance(result, list):
                    captures[name] = [dataclasses.asdict(i) for i in result]
                else:
                    captures[name] = result
                (net_dir / f"{name}.txt").write_text(str(result), encoding="utf-8")
            except (OSError, RuntimeError) as exc:
                errors.append(f"{name}: {exc}")
                captures[name] = {"error": str(exc)}

        manifest = {
            "acquisition": {
                "timestamp": dt.datetime.now()
                .astimezone()
                .isoformat(timespec="seconds"),
                "categories": list(captures.keys()),
                "error_count": len(errors),
            },
            "data": captures,
            "errors": errors,
        }

        manifest_path = net_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return manifest
