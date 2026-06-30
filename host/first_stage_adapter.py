#!/usr/bin/env python3
"""Authorized first-stage adapter contract and deterministic simulator."""
from __future__ import annotations

import abc
import base64
import dataclasses
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from typing import Sequence

try:
    from .bridge_protocol import BridgeProcessClient, BridgeProtocolError, MAX_CHUNK_SIZE
except ImportError:
    from bridge_protocol import BridgeProcessClient, BridgeProtocolError, MAX_CHUNK_SIZE

try:
    from .boot_image import BootImageError, inspect_image, parse_int
except ImportError:
    from boot_image import BootImageError, inspect_image, parse_int

ADAPTER_ABI_VERSION = 1
MAX_ADAPTER_OUTPUT = 1024 * 1024
MAX_STATE_SIZE = 1024 * 1024
MAX_REGIONS = 32
MAX_TRANSCRIPT = 256
UINT64_MAX = (1 << 64) - 1
PERMISSIONS = frozenset("rwx")
AUTH_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class AdapterError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class MemoryRegion:
    name: str
    base: int
    size: int
    permissions: str

    @property
    def end(self) -> int:
        return self.base + self.size

    def public_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class AdapterIdentity:
    adapter_id: str
    adapter_version: int
    device: dict[str, object]
    memory_regions: tuple[MemoryRegion, ...]
    capabilities: tuple[str, ...]
    session_generation: int

    def public_dict(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "device": self.device,
            "memory_regions": [region.public_dict() for region in self.memory_regions],
            "capabilities": list(self.capabilities),
            "session_generation": self.session_generation,
        }


def _uint64(value: object, field: str) -> int:
    result = parse_int(value, field=field)
    if result > UINT64_MAX:
        raise AdapterError(f"{field} is outside uint64 range")
    return result


def validate_regions(values: object) -> tuple[MemoryRegion, ...]:
    if not isinstance(values, list) or not values or len(values) > MAX_REGIONS:
        raise AdapterError(f"memory_regions must contain 1..{MAX_REGIONS} entries")
    regions: list[MemoryRegion] = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            raise AdapterError(f"memory_regions[{index}] must be an object")
        unknown = set(value) - {"name", "base", "size", "permissions"}
        if unknown:
            raise AdapterError(f"memory_regions[{index}] has unknown fields")
        name = value.get("name")
        permissions = value.get("permissions")
        if not isinstance(name, str) or not name or len(name) > 64:
            raise AdapterError("region name must be 1..64 characters")
        if not isinstance(permissions, str) or not permissions or set(permissions) - PERMISSIONS:
            raise AdapterError("region permissions must use r, w, and x")
        permissions = "".join(letter for letter in "rwx" if letter in permissions)
        base = _uint64(value.get("base"), "region base")
        size = _uint64(value.get("size"), "region size")
        if size == 0 or base + size > UINT64_MAX + 1:
            raise AdapterError("region range overflows uint64")
        regions.append(MemoryRegion(name, base, size, permissions))
    ordered = sorted(regions, key=lambda item: (item.base, item.end))
    for previous, current in zip(ordered, ordered[1:]):
        if current.base < previous.end:
            raise AdapterError(f"memory regions overlap: {previous.name}, {current.name}")
    return tuple(ordered)


def validate_image_ranges(image: dict[str, object], regions: Sequence[MemoryRegion]) -> list[dict[str, object]]:
    manifest = image.get("manifest")
    if not isinstance(manifest, dict):
        raise AdapterError("boot image manifest is unavailable")
    components = manifest.get("components")
    if not isinstance(components, list):
        raise AdapterError("boot image component table is invalid")
    validated: list[dict[str, object]] = []
    for record in components:
        if not isinstance(record, dict):
            raise AdapterError("invalid component record")
        role = str(record.get("role", ""))
        load = _uint64(record.get("load_address", 0), f"{role} load_address")
        size = _uint64(record.get("size", 0), f"{role} size")
        entry = _uint64(record.get("entry_address", 0), f"{role} entry_address")
        if size == 0:
            raise AdapterError(f"{role} has zero size")
        # Zero means the first-stage adapter owns placement for metadata-only
        # components. Executable monitor components must always be explicit.
        if load == 0:
            if role == "monitor":
                raise AdapterError("monitor requires an explicit load address")
            validated.append({"role": role, "placement": "adapter-assigned"})
            continue
        end = load + size
        if end > UINT64_MAX + 1:
            raise AdapterError(f"{role} load range overflows uint64")
        required = "wx" if role in {"monitor", "stage0"} else "w"
        container = next((region for region in regions
                          if load >= region.base and end <= region.end
                          and all(flag in region.permissions for flag in required)), None)
        if container is None:
            raise AdapterError(f"{role} load range is outside an authorized {required} region")
        if entry and not (load <= entry < end):
            raise AdapterError(f"{role} entry address is outside its load range")
        validated.append({
            "role": role,
            "load_address": load,
            "end_address": end,
            "entry_address": entry,
            "region": container.name,
        })
    return validated


def _atomic_json(path: pathlib.Path, value: dict[str, object]) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > MAX_STATE_SIZE:
        raise AdapterError("adapter state exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as stream:
        temporary = pathlib.Path(stream.name)
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _hash_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FirstStageAdapter(abc.ABC):
    @abc.abstractmethod
    def identify(self) -> AdapterIdentity: ...
    @abc.abstractmethod
    def authorize(self, authorization_id: str) -> dict[str, object]: ...
    @abc.abstractmethod
    def verify_image(self, image: pathlib.Path) -> dict[str, object]: ...
    @abc.abstractmethod
    def upload(self, image: pathlib.Path) -> dict[str, object]: ...
    @abc.abstractmethod
    def start(self) -> dict[str, object]: ...
    @abc.abstractmethod
    def probe_stage(self, stage: str) -> dict[str, object]: ...
    @abc.abstractmethod
    def collect(self) -> dict[str, object]: ...
    @abc.abstractmethod
    def reset(self, authorization_id: str) -> dict[str, object]: ...
    def read_console(self, cursor: int = 0) -> dict[str, object]:
        return {"cursor": cursor, "next_cursor": cursor, "lines": []}
    def close(self) -> None:
        return None


class SimulatorFirstStageAdapter(FirstStageAdapter):
    """File-backed adapter used to validate authorization and recovery logic."""

    def __init__(self, state_dir: pathlib.Path, device: dict[str, object], *,
                 regions: Sequence[dict[str, object]] | None = None,
                 inject_failure: str | None = None) -> None:
        self.state_dir = state_dir.resolve()
        self.state_path = self.state_dir / "adapter-state.json"
        self.image_path = self.state_dir / "uploaded-boot.img"
        self.device = dict(device)
        self.regions = validate_regions(list(regions or [{
            "name": "simulated-monitor-window",
            "base": "0x80000000",
            "size": "0x04000000",
            "permissions": "rwx",
        }]))
        self.inject_failure = inject_failure
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._save({
                "schema_version": 1,
                "adapter_abi": ADAPTER_ABI_VERSION,
                "session_generation": 1,
                "authorized_generation": 0,
                "authorization_hash": None,
                "uploaded": None,
                "running": False,
                "reset_count": 0,
                "previous_failure": None,
                "transcript": [],
                "console": [],
            })

    def _load(self) -> dict[str, object]:
        if not self.state_path.is_file() or self.state_path.stat().st_size > MAX_STATE_SIZE:
            raise AdapterError("invalid adapter state")
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("adapter_abi") != ADAPTER_ABI_VERSION:
            raise AdapterError("unsupported adapter state")
        return value

    def _save(self, state: dict[str, object]) -> None:
        _atomic_json(self.state_path, state)

    def _record(self, operation: str, status: str, detail: str = "") -> None:
        state = self._load()
        transcript = state.setdefault("transcript", [])
        if not isinstance(transcript, list):
            raise AdapterError("invalid transcript")
        transcript.append({
            "sequence": len(transcript) + 1,
            "operation": operation,
            "status": status,
            "detail": detail[:256],
        })
        del transcript[:-MAX_TRANSCRIPT]
        self._save(state)

    def _console(self, line: str) -> None:
        state = self._load()
        console = state.setdefault("console", [])
        if not isinstance(console, list):
            raise AdapterError("invalid console state")
        console.append(str(line)[:512])
        del console[:-MAX_TRANSCRIPT]
        self._save(state)

    def _failpoint(self, operation: str) -> None:
        if self.inject_failure == operation:
            state = self._load()
            state["previous_failure"] = operation
            self._save(state)
            self._record(operation, "failed", "deterministic injected failure")
            raise AdapterError(f"injected adapter failure at {operation}")

    def _require_authorized(self) -> dict[str, object]:
        state = self._load()
        if state.get("authorized_generation") != state.get("session_generation"):
            raise AdapterError("adapter session is not authorized; authorize again after every reset")
        return state

    def identify(self) -> AdapterIdentity:
        state = self._load()
        self._record("identify", "passed")
        return AdapterIdentity(
            adapter_id="fbr34ker-simulator",
            adapter_version=ADAPTER_ABI_VERSION,
            device=self.device,
            memory_regions=self.regions,
            capabilities=("upload", "chunked-upload", "start", "console", "inventory", "timer",
                          "interrupts", "watchdog", "boot-evidence", "reset"),
            session_generation=int(state["session_generation"]),
        )

    def authorize(self, authorization_id: str) -> dict[str, object]:
        if not AUTH_PATTERN.fullmatch(authorization_id):
            raise AdapterError("authorization id must be 8..128 safe characters")
        state = self._load()
        state["authorized_generation"] = state["session_generation"]
        state["authorization_hash"] = hashlib.sha256(authorization_id.encode("utf-8")).hexdigest()
        self._save(state)
        self._record("authorize", "passed")
        return {"authorized": True, "session_generation": state["session_generation"]}

    def verify_image(self, image: pathlib.Path) -> dict[str, object]:
        self._failpoint("verify-image")
        try:
            info = inspect_image(image)
        except BootImageError as exc:
            raise AdapterError(str(exc)) from exc
        placements = validate_image_ranges(info, self.regions)
        result = {"image": info, "placements": placements}
        self._record("verify-image", "passed", str(info["sha256"]))
        return result

    def upload(self, image: pathlib.Path) -> dict[str, object]:
        state = self._require_authorized()
        self._failpoint("upload")
        verified = self.verify_image(image)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.image_path.with_suffix(".tmp")
        shutil.copyfile(image, temporary)
        if _hash_file(temporary) != verified["image"]["sha256"]:
            temporary.unlink(missing_ok=True)
            raise AdapterError("uploaded image verification failed")
        temporary.replace(self.image_path)
        state = self._load()
        state["uploaded"] = {
            "path": self.image_path.name,
            "sha256": verified["image"]["sha256"],
            "size": verified["image"]["size"],
            "family": verified["image"]["family"],
            "placements": verified["placements"],
        }
        state["running"] = False
        self._save(state)
        self._record("upload", "passed", str(verified["image"]["sha256"]))
        return dict(state["uploaded"])

    def start(self) -> dict[str, object]:
        state = self._require_authorized()
        self._failpoint("start")
        if not state.get("uploaded") or not self.image_path.is_file():
            raise AdapterError("no verified image has been uploaded")
        state["running"] = True
        self._save(state)
        self._record("start", "passed")
        self._console("FBR34KER monitor entry observed")
        return {"started": True, "entry_contract": "fbri-monitor-component"}

    def probe_stage(self, stage: str) -> dict[str, object]:
        allowed = {"console", "board-inventory", "memory-map", "timer", "interrupts",
                   "watchdog", "boot-evidence", "reboot"}
        if stage not in allowed:
            raise AdapterError(f"unknown bring-up stage: {stage}")
        state = self._require_authorized()
        if not state.get("running") and stage != "reboot":
            raise AdapterError("monitor is not running")
        self._failpoint(stage)
        details: dict[str, object] = {
            "console": {"transport": "simulated-ring", "writable": True},
            "board-inventory": {"cpid": self.device.get("cpid"), "mode": self.device.get("mode")},
            "memory-map": {"regions": [region.public_dict() for region in self.regions]},
            "timer": {"monotonic": True, "frequency_hz": 24_000_000},
            "interrupts": {"controller": "simulated", "delivery": True},
            "watchdog": {"available": True, "timeout_ms": 5000},
            "boot-evidence": {"persistent": True, "previous_failure": state.get("previous_failure")},
            "reboot": {"supported": True},
        }[stage]
        self._record(stage, "passed")
        self._console(f"bringup {stage}: passed")
        return {"stage": stage, "status": "passed", "details": details}

    def read_console(self, cursor: int = 0) -> dict[str, object]:
        if cursor < 0:
            raise AdapterError("console cursor must be non-negative")
        state = self._load()
        console = state.get("console", [])
        if not isinstance(console, list):
            raise AdapterError("invalid console state")
        cursor = min(cursor, len(console))
        return {"cursor": cursor, "next_cursor": len(console),
                "lines": [str(value) for value in console[cursor:]]}

    def collect(self) -> dict[str, object]:
        identity = self.identify().public_dict()
        state = self._load()
        return {
            "schema_version": 1,
            "adapter": identity,
            "state": state,
            "uploaded_image_present": self.image_path.is_file(),
        }

    def reset(self, authorization_id: str) -> dict[str, object]:
        # Reset itself is a mutation, so the currently active session must be
        # authorized. The new session is deliberately left unauthorized.
        if not AUTH_PATTERN.fullmatch(authorization_id):
            raise AdapterError("authorization id must be 8..128 safe characters")
        state = self._require_authorized()
        expected = hashlib.sha256(authorization_id.encode("utf-8")).hexdigest()
        if state.get("authorization_hash") != expected:
            raise AdapterError("authorization id does not match the active session")
        state["session_generation"] = int(state["session_generation"]) + 1
        state["authorized_generation"] = 0
        state["authorization_hash"] = None
        state["running"] = False
        state["reset_count"] = int(state.get("reset_count", 0)) + 1
        self._save(state)
        self._record("reset", "passed", "authorization invalidated")
        return {"reset": True, "session_generation": state["session_generation"], "authorized": False}


class CommandFirstStageAdapter(FirstStageAdapter):
    """Bounded JSON command adapter for user-supplied authorized integrations."""

    def __init__(self, command: Sequence[str], timeout: float = 30.0) -> None:
        if not command:
            raise AdapterError("adapter command is empty")
        self.command = tuple(command)
        self.timeout = timeout

    def _call(self, operation: str, **arguments: object) -> dict[str, object]:
        request = {"schema_version": 1, "adapter_abi": ADAPTER_ABI_VERSION,
                   "operation": operation, "arguments": arguments}
        try:
            result = subprocess.run(
                list(self.command), input=json.dumps(request), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AdapterError(f"adapter command failed: {exc}") from exc
        if len(result.stdout.encode("utf-8")) > MAX_ADAPTER_OUTPUT:
            raise AdapterError("adapter response exceeds size limit")
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AdapterError("adapter returned invalid JSON") from exc
        if result.returncode != 0 or not isinstance(response, dict) or not response.get("ok"):
            detail = response.get("error") if isinstance(response, dict) else result.stderr.strip()
            raise AdapterError(f"adapter operation {operation} failed: {detail}")
        value = response.get("result")
        if not isinstance(value, dict):
            raise AdapterError("adapter result must be an object")
        return value

    def identify(self) -> AdapterIdentity:
        value = self._call("identify")
        regions = validate_regions(value.get("memory_regions"))
        device = value.get("device")
        capabilities = value.get("capabilities")
        if not isinstance(device, dict) or not isinstance(capabilities, list) or not all(isinstance(x, str) for x in capabilities):
            raise AdapterError("adapter identity is invalid")
        return AdapterIdentity(str(value.get("adapter_id", "external")),
                               int(value.get("adapter_version", 0)), device, regions,
                               tuple(capabilities), int(value.get("session_generation", 0)))

    def authorize(self, authorization_id: str) -> dict[str, object]:
        return self._call("authorize", authorization_id=authorization_id)

    def verify_image(self, image: pathlib.Path) -> dict[str, object]:
        identity = self.identify()
        info = inspect_image(image)
        return {"image": info, "placements": validate_image_ranges(info, identity.memory_regions)}

    def upload(self, image: pathlib.Path) -> dict[str, object]:
        verified = self.verify_image(image)
        return self._call("upload", image_path=str(image.resolve()),
                          image_sha256=verified["image"]["sha256"],
                          image_size=verified["image"]["size"])

    def start(self) -> dict[str, object]: return self._call("start")
    def probe_stage(self, stage: str) -> dict[str, object]: return self._call("probe-stage", stage=stage)
    def read_console(self, cursor: int = 0) -> dict[str, object]:
        return self._call("console-read", cursor=cursor)
    def collect(self) -> dict[str, object]: return self._call("collect")
    def reset(self, authorization_id: str) -> dict[str, object]:
        return self._call("reset", authorization_id=authorization_id)


class BridgeFirstStageAdapter(FirstStageAdapter):
    """Persistent chunked adapter for authorized external first-stage bridges."""

    def __init__(self, command: Sequence[str], timeout: float = 30.0,
                 chunk_size: int = MAX_CHUNK_SIZE) -> None:
        if chunk_size <= 0 or chunk_size > MAX_CHUNK_SIZE:
            raise AdapterError("bridge chunk size is outside the allowed range")
        try:
            self.client = BridgeProcessClient(command, timeout=timeout)
        except BridgeProtocolError as exc:
            raise AdapterError(str(exc)) from exc
        self.chunk_size = chunk_size

    def _call(self, operation: str, **arguments: object) -> dict[str, object]:
        try:
            return self.client.request(operation, **arguments)
        except BridgeProtocolError as exc:
            raise AdapterError(f"bridge operation {operation} failed: {exc}") from exc

    def identify(self) -> AdapterIdentity:
        value = self._call("identify")
        regions = validate_regions(value.get("memory_regions"))
        device = value.get("device")
        capabilities = value.get("capabilities")
        if not isinstance(device, dict) or not isinstance(capabilities, list) or not all(isinstance(x, str) for x in capabilities):
            raise AdapterError("bridge identity is invalid")
        if "chunked-upload" not in capabilities:
            raise AdapterError("bridge does not advertise chunked-upload")
        return AdapterIdentity(str(value.get("adapter_id", "bridge")),
                               int(value.get("adapter_version", 0)), device, regions,
                               tuple(capabilities), int(value.get("session_generation", 0)))

    def authorize(self, authorization_id: str) -> dict[str, object]:
        return self._call("authorize", authorization_id=authorization_id)

    def verify_image(self, image: pathlib.Path) -> dict[str, object]:
        identity = self.identify()
        info = inspect_image(image)
        return {"image": info, "placements": validate_image_ranges(info, identity.memory_regions)}

    def upload(self, image: pathlib.Path) -> dict[str, object]:
        verified = self.verify_image(image)
        size = image.stat().st_size
        self._call("upload-begin", name=image.name, size=size,
                   sha256=verified["image"]["sha256"])
        offset = 0
        with image.open("rb") as stream:
            while True:
                chunk = stream.read(self.chunk_size)
                if not chunk:
                    break
                result = self._call("upload-chunk", offset=offset,
                                    data=base64.b64encode(chunk).decode("ascii"))
                accepted = result.get("accepted")
                if accepted != len(chunk):
                    raise AdapterError("bridge accepted an unexpected chunk length")
                offset += len(chunk)
        return self._call("upload-commit")

    def start(self) -> dict[str, object]: return self._call("start")
    def probe_stage(self, stage: str) -> dict[str, object]:
        return self._call("probe-stage", stage=stage)
    def read_console(self, cursor: int = 0) -> dict[str, object]:
        return self._call("console-read", cursor=cursor)
    def collect(self) -> dict[str, object]: return self._call("collect")
    def reset(self, authorization_id: str) -> dict[str, object]:
        return self._call("reset", authorization_id=authorization_id)
    def close(self) -> None:
        try:
            self.client.close()
        except BridgeProtocolError as exc:
            raise AdapterError(str(exc)) from exc
