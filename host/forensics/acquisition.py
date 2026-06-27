"""Core acquisition engine for forensic data capture.

Coordinates memory, storage, filesystem, and network acquisition
with chain-of-custody logging and evidence bundle output.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib
from typing import Any

from host.forensics.chain_of_custody import CustodyLog
from host.forensics.profiles import AcquisitionProfile


class AcquisitionError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class AcquisitionTarget:
    """Describes the target device for acquisition."""
    device_id: str
    product: str = ""
    model: str = ""
    ios_version: str = ""
    ecid: str = ""
    serial: str = ""
    chipset: str = ""
    mode: str = ""
    operator: str = ""


@dataclasses.dataclass
class AcquisitionResult:
    """Result of a single acquisition operation."""
    acquirer: str
    target: str
    started_at: str = ""
    completed_at: str = ""
    status: str = "pending"
    total_bytes: int = 0
    file_count: int = 0
    sha256: str = ""
    error: str = ""
    details: dict[str, Any] = dataclasses.field(default_factory=dict)


class AcquisitionSession:
    """Manages a complete forensic acquisition session with chain-of-custody."""

    def __init__(
        self,
        target: AcquisitionTarget,
        output_dir: pathlib.Path,
        *,
        profile: AcquisitionProfile | None = None,
    ):
        self.target = target
        self.output_dir = output_dir
        self.profile = profile or AcquisitionProfile()
        self.results: list[AcquisitionResult] = []
        self.custody = CustodyLog(
            operator=target.operator,
            device_id=target.device_id,
        )
        self._finalized = False
        self.started_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")

    @property
    def session_dir(self) -> pathlib.Path:
        stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        return self.output_dir / f"acquisition-{self.target.device_id}-{stamp}"

    def record_result(self, result: AcquisitionResult) -> None:
        self.results.append(result)
        self.custody.record(
            action=f"acquisition.{result.acquirer}",
            detail=(
                f"{result.status}: "
                f"{result.total_bytes} bytes, "
                f"{result.file_count} files"
                f"{', SHA256=' + result.sha256 if result.sha256 else ''}"
                f"{', error=' + result.error if result.error else ''}"
            ),
        )

    def summary(self) -> dict[str, Any]:
        passed = sum(1 for r in self.results if r.status == "completed")
        failed = sum(1 for r in self.results if r.status == "failed")
        total_bytes = sum(r.total_bytes for r in self.results)
        return {
            "schema": "acquisition-session-v1",
            "started_at": self.started_at,
            "target": {
                "device_id": self.target.device_id,
                "product": self.target.product,
                "model": self.target.model,
                "ios_version": self.target.ios_version,
                "ecid": self.target.ecid,
                "chipset": self.target.chipset,
                "mode": self.target.mode,
                "operator": self.target.operator,
            },
            "profile": {
                "name": self.profile.name,
                "description": self.profile.description,
                "categories": list(self.profile.categories),
            },
            "results": [
                {
                    "acquirer": r.acquirer,
                    "status": r.status,
                    "total_bytes": r.total_bytes,
                    "file_count": r.file_count,
                    "sha256": r.sha256,
                    "error": r.error,
                }
                for r in self.results
            ],
            "summary": {
                "total_operations": len(self.results),
                "passed": passed,
                "failed": failed,
                "total_bytes": total_bytes,
            },
            "custody_hash": self.custody.last_hash,
            "custody_verified": self.custody.verify(),
        }

    def finalize(self) -> pathlib.Path:
        if self._finalized:
            raise AcquisitionError("session already finalized")
        self.custody.record(
            action="session.finalized",
            detail=f"Acquisition session completed with {len(self.results)} results",
        )
        self.custody.seal()
        session_dir = self.session_dir
        session_dir.mkdir(parents=True, exist_ok=True)

        summary_path = session_dir / "acquisition-summary.json"
        summary_path.write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        custody_path = session_dir / "chain-of-custody.json"
        self.custody.write(custody_path)

        self._finalized = True
        return session_dir


class AcquisitionEngine:
    """Orchestrates forensic acquisition using connected device transports."""

    def __init__(self, session: AcquisitionSession):
        self.session = session

    @classmethod
    def create(
        cls,
        target: AcquisitionTarget,
        output_dir: pathlib.Path,
        *,
        profile: AcquisitionProfile | None = None,
    ) -> AcquisitionEngine:
        session = AcquisitionSession(target, output_dir, profile=profile)
        return cls(session)

    def run(self) -> AcquisitionSession:
        self.session.custody.record(
            action="session.started",
            detail=f"Acquisition session started with profile: {self.session.profile.name}",
        )
        return self.session
