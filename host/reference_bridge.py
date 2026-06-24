#!/usr/bin/env python3
"""Reference persistent first-stage bridge backed by the deterministic simulator."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import sys
import tempfile
from typing import Any

from bridge_protocol import (BRIDGE_SCHEMA_VERSION, MAX_BRIDGE_LINE,
                             MAX_CHUNK_SIZE, BridgeProtocolError,
                             decode_message, encode_message)
from first_stage_adapter import AdapterError, SimulatorFirstStageAdapter
from irecovery_boot import load_device_info

MAX_UPLOAD_SIZE = 64 * 1024 * 1024


class BridgeServer:
    def __init__(self, args: argparse.Namespace) -> None:
        device = load_device_info(args.device_info)
        regions = None
        if args.memory_map:
            value = json.loads(args.memory_map.read_text(encoding="utf-8"))
            regions = value.get("memory_regions") if isinstance(value, dict) else value
        self.adapter = SimulatorFirstStageAdapter(
            args.state_dir, device.public_dict(), regions=regions,
            inject_failure=args.inject_failure,
        )
        self.incoming = args.state_dir / "bridge-incoming.tmp"
        self.expected_size = 0
        self.expected_hash = ""
        self.received = 0
        self.digest: hashlib._Hash | None = None

    def _upload_begin(self, arguments: dict[str, Any]) -> dict[str, object]:
        size = arguments.get("size")
        digest = arguments.get("sha256")
        if not isinstance(size, int) or size <= 0 or size > MAX_UPLOAD_SIZE:
            raise AdapterError("upload size is outside the bridge limit")
        if not isinstance(digest, str) or len(digest) != 64:
            raise AdapterError("upload SHA-256 is invalid")
        int(digest, 16)
        self.incoming.parent.mkdir(parents=True, exist_ok=True)
        self.incoming.write_bytes(b"")
        self.expected_size = size
        self.expected_hash = digest.lower()
        self.received = 0
        self.digest = hashlib.sha256()
        return {"accepted": True, "chunk_size": MAX_CHUNK_SIZE}

    def _upload_chunk(self, arguments: dict[str, Any]) -> dict[str, object]:
        if self.digest is None:
            raise AdapterError("upload has not started")
        offset = arguments.get("offset")
        encoded = arguments.get("data")
        if offset != self.received or not isinstance(encoded, str):
            raise AdapterError("upload chunk offset is invalid")
        try:
            chunk = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise AdapterError("upload chunk is not valid base64") from exc
        if not chunk or len(chunk) > MAX_CHUNK_SIZE:
            raise AdapterError("upload chunk size is invalid")
        if self.received + len(chunk) > self.expected_size:
            raise AdapterError("upload exceeds declared size")
        with self.incoming.open("ab") as stream:
            stream.write(chunk)
        self.digest.update(chunk)
        self.received += len(chunk)
        return {"accepted": len(chunk), "received": self.received}

    def _upload_commit(self) -> dict[str, object]:
        if self.digest is None or self.received != self.expected_size:
            raise AdapterError("upload is incomplete")
        if self.digest.hexdigest() != self.expected_hash:
            raise AdapterError("upload hash mismatch")
        result = self.adapter.upload(self.incoming)
        self.digest = None
        return result

    def dispatch(self, operation: str, arguments: dict[str, Any]) -> dict[str, object]:
        if operation == "identify": return self.adapter.identify().public_dict()
        if operation == "authorize": return self.adapter.authorize(str(arguments.get("authorization_id", "")))
        if operation == "upload-begin": return self._upload_begin(arguments)
        if operation == "upload-chunk": return self._upload_chunk(arguments)
        if operation == "upload-commit": return self._upload_commit()
        if operation == "start": return self.adapter.start()
        if operation == "probe-stage": return self.adapter.probe_stage(str(arguments.get("stage", "")))
        if operation == "console-read": return self.adapter.read_console(int(arguments.get("cursor", 0)))
        if operation == "collect": return self.adapter.collect()
        if operation == "reset": return self.adapter.reset(str(arguments.get("authorization_id", "")))
        if operation == "close": return {"closed": True}
        raise AdapterError(f"unsupported bridge operation: {operation}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=pathlib.Path, required=True)
    parser.add_argument("--device-info", type=pathlib.Path, required=True)
    parser.add_argument("--memory-map", type=pathlib.Path)
    parser.add_argument("--inject-failure")
    args = parser.parse_args(argv)
    server = BridgeServer(args)
    for raw in sys.stdin.buffer:
        if len(raw) > MAX_BRIDGE_LINE:
            return 2
        request: dict[str, Any] = {}
        try:
            request = decode_message(raw)
            result = server.dispatch(request["operation"], request["arguments"])
            response = {"schema_version": BRIDGE_SCHEMA_VERSION,
                        "sequence": request["sequence"], "ok": True,
                        "result": result}
        except (BridgeProtocolError, AdapterError, OSError, ValueError,
                json.JSONDecodeError) as exc:
            sequence = request.get("sequence", 1) if isinstance(locals().get("request"), dict) else 1
            response = {"schema_version": BRIDGE_SCHEMA_VERSION,
                        "sequence": sequence, "ok": False, "error": str(exc)}
        sys.stdout.buffer.write(encode_message(response))
        sys.stdout.buffer.flush()
        if request.get("operation") == "close":
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
