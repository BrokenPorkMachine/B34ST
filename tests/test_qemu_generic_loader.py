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
EXPECTED_VERSION = os.environ.get("FBR34KER_EXPECTED_VERSION", "0.4.5b")
LOADER = pathlib.Path(os.environ.get(
    "FBR34KER_GENERIC_LOADER_IMAGE",
    str(ROOT / "build-loader" / "fbr34ker-qemu-loader.bin"),
)).resolve()
MONITOR = pathlib.Path(os.environ.get(
    "FBR34KER_GENERIC_MONITOR_IMAGE",
    str(ROOT / "build-generic" / "fbr34ker-generic.bin"),
)).resolve()
AVAILABLE = (
    not SKIP_QEMU
    and QEMU is not None
    and LOADER.is_file()
    and MONITOR.is_file()
)


class GenericQemuSession:
    def __init__(self) -> None:
        for image in (LOADER, MONITOR):
            if not image.is_file():
                raise RuntimeError(f"required image is missing: {image}")
        self.process = subprocess.Popen(
            [
                QEMU or "qemu-system-aarch64",
                "-machine", "virt,gic-version=3",
                "-cpu", "cortex-a72",
                "-m", "2G",
                "-nographic",
                "-monitor", "none",
                "-serial", "stdio",
                "-no-reboot",
                "-semihosting-config", "enable=on,target=native",
                "-kernel", str(LOADER),
                "-device", f"loader,file={MONITOR},addr=0x80000000,force-raw=on",
            ],
            cwd=ROOT,
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
        readable, _, _ = select.select([self.process.stdout.fileno()], [], [], timeout)
        if not readable:
            return b""
        return os.read(self.process.stdout.fileno(), maximum)

    def read_until(self, marker: bytes, timeout: float = 10.0) -> bytes:
        deadline = time.monotonic() + timeout
        output = bytearray()
        while marker not in output:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"timed out waiting for {marker!r}; output={bytes(output)!r}")
            chunk = self.recv(4096, min(remaining, 0.25))
            if not chunk:
                if self.process.poll() is not None:
                    raise AssertionError(
                        f"QEMU exited with {self.process.returncode}; output={bytes(output)!r}"
                    )
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
    "QEMU generic-loader images are unavailable; run make generic-loader generic",
)
class GenericLoaderQemuTests(unittest.TestCase):
    def setUp(self) -> None:
        if QEMU is None:
            self.fail("FBR34KER_QEMU_REQUIRED=1 but qemu-system-aarch64 is unavailable")
        self.session = GenericQemuSession()
        banner = self.session.read_until(b"fbr34ker(bringup)> ")
        self.assertIn(b"LDR", banner)
        self.assertIn(f"FBR34KER {EXPECTED_VERSION}".encode("ascii"), banner)
        self.assertIn(b"Generic ARM64 handoff", banner)
        self.client = fbr34kctl.FramedClient(self.session, timeout=4.0, retries=2)

    def tearDown(self) -> None:
        self.session.close()

    def test_handoff_platform_and_module_lifecycle(self) -> None:
        hello = self.client.hello()
        self.assertIn(b"target=generic_arm64", hello)
        handoff = self.client.command("handoff-info")
        self.assertIn(b"Version:        4", handoff)
        self.assertIn(b"Memory regions: 9", handoff)
        features = self.client.command("platform-features")
        self.assertIn(b"framebuffer: yes", features)
        self.assertIn(b"direct GIC driver: yes", features)
        self.assertIn(
            b"passed",
            self.client.command("probe-validate interrupts acknowledge"),
        )
        self.assertIn(
            b"passed",
            self.client.command("probe-validate framebuffer acknowledge"),
        )
        self.assertIn(
            b"passed",
            self.client.command("probe-validate watchdog acknowledge"),
        )
        self.assertIn(
            b"accepted",
            self.client.command("probe-validate power acknowledge"),
        )
        self.assertIn(
            b"full shell commands",
            self.client.command("bringup-exit unlock"),
        )
        irq = self.client.command("irq-info")
        self.assertIn(b"GICv3", irq)
        self.assertIn(b"passed", self.client.command("irq-selftest"))
        self.assertIn(b"frequency=", self.client.command("timer-test 1"))
        self.assertIn(b"ready / healthy", self.client.command("architecture"))
        self.assertIn(b"platform-catalog", self.client.command("components"))
        self.assertIn(b"display.framebuffer", self.client.command("service-registry"))
        self.assertIn(b"framebuffer: active", self.client.command("drivers"))
        transports = self.client.command("console-transports")
        self.assertIn(b"Memory ring", transports)
        self.assertIn(b"Semihosting", transports)
        self.assertIn(b"passed", self.client.command("watchdog-test"))
        display = self.client.command("display-info")
        self.assertIn(b"1024x768", display)
        self.assertIn(b"enabled", self.client.command("display-console on"))
        self.assertIn(b"rendered and flushed", self.client.command("display-test"))
        self.assertIn(b"console=ok", self.client.command("platform-selftest"))

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            spec = root / "generic.json"
            module = root / "generic.fmod"
            spec.write_text(json.dumps({
                "name": "generic-loader-test",
                "version": "1.0.0",
                "command": "generic-loader-run",
                "program": [
                    {"op": "print", "text": "GENERIC-LOADER-MODULE-OK\\n"},
                    {"op": "event", "text": "generic loader module completed"},
                ],
            }), encoding="utf-8")
            fbr34kctl.compile_module(spec, module)
            self.assertIn(b"OK generic-loader-test", self.client.upload(module.read_bytes()))
            self.assertIn(b"GENERIC-LOADER-MODULE-OK", self.client.module_run("generic-loader-test"))
            self.assertIn(b"generic loader module completed", self.client.events())
            self.assertIn(
                b"unloaded dynamic module generic-loader-test",
                self.client.module_unload("generic-loader-test"),
            )


if __name__ == "__main__":
    unittest.main()
