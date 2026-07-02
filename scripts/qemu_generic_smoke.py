#!/usr/bin/env python3

"""Boot the generic image through the QEMU handoff loader and capture evidence."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import argparse
import json
import os
import pathlib
import select
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
import fbr34kctl  # noqa: E402


class Endpoint:
    def __init__(self, qemu: str, loader: pathlib.Path, image: pathlib.Path,
                 serial_path: pathlib.Path) -> None:
        self.serial = serial_path.open("wb")
        self.process = subprocess.Popen([
            qemu, "-machine", "virt,gic-version=3", "-cpu", "cortex-a72",
            "-m", "2G", "-nographic", "-monitor", "none", "-serial", "stdio",
            "-no-reboot", "-semihosting-config", "enable=on,target=native",
            "-kernel", str(loader),
            "-device", f"loader,file={image},addr=0x80000000,force-raw=on",
        ], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
           stderr=subprocess.STDOUT, bufsize=0)

    def sendall(self, data: bytes) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def recv(self, maximum: int, timeout: float) -> bytes:
        assert self.process.stdout is not None
        ready, _, _ = select.select([self.process.stdout.fileno()], [], [], timeout)
        if not ready:
            return b""
        data = os.read(self.process.stdout.fileno(), maximum)
        self.serial.write(data)
        self.serial.flush()
        return data

    def read_until(self, marker: bytes, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        data = bytearray()
        while marker not in data:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"timed out waiting for {marker!r}")
            chunk = self.recv(4096, 0.25)
            if not chunk:
                if self.process.poll() is not None:
                    raise RuntimeError(f"QEMU exited with {self.process.returncode}")
                continue
            data += chunk
        return bytes(data)

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.serial.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loader", type=pathlib.Path, required=True)
    parser.add_argument("--image", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    qemu = shutil.which("qemu-system-aarch64")
    if qemu is None:
        parser.error("qemu-system-aarch64 is required")
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    endpoint = Endpoint(qemu, args.loader.resolve(), args.image.resolve(),
                        output / "serial.bin")
    results: list[dict[str, object]] = []
    passed = False
    try:
        banner = endpoint.read_until(b"fbr34ker(bringup)> ", 12.0)
        if f"FBR34KER {args.expected_version}".encode() not in banner:
            raise RuntimeError("version banner mismatch")
        client = fbr34kctl.FramedClient(endpoint, timeout=4.0, retries=2)
        commands = [
            ("hello", client.hello, b"target=generic_arm64"),
            ("handoff", lambda: client.command("handoff-info"), b"Version:        4"),
            ("features", lambda: client.command("platform-features"), b"direct GIC driver: yes"),
            ("timer", lambda: client.command("timer-test 1"), b"frequency="),
            ("console-transports", lambda: client.command("console-transports"), b"Memory ring"),
            ("validate-irq", lambda: client.command("probe-validate interrupts acknowledge"), b"passed"),
            ("validate-framebuffer", lambda: client.command("probe-validate framebuffer acknowledge"), b"passed"),
            ("validate-watchdog", lambda: client.command("probe-validate watchdog acknowledge"), b"passed"),
            ("validate-power", lambda: client.command("probe-validate power acknowledge"), b"accepted"),
            ("unlock", lambda: client.command("bringup-exit unlock"), b"full shell commands"),
            ("irq", lambda: client.command("irq-selftest"), b"passed"),
            ("watchdog", lambda: client.command("watchdog-test"), b"passed"),
            ("display", lambda: client.command("display-info"), b"1024x768"),
            ("display-console", lambda: client.command("display-console on"), b"enabled"),
            ("display-test", lambda: client.command("display-test"), b"rendered and flushed"),
            ("selftest", lambda: client.command("platform-selftest"), b"console=ok"),
        ]
        for name, operation, marker in commands:
            started = time.monotonic()
            response = operation()
            if marker not in response:
                raise RuntimeError(f"{name} missing marker {marker!r}")
            (output / f"{name}.txt").write_bytes(response)
            results.append({"name": name, "passed": True,
                            "duration_ms": int((time.monotonic()-started)*1000)})
        passed = True
    except Exception as exc:  # noqa: BLE001
        results.append({"name": "failure", "passed": False,
                        "detail": f"{type(exc).__name__}: {exc}"})
    finally:
        endpoint.close()
        raw = (output / "serial.bin").read_bytes()
        (output / "serial.txt").write_text(raw.decode("utf-8", errors="replace"), encoding="utf-8")
        (output / "summary.json").write_text(json.dumps({
            "schema_version": 1, "passed": passed, "steps": results,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
