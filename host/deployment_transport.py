#!/usr/bin/env python3
"""Transport adapters for the bounded FBR34KER deployment protocol."""
from __future__ import annotations

import dataclasses
import os
import pathlib
import select
import socket
import termios
import time
from typing import Protocol

from deployment_target import SimulatedDeploymentTarget
from wire_protocol import Frame, ProtocolError, StreamDecoder, decode_frame, encode_frame


class TransportError(IOError):
    """Base transport error."""


class TransportTimeout(TransportError):
    """Raised when a bounded exchange makes no progress."""


class TransportDisconnected(TransportError):
    """Raised when the endpoint closes or a test fault disconnects it."""


class DeploymentTransport(Protocol):
    def exchange(self, frame: Frame, timeout: float) -> Frame: ...
    def close(self) -> None: ...


@dataclasses.dataclass(frozen=True)
class FaultPlan:
    drop_request_at: frozenset[int] = frozenset()
    drop_response_at: frozenset[int] = frozenset()
    corrupt_response_at: frozenset[int] = frozenset()
    disconnect_at: frozenset[int] = frozenset()
    delay_ms: int = 0

    @classmethod
    def from_json(cls, value: object) -> "FaultPlan":
        if not isinstance(value, dict):
            raise TransportError("fault plan must be a JSON object")
        allowed = {"drop_request_at", "drop_response_at", "corrupt_response_at",
                   "disconnect_at", "delay_ms"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise TransportError("unknown fault-plan fields: " + ", ".join(unknown))

        def indexes(name: str) -> frozenset[int]:
            raw = value.get(name, [])
            if not isinstance(raw, list) or not all(isinstance(item, int) and item > 0 for item in raw):
                raise TransportError(f"{name} must contain positive frame numbers")
            return frozenset(raw)

        delay = value.get("delay_ms", 0)
        if not isinstance(delay, int) or not 0 <= delay <= 10000:
            raise TransportError("delay_ms must be 0..10000")
        return cls(indexes("drop_request_at"), indexes("drop_response_at"),
                   indexes("corrupt_response_at"), indexes("disconnect_at"), delay)


class SimulatorTransport:
    def __init__(self, target: SimulatedDeploymentTarget, fault_plan: FaultPlan | None = None):
        self.target = target
        self.fault_plan = fault_plan or FaultPlan()
        self.exchange_count = 0
        self.closed = False

    def exchange(self, frame: Frame, timeout: float) -> Frame:
        if self.closed:
            raise TransportDisconnected("simulator transport is closed")
        if timeout <= 0:
            raise TransportTimeout("transport timeout must be positive")
        self.exchange_count += 1
        number = self.exchange_count
        if number in self.fault_plan.disconnect_at:
            self.closed = True
            raise TransportDisconnected(f"injected disconnect at exchange {number}")
        if self.fault_plan.delay_ms:
            delay = self.fault_plan.delay_ms / 1000.0
            if delay >= timeout:
                raise TransportTimeout(f"injected delay exceeded timeout at exchange {number}")
            time.sleep(delay)
        request = encode_frame(frame)
        if number in self.fault_plan.drop_request_at:
            raise TransportTimeout(f"injected request loss at exchange {number}")
        decoded = decode_frame(request)
        response = encode_frame(self.target.handle(decoded))
        if number in self.fault_plan.drop_response_at:
            raise TransportTimeout(f"injected response loss at exchange {number}")
        if number in self.fault_plan.corrupt_response_at and response:
            mutable = bytearray(response)
            mutable[-1] ^= 0x80
            response = bytes(mutable)
        try:
            return decode_frame(response)
        except ProtocolError as exc:
            raise TransportError(str(exc)) from exc

    def close(self) -> None:
        self.closed = True


class StreamEndpoint(Protocol):
    def sendall(self, data: bytes, timeout: float) -> None: ...
    def recv(self, maximum: int, timeout: float) -> bytes: ...
    def close(self) -> None: ...


class FramedStreamTransport:
    """Frame exchange over an authorized serial or socket endpoint."""

    def __init__(self, endpoint: StreamEndpoint):
        self.endpoint = endpoint
        self.decoder = StreamDecoder()

    def exchange(self, frame: Frame, timeout: float) -> Frame:
        if timeout <= 0:
            raise TransportTimeout("transport timeout must be positive")
        deadline = time.monotonic() + timeout
        self.endpoint.sendall(encode_frame(frame), timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportTimeout("deployment response timed out")
            data = self.endpoint.recv(8192, remaining)
            if not data:
                continue
            try:
                frames = self.decoder.feed(data)
            except ProtocolError as exc:
                raise TransportError(str(exc)) from exc
            for response in frames:
                if response.sequence == frame.sequence:
                    return response

    def close(self) -> None:
        self.endpoint.close()


class SocketEndpoint:
    def __init__(self, connection: socket.socket):
        self.connection = connection

    @classmethod
    def tcp(cls, endpoint: str, timeout: float) -> "SocketEndpoint":
        if ":" not in endpoint:
            raise TransportError("TCP endpoint must be HOST:PORT")
        host, port_text = endpoint.rsplit(":", 1)
        try:
            port = int(port_text)
        except ValueError as exc:
            raise TransportError("TCP port is not an integer") from exc
        if not 1 <= port <= 65535:
            raise TransportError("TCP port must be 1..65535")
        return cls(socket.create_connection((host, port), timeout=timeout))

    @classmethod
    def unix(cls, path: pathlib.Path, timeout: float) -> "SocketEndpoint":
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(timeout)
        connection.connect(str(path))
        return cls(connection)

    def sendall(self, data: bytes, timeout: float) -> None:
        self.connection.settimeout(timeout)
        self.connection.sendall(data)

    def recv(self, maximum: int, timeout: float) -> bytes:
        self.connection.settimeout(timeout)
        try:
            value = self.connection.recv(maximum)
        except socket.timeout:
            return b""
        if value == b"":
            raise TransportDisconnected("socket endpoint closed")
        return value

    def close(self) -> None:
        self.connection.close()


class PosixSerialEndpoint:
    """Raw 8N1 serial stream. The peer must implement FBDP framing."""

    def __init__(self, path: pathlib.Path, baud: int):
        speed = getattr(termios, f"B{baud}", None)
        if speed is None:
            raise TransportError(f"unsupported serial baud rate {baud}")
        self.file_descriptor = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            attributes = termios.tcgetattr(self.file_descriptor)
            attributes[0] = 0
            attributes[1] = 0
            attributes[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
            attributes[3] = 0
            attributes[4] = speed
            attributes[5] = speed
            attributes[6][termios.VMIN] = 0
            attributes[6][termios.VTIME] = 0
            termios.tcsetattr(self.file_descriptor, termios.TCSANOW, attributes)
        except BaseException:
            os.close(self.file_descriptor)
            raise

    def sendall(self, data: bytes, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        view = memoryview(data)
        while view:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportTimeout("serial write timed out")
            _, writable, _ = select.select([], [self.file_descriptor], [], remaining)
            if not writable:
                raise TransportTimeout("serial write timed out")
            written = os.write(self.file_descriptor, view)
            if written <= 0:
                raise TransportDisconnected("serial write made no progress")
            view = view[written:]

    def recv(self, maximum: int, timeout: float) -> bytes:
        readable, _, _ = select.select([self.file_descriptor], [], [], timeout)
        if not readable:
            return b""
        try:
            return os.read(self.file_descriptor, maximum)
        except BlockingIOError:
            return b""

    def close(self) -> None:
        os.close(self.file_descriptor)
