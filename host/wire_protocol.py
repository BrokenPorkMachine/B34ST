#!/usr/bin/env python3
"""Bounded framed protocol used by the FBR34KER deployment host tools.

This protocol is intentionally transport-neutral.  It carries only deployment
artifacts that have already been checked against a board profile.  It does not
provide arbitrary memory access or an exploit transport.
"""
from __future__ import annotations

import dataclasses
import enum
import struct
import zlib

MAGIC = b"FBDP"
VERSION = 1
HEADER = struct.Struct("<4sBBHIII")
HEADER_SIZE = HEADER.size
MAX_PAYLOAD = 64 * 1024
MAX_CHUNK = 4096

FLAG_ACK = 1 << 0
FLAG_ERROR = 1 << 1
FLAG_EVENT = 1 << 2


class ProtocolError(ValueError):
    """Raised when a deployment frame is malformed or unsupported."""


class MessageType(enum.IntEnum):
    PING = 0x01
    HELLO = 0x02
    CAPABILITIES = 0x03
    BEGIN_DEPLOY = 0x10
    QUERY_PROGRESS = 0x11
    PUT_CHUNK = 0x12
    COMMIT_ARTIFACT = 0x13
    START = 0x14
    EVIDENCE_GET = 0x20
    RESET_SESSION = 0x21
    RECOVER_SESSION = 0x22


@dataclasses.dataclass(frozen=True)
class Frame:
    message_type: int
    flags: int
    sequence: int
    payload: bytes = b""

    @property
    def is_error(self) -> bool:
        return bool(self.flags & FLAG_ERROR)


def _crc(prefix: bytes, payload: bytes) -> int:
    return zlib.crc32(payload, zlib.crc32(prefix)) & 0xFFFFFFFF


def encode_frame(frame: Frame) -> bytes:
    payload = bytes(frame.payload)
    if not 0 <= int(frame.message_type) <= 0xFF:
        raise ProtocolError("message type must fit in one byte")
    if frame.flags & ~0xFFFF:
        raise ProtocolError("frame flags exceed 16 bits")
    if not 0 <= frame.sequence <= 0xFFFFFFFF:
        raise ProtocolError("sequence must fit in 32 bits")
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError(f"payload exceeds {MAX_PAYLOAD} bytes")
    prefix = HEADER.pack(
        MAGIC,
        VERSION,
        int(frame.message_type),
        frame.flags,
        frame.sequence,
        len(payload),
        0,
    )[:16]
    checksum = _crc(prefix, payload)
    return HEADER.pack(
        MAGIC,
        VERSION,
        int(frame.message_type),
        frame.flags,
        frame.sequence,
        len(payload),
        checksum,
    ) + payload


def decode_frame(data: bytes, *, require_exact: bool = True) -> Frame:
    if len(data) < HEADER_SIZE:
        raise ProtocolError("truncated deployment frame header")
    magic, version, message_type, flags, sequence, length, checksum = HEADER.unpack_from(data)
    if magic != MAGIC:
        raise ProtocolError("deployment frame magic mismatch")
    if version != VERSION:
        raise ProtocolError(f"unsupported deployment protocol version {version}")
    if length > MAX_PAYLOAD:
        raise ProtocolError(f"declared payload exceeds {MAX_PAYLOAD} bytes")
    total = HEADER_SIZE + length
    if len(data) < total:
        raise ProtocolError("truncated deployment frame payload")
    if require_exact and len(data) != total:
        raise ProtocolError("trailing bytes after deployment frame")
    payload = bytes(data[HEADER_SIZE:total])
    if _crc(data[:16], payload) != checksum:
        raise ProtocolError("deployment frame CRC-32 mismatch")
    return Frame(message_type, flags, sequence, payload)


class StreamDecoder:
    """Incremental bounded decoder for serial and socket transports."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        if data:
            self._buffer.extend(data)
        frames: list[Frame] = []
        while True:
            if len(self._buffer) < HEADER_SIZE:
                break
            magic, version, _kind, _flags, _seq, length, _crc_value = HEADER.unpack_from(self._buffer)
            if magic != MAGIC:
                del self._buffer[0]
                continue
            if version != VERSION:
                raise ProtocolError(f"unsupported deployment protocol version {version}")
            if length > MAX_PAYLOAD:
                raise ProtocolError(f"declared payload exceeds {MAX_PAYLOAD} bytes")
            total = HEADER_SIZE + length
            if len(self._buffer) < total:
                break
            raw = bytes(self._buffer[:total])
            del self._buffer[:total]
            frames.append(decode_frame(raw))
        return frames

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)
