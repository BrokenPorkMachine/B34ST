#!/usr/bin/env python3
"""Deployment orchestration, retry, resume, and evidence collection."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import struct
import threading
import time
import zipfile
from typing import Iterable

from deployment_profile import DeploymentProfile, ProfileError
from deployment_target import CHUNK_HEADER, INDEX_TOKEN, TOKEN_ONLY
from deployment_transport import (DeploymentTransport, TransportDisconnected,
                                  TransportError, TransportTimeout)
from wire_protocol import FLAG_ACK, FLAG_ERROR, MAX_CHUNK, Frame, MessageType


class DeploymentError(RuntimeError):
    """Raised when a deployment cannot be completed safely."""


class DeploymentCancelled(DeploymentError):
    """Raised when the caller cancels a bounded deployment."""


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise DeploymentCancelled("deployment was cancelled")


def hash_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclasses.dataclass(frozen=True)
class LocalArtifact:
    name: str
    kind: str
    path: pathlib.Path
    load_address: int
    size: int
    sha256: str

    @classmethod
    def from_path(cls, name: str, kind: str, path: pathlib.Path,
                  load_address: int) -> "LocalArtifact":
        resolved = path.resolve()
        if not resolved.is_file():
            raise DeploymentError(f"artifact does not exist: {path}")
        size = resolved.stat().st_size
        digest = hash_file(resolved)
        return cls(name, kind, resolved, load_address, size, digest)

    def manifest_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "load_address": self.load_address,
            "size": self.size,
            "sha256": self.sha256,
        }


@dataclasses.dataclass
class TranscriptEntry:
    sequence: int
    message: str
    status: str
    attempt: int
    duration_ms: int
    detail: str


class DeploymentClient:
    def __init__(self, transport: DeploymentTransport, *, timeout: float = 3.0,
                 retries: int = 3, chunk_size: int = MAX_CHUNK,
                 cancellation: CancellationToken | None = None):
        if timeout <= 0:
            raise DeploymentError("timeout must be positive")
        if not 0 <= retries <= 10:
            raise DeploymentError("retries must be 0..10")
        if not 1 <= chunk_size <= MAX_CHUNK:
            raise DeploymentError(f"chunk_size must be 1..{MAX_CHUNK}")
        self.transport = transport
        self.timeout = timeout
        self.retries = retries
        self.chunk_size = chunk_size
        self.sequence = 0
        self.transcript: list[TranscriptEntry] = []
        self.cancellation = cancellation or CancellationToken()

    def close(self) -> None:
        self.transport.close()

    def _next_sequence(self) -> int:
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        if self.sequence == 0:
            self.sequence = 1
        return self.sequence

    def _exchange(self, kind: MessageType, payload: bytes = b"") -> bytes:
        self.cancellation.raise_if_cancelled()
        sequence = self._next_sequence()
        request = Frame(int(kind), 0, sequence, payload)
        last_error: BaseException | None = None
        for attempt in range(1, self.retries + 2):
            self.cancellation.raise_if_cancelled()
            started = time.monotonic()
            try:
                response = self.transport.exchange(request, self.timeout)
                duration = int((time.monotonic() - started) * 1000)
                expected_type = int(kind) | 0x80
                if response.sequence != sequence or response.message_type != expected_type:
                    raise DeploymentError("deployment response does not match request")
                if not response.flags & FLAG_ACK:
                    raise DeploymentError("deployment response is missing ACK")
                if response.flags & FLAG_ERROR:
                    detail = response.payload.decode("utf-8", errors="replace").strip()
                    self.transcript.append(TranscriptEntry(sequence, kind.name, "target-error",
                                                           attempt, duration, detail))
                    raise DeploymentError(detail or "target rejected deployment request")
                self.transcript.append(TranscriptEntry(sequence, kind.name, "passed", attempt,
                                                       duration, f"payload={len(response.payload)}"))
                return response.payload
            except (TransportTimeout, TransportDisconnected, TransportError) as exc:
                last_error = exc
                duration = int((time.monotonic() - started) * 1000)
                self.transcript.append(TranscriptEntry(sequence, kind.name, "retry",
                                                       attempt, duration, str(exc)))
                if attempt > self.retries:
                    break
                self.cancellation.raise_if_cancelled()
                time.sleep(min(0.05 * (2 ** (attempt - 1)), 0.5))
        raise DeploymentError(f"{kind.name} failed after {self.retries + 1} attempts: {last_error}")

    @staticmethod
    def _parse_json(payload: bytes, context: str) -> dict[str, object]:
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeploymentError(f"{context} response is not valid JSON") from exc
        if not isinstance(value, dict):
            raise DeploymentError(f"{context} response root is not an object")
        return value

    def hello(self) -> dict[str, object]:
        return self._parse_json(self._exchange(MessageType.HELLO), "HELLO")

    def capabilities(self) -> dict[str, object]:
        return self._parse_json(self._exchange(MessageType.CAPABILITIES), "CAPABILITIES")

    def recover(self) -> dict[str, object]:
        return self._parse_json(self._exchange(MessageType.RECOVER_SESSION), "RECOVER_SESSION")

    def evidence(self) -> dict[str, object]:
        return self._parse_json(self._exchange(MessageType.EVIDENCE_GET), "EVIDENCE_GET")

    def reset(self) -> dict[str, object]:
        recovered = self.recover()
        token = recovered.get("authorization_token")
        if not isinstance(token, int) or token <= 0:
            raise DeploymentError("target has no active deployment session to reset")
        return self._parse_json(
            self._exchange(MessageType.RESET_SESSION, TOKEN_ONLY.pack(token)),
            "RESET_SESSION",
        )

    def deploy(self, profile: DeploymentProfile, artifacts: Iterable[LocalArtifact],
               *, authorize: bool, resume: bool = True, start: bool = True) -> dict[str, object]:
        artifacts_list = list(artifacts)
        validate_local_plan(profile, artifacts_list)
        if not authorize:
            raise DeploymentError("deployment mutation requires explicit --authorize")
        hello = self.hello()
        if hello.get("profile") != profile.name:
            raise DeploymentError("target profile does not match selected deployment profile")
        capabilities = self.capabilities()
        if 1 not in capabilities.get("protocol_versions", []):
            raise DeploymentError("target does not support deployment protocol version 1")
        remote_max_chunk = capabilities.get("max_chunk")
        if not isinstance(remote_max_chunk, int) or not 1 <= remote_max_chunk <= MAX_CHUNK:
            raise DeploymentError("target returned an invalid max_chunk capability")
        chunk_size = min(self.chunk_size, remote_max_chunk)

        token: int
        if resume:
            recovered = self.recover()
            recovered_artifacts = recovered.get("artifacts")
            expected_records = [artifact.manifest_record() for artifact in artifacts_list]
            same = isinstance(recovered_artifacts, list) and len(recovered_artifacts) == len(expected_records)
            if same:
                for expected, actual in zip(expected_records, recovered_artifacts):
                    if not isinstance(actual, dict) or any(actual.get(key) != expected[key]
                                                           for key in expected):
                        same = False
                        break
            if same and isinstance(recovered.get("authorization_token"), int):
                token = int(recovered["authorization_token"])
            else:
                token = self._begin(artifacts_list)
        else:
            token = self._begin(artifacts_list)

        for index, artifact in enumerate(artifacts_list):
            progress = self._parse_json(
                self._exchange(MessageType.QUERY_PROGRESS, INDEX_TOKEN.pack(index, token)),
                "QUERY_PROGRESS",
            )
            offset = progress.get("received")
            if not isinstance(offset, int) or not 0 <= offset <= artifact.size:
                raise DeploymentError(f"target returned invalid progress for {artifact.name}")
            if progress.get("committed") is True:
                continue
            with artifact.path.open("rb") as stream:
                stream.seek(offset)
                while offset < artifact.size:
                    self.cancellation.raise_if_cancelled()
                    chunk = stream.read(min(chunk_size, artifact.size - offset))
                    if not chunk:
                        raise DeploymentError(f"unexpected EOF in artifact {artifact.name}")
                    payload = CHUNK_HEADER.pack(index, token, offset, len(chunk)) + chunk
                    result = self._parse_json(self._exchange(MessageType.PUT_CHUNK, payload),
                                              "PUT_CHUNK")
                    received = result.get("received")
                    if received != offset + len(chunk):
                        raise DeploymentError(f"target progress mismatch for {artifact.name}")
                    offset = received
            committed = self._parse_json(
                self._exchange(MessageType.COMMIT_ARTIFACT, INDEX_TOKEN.pack(index, token)),
                "COMMIT_ARTIFACT",
            )
            if committed.get("sha256") != artifact.sha256 or committed.get("committed") is not True:
                raise DeploymentError(f"target did not verify {artifact.name}")
        if start:
            return self._parse_json(self._exchange(MessageType.START, TOKEN_ONLY.pack(token)),
                                    "START")
        return {
            "schema_version": 1,
            "status": "staged",
            "profile": profile.name,
            "artifacts": [artifact.manifest_record() for artifact in artifacts_list],
        }

    def _begin(self, artifacts: list[LocalArtifact]) -> int:
        payload = json.dumps({
            "authorization_intent": "authorized-development",
            "artifacts": [artifact.manifest_record() for artifact in artifacts],
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        result = self._parse_json(self._exchange(MessageType.BEGIN_DEPLOY, payload),
                                  "BEGIN_DEPLOY")
        token = result.get("authorization_token")
        if not isinstance(token, int) or token <= 0:
            raise DeploymentError("target did not return a valid authorization token")
        return token


def validate_local_plan(profile: DeploymentProfile, artifacts: list[LocalArtifact]) -> None:
    if not artifacts or len(artifacts) > 16:
        raise DeploymentError("deployment requires 1 to 16 artifacts")
    total = 0
    names: set[str] = set()
    occupied: list[tuple[int, int, str]] = []
    monitor_count = 0
    for artifact in artifacts:
        if artifact.name in names:
            raise DeploymentError(f"duplicate artifact name {artifact.name}")
        names.add(artifact.name)
        if artifact.kind == "monitor":
            monitor_count += 1
        if artifact.size <= 0 or artifact.size > profile.max_artifact_size:
            raise DeploymentError(f"artifact {artifact.name} violates size limit")
        if artifact.load_address % profile.entry_alignment:
            raise DeploymentError(f"artifact {artifact.name} load address is misaligned")
        try:
            profile.region_for(artifact.load_address, artifact.size, artifact.kind)
        except ProfileError as exc:
            raise DeploymentError(str(exc)) from exc
        end = artifact.load_address + artifact.size
        for prior_base, prior_end, prior_name in occupied:
            if artifact.load_address < prior_end and prior_base < end:
                raise DeploymentError(f"artifact {artifact.name} overlaps artifact {prior_name}")
        occupied.append((artifact.load_address, end, artifact.name))
        total += artifact.size
    if monitor_count != 1:
        raise DeploymentError("deployment requires exactly one monitor artifact")
    if total > profile.max_total_size:
        raise DeploymentError("deployment exceeds total-size limit")


def write_evidence_bundle(output: pathlib.Path, *, profile: DeploymentProfile,
                          artifacts: list[LocalArtifact], evidence: dict[str, object],
                          transcript: list[TranscriptEntry],
                          deterministic: bool = False) -> pathlib.Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "profile": profile.name,
        "evidence": evidence,
        "artifacts": [artifact.manifest_record() for artifact in artifacts],
        "transcript": [
            {**dataclasses.asdict(entry),
             "duration_ms": 0 if deterministic else entry.duration_ms}
            for entry in transcript
        ],
    }
    report_path = output / "deployment-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    hashes = {
        "deployment-report.json": hashlib.sha256(report_path.read_bytes()).hexdigest(),
    }
    hash_path = output / "SHA256SUMS"
    hash_path.write_text("\n".join(f"{digest}  {name}" for name, digest in hashes.items()) + "\n",
                         encoding="ascii")
    archive = output.with_suffix(".zip")
    temporary = archive.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as bundle:
        for path in (report_path, hash_path):
            info = zipfile.ZipInfo(f"{output.name}/{path.name}", (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                            compresslevel=9)
    temporary.replace(archive)
    return archive
