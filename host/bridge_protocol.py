#!/usr/bin/env python3
"""Bounded persistent JSON-lines protocol for authorized first-stage bridges."""
from __future__ import annotations

import json
import pathlib
import select
import subprocess
from typing import Any, Sequence

BRIDGE_SCHEMA_VERSION = 1
MAX_BRIDGE_LINE = 1024 * 1024
MAX_BRIDGE_MESSAGES = 4096
MAX_CHUNK_SIZE = 128 * 1024


class BridgeProtocolError(RuntimeError):
    pass


def validate_message(value: object, *, response: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BridgeProtocolError("bridge message must be an object")
    required = {"schema_version", "sequence"}
    if response:
        required |= {"ok"}
    else:
        required |= {"operation", "arguments"}
    if not required.issubset(value):
        raise BridgeProtocolError("bridge message is missing required fields")
    if value.get("schema_version") != BRIDGE_SCHEMA_VERSION:
        raise BridgeProtocolError("unsupported bridge protocol version")
    sequence = value.get("sequence")
    if not isinstance(sequence, int) or sequence < 1 or sequence > MAX_BRIDGE_MESSAGES:
        raise BridgeProtocolError("invalid bridge sequence")
    if response:
        if not isinstance(value.get("ok"), bool):
            raise BridgeProtocolError("bridge response ok flag is invalid")
    else:
        if not isinstance(value.get("operation"), str) or not value["operation"]:
            raise BridgeProtocolError("bridge operation is invalid")
        if not isinstance(value.get("arguments"), dict):
            raise BridgeProtocolError("bridge arguments must be an object")
    return value


def encode_message(value: dict[str, Any]) -> bytes:
    encoded = (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > MAX_BRIDGE_LINE:
        raise BridgeProtocolError("bridge message exceeds size limit")
    return encoded


def decode_message(line: bytes, *, response: bool = False) -> dict[str, Any]:
    if not line or len(line) > MAX_BRIDGE_LINE or not line.endswith(b"\n"):
        raise BridgeProtocolError("invalid bridge message framing")
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeProtocolError("invalid bridge JSON") from exc
    return validate_message(value, response=response)


class BridgeProcessClient:
    """Persistent bridge subprocess client with strict request/response sequencing."""

    def __init__(self, command: Sequence[str], *, timeout: float = 30.0,
                 cwd: pathlib.Path | None = None) -> None:
        if not command:
            raise BridgeProtocolError("bridge command is empty")
        if timeout <= 0 or timeout > 300:
            raise BridgeProtocolError("bridge timeout must be in the range 0..300 seconds")
        self.command = tuple(str(value) for value in command)
        self.timeout = timeout
        self.cwd = cwd
        self._sequence = 0
        try:
            self._process = subprocess.Popen(
                self.command,
                cwd=str(cwd) if cwd else None,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except OSError as exc:
            raise BridgeProtocolError(f"unable to start bridge: {exc}") from exc
        if self._process.stdin is None or self._process.stdout is None:
            self.close()
            raise BridgeProtocolError("bridge pipes are unavailable")

    def _readline(self) -> bytes:
        stdout = self._process.stdout
        if stdout is None:
            raise BridgeProtocolError("bridge stdout is closed")
        ready, _, _ = select.select([stdout], [], [], self.timeout)
        if not ready:
            self.close(force=True)
            raise BridgeProtocolError(f"bridge response timed out after {self.timeout:g}s")
        line = stdout.readline(MAX_BRIDGE_LINE + 1)
        if len(line) > MAX_BRIDGE_LINE:
            self.close(force=True)
            raise BridgeProtocolError("bridge response exceeds size limit")
        if not line:
            detail = ""
            if self._process.stderr is not None:
                try:
                    detail = self._process.stderr.read(MAX_BRIDGE_LINE).decode("utf-8", "replace").strip()
                except OSError:
                    detail = ""
            raise BridgeProtocolError(f"bridge closed unexpectedly{': ' + detail if detail else ''}")
        return line

    def request(self, operation: str, **arguments: object) -> dict[str, Any]:
        if self._process.poll() is not None:
            raise BridgeProtocolError("bridge process is not running")
        if self._sequence >= MAX_BRIDGE_MESSAGES:
            raise BridgeProtocolError("bridge message limit reached")
        self._sequence += 1
        request = validate_message({
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "sequence": self._sequence,
            "operation": operation,
            "arguments": arguments,
        })
        encoded = encode_message(request)
        try:
            assert self._process.stdin is not None
            self._process.stdin.write(encoded)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise BridgeProtocolError(f"bridge request failed: {exc}") from exc
        response = decode_message(self._readline(), response=True)
        if response["sequence"] != self._sequence:
            raise BridgeProtocolError("bridge response sequence mismatch")
        if not response["ok"]:
            error = response.get("error", "bridge operation failed")
            raise BridgeProtocolError(str(error))
        result = response.get("result")
        if not isinstance(result, dict):
            raise BridgeProtocolError("bridge result must be an object")
        return result

    def close(self, *, force: bool = False) -> None:
        process = getattr(self, "_process", None)
        if process is None:
            return
        if process.poll() is None and not force:
            try:
                self.request("close")
            except BridgeProtocolError:
                force = True
        if process.poll() is None:
            if force:
                process.kill()
            else:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        self._process = None

    def __enter__(self) -> "BridgeProcessClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close(force=exc is not None)
