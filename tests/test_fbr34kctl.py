# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import json
import pathlib
import struct
import sys
import tempfile
import unittest
import zlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

import fbr34kctl  # noqa: E402


class FakeEndpoint:
    def __init__(self, handler=None, *, noise: bytes = b""):
        self.handler = handler
        self.responses: list[bytes] = []
        self.sent = bytearray()
        self.closed = False
        self.noise = noise
        self.send_count = 0

    def sendall(self, data: bytes) -> None:
        self.sent += data
        self.send_count += 1
        if self.handler is not None:
            response = self.handler(data, self.send_count)
            if response is not None:
                self.responses.append(self.noise + response)
                self.noise = b""

    def recv(self, maximum: int, timeout: float) -> bytes:
        del timeout
        if not self.responses:
            return b""
        data = self.responses.pop(0)
        if len(data) > maximum:
            self.responses.insert(0, data[maximum:])
            return data[:maximum]
        return data

    def close(self) -> None:
        self.closed = True


def response_for(request: bytes, payload: bytes = b"ok\n", *, error: bool = False) -> bytes:
    frame = fbr34kctl.decode_frame(request)
    flags = fbr34kctl.PROTOCOL_FLAG_ACK | (fbr34kctl.PROTOCOL_FLAG_ERROR if error else 0)
    prefix = fbr34kctl.PROTOCOL_HEADER.pack(
        fbr34kctl.PROTOCOL_MAGIC,
        fbr34kctl.PROTOCOL_VERSION,
        frame.message_type | 0x80,
        flags,
        frame.sequence,
        len(payload),
        0,
    )
    checksum = zlib.crc32(prefix[:16] + payload) & 0xFFFFFFFF
    return prefix[:16] + struct.pack("<I", checksum) + payload


class FBR34KCtlTests(unittest.TestCase):
    def test_pack_and_inspect_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            payload = root / "module.bin"
            container = root / "module.fmod"
            payload.write_bytes(bytes(range(64)))
            packed = fbr34kctl.pack_module(payload, container, "example", "1.2.3")
            inspected = fbr34kctl.inspect_module(container)
            self.assertEqual(packed.name, inspected.name)
            self.assertEqual(inspected.flags, 0)
            self.assertEqual(inspected.payload_kind, "opaque")
            self.assertTrue(inspected.hash_valid)

    def test_rejects_unsupported_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            payload = root / "module.bin"
            payload.write_bytes(b"x")
            with self.assertRaises(fbr34kctl.FBR34KCtlError):
                fbr34kctl.pack_module(
                    payload, root / "bad.fmod", "example", "1.0", flags=1
                )

    def test_instruction_budget_includes_implicit_halt(self) -> None:
        with self.assertRaises(fbr34kctl.FBR34KCtlError):
            fbr34kctl.compile_bytecode({
                "instruction_budget": 1,
                "program": [{"op": "push", "value": 1}],
            })

    def test_state_capability_requires_storage(self) -> None:
        with self.assertRaises(fbr34kctl.FBR34KCtlError):
            fbr34kctl.compile_bytecode({
                "capabilities": ["state"],
                "state_slots": 0,
                "program": [{"op": "halt"}],
            })

    def test_wire_text_rejects_non_ascii(self) -> None:
        client = fbr34kctl.FramedClient(FakeEndpoint(), timeout=0.001, retries=1)
        with self.assertRaises(fbr34kctl.FBR34KCtlError):
            client.command("echo café")

    def test_compile_fmbc_v2_module(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            specification = root / "module.json"
            output = root / "module.fmod"
            specification.write_text(json.dumps({
                "name": "clock",
                "version": "1.0.0",
                "command": "clock-now",
                "state_slots": 2,
                "program": [
                    {"op": "push", "value": 7},
                    {"op": "state_set", "key": "runs"},
                    {"op": "print", "text": "uptime="},
                    {"op": "uptime"},
                    {"op": "print_u64"},
                    {"op": "event", "text": "clock completed"},
                ],
            }), encoding="utf-8")
            info = fbr34kctl.compile_module(specification, output)
            self.assertEqual(info.payload_kind, "FMBC-v2")
            self.assertEqual(info.command, "clock-now")
            self.assertEqual(info.state_slots, 2)
            self.assertEqual(info.capabilities, ("console", "time", "state", "host"))
            self.assertTrue(info.hash_valid)

    def test_declared_capabilities_are_enforced(self) -> None:
        with self.assertRaises(fbr34kctl.FBR34KCtlError):
            fbr34kctl.compile_bytecode({
                "capabilities": ["console"],
                "program": [{"op": "uptime"}],
            })

    def test_compiler_rejects_stack_underflow(self) -> None:
        with self.assertRaises(fbr34kctl.FBR34KCtlError):
            fbr34kctl.compile_bytecode({"program": [{"op": "add"}]})

    def test_frame_round_trip_and_crc(self) -> None:
        raw = fbr34kctl.encode_frame(fbr34kctl.MSG_PING, 42, b"payload")
        frame = fbr34kctl.decode_frame(raw)
        self.assertEqual(frame.sequence, 42)
        self.assertEqual(frame.payload, b"payload")
        corrupted = bytearray(raw)
        corrupted[-1] ^= 1
        with self.assertRaises(fbr34kctl.FBR34KCtlError):
            fbr34kctl.decode_frame(bytes(corrupted))

    def test_framed_client_ignores_console_noise(self) -> None:
        endpoint = FakeEndpoint(lambda request, count: response_for(request, b"hello\n"), noise=b"fbr34ker> ")
        client = fbr34kctl.FramedClient(endpoint, timeout=0.02)
        self.assertEqual(client.hello(), b"hello\n")

    def test_framed_client_retries_same_sequence(self) -> None:
        sequences: list[int] = []
        def handler(request: bytes, count: int):
            sequences.append(fbr34kctl.decode_frame(request).sequence)
            return None if count == 1 else response_for(request, b"retried\n")
        endpoint = FakeEndpoint(handler)
        client = fbr34kctl.FramedClient(endpoint, timeout=0.005, retries=2)
        self.assertEqual(client.hello(), b"retried\n")
        self.assertEqual(sequences[0], sequences[1])

    def test_framed_upload_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            spec = root / "module.json"
            output = root / "module.fmod"
            spec.write_text(json.dumps({
                "name": "example", "version": "1.0",
                "program": [{"op": "print", "text": "ok\n"}],
            }), encoding="utf-8")
            fbr34kctl.compile_module(spec, output)
            seen: list[int] = []
            def handler(request: bytes, count: int):
                frame = fbr34kctl.decode_frame(request)
                seen.append(frame.message_type)
                if frame.message_type == fbr34kctl.MSG_MODULE_PUT:
                    self.assertEqual(frame.payload, output.read_bytes())
                    return response_for(request, b"OK example\n")
                return response_for(request, b"ok\n")
            endpoint = FakeEndpoint(handler)
            transcript = fbr34kctl.upload_module(endpoint, output, run=True, timeout=0.02)
            self.assertIn(b"OK example", transcript)
            self.assertEqual(seen, [fbr34kctl.MSG_MODULE_PUT, fbr34kctl.MSG_MODULE_RUN])

    def test_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            payload = root / "module.bin"
            container = root / "module.fmod"
            payload.write_bytes(b"original")
            fbr34kctl.pack_module(payload, container, "example", "1.0")
            data = bytearray(container.read_bytes())
            data[-1] ^= 0xFF
            container.write_bytes(data)
            self.assertFalse(fbr34kctl.inspect_module(container).hash_valid)

    def test_rejects_unsafe_identifier_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            payload = root / "module.bin"
            payload.write_bytes(b"x")
            with self.assertRaises(fbr34kctl.FBR34KCtlError):
                fbr34kctl.pack_module(payload, root / "bad.fmod", "bad name", "1.0")
            with self.assertRaises(fbr34kctl.FBR34KCtlError):
                fbr34kctl.compile_bytecode({"program": [{"op": "print", "text": "bad\x1b[2J"}]})

    def test_hardware_diagnostics_excludes_memory_contents(self) -> None:
        class FakeClient:
            def command(self, command: str) -> bytes:
                return (command + " ok\n").encode("ascii")
            def logs(self) -> bytes:
                return b"logs ok\n"
            def crash(self) -> bytes:
                return b"no crash\n"

        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "hardware"
            report = fbr34kctl.collect_hardware_diagnostics(FakeClient(), output)
            self.assertFalse(report["sensitive_memory_included"])
            self.assertTrue((output / "summary.json").is_file())
            self.assertTrue(output.with_suffix(".zip").is_file())
            self.assertFalse(any("memory.bin" in item.name for item in output.iterdir()))

    def test_legacy_command_accepts_restricted_bringup_prompt(self) -> None:
        endpoint = FakeEndpoint(
            lambda request, count: b"restricted diagnostics\nfbr34ker(bringup)> "
        )
        output = fbr34kctl.send_command(endpoint, "platform-info", timeout=0.5)
        self.assertIn(b"fbr34ker(bringup)> ", output)

    def test_legacy_command_accepts_immutable_probe_prompt(self) -> None:
        endpoint = FakeEndpoint(
            lambda request, count: b"read-only diagnostics\nfbr34ker(probe)> "
        )
        output = fbr34kctl.send_command(endpoint, "probe-status", timeout=0.5)
        self.assertIn(b"fbr34ker(probe)> ", output)

    def test_probe_session_captures_transcript_and_profile_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            profile = root / "board.json"
            profile.write_text(json.dumps({
                "schema_version": 1,
                "name": "test-board",
                "architecture": "arm64",
                "expected_el": 1,
                "console": "callback",
                "interrupt_controller": "gicv3",
                "timer": "arm-generic",
                "framebuffer": None,
                "required_services": [],
            }), encoding="utf-8")
            endpoint = FakeEndpoint(lambda request, count: response_for(request, b"ok\n"))
            endpoint.responses.append(b"boot banner\nfbr34ker(probe)> ")
            output = root / "session"
            report = fbr34kctl.record_probe_session(
                endpoint, output, duration=0.001, timeout=0.02,
                profile_path=profile,
            )
            self.assertTrue((output / "boot-transcript.raw").is_file())
            self.assertTrue((output / "probe-session.json").is_file())
            self.assertTrue((output / "compatibility-profile.json").is_file())
            self.assertTrue(pathlib.Path(report["archive"]).is_file())
            with zipfile.ZipFile(report["archive"]) as bundle:
                self.assertIn("boot-transcript.txt", bundle.namelist())
                self.assertIn("compatibility-profile.txt", bundle.namelist())

    def test_hardware_diagnostics_never_requests_mutating_selftests(self) -> None:
        commands: list[str] = []
        class FakeClient:
            def command(self, command: str) -> bytes:
                commands.append(command)
                return b"ok\n"
            def logs(self) -> bytes: return b"logs\n"
            def crash(self) -> bytes: return b"crash\n"
        with tempfile.TemporaryDirectory() as directory:
            fbr34kctl.collect_hardware_diagnostics(
                FakeClient(), pathlib.Path(directory) / "hardware")
        joined = " ".join(commands)
        self.assertNotIn("irq-selftest", joined)
        self.assertNotIn("watchdog-test", joined)
        self.assertNotIn("platform-selftest", joined)
        self.assertIn("probe-status", commands)
        self.assertIn("compatibility", commands)


if __name__ == "__main__":
    unittest.main()
