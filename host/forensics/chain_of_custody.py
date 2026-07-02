"""Immutable chain-of-custody log for forensic acquisitions.

# SPDX-License-Identifier: BSD-2-Clause
Each entry is cryptographically linked to the previous via SHA-256,
providing tamper-evident provenance for all acquired evidence.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
from typing import Any


class CustodyError(RuntimeError):
    pass


class CustodyEntry:
    """A single entry in the chain-of-custody log."""

    def __init__(
        self,
        action: str,
        detail: str,
        previous_hash: str = "",
        *,
        operator: str = "",
        device_id: str = "",
    ):
        self.timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        self.action = action
        self.detail = detail
        self.operator = operator
        self.device_id = device_id
        self.previous_hash = previous_hash

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "detail": self.detail,
            "operator": self.operator,
            "device_id": self.device_id,
            "previous_hash": self.previous_hash,
        }

    def compute_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def to_dict(self, entry_hash: str = "") -> dict[str, Any]:
        data: dict[str, Any] = dict(self.payload)
        if entry_hash:
            data["entry_hash"] = entry_hash
        return data


class CustodyLog:
    """Append-only tamper-evident chain-of-custody log."""

    def __init__(self, *, operator: str = "", device_id: str = ""):
        self.operator = operator
        self.device_id = device_id
        self._entries: list[tuple[CustodyEntry, str]] = []
        self._sealed = False

    def record(
        self,
        action: str,
        detail: str,
    ) -> str:
        if self._sealed:
            raise CustodyError("cannot record: custody log is sealed")
        previous = self._entries[-1][1] if self._entries else ""
        entry = CustodyEntry(
            action=action,
            detail=detail,
            previous_hash=previous,
            operator=self.operator,
            device_id=self.device_id,
        )
        entry_hash = entry.compute_hash()
        self._entries.append((entry, entry_hash))
        return entry_hash

    @property
    def last_hash(self) -> str:
        if not self._entries:
            return ""
        return self._entries[-1][1]

    @property
    def entries(self) -> list[dict[str, Any]]:
        return [e.to_dict(h) for e, h in self._entries]

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def seal(self) -> str:
        if self._sealed:
            raise CustodyError("custody log is already sealed")
        self._sealed = True
        seal = CustodyEntry(
            action="log.sealed",
            detail=f"Chain-of-custody log sealed with {self.entry_count} entries",
            previous_hash=self.last_hash,
            operator=self.operator,
            device_id=self.device_id,
        )
        seal_hash = seal.compute_hash()
        self._entries.append((seal, seal_hash))
        return seal_hash

    def verify(self) -> bool:
        for i, (entry, stored_hash) in enumerate(self._entries):
            computed = entry.compute_hash()
            if computed != stored_hash:
                return False
            if i > 0:
                expected_prev = self._entries[i - 1][1]
                if entry.previous_hash != expected_prev:
                    return False
        return True

    def export_json(self) -> str:
        entries = self.entries
        return json.dumps(
            {
                "schema": "chain-of-custody-v1",
                "operator": self.operator,
                "device_id": self.device_id,
                "sealed": self._sealed,
                "entry_count": self.entry_count,
                "last_hash": self.last_hash,
                "verified": self.verify(),
                "entries": entries,
            },
            indent=2,
            sort_keys=True,
        )

    def write(self, path: pathlib.Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.export_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: pathlib.Path) -> CustodyLog:
        data = json.loads(path.read_text(encoding="utf-8"))
        log = cls(operator=data.get("operator", ""), device_id=data.get("device_id", ""))
        for entry_data in data.get("entries", []):
            entry = CustodyEntry(
                action=entry_data["action"],
                detail=entry_data["detail"],
                previous_hash=entry_data.get("previous_hash", ""),
                operator=entry_data.get("operator", log.operator),
                device_id=entry_data.get("device_id", log.device_id),
            )
            entry.timestamp = entry_data["timestamp"]
            entry_hash = entry_data.get("entry_hash", "")
            if entry_hash:
                log._entries.append((entry, entry_hash))
        if data.get("sealed"):
            log._sealed = True
        return log
