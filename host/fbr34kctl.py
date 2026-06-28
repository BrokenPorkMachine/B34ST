#!/usr/bin/env python3
"""FBR34KER FMOD compiler and framed/legacy host control utility."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import pathlib
import select
import socket
import struct
import sys
import termios
import threading
import time
import tty
import zlib
import zipfile
from dataclasses import asdict, dataclass
from typing import BinaryIO, Protocol

from handoff_schema import (HandoffSchemaError, load_and_validate, write_template)
from handoff_binary import (HandoffBinaryError, inspect_blob, roundtrip_blob, write_blob)
from sdk_conformance import (SDKConformanceError, check as check_sdk_conformance,
                             format_report as format_sdk_conformance)
from loader_simulator import (LoaderSimulationError, format_report, load_report,
                              simulate_loader)
from hardware_profile import (HardwareProfileError, check_profile, format_matrix,
                              import_probe_results, load_profile, validate_profile,
                              write_profile_template)

FBR34KCTL_VERSION = "0.3.0"

FMOD_MAGIC = b"FMOD"
FMOD_FORMAT_VERSION = 1
FMOD_FLAGS_SUPPORTED = 0
FMOD_HEADER = struct.Struct("<4sHHII32s16s32s")
MAX_NAME_BYTES = 31
MAX_VERSION_BYTES = 15
MAX_CONTAINER_SIZE = 64 * 1024

BYTECODE_MAGIC = b"FBC0"
BYTECODE_VERSION_V1 = 1
BYTECODE_VERSION_V2 = 2
BYTECODE_HEADER_V1 = struct.Struct("<4sHHIII")
BYTECODE_HEADER_V2 = struct.Struct("<4sHHIIHH32sI")
BYTECODE_MAX_TEXT = 1024
BYTECODE_MAX_KEY = 23
BYTECODE_MAX_STATE_SLOTS = 8
BYTECODE_MAX_INSTRUCTION_BUDGET = 4096
BYTECODE_STACK_CAPACITY = 16

CAP_CONSOLE = 1 << 0
CAP_LOG = 1 << 1
CAP_TIME = 1 << 2
CAP_DT = 1 << 3
CAP_STATE = 1 << 4
CAP_HOST = 1 << 5
CAP_NAMES = {
    "console": CAP_CONSOLE,
    "log": CAP_LOG,
    "time": CAP_TIME,
    "dt": CAP_DT,
    "state": CAP_STATE,
    "host": CAP_HOST,
}

OP_HALT = 0x00
OP_PUSH_U64 = 0x01
OP_PRINT_TEXT = 0x02
OP_LOG_TEXT = 0x03
OP_UPTIME_MS = 0x04
OP_ADD = 0x05
OP_SUB = 0x06
OP_PRINT_U64 = 0x07
OP_DUP = 0x08
OP_MUL = 0x09
OP_AND = 0x0A
OP_OR = 0x0B
OP_XOR = 0x0C
OP_EQ = 0x0D
OP_DROP = 0x0E
OP_SWAP = 0x0F
OP_STATE_SET = 0x10
OP_STATE_GET = 0x11
OP_DT_HAS_NODE = 0x12
OP_DT_GET_U32 = 0x13
OP_LOG_KV = 0x14
OP_HOST_EVENT = 0x15

PROTOCOL_MAGIC = 0x334D461E
PROTOCOL_MAGIC_BYTES = struct.pack("<I", PROTOCOL_MAGIC)
PROTOCOL_VERSION = 1
PROTOCOL_HEADER = struct.Struct("<IBBHIII")
PROTOCOL_FLAG_ACK = 1 << 0
PROTOCOL_FLAG_ERROR = 1 << 1
PROTOCOL_FLAG_EVENT = 1 << 2
PROTOCOL_MAX_PAYLOAD = 64 * 1024
PROTOCOL_MAX_RESPONSE = 16 * 1024

MSG_PING = 0x01
MSG_HELLO = 0x02
MSG_COMMAND = 0x03
MSG_MODULE_PUT = 0x04
MSG_MODULE_RUN = 0x05
MSG_MODULE_UNLOAD = 0x06
MSG_LOG_GET = 0x07
MSG_CRASH_GET = 0x08
MSG_EVENT_GET = 0x09
MSG_REBOOT = 0x0A
MSG_HALT = 0x0B


class FBR34KCtlError(ValueError):
    """Raised for malformed input, protocol failures, or invalid arguments."""


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    version: str
    flags: int
    image_size: int
    sha256: str
    hash_valid: bool
    payload_kind: str
    capabilities: tuple[str, ...]
    code_size: int | None
    command: str | None = None
    state_slots: int = 0
    instruction_budget: int | None = None


@dataclass(frozen=True)
class ProtocolFrame:
    message_type: int
    flags: int
    sequence: int
    payload: bytes


class Endpoint(Protocol):
    def sendall(self, data: bytes) -> None: ...
    def recv(self, maximum: int, timeout: float) -> bytes: ...
    def close(self) -> None: ...


class SocketEndpoint:
    def __init__(self, connection: socket.socket):
        self.connection = connection

    @classmethod
    def unix(cls, path: pathlib.Path, timeout: float) -> "SocketEndpoint":
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.settimeout(timeout)
            connection.connect(str(path))
        except BaseException:
            connection.close()
            raise
        return cls(connection)

    @classmethod
    def tcp(cls, address: str, timeout: float) -> "SocketEndpoint":
        if ":" not in address:
            raise FBR34KCtlError("TCP endpoint must be HOST:PORT")
        host, port_text = address.rsplit(":", 1)
        try:
            port = int(port_text)
        except ValueError as exc:
            raise FBR34KCtlError("TCP port is not an integer") from exc
        if not 1 <= port <= 65535:
            raise FBR34KCtlError("TCP port must be between 1 and 65535")
        return cls(socket.create_connection((host, port), timeout=timeout))

    def sendall(self, data: bytes) -> None:
        self.connection.sendall(data)

    def recv(self, maximum: int, timeout: float) -> bytes:
        self.connection.settimeout(timeout)
        try:
            data = self.connection.recv(maximum)
        except socket.timeout:
            return b""
        if data == b"":
            raise FBR34KCtlError("endpoint closed")
        return data

    def close(self) -> None:
        self.connection.close()


class SerialEndpoint:
    def __init__(self, path: pathlib.Path, baud: int):
        self.file_descriptor = os.open(
            path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK
        )
        try:
            attributes = termios.tcgetattr(self.file_descriptor)
            attributes[0] = 0
            attributes[1] = 0
            attributes[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
            attributes[3] = 0
            attributes[6][termios.VMIN] = 0
            attributes[6][termios.VTIME] = 0
            speed = getattr(termios, f"B{baud}", None)
            if speed is None:
                raise FBR34KCtlError(f"unsupported serial baud rate {baud}")
            attributes[4] = speed
            attributes[5] = speed
            termios.tcsetattr(self.file_descriptor, termios.TCSANOW, attributes)
        except BaseException:
            os.close(self.file_descriptor)
            raise

    def sendall(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            _, writable, _ = select.select([], [self.file_descriptor], [], 1.0)
            if not writable:
                raise FBR34KCtlError("serial write timed out")
            written = os.write(self.file_descriptor, view)
            if written <= 0:
                raise FBR34KCtlError("serial endpoint made no write progress")
            view = view[written:]

    def recv(self, maximum: int, timeout: float) -> bytes:
        readable, _, _ = select.select(
            [self.file_descriptor], [], [], max(timeout, 0.0)
        )
        if not readable:
            return b""
        try:
            return os.read(self.file_descriptor, maximum)
        except BlockingIOError:
            return b""

    def close(self) -> None:
        os.close(self.file_descriptor)


def _ascii_wire_text(value: str, field: str, maximum: int) -> bytes:
    if not value:
        raise FBR34KCtlError(f"{field} cannot be empty")
    if "\n" in value or "\r" in value:
        raise FBR34KCtlError(f"{field} must be one line")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise FBR34KCtlError(f"{field} must use ASCII") from exc
    if len(encoded) > maximum:
        raise FBR34KCtlError(f"{field} exceeds {maximum} bytes")
    return encoded


def _positive_float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not result > 0.0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def _positive_int(value: str) -> int:
    try:
        result = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def _identifier_bytes(
    value: str, maximum: int, field: str, *, allow_empty: bool = False
) -> bytes:
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise FBR34KCtlError(f"{field} must use ASCII identifier characters") from exc
    if not encoded and not allow_empty:
        raise FBR34KCtlError(f"{field} cannot be empty")
    if len(encoded) > maximum:
        raise FBR34KCtlError(f"{field} exceeds {maximum} bytes")
    allowed = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-+"
    if any(character not in allowed for character in encoded):
        raise FBR34KCtlError(
            f"{field} may contain only letters, digits, '.', '_', '-', and '+'"
        )
    return encoded + b"\0" * (maximum + 1 - len(encoded))


def _decode_identifier(value: bytes, field: str, *, allow_empty: bool = False) -> str:
    raw = value.split(b"\0", 1)[0]
    if not raw and not allow_empty:
        raise FBR34KCtlError(f"{field} cannot be empty")
    try:
        decoded = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise FBR34KCtlError(f"{field} is not valid ASCII") from exc
    if decoded:
        _identifier_bytes(decoded, len(value) - 1, field)
    return decoded


def _capability_names(mask: int) -> tuple[str, ...]:
    names = tuple(name for name, bit in CAP_NAMES.items() if mask & bit)
    known = 0
    for bit in CAP_NAMES.values():
        known |= bit
    if mask & ~known:
        names += (f"unknown:0x{mask & ~known:x}",)
    return names


def _parse_capabilities(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise FBR34KCtlError("capabilities must be a list of names")
    result = 0
    for name in value:
        if name not in CAP_NAMES:
            raise FBR34KCtlError(f"unknown capability {name!r}")
        result |= CAP_NAMES[name]
    return result


def _encode_inline(opcode: int, value: object, field: str, *, key: bool = False) -> bytes:
    if not isinstance(value, str):
        raise FBR34KCtlError(f"{field} must be a string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise FBR34KCtlError(f"{field} is not valid UTF-8") from exc
    maximum = BYTECODE_MAX_KEY if key else BYTECODE_MAX_TEXT
    if not encoded or len(encoded) > maximum:
        raise FBR34KCtlError(f"{field} must contain 1..{maximum} bytes")
    if key:
        allowed = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        if any(character not in allowed for character in encoded):
            raise FBR34KCtlError(f"{field} contains invalid key characters")
    elif any(
        character == 0
        or (character < 0x20 and character not in (0x09, 0x0A, 0x0D))
        for character in encoded
    ):
        raise FBR34KCtlError(f"{field} contains a disallowed control character")
    return bytes([opcode]) + struct.pack("<H", len(encoded)) + encoded


def compile_bytecode(specification: dict[str, object]) -> tuple[bytes, int]:
    program = specification.get("program")
    if not isinstance(program, list) or not program:
        raise FBR34KCtlError("module specification requires a non-empty program")
    if len(program) > BYTECODE_MAX_INSTRUCTION_BUDGET:
        raise FBR34KCtlError("program exceeds instruction budget")

    output = bytearray()
    inferred = 0
    halted = False
    stack_depth = 0
    uses_state = False

    def require_stack(count: int, index: int) -> None:
        nonlocal stack_depth
        if stack_depth < count:
            raise FBR34KCtlError(f"program[{index}] underflows the value stack")

    def push_stack(index: int) -> None:
        nonlocal stack_depth
        if stack_depth >= BYTECODE_STACK_CAPACITY:
            raise FBR34KCtlError(f"program[{index}] overflows the value stack")
        stack_depth += 1

    for index, item in enumerate(program):
        if not isinstance(item, dict) or not isinstance(item.get("op"), str):
            raise FBR34KCtlError(f"program[{index}] requires a string op")
        op = item["op"]
        if halted:
            raise FBR34KCtlError("instructions cannot appear after halt")
        if op == "halt":
            output.append(OP_HALT)
            halted = True
        elif op == "push":
            value = item.get("value")
            if not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
                raise FBR34KCtlError("push.value must be an unsigned 64-bit integer")
            push_stack(index)
            output += bytes([OP_PUSH_U64]) + struct.pack("<Q", value)
        elif op == "print":
            output += _encode_inline(OP_PRINT_TEXT, item.get("text"), "print.text")
            inferred |= CAP_CONSOLE
        elif op == "log":
            output += _encode_inline(OP_LOG_TEXT, item.get("text"), "log.text")
            inferred |= CAP_LOG
        elif op == "event":
            output += _encode_inline(OP_HOST_EVENT, item.get("text"), "event.text")
            inferred |= CAP_HOST
        elif op == "uptime":
            push_stack(index)
            output.append(OP_UPTIME_MS)
            inferred |= CAP_TIME
        elif op in {"add", "sub", "mul", "and", "or", "xor", "eq"}:
            require_stack(2, index)
            stack_depth -= 1
            output.append({
                "add": OP_ADD, "sub": OP_SUB, "mul": OP_MUL,
                "and": OP_AND, "or": OP_OR, "xor": OP_XOR, "eq": OP_EQ,
            }[op])
        elif op == "print_u64":
            require_stack(1, index)
            stack_depth -= 1
            output.append(OP_PRINT_U64)
            inferred |= CAP_CONSOLE
        elif op == "dup":
            require_stack(1, index)
            push_stack(index)
            output.append(OP_DUP)
        elif op == "drop":
            require_stack(1, index)
            stack_depth -= 1
            output.append(OP_DROP)
        elif op == "swap":
            require_stack(2, index)
            output.append(OP_SWAP)
        elif op == "state_set":
            require_stack(1, index)
            stack_depth -= 1
            output += _encode_inline(
                OP_STATE_SET, item.get("key"), "state_set.key", key=True
            )
            inferred |= CAP_STATE
            uses_state = True
        elif op == "state_get":
            push_stack(index)
            output += _encode_inline(
                OP_STATE_GET, item.get("key"), "state_get.key", key=True
            )
            inferred |= CAP_STATE
            uses_state = True
        elif op == "dt_has_node":
            push_stack(index)
            output += _encode_inline(
                OP_DT_HAS_NODE, item.get("path"), "dt_has_node.path"
            )
            inferred |= CAP_DT
        elif op == "dt_get_u32":
            push_stack(index)
            output += _encode_inline(
                OP_DT_GET_U32, item.get("path"), "dt_get_u32.path"
            )
            output += _encode_inline(
                0, item.get("property"), "dt_get_u32.property", key=True
            )[1:]
            inferred |= CAP_DT
        elif op == "log_kv":
            require_stack(1, index)
            stack_depth -= 1
            output += _encode_inline(OP_LOG_KV, item.get("key"), "log_kv.key", key=True)
            inferred |= CAP_LOG
        else:
            raise FBR34KCtlError(f"unsupported operation {op!r}")

    if not halted:
        output.append(OP_HALT)

    declared = _parse_capabilities(specification.get("capabilities"))
    capabilities = inferred if declared is None else declared
    if inferred & ~capabilities:
        missing = ", ".join(_capability_names(inferred & ~capabilities))
        raise FBR34KCtlError(f"declared capabilities omit required: {missing}")

    command_value = specification.get("command", "")
    if not isinstance(command_value, str):
        raise FBR34KCtlError("command must be a string")
    command = _identifier_bytes(
        command_value, 31, "command", allow_empty=True
    )
    state_slots_value = specification.get("state_slots", 4 if uses_state else 0)
    if not isinstance(state_slots_value, int) or not 0 <= state_slots_value <= BYTECODE_MAX_STATE_SLOTS:
        raise FBR34KCtlError("state_slots must be between 0 and 8")
    if uses_state and state_slots_value == 0:
        raise FBR34KCtlError("state operations require at least one state slot")
    if capabilities & CAP_STATE and state_slots_value == 0:
        raise FBR34KCtlError("the state capability requires at least one state slot")
    budget = specification.get("instruction_budget", BYTECODE_MAX_INSTRUCTION_BUDGET)
    if not isinstance(budget, int) or not 1 <= budget <= BYTECODE_MAX_INSTRUCTION_BUDGET:
        raise FBR34KCtlError("instruction_budget must be between 1 and 4096")
    instruction_count = len(program) + (0 if halted else 1)
    if instruction_count > budget:
        raise FBR34KCtlError(
            f"instruction_budget {budget} is smaller than the {instruction_count} "
            "instructions emitted"
        )

    header = BYTECODE_HEADER_V2.pack(
        BYTECODE_MAGIC,
        BYTECODE_VERSION_V2,
        BYTECODE_HEADER_V2.size,
        len(output),
        capabilities,
        state_slots_value,
        0,
        command,
        budget,
    )
    return header + output, capabilities


def pack_module_bytes(
    payload: bytes,
    output_path: pathlib.Path,
    name: str,
    version: str,
    flags: int = 0,
) -> ModuleInfo:
    if not isinstance(flags, int) or not 0 <= flags <= 0xFFFFFFFF:
        raise FBR34KCtlError("flags must be an unsigned 32-bit integer")
    if flags & ~FMOD_FLAGS_SUPPORTED:
        raise FBR34KCtlError(f"unsupported FMOD flags 0x{flags:x}")
    digest = hashlib.sha256(payload).digest()
    header = FMOD_HEADER.pack(
        FMOD_MAGIC,
        FMOD_FORMAT_VERSION,
        FMOD_HEADER.size,
        len(payload),
        flags,
        _identifier_bytes(name, MAX_NAME_BYTES, "name"),
        _identifier_bytes(version, MAX_VERSION_BYTES, "version"),
        digest,
    )
    container = header + payload
    if len(container) > MAX_CONTAINER_SIZE:
        raise FBR34KCtlError(f"FMOD container exceeds {MAX_CONTAINER_SIZE} bytes")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(container)
    return inspect_module(output_path)


def pack_module(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    name: str,
    version: str,
    flags: int = 0,
) -> ModuleInfo:
    return pack_module_bytes(input_path.read_bytes(), output_path, name, version, flags)


def compile_module(specification_path: pathlib.Path, output_path: pathlib.Path) -> ModuleInfo:
    try:
        specification = json.loads(specification_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FBR34KCtlError(f"unable to read module specification: {exc}") from exc
    if not isinstance(specification, dict):
        raise FBR34KCtlError("module specification must be a JSON object")
    name = specification.get("name")
    version = specification.get("version")
    flags = specification.get("flags", 0)
    if not isinstance(name, str) or not isinstance(version, str):
        raise FBR34KCtlError("module specification requires string name and version")
    if not isinstance(flags, int) or not 0 <= flags <= 0xFFFFFFFF:
        raise FBR34KCtlError("flags must be an unsigned 32-bit integer")
    if flags & ~FMOD_FLAGS_SUPPORTED:
        raise FBR34KCtlError(f"unsupported FMOD flags 0x{flags:x}")
    payload, _ = compile_bytecode(specification)
    return pack_module_bytes(payload, output_path, name, version, flags)


def inspect_module(path: pathlib.Path) -> ModuleInfo:
    try:
        size_on_disk = path.stat().st_size
    except OSError as exc:
        raise FBR34KCtlError(f"unable to stat FMOD: {exc}") from exc
    if size_on_disk > MAX_CONTAINER_SIZE:
        raise FBR34KCtlError(f"FMOD container exceeds {MAX_CONTAINER_SIZE} bytes")
    data = path.read_bytes()
    if len(data) < FMOD_HEADER.size:
        raise FBR34KCtlError("file is smaller than an FMOD header")
    (
        magic, format_version, header_size, image_size, flags,
        name_raw, version_raw, expected_digest,
    ) = FMOD_HEADER.unpack_from(data)
    if magic != FMOD_MAGIC or format_version != FMOD_FORMAT_VERSION:
        raise FBR34KCtlError("unsupported FMOD container")
    if flags & ~FMOD_FLAGS_SUPPORTED:
        raise FBR34KCtlError(f"unsupported FMOD flags 0x{flags:x}")
    if header_size != FMOD_HEADER.size or image_size != len(data) - header_size:
        raise FBR34KCtlError("FMOD size fields are inconsistent")
    payload = data[header_size:]
    actual_digest = hashlib.sha256(payload).digest()
    payload_kind = "opaque"
    capabilities: tuple[str, ...] = ()
    code_size: int | None = None
    command: str | None = None
    state_slots = 0
    instruction_budget: int | None = None
    if len(payload) >= BYTECODE_HEADER_V1.size and payload[:4] == BYTECODE_MAGIC:
        version = struct.unpack_from("<H", payload, 4)[0]
        if version == BYTECODE_VERSION_V1:
            magic2, version2, size2, code2, caps2, reserved = BYTECODE_HEADER_V1.unpack_from(payload)
            if size2 == BYTECODE_HEADER_V1.size and reserved == 0 and code2 == len(payload) - size2:
                payload_kind = "FMBC-v1"
                capabilities = _capability_names(caps2)
                code_size = code2
                instruction_budget = BYTECODE_MAX_INSTRUCTION_BUDGET
            else:
                payload_kind = "malformed-FMBC"
        elif version == BYTECODE_VERSION_V2 and len(payload) >= BYTECODE_HEADER_V2.size:
            (
                magic2, version2, size2, code2, caps2, state_slots,
                reserved, command_raw, instruction_budget,
            ) = BYTECODE_HEADER_V2.unpack_from(payload)
            if (
                size2 == BYTECODE_HEADER_V2.size
                and reserved == 0
                and code2 == len(payload) - size2
                and state_slots <= BYTECODE_MAX_STATE_SLOTS
                and 1 <= instruction_budget <= BYTECODE_MAX_INSTRUCTION_BUDGET
            ):
                payload_kind = "FMBC-v2"
                capabilities = _capability_names(caps2)
                code_size = code2
                command = _decode_identifier(command_raw, "command", allow_empty=True) or None
            else:
                payload_kind = "malformed-FMBC"
        else:
            payload_kind = f"FMBC-v{version}"
    return ModuleInfo(
        _decode_identifier(name_raw, "name"),
        _decode_identifier(version_raw, "version"),
        flags,
        image_size,
        expected_digest.hex(),
        actual_digest == expected_digest,
        payload_kind,
        capabilities,
        code_size,
        command,
        state_slots,
        instruction_budget,
    )


def file_manifest(path: pathlib.Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {"file": path.name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def encode_frame(message_type: int, sequence: int, payload: bytes = b"") -> bytes:
    if not 0 <= message_type <= 0x7F:
        raise FBR34KCtlError("request message type is out of range")
    if len(payload) > PROTOCOL_MAX_PAYLOAD:
        raise FBR34KCtlError("protocol payload exceeds monitor limit")
    prefix = PROTOCOL_HEADER.pack(
        PROTOCOL_MAGIC, PROTOCOL_VERSION, message_type, 0,
        sequence & 0xFFFFFFFF, len(payload), 0,
    )
    checksum = zlib.crc32(prefix[:16] + payload) & 0xFFFFFFFF
    return prefix[:16] + struct.pack("<I", checksum) + payload


def decode_frame(data: bytes) -> ProtocolFrame:
    if len(data) < PROTOCOL_HEADER.size:
        raise FBR34KCtlError("truncated protocol frame")
    magic, version, message_type, flags, sequence, length, checksum = PROTOCOL_HEADER.unpack_from(data)
    if magic != PROTOCOL_MAGIC or version != PROTOCOL_VERSION:
        raise FBR34KCtlError("invalid protocol header")
    if length > PROTOCOL_MAX_PAYLOAD or len(data) != PROTOCOL_HEADER.size + length:
        raise FBR34KCtlError("invalid protocol payload length")
    payload = data[PROTOCOL_HEADER.size:]
    actual = zlib.crc32(data[:16] + payload) & 0xFFFFFFFF
    if actual != checksum:
        raise FBR34KCtlError("protocol CRC-32 mismatch")
    return ProtocolFrame(message_type, flags, sequence, payload)


class FramedClient:
    def __init__(self, endpoint: Endpoint, *, timeout: float = 10.0, retries: int = 3):
        self.endpoint = endpoint
        self.timeout = timeout
        self.retries = retries
        self.sequence = int(time.monotonic_ns()) & 0xFFFFFFFF
        self.buffer = bytearray()

    def _next_sequence(self) -> int:
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        return self.sequence

    def _receive(self, expected_type: int, sequence: int, timeout: float) -> ProtocolFrame:
        deadline = time.monotonic() + timeout
        while True:
            marker = self.buffer.find(PROTOCOL_MAGIC_BYTES)
            if marker >= 0:
                if marker:
                    del self.buffer[:marker]
                if len(self.buffer) >= PROTOCOL_HEADER.size:
                    _, version, message_type, _, frame_sequence, length, _ = PROTOCOL_HEADER.unpack_from(self.buffer)
                    if version != PROTOCOL_VERSION or length > PROTOCOL_MAX_RESPONSE:
                        del self.buffer[0]
                        continue
                    total = PROTOCOL_HEADER.size + length
                    if len(self.buffer) >= total:
                        raw = bytes(self.buffer[:total])
                        del self.buffer[:total]
                        frame = decode_frame(raw)
                        if frame.sequence != sequence or frame.message_type != (expected_type | 0x80):
                            continue
                        return frame
            elif len(self.buffer) > 3:
                del self.buffer[:-3]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FBR34KCtlError("timed out waiting for framed response")
            chunk = self.endpoint.recv(4096, min(remaining, 0.25))
            if chunk:
                self.buffer += chunk

    def request(self, message_type: int, payload: bytes = b"") -> bytes:
        sequence = self._next_sequence()
        frame = encode_frame(message_type, sequence, payload)
        last_error: FBR34KCtlError | None = None
        for _attempt in range(self.retries):
            self.endpoint.sendall(frame)
            try:
                response = self._receive(message_type, sequence, self.timeout)
            except FBR34KCtlError as exc:
                last_error = exc
                continue
            if not response.flags & PROTOCOL_FLAG_ACK:
                raise FBR34KCtlError("response did not acknowledge request")
            if response.flags & PROTOCOL_FLAG_ERROR:
                detail = response.payload.decode("utf-8", errors="replace").strip()
                raise FBR34KCtlError(detail or "monitor rejected request")
            return response.payload
        raise last_error or FBR34KCtlError("framed request failed")

    def hello(self) -> bytes:
        return self.request(MSG_HELLO)

    def command(self, command: str) -> bytes:
        return self.request(MSG_COMMAND, _ascii_wire_text(command, "command", 159))

    def upload(self, data: bytes) -> bytes:
        return self.request(MSG_MODULE_PUT, data)

    def module_run(self, name: str) -> bytes:
        return self.request(MSG_MODULE_RUN, _ascii_wire_text(name, "module name", 31))

    def module_unload(self, name: str) -> bytes:
        return self.request(MSG_MODULE_UNLOAD, _ascii_wire_text(name, "module name", 31))

    def logs(self) -> bytes:
        return self.request(MSG_LOG_GET)

    def crash(self) -> bytes:
        return self.request(MSG_CRASH_GET)

    def events(self) -> bytes:
        return self.request(MSG_EVENT_GET)

    def reboot(self) -> bytes:
        return self.request(MSG_REBOOT)

    def halt(self) -> bytes:
        return self.request(MSG_HALT)


def read_until(endpoint: Endpoint, marker: bytes, timeout: float, *, limit: int = 1024 * 1024) -> bytes:
    deadline = time.monotonic() + timeout
    buffer = bytearray()
    while marker not in buffer:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FBR34KCtlError(f"timed out waiting for {marker!r}")
        chunk = endpoint.recv(4096, min(remaining, 0.25))
        if chunk:
            buffer += chunk
        if len(buffer) > limit:
            raise FBR34KCtlError("monitor response exceeded safety limit")
    return bytes(buffer)


MONITOR_PROMPTS = (b"fbr34ker> ", b"fbr34ker(bringup)> ", b"fbr34ker(probe)> ")


def read_until_prompt(endpoint: Endpoint, timeout: float, *, limit: int = 1024 * 1024) -> bytes:
    deadline = time.monotonic() + timeout
    buffer = bytearray()
    while not any(prompt in buffer for prompt in MONITOR_PROMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FBR34KCtlError("timed out waiting for a FBR34KER prompt")
        chunk = endpoint.recv(4096, min(remaining, 0.25))
        if chunk:
            buffer += chunk
        if len(buffer) > limit:
            raise FBR34KCtlError("monitor response exceeded safety limit")
    return bytes(buffer)


def send_command(endpoint: Endpoint, command: str, timeout: float = 5.0) -> bytes:
    if "\n" in command or "\r" in command:
        raise FBR34KCtlError("command must be a single line")
    endpoint.sendall(command.encode("utf-8") + b"\n")
    return read_until_prompt(endpoint, timeout)


def upload_module(
    endpoint: Endpoint,
    path: pathlib.Path,
    *,
    run: bool = False,
    timeout: float = 10.0,
    legacy: bool = False,
) -> bytes:
    data = path.read_bytes()
    information = inspect_module(path)
    if not information.hash_valid:
        raise FBR34KCtlError("refusing to upload an FMOD with an invalid hash")
    if information.payload_kind not in {"FMBC-v1", "FMBC-v2"}:
        raise FBR34KCtlError("monitor only executes validated FMBC payloads")
    if legacy:
        endpoint.sendall(f"module-load {len(data)}\n".encode("ascii"))
        ready = read_until(endpoint, f"FMOD-READY {len(data)}".encode("ascii"), timeout)
        endpoint.sendall(data)
        result = read_until_prompt(endpoint, timeout)
        if b"FMOD-RESULT OK " not in result:
            raise FBR34KCtlError(result.decode("utf-8", errors="replace").strip())
        transcript = ready + result
        if run:
            transcript += send_command(endpoint, f"module-run {information.name}", timeout)
        return transcript
    client = FramedClient(endpoint, timeout=timeout)
    transcript = client.upload(data)
    if run:
        transcript += client.module_run(information.name)
    return transcript


def _open_endpoint(arguments: argparse.Namespace) -> Endpoint:
    if arguments.unix is not None:
        return SocketEndpoint.unix(arguments.unix, arguments.timeout)
    if arguments.tcp is not None:
        return SocketEndpoint.tcp(arguments.tcp, arguments.timeout)
    if arguments.device is not None:
        return SerialEndpoint(arguments.device, arguments.baud)
    raise FBR34KCtlError("an endpoint is required")


def _add_endpoint_arguments(parser: argparse.ArgumentParser, *, legacy: bool = False) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--unix", type=pathlib.Path, help="QEMU UNIX serial socket")
    group.add_argument("--tcp", help="TCP serial endpoint as HOST:PORT")
    group.add_argument("--device", type=pathlib.Path, help="serial device path")
    parser.add_argument("--baud", type=_positive_int, default=115200)
    parser.add_argument("--timeout", type=_positive_float, default=10.0)
    if legacy:
        parser.add_argument("--legacy", action="store_true", help="use the v0.2 line protocol")


def interactive_console(endpoint: Endpoint) -> None:
    stop = threading.Event()

    def reader() -> None:
        while not stop.is_set():
            chunk = endpoint.recv(4096, 0.2)
            if chunk:
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    input_fd = sys.stdin.fileno()
    try:
        with _raw_terminal(input_fd):
            while True:
                chunk = os.read(input_fd, 1024)
                if not chunk or chunk == b"\x1d":
                    break
                endpoint.sendall(chunk)
    finally:
        stop.set()
        thread.join(timeout=1.0)


@contextlib.contextmanager
def _raw_terminal(file_descriptor: int):
    if not os.isatty(file_descriptor):
        yield
        return
    previous = termios.tcgetattr(file_descriptor)
    try:
        tty.setraw(file_descriptor)
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, previous)


def _print_json(value: object, output: BinaryIO = sys.stdout) -> None:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    output.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _archive_directory(output: pathlib.Path) -> pathlib.Path:
    archive = output.with_suffix(".zip")
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as bundle:
        for path in sorted(output.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                            compresslevel=9)
    temporary.replace(archive)
    return archive


def collect_hardware_diagnostics(
    client: FramedClient,
    output: pathlib.Path,
    *,
    create_archive: bool = True,
) -> dict[str, object]:
    """Collect read-only platform metadata and text diagnostics.

    The bundle intentionally excludes physical-memory contents and arbitrary
    address reads. Defensive-mode diagnostics never run IRQ, watchdog,
    framebuffer, power, or module mutations. Individual failures are recorded
    instead of aborting the remaining collection.
    """
    output.mkdir(parents=True, exist_ok=True)
    requests = (
        ("platform-info", lambda: client.command("platform-info")),
        ("exception-level", lambda: client.command("exception-level")),
        ("system-registers", lambda: client.command("system-registers")),
        ("handoff-info", lambda: client.command("handoff-info")),
        ("boot-modules", lambda: client.command("boot-modules")),
        ("probe-status", lambda: client.command("probe-status")),
        ("compatibility", lambda: client.command("compatibility")),
        ("services", lambda: client.command("services")),
        ("service-health", lambda: client.command("service-health")),
        ("console-services", lambda: client.command("console-services")),
        ("console-transports", lambda: client.command("console-transports")),
        ("memory-map", lambda: client.command("memory-map")),
        ("memory-check", lambda: client.command("memory-check")),
        ("device-tree-summary", lambda: client.command("device-tree-summary")),
        ("device-tree-stdout", lambda: client.command("dt-stdout")),
        ("timer-frequency", lambda: client.command("timer-frequency")),
        ("timer-test", lambda: client.command("timer-test 10")),
        ("console-history", lambda: client.command("console-history")),
        ("irq-controller", lambda: client.command("irq-controller")),
        ("watchdog-services", lambda: client.command("watchdog-services")),
        ("framebuffer-info", lambda: client.command("framebuffer-info")),
        ("logs", client.logs),
        ("crash", client.crash),
    )
    records: list[dict[str, object]] = []
    for name, action in requests:
        status = "supported"
        try:
            payload = action()
        except FBR34KCtlError as exc:
            status = "unsupported"
            payload = (f"{exc}\n").encode("utf-8", errors="replace")
        path = output / f"{name}.txt"
        path.write_bytes(payload)
        records.append({
            "name": name,
            "status": status,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    summary = {
        "schema_version": 1,
        "project": "FBR34KER",
        "version": FBR34KCTL_VERSION,
        "sensitive_memory_included": False,
        "mutation_tests_executed": False,
        "records": records,
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    archive = _archive_directory(output) if create_archive else None
    result: dict[str, object] = {"output": str(output), **summary}
    if archive is not None:
        result["archive"] = str(archive)
    return result


def record_probe_session(
    endpoint: Endpoint,
    output: pathlib.Path,
    *,
    duration: float,
    timeout: float,
    profile_path: pathlib.Path | None = None,
) -> dict[str, object]:
    """Capture bounded boot output, then collect read-only framed diagnostics."""
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + duration
    raw = bytearray()
    while time.monotonic() < deadline and len(raw) < 1024 * 1024:
        remaining = deadline - time.monotonic()
        chunk = endpoint.recv(4096, min(max(remaining, 0.0), 0.25))
        if chunk:
            raw += chunk
    raw_path = output / "boot-transcript.raw"
    decoded_path = output / "boot-transcript.txt"
    raw_path.write_bytes(bytes(raw))
    decoded_path.write_text(raw.decode("utf-8", errors="replace"), encoding="utf-8")

    client = FramedClient(endpoint, timeout=timeout)
    result = collect_hardware_diagnostics(client, output, create_archive=False)
    result["boot_capture_seconds"] = duration
    result["boot_transcript_bytes"] = len(raw)

    if profile_path is not None:
        profile = load_profile(profile_path)
        report = check_profile(profile, output)
        compatibility_json = output / "compatibility-profile.json"
        compatibility_text = output / "compatibility-profile.txt"
        compatibility_json.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        compatibility_text.write_text(format_matrix(report), encoding="utf-8")
        result["profile"] = profile["name"]
        result["profile_result"] = report["result"]

    session = {
        "schema_version": 1,
        "project": "FBR34KER",
        "version": FBR34KCTL_VERSION,
        "sensitive_memory_included": False,
        "mutation_tests_executed": False,
        "boot_capture_seconds": duration,
        "boot_transcript_bytes": len(raw),
        "profile": result.get("profile"),
        "profile_result": result.get("profile_result"),
    }
    (output / "probe-session.json").write_text(
        json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    archive = _archive_directory(output)
    result["archive"] = str(archive)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fbr34kctl")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {FBR34KCTL_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile-module", help="compile JSON FMBC v2 into FMOD")
    compile_parser.add_argument("specification", type=pathlib.Path)
    compile_parser.add_argument("output", type=pathlib.Path)

    pack = subparsers.add_parser("pack-module", help="wrap an opaque payload in FMOD")
    pack.add_argument("input", type=pathlib.Path)
    pack.add_argument("output", type=pathlib.Path)
    pack.add_argument("--name", required=True)
    pack.add_argument("--version", required=True)
    pack.add_argument("--flags", type=lambda value: int(value, 0), default=0)

    inspect_parser = subparsers.add_parser("inspect-module", help="inspect FMOD")
    inspect_parser.add_argument("input", type=pathlib.Path)
    manifest = subparsers.add_parser("manifest", help="hash a monitor image")
    manifest.add_argument("input", type=pathlib.Path)

    handoff_template = subparsers.add_parser(
        "handoff-template", help="write a hardware-neutral handoff-v4 JSON template")
    handoff_template.add_argument("output", type=pathlib.Path)
    handoff_validate = subparsers.add_parser(
        "handoff-validate", help="validate and normalize a handoff-v4 JSON document")
    handoff_validate.add_argument("input", type=pathlib.Path)
    handoff_validate.add_argument("--output", type=pathlib.Path)
    handoff_build = subparsers.add_parser(
        "handoff-build", help="compile handoff JSON into a relocatable FBHB binary")
    handoff_build.add_argument("input", type=pathlib.Path)
    handoff_build.add_argument("output", type=pathlib.Path)
    handoff_inspect = subparsers.add_parser(
        "handoff-inspect", help="validate and inspect a relocatable FBHB binary")
    handoff_inspect.add_argument("input", type=pathlib.Path)
    handoff_roundtrip = subparsers.add_parser(
        "handoff-roundtrip", help="rebuild an FBHB binary and verify deterministic equality")
    handoff_roundtrip.add_argument("input", type=pathlib.Path)

    loader_conformance = subparsers.add_parser(
        "loader-conformance", help="certify an FBHB design against memory and board contracts")
    loader_conformance.add_argument("--handoff", type=pathlib.Path, required=True)
    loader_conformance.add_argument("--memory-map", type=pathlib.Path)
    loader_conformance.add_argument("--profile", type=pathlib.Path)
    loader_conformance.add_argument("--report", type=pathlib.Path)

    loader_simulate = subparsers.add_parser(
        "loader-simulate", help="construct an offline sparse-memory handoff-v4 loader plan")
    loader_simulate.add_argument("handoff", type=pathlib.Path)
    loader_simulate.add_argument("--image", type=pathlib.Path,
                                 default=pathlib.Path("build-generic/fbr34ker-generic.elf"))
    loader_simulate.add_argument("--output", type=pathlib.Path,
                                 default=pathlib.Path("loader-simulation"))
    loader_simulate.add_argument("--dtb", type=pathlib.Path)
    loader_simulate.add_argument("--module", type=pathlib.Path, action="append", default=[])

    loader_check = subparsers.add_parser(
        "loader-check", help="run the handoff conformance suite and print its status")
    loader_check.add_argument("handoff", type=pathlib.Path)
    loader_check.add_argument("--image", type=pathlib.Path,
                              default=pathlib.Path("build-generic/fbr34ker-generic.elf"))
    loader_check.add_argument("--output", type=pathlib.Path,
                              default=pathlib.Path("loader-conformance"))
    loader_check.add_argument("--dtb", type=pathlib.Path)
    loader_check.add_argument("--module", type=pathlib.Path, action="append", default=[])

    loader_report = subparsers.add_parser(
        "loader-report", help="format a machine-readable loader conformance report")
    loader_report.add_argument("input", type=pathlib.Path)

    hardware_diagnostics = subparsers.add_parser(
        "hardware-diagnostics", help="collect a safe loader/platform diagnostics bundle")
    _add_endpoint_arguments(hardware_diagnostics)
    hardware_diagnostics.add_argument("--output", type=pathlib.Path,
                                      default=pathlib.Path("hardware-diagnostics"))

    profile_template = subparsers.add_parser(
        "profile-template", help="write an ARM64 physical-hardware profile template")
    profile_template.add_argument("output", type=pathlib.Path)

    profile_validate = subparsers.add_parser(
        "profile-validate", help="validate and normalize a hardware profile")
    profile_validate.add_argument("input", type=pathlib.Path)
    profile_validate.add_argument("--output", type=pathlib.Path)

    profile_check = subparsers.add_parser(
        "profile-check", help="compare a profile with a hardware diagnostics directory")
    profile_check.add_argument("profile", type=pathlib.Path)
    profile_check.add_argument("diagnostics", type=pathlib.Path)
    profile_check.add_argument("--output", type=pathlib.Path)

    profile_report = subparsers.add_parser(
        "profile-report", help="format a machine-readable compatibility matrix")
    profile_report.add_argument("input", type=pathlib.Path)
    profile_import = subparsers.add_parser(
        "profile-import", help="attach conservative probe observations to a board profile")
    profile_import.add_argument("profile", type=pathlib.Path)
    profile_import.add_argument("diagnostics", type=pathlib.Path)
    profile_import.add_argument("--output", type=pathlib.Path, required=True)

    probe_record = subparsers.add_parser(
        "probe-record", help="capture bounded boot output and read-only probe diagnostics")
    _add_endpoint_arguments(probe_record)
    probe_record.add_argument("--output", type=pathlib.Path,
                              default=pathlib.Path("hardware-probe-session"))
    probe_record.add_argument("--duration", type=_positive_float, default=30.0)
    probe_record.add_argument("--profile", type=pathlib.Path)

    command = subparsers.add_parser("command", help="run one framed monitor command")
    _add_endpoint_arguments(command, legacy=True)
    command.add_argument("monitor_command", nargs=argparse.REMAINDER)

    for action, help_text in (
        ("hello", "negotiate the framed protocol"),
        ("info", "show monitor platform and runtime information"),
        ("logs", "retrieve the monitor log ring"),
        ("crash", "retrieve the preserved/live crash report"),
        ("events", "retrieve structured module host events"),
        ("reboot", "request a monitor reboot"),
        ("halt", "request monitor shutdown"),
    ):
        action_parser = subparsers.add_parser(action, help=help_text)
        _add_endpoint_arguments(action_parser)

    upload = subparsers.add_parser("upload", help="upload an FMBC module")
    _add_endpoint_arguments(upload, legacy=True)
    upload.add_argument("input", type=pathlib.Path)
    upload.add_argument("--run", action="store_true")

    unload = subparsers.add_parser("unload", help="unload an FMBC module")
    _add_endpoint_arguments(unload)
    unload.add_argument("name")

    console = subparsers.add_parser("console", help="open an interactive raw console")
    _add_endpoint_arguments(console)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    endpoint: Endpoint | None = None
    try:
        if arguments.command == "compile-module":
            _print_json(compile_module(arguments.specification, arguments.output))
        elif arguments.command == "pack-module":
            _print_json(pack_module(arguments.input, arguments.output, arguments.name, arguments.version, arguments.flags))
        elif arguments.command == "inspect-module":
            _print_json(inspect_module(arguments.input))
        elif arguments.command == "manifest":
            _print_json(file_manifest(arguments.input))
        elif arguments.command == "handoff-template":
            write_template(arguments.output)
            _print_json({"output": str(arguments.output), "version": 4})
        elif arguments.command == "handoff-validate":
            normalized = load_and_validate(arguments.input)
            if arguments.output is not None:
                arguments.output.parent.mkdir(parents=True, exist_ok=True)
                arguments.output.write_text(
                    json.dumps(normalized, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            _print_json(normalized)
        elif arguments.command == "handoff-build":
            _print_json(write_blob(arguments.input, arguments.output))
        elif arguments.command == "handoff-inspect":
            _print_json(inspect_blob(arguments.input))
        elif arguments.command == "handoff-roundtrip":
            result = roundtrip_blob(arguments.input)
            _print_json(result)
            if not result.get("roundtrip_equal"):
                return 2
        elif arguments.command == "loader-conformance":
            report = check_sdk_conformance(arguments.handoff, arguments.memory_map, arguments.profile)
            if arguments.report is not None:
                arguments.report.parent.mkdir(parents=True, exist_ok=True)
                arguments.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            sys.stdout.write(format_sdk_conformance(report))
            if report.get("result") == "fail":
                return 2
        elif arguments.command in {"loader-simulate", "loader-check"}:
            report = simulate_loader(
                arguments.handoff, arguments.image, arguments.output,
                dtb_path=arguments.dtb, module_paths=arguments.module,
            )
            if arguments.command == "loader-check":
                sys.stdout.write(format_report(report))
                if report.get("result") != "pass":
                    return 2
            else:
                _print_json(report)
        elif arguments.command == "loader-report":
            sys.stdout.write(format_report(load_report(arguments.input)))
        elif arguments.command == "profile-template":
            write_profile_template(arguments.output)
            _print_json({"output": str(arguments.output), "schema_version": 1})
        elif arguments.command == "profile-validate":
            normalized = load_profile(arguments.input)
            if arguments.output is not None:
                arguments.output.parent.mkdir(parents=True, exist_ok=True)
                arguments.output.write_text(
                    json.dumps(normalized, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            _print_json(normalized)
        elif arguments.command == "profile-check":
            report = check_profile(load_profile(arguments.profile), arguments.diagnostics)
            if arguments.output is not None:
                arguments.output.parent.mkdir(parents=True, exist_ok=True)
                arguments.output.write_text(
                    json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            sys.stdout.write(format_matrix(report))
            if report.get("result") == "fail":
                return 2
        elif arguments.command == "profile-report":
            try:
                report_document = json.loads(arguments.input.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise HardwareProfileError(f"unable to read compatibility report: {exc}") from exc
            sys.stdout.write(format_matrix(report_document))
        elif arguments.command == "profile-import":
            reviewed = import_probe_results(load_profile(arguments.profile), arguments.diagnostics)
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(json.dumps(reviewed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            _print_json(reviewed)
        elif arguments.command == "hardware-diagnostics":
            endpoint = _open_endpoint(arguments)
            client = FramedClient(endpoint, timeout=arguments.timeout)
            _print_json(collect_hardware_diagnostics(client, arguments.output))
        elif arguments.command == "probe-record":
            endpoint = _open_endpoint(arguments)
            _print_json(record_probe_session(
                endpoint, arguments.output, duration=arguments.duration,
                timeout=arguments.timeout, profile_path=arguments.profile,
            ))
        elif arguments.command == "console":
            endpoint = _open_endpoint(arguments)
            print("Connected. Press Ctrl-] to exit.")
            interactive_console(endpoint)
        elif arguments.command == "upload":
            endpoint = _open_endpoint(arguments)
            sys.stdout.buffer.write(upload_module(endpoint, arguments.input, run=arguments.run, timeout=arguments.timeout, legacy=arguments.legacy))
        else:
            endpoint = _open_endpoint(arguments)
            if arguments.command == "command" and arguments.legacy:
                if not arguments.monitor_command:
                    raise FBR34KCtlError("monitor command cannot be empty")
                sys.stdout.buffer.write(send_command(endpoint, " ".join(arguments.monitor_command), arguments.timeout))
            else:
                client = FramedClient(endpoint, timeout=arguments.timeout)
                if arguments.command == "hello":
                    output = client.hello()
                elif arguments.command == "info":
                    output = client.command("info")
                elif arguments.command == "logs":
                    output = client.logs()
                elif arguments.command == "crash":
                    output = client.crash()
                elif arguments.command == "events":
                    output = client.events()
                elif arguments.command == "reboot":
                    output = client.reboot()
                elif arguments.command == "halt":
                    output = client.halt()
                elif arguments.command == "unload":
                    output = client.module_unload(arguments.name)
                elif arguments.command == "command":
                    if not arguments.monitor_command:
                        raise FBR34KCtlError("monitor command cannot be empty")
                    output = client.command(" ".join(arguments.monitor_command))
                else:
                    raise FBR34KCtlError(f"unknown command {arguments.command}")
                sys.stdout.buffer.write(output)
    except (OSError, FBR34KCtlError, HandoffSchemaError, HandoffBinaryError, LoaderSimulationError, SDKConformanceError, HardwareProfileError) as exc:
        print(f"fbr34kctl: {exc}", file=sys.stderr)
        return 1
    finally:
        if endpoint is not None:
            endpoint.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
