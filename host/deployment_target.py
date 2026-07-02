#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""File-backed development target for the FBR34KER deployment protocol."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import secrets
import struct
import time
from dataclasses import dataclass
from typing import Callable

from deployment_profile import DeploymentProfile, ProfileError
from wire_protocol import FLAG_ACK, FLAG_ERROR, MAX_CHUNK, Frame, MessageType

CHUNK_HEADER = struct.Struct("<HQQI")  # artifact index, token, offset, data length
INDEX_TOKEN = struct.Struct("<HQ")
TOKEN_ONLY = struct.Struct("<Q")
MAX_ARTIFACTS = 16


class TargetError(ValueError):
    """Raised for invalid deployment state or policy violations."""


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _safe_artifact_name(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise TargetError("artifact name is invalid")
    if any(
        ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
        for ch in value
    ):
        raise TargetError("artifact name contains unsupported characters")
    return value


def _bounded_json(payload: bytes) -> dict[str, object]:
    if len(payload) > 32768:
        raise TargetError("JSON request exceeds 32768 bytes")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TargetError("request payload is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise TargetError("request payload root must be an object")
    return value


@dataclass
class ArtifactState:
    index: int
    name: str
    kind: str
    load_address: int
    size: int
    sha256: str
    received: int = 0
    committed: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "index": self.index,
            "name": self.name,
            "kind": self.kind,
            "load_address": self.load_address,
            "size": self.size,
            "sha256": self.sha256,
            "received": self.received,
            "committed": self.committed,
        }


class SimulatedDeploymentTarget:
    """A persistent, bounded target used for integration and recovery testing."""

    def __init__(
        self,
        profile: DeploymentProfile,
        state_dir: pathlib.Path,
        *,
        clock_ns: Callable[[], int] | None = None,
        session_factory: Callable[[], str] | None = None,
        token_factory: Callable[[], int] | None = None,
    ):
        self.profile = profile
        self.clock_ns = clock_ns or time.time_ns
        self.session_factory = session_factory or (lambda: secrets.token_hex(12))
        self.token_factory = token_factory or (lambda: secrets.randbits(63) | 1)
        self.state_dir = state_dir.resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir = self.state_dir / "artifacts"
        self.artifact_dir.mkdir(exist_ok=True)
        self.session_path = self.state_dir / "session.json"
        self.evidence_path = self.state_dir / "boot-evidence.json"
        self.session_id = ""
        self.token = 0
        self.artifacts: list[ArtifactState] = []
        self.started = False
        self.last_event = "idle"
        self._response_cache: dict[int, tuple[bytes, Frame]] = {}
        self._load_session()

    def _load_session(self) -> None:
        if not self.session_path.exists():
            self.last_event = "no-session"
            return
        backup_path = self.session_path.with_suffix(".bak")
        source = self.session_path
        if backup_path.exists():
            try:
                backup_mtime = backup_path.stat().st_mtime
                source_mtime = source.stat().st_mtime
                if backup_mtime > source_mtime:
                    source = backup_path
            except OSError:
                pass
        try:
            with source.open("r", encoding="utf-8") as stream:
                raw = json.load(stream)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            if backup_path.exists():
                try:
                    with backup_path.open("r", encoding="utf-8") as stream:
                        raw = json.load(stream)
                    self.last_event = "recovered-from-backup"
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    self.last_event = "invalid-session-discarded"
                    return
            else:
                self.last_event = "invalid-session-discarded"
                return
        try:
            self.session_id = str(raw.get("session_id", ""))
            self.token = int(raw.get("token", 0))
            self.started = bool(raw.get("started", False))
            self.last_event = str(raw.get("last_event", "recovered"))
            artifacts_raw = raw.get("artifacts", [])
            if (
                not isinstance(artifacts_raw, list)
                or len(artifacts_raw) > MAX_ARTIFACTS
            ):
                raise ValueError("invalid persisted artifact list")
            recovered: list[ArtifactState] = []
            for item in artifacts_raw:
                if not isinstance(item, dict):
                    raise ValueError("invalid persisted artifact")
                artifact = ArtifactState(**item)
                _safe_artifact_name(artifact.name)
                self.profile.region_for(
                    artifact.load_address, artifact.size, artifact.kind
                )
                if not 0 <= artifact.received <= artifact.size:
                    raise ValueError("invalid persisted progress")
                recovered.append(artifact)
            self.artifacts = recovered
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.session_id = ""
            self.token = 0
            self.artifacts = []
            self.started = False
            self.last_event = "invalid-session-discarded"

    def _save_session(self) -> None:
        data = {
            "schema_version": 1,
            "profile": self.profile.name,
            "session_id": self.session_id,
            "token": self.token,
            "started": self.started,
            "last_event": self.last_event,
            "artifacts": [artifact.to_json() for artifact in self.artifacts],
        }
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = self.session_path.with_suffix(".bak")
        try:
            backup_content = self.session_path.read_text(encoding="utf-8")
            backup_path.write_text(backup_content, encoding="utf-8")
        except OSError:
            pass
        temporary = self.session_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(self.session_path)

    def _response(
        self, request: Frame, payload: object = b"", *, error: bool = False
    ) -> Frame:
        if isinstance(payload, bytes):
            encoded = payload
        elif isinstance(payload, str):
            encoded = payload.encode("utf-8")
        else:
            encoded = _json_bytes(payload)
        flags = FLAG_ACK | (FLAG_ERROR if error else 0)
        return Frame(request.message_type | 0x80, flags, request.sequence, encoded)

    def _require_token(self, token: int) -> None:
        if self.token == 0 or token != self.token:
            raise TargetError("session authorization token mismatch")

    def _artifact(self, index: int) -> ArtifactState:
        if not 0 <= index < len(self.artifacts):
            raise TargetError("artifact index is out of range")
        return self.artifacts[index]

    def _artifact_path(self, artifact: ArtifactState) -> pathlib.Path:
        return self.artifact_dir / f"{artifact.index:02d}-{artifact.name}.partial"

    def _begin(self, request: Frame) -> Frame:
        raw = _bounded_json(request.payload)
        if raw.get("authorization_intent") != "authorized-development":
            raise TargetError("explicit authorized-development intent is required")
        artifacts_raw = raw.get("artifacts")
        if (
            not isinstance(artifacts_raw, list)
            or not 1 <= len(artifacts_raw) <= MAX_ARTIFACTS
        ):
            raise TargetError(f"artifacts must contain 1 to {MAX_ARTIFACTS} entries")
        artifacts: list[ArtifactState] = []
        total = 0
        occupied: list[tuple[int, int, str]] = []
        for index, item in enumerate(artifacts_raw):
            if not isinstance(item, dict):
                raise TargetError(f"artifact {index} must be an object")
            if set(item) != {"name", "kind", "load_address", "size", "sha256"}:
                raise TargetError(f"artifact {index} fields are invalid")
            name = _safe_artifact_name(item["name"])
            kind = item["kind"]
            if not isinstance(kind, str):
                raise TargetError(f"artifact {index} kind is invalid")
            try:
                address = int(item["load_address"])
                size = int(item["size"])
            except (TypeError, ValueError) as exc:
                raise TargetError(
                    f"artifact {index} address or size is invalid"
                ) from exc
            digest = item["sha256"]
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(ch not in "0123456789abcdef" for ch in digest)
            ):
                raise TargetError(f"artifact {index} sha256 is invalid")
            if size <= 0 or size > self.profile.max_artifact_size:
                raise TargetError(f"artifact {index} size violates profile limit")
            if address % self.profile.entry_alignment != 0:
                raise TargetError(f"artifact {index} load address is misaligned")
            self.profile.region_for(address, size, kind)
            end = address + size
            for prior_base, prior_end, prior_name in occupied:
                if address < prior_end and prior_base < end:
                    raise TargetError(f"artifact {name} overlaps artifact {prior_name}")
            occupied.append((address, end, name))
            total += size
            if total > self.profile.max_total_size:
                raise TargetError("deployment exceeds profile total-size limit")
            artifacts.append(ArtifactState(index, name, kind, address, size, digest))
        for path in self.artifact_dir.glob("*.partial"):
            path.unlink()
        self.session_id = self.session_factory()
        self.token = self.token_factory()
        if not self.session_id or len(self.session_id) > 64 or self.token <= 0:
            raise TargetError("session factory returned invalid state")
        self.artifacts = artifacts
        self.started = False
        self.last_event = "deployment-begun"
        self._save_session()
        return self._response(
            request,
            {
                "session_id": self.session_id,
                "authorization_token": self.token,
                "max_chunk": MAX_CHUNK,
                "artifact_count": len(self.artifacts),
            },
        )

    def _query(self, request: Frame) -> Frame:
        if len(request.payload) != INDEX_TOKEN.size:
            raise TargetError("progress query has invalid size")
        index, token = INDEX_TOKEN.unpack(request.payload)
        self._require_token(token)
        artifact = self._artifact(index)
        path = self._artifact_path(artifact)
        on_disk = path.stat().st_size if path.is_file() else 0
        if on_disk != artifact.received:
            artifact.received = min(on_disk, artifact.size)
            artifact.committed = False
            self._save_session()
        return self._response(request, artifact.to_json())

    def _put_chunk(self, request: Frame) -> Frame:
        if len(request.payload) < CHUNK_HEADER.size:
            raise TargetError("chunk payload is truncated")
        index, token, offset, length = CHUNK_HEADER.unpack_from(request.payload)
        data = request.payload[CHUNK_HEADER.size :]
        if length != len(data) or length == 0 or length > MAX_CHUNK:
            raise TargetError("chunk length is invalid")
        self._require_token(token)
        artifact = self._artifact(index)
        if artifact.committed:
            raise TargetError("committed artifact cannot be modified")
        if offset != artifact.received:
            raise TargetError(
                f"chunk offset {offset} does not match resumable offset {artifact.received}"
            )
        if offset + length > artifact.size:
            raise TargetError("chunk exceeds declared artifact size")
        path = self._artifact_path(artifact)
        mode = "r+b" if path.exists() else "wb"
        with path.open(mode) as stream:
            stream.seek(offset)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        artifact.received += length
        self.last_event = f"chunk:{artifact.name}:{artifact.received}"
        self._save_session()
        return self._response(
            request,
            {
                "index": index,
                "received": artifact.received,
                "remaining": artifact.size - artifact.received,
            },
        )

    def _commit(self, request: Frame) -> Frame:
        if len(request.payload) != INDEX_TOKEN.size:
            raise TargetError("commit request has invalid size")
        index, token = INDEX_TOKEN.unpack(request.payload)
        self._require_token(token)
        artifact = self._artifact(index)
        path = self._artifact_path(artifact)
        if artifact.received != artifact.size or not path.is_file():
            raise TargetError("artifact is incomplete")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest != artifact.sha256:
            raise TargetError("artifact SHA-256 mismatch")
        artifact.committed = True
        self.last_event = f"committed:{artifact.name}"
        self._save_session()
        return self._response(
            request, {"index": index, "sha256": digest, "committed": True}
        )

    def _start(self, request: Frame) -> Frame:
        if len(request.payload) != TOKEN_ONLY.size:
            raise TargetError("start request has invalid size")
        (token,) = TOKEN_ONLY.unpack(request.payload)
        self._require_token(token)
        if not self.artifacts or not all(
            artifact.committed for artifact in self.artifacts
        ):
            raise TargetError("all artifacts must be committed before start")
        monitors = [
            artifact for artifact in self.artifacts if artifact.kind == "monitor"
        ]
        if len(monitors) != 1:
            raise TargetError("deployment must contain exactly one monitor artifact")
        self.started = True
        self.last_event = "monitor-started"
        evidence = {
            "schema_version": 1,
            "target": "file-backed-development-target",
            "profile": self.profile.name,
            "session_id": self.session_id,
            "started": True,
            "boot_stage": "monitor-entry",
            "timestamp_ns": self.clock_ns(),
            "artifacts": [artifact.to_json() for artifact in self.artifacts],
        }
        self.evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self._save_session()
        return self._response(request, evidence)

    def _evidence(self, request: Frame) -> Frame:
        if self.evidence_path.is_file():
            try:
                if self.evidence_path.stat().st_size > 64 * 1024:
                    raise ValueError("evidence exceeds bounded size")
                evidence = json.loads(self.evidence_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                evidence = {"schema_version": 1, "started": False, "status": "invalid"}
        else:
            evidence = {
                "schema_version": 1,
                "target": "file-backed-development-target",
                "profile": self.profile.name,
                "session_id": self.session_id or None,
                "started": self.started,
                "boot_stage": "not-started",
            }
        return self._response(request, evidence)

    def _reset(self, request: Frame) -> Frame:
        if len(request.payload) != TOKEN_ONLY.size:
            raise TargetError("reset request has invalid size")
        (token,) = TOKEN_ONLY.unpack(request.payload)
        self._require_token(token)
        for path in self.artifact_dir.glob("*.partial"):
            path.unlink()
        self.session_id = ""
        self.token = 0
        self.artifacts = []
        self.started = False
        self.last_event = "session-reset"
        if self.session_path.exists():
            self.session_path.unlink()
        return self._response(
            request, {"reset": True, "evidence_preserved": self.evidence_path.exists()}
        )

    def _dispatch(self, request: Frame) -> Frame:
        try:
            kind = MessageType(request.message_type)
            if request.flags != 0:
                raise TargetError("request flags must be zero")
            if kind == MessageType.PING:
                return self._response(request, request.payload)
            if kind == MessageType.HELLO:
                return self._response(
                    request,
                    {
                        "protocol": 1,
                        "target": "file-backed-development-target",
                        "profile": self.profile.name,
                        "board_compatible": self.profile.board_compatible,
                        "session_active": bool(self.session_id),
                        "started": self.started,
                    },
                )
            if kind == MessageType.CAPABILITIES:
                return self._response(
                    request,
                    {
                        "protocol_versions": [1],
                        "max_chunk": MAX_CHUNK,
                        "max_artifacts": MAX_ARTIFACTS,
                        "resume": True,
                        "evidence": True,
                        "arbitrary_memory": False,
                        "exploit_transport": False,
                        "deployment_regions": [
                            {
                                "name": region.name,
                                "base": region.base,
                                "size": region.size,
                                "artifact_kinds": sorted(region.kinds),
                            }
                            for region in self.profile.regions
                        ],
                    },
                )
            if kind == MessageType.BEGIN_DEPLOY:
                return self._begin(request)
            if kind == MessageType.QUERY_PROGRESS:
                return self._query(request)
            if kind == MessageType.PUT_CHUNK:
                return self._put_chunk(request)
            if kind == MessageType.COMMIT_ARTIFACT:
                return self._commit(request)
            if kind == MessageType.START:
                return self._start(request)
            if kind == MessageType.EVIDENCE_GET:
                return self._evidence(request)
            if kind == MessageType.RESET_SESSION:
                return self._reset(request)
            if kind == MessageType.RECOVER_SESSION:
                self._load_session()
                return self._response(
                    request,
                    {
                        "session_id": self.session_id or None,
                        "authorization_token": self.token if self.session_id else None,
                        "started": self.started,
                        "artifacts": [
                            artifact.to_json() for artifact in self.artifacts
                        ],
                    },
                )
            raise TargetError("unsupported deployment message")
        except (TargetError, ProfileError, ValueError) as exc:
            return self._response(request, {"error": str(exc)}, error=True)

    def handle(self, request: Frame) -> Frame:
        request_fingerprint = hashlib.sha256(
            bytes((request.message_type & 0xFF,))
            + request.flags.to_bytes(2, "little")
            + request.payload
        ).digest()
        cached = self._response_cache.get(request.sequence)
        if cached is not None:
            fingerprint, response = cached
            if fingerprint == request_fingerprint:
                return response
            return self._response(
                request,
                {"error": "sequence number reused with different request"},
                error=True,
            )
        response = self._dispatch(request)
        # Keep the cache bounded.  Deployment clients retry only the current
        # exchange, so retaining the most recent 32 responses is sufficient.
        if len(self._response_cache) >= 32:
            oldest = next(iter(self._response_cache))
            del self._response_cache[oldest]
        self._response_cache[request.sequence] = (request_fingerprint, response)
        return response
