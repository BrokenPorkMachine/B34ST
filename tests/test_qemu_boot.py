from __future__ import annotations

import json
import os
import pathlib
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

import fbr34kctl  # noqa: E402

QEMU = shutil.which("qemu-system-aarch64")
REQUIRED = os.environ.get("FBR34KER_QEMU_REQUIRED") == "1"
SKIP_QEMU = os.environ.get("FBR34KER_SKIP_QEMU_TESTS") == "1"
EXPECTED_VERSION = os.environ.get("FBR34KER_EXPECTED_VERSION", "0.4.0")
IMAGE = pathlib.Path(os.environ.get(
    "FBR34KER_QEMU_IMAGE", str(ROOT / "build" / "fbr34ker.bin")
)).resolve()
CRASH_TEST_ENABLED = os.environ.get("FBR34KER_ENABLE_CRASH_TEST") == "1"
AVAILABLE = not SKIP_QEMU and QEMU is not None and IMAGE.is_file()


class QemuSession:
    def __init__(self) -> None:
        image = IMAGE
        if not image.exists():
            raise RuntimeError(f"monitor image is missing: {image}")
        self.process = subprocess.Popen(
            [
                QEMU or "qemu-system-aarch64",
                "-machine", "virt,gic-version=3",
                "-cpu", "cortex-a72",
                "-m", "256M",
                "-nographic",
                "-monitor", "none",
                "-serial", "stdio",
                "-no-reboot",
                "-kernel", str(image),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )

    def sendall(self, data: bytes) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def recv(self, maximum: int, timeout: float) -> bytes:
        assert self.process.stdout is not None
        fd = self.process.stdout.fileno()
        readable, _, _ = select.select([fd], [], [], timeout)
        if not readable:
            return b""
        return os.read(fd, maximum)

    def read_until(self, marker: bytes, timeout: float = 8.0) -> bytes:
        deadline = time.monotonic() + timeout
        output = bytearray()
        while marker not in output:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"timed out waiting for {marker!r}; output={bytes(output)!r}")
            chunk = self.recv(4096, min(remaining, 0.2))
            if not chunk:
                if self.process.poll() is not None:
                    raise AssertionError(f"QEMU exited with {self.process.returncode}; output={bytes(output)!r}")
                continue
            output += chunk
        return bytes(output)

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2.0)
        if self.process.stdin is not None:
            self.process.stdin.close()
        if self.process.stdout is not None:
            self.process.stdout.close()


@unittest.skipUnless(
    AVAILABLE or REQUIRED,
    "QEMU runtime image is unavailable; run make integration-build",
)
class QemuBootTests(unittest.TestCase):
    def setUp(self) -> None:
        if QEMU is None:
            self.fail("FBR34KER_QEMU_REQUIRED=1 but qemu-system-aarch64 is unavailable")
        self.session = QemuSession()
        banner = self.session.read_until(b"fbr34ker> ")
        self.assertIn(f"FBR34KER {EXPECTED_VERSION}".encode("ascii"), banner)
        self.client = fbr34kctl.FramedClient(self.session, timeout=3.0)

    def tearDown(self) -> None:
        self.session.close()

    def test_framed_protocol_fdt_health_and_module_lifecycle(self) -> None:
        hello = self.client.hello()
        self.assertIn(b"protocol=1", hello)
        help_text = self.client.command("help")
        self.assertIn(b"help                      List available commands.", help_text)
        self.assertIn(b"Total commands available: ", help_text)
        self.assertNotIn(b"%-25s", help_text)
        self.assertNotIn(b"%zu", help_text)
        info = self.client.command("info")
        self.assertIn(b"framed v1", info)
        health = self.client.command("health")
        self.assertIn(b"Heap red zones: ok", health)
        dt_info = self.client.command("dt-info")
        self.assertIn(b"Nodes:", dt_info)
        self.assertIn(b"ready / healthy", self.client.command("architecture"))
        self.assertIn(b"event-bus", self.client.command("components"))
        self.assertIn(b"console.output", self.client.command("service-registry"))
        self.assertIn(b"console-output: active", self.client.command("drivers"))
        self.assertIn(b"architecture", self.client.command("events"))

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            specification = root / "integration.json"
            container = root / "integration.fmod"
            specification.write_text(json.dumps({
                "name": "integration",
                "version": "1.0.0",
                "command": "integration-run",
                "state_slots": 2,
                "program": [
                    {"op": "state_get", "key": "runs"},
                    {"op": "push", "value": 1},
                    {"op": "add"},
                    {"op": "dup"},
                    {"op": "state_set", "key": "runs"},
                    {"op": "print", "text": "QEMU-MODULE-OK run="},
                    {"op": "print_u64"},
                    {"op": "print", "text": "\n"},
                    {"op": "event", "text": "integration completed"},
                ],
            }), encoding="utf-8")
            fbr34kctl.compile_module(specification, container)
            payload = container.read_bytes()

            tampered = bytearray(payload)
            tampered[-1] ^= 1
            with self.assertRaises(fbr34kctl.FBR34KCtlError):
                self.client.upload(bytes(tampered))

            loaded = self.client.upload(payload)
            self.assertIn(b"OK integration", loaded)
            run = self.client.module_run("integration")
            self.assertIn(b"QEMU-MODULE-OK run=1", run)
            alias = self.client.command("integration-run")
            self.assertIn(b"QEMU-MODULE-OK run=2", alias)
            events = self.client.events()
            self.assertIn(b"integration completed", events)
            listed = self.client.command("modules")
            self.assertIn(b"command: integration-run", listed)
            unloaded = self.client.module_unload("integration")
            self.assertIn(b"unloaded dynamic module integration", unloaded)


    def test_transactional_rollback_fault_injection_and_recovery(self) -> None:
        status = self.client.command("fault-status")
        self.assertIn(b"available", status)
        armed = self.client.command(
            "fault-arm component-start 0 1 platform-catalog"
        )
        self.assertIn(b"armed component-start", armed)
        with self.assertRaises(fbr34kctl.FBR34KCtlError) as context:
            self.client.command("architecture-restart")
        self.assertIn("rollbacks=1", str(context.exception))
        self.assertIn("last=platform-catalog", str(context.exception))
        consumed = self.client.command("fault-status")
        self.assertIn(b"state=idle", consumed)
        self.assertIn(b"injections=1", consumed)
        recovered = self.client.command("architecture-restart")
        self.assertIn(b"architecture restart: passed", recovered)
        architecture = self.client.command("architecture")
        self.assertIn(b"ready / healthy", architecture)
        trace = self.client.command("trace-json")
        document = json.loads(trace)
        self.assertEqual(document["schema"], 1)
        self.assertTrue(document["records"])

    @unittest.skipUnless(CRASH_TEST_ENABLED, "integration crash hook not enabled")
    def test_crash_capture_and_restricted_recovery(self) -> None:
        with self.assertRaises(fbr34kctl.FBR34KCtlError) as context:
            self.client.command("test-crash")
        self.assertIn("crash mode", str(context.exception))
        crash = self.client.crash()
        self.assertIn(b"FBR34KER crash report", crash)
        self.assertIn(b"BRK instruction", crash)
        self.assertIn(b"capture=1", crash)
        hello = self.client.hello()
        self.assertIn(EXPECTED_VERSION.encode("ascii"), hello)


if __name__ == "__main__":
    unittest.main()
