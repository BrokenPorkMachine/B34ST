#!/usr/bin/env python3

"""Run a bounded FBR34KER QEMU smoke test and capture diagnostics."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import select
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

import fbr34kctl  # noqa: E402


@dataclass
class StepResult:
    name: str
    passed: bool
    duration_ms: int
    output_file: str | None
    detail: str


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def display_path(path: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value).strip("-")


class QemuEndpoint:
    def __init__(
        self,
        qemu: str,
        image: pathlib.Path,
        output: pathlib.Path,
        label: str,
        deadline_seconds: float,
    ) -> None:
        self.label = label
        self.output = output
        self.deadline_seconds = deadline_seconds
        self.deadline = time.monotonic() + deadline_seconds
        self.rx_path = output / f"{label}.serial.bin"
        self.tx_path = output / f"{label}.host-transmit.bin"
        self.rx = self.rx_path.open("wb")
        self.tx = self.tx_path.open("wb")
        self.process = subprocess.Popen(
            [
                qemu,
                "-machine", "virt,gic-version=3",
                "-cpu", "cortex-a72",
                "-m", "256M",
                "-nographic",
                "-monitor", "none",
                "-serial", "stdio",
                "-no-reboot",
                "-kernel", str(image),
            ],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )

    def _remaining(self, timeout: float) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise fbr34kctl.FBR34KCtlError(
                f"{self.label} exceeded its {self.deadline_seconds:g}s session deadline"
            )
        return min(max(timeout, 0.0), remaining)

    def sendall(self, data: bytes) -> None:
        if self.process.poll() is not None:
            raise fbr34kctl.FBR34KCtlError(
                f"QEMU exited with status {self.process.returncode} before write"
            )
        assert self.process.stdin is not None
        self.tx.write(data)
        self.tx.flush()
        try:
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except BrokenPipeError as exc:
            raise fbr34kctl.FBR34KCtlError("QEMU serial input closed") from exc

    def recv(self, maximum: int, timeout: float) -> bytes:
        assert self.process.stdout is not None
        fd = self.process.stdout.fileno()
        wait = self._remaining(timeout)
        readable, _, _ = select.select([fd], [], [], wait)
        if not readable:
            if self.process.poll() is not None:
                raise fbr34kctl.FBR34KCtlError(
                    f"QEMU exited with status {self.process.returncode}"
                )
            return b""
        data = os.read(fd, maximum)
        if not data:
            status = self.process.poll()
            raise fbr34kctl.FBR34KCtlError(
                f"QEMU serial output closed (status={status})"
            )
        self.rx.write(data)
        self.rx.flush()
        return data

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2.0)
        self.rx.close()
        self.tx.close()
        text_path = self.output / f"{self.label}.serial.txt"
        text_path.write_text(
            self.rx_path.read_bytes().decode("utf-8", errors="replace"),
            encoding="utf-8",
        )


def read_until(endpoint: QemuEndpoint, marker: bytes, timeout: float) -> bytes:
    deadline = time.monotonic() + timeout
    output = bytearray()
    while marker not in output:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise fbr34kctl.FBR34KCtlError(
                f"timed out waiting for {marker!r}; received {len(output)} bytes"
            )
        output += endpoint.recv(4096, min(0.25, remaining))
        if len(output) > 1024 * 1024:
            raise fbr34kctl.FBR34KCtlError("boot transcript exceeded 1 MiB")
    return bytes(output)


class SmokeRun:
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output
        self.steps: list[StepResult] = []

    def step(
        self,
        name: str,
        operation: Callable[[], bytes],
        *required: bytes,
    ) -> bytes:
        started = time.monotonic()
        file_name = f"step-{len(self.steps) + 1:02d}-{safe_name(name)}.txt"
        path = self.output / file_name
        try:
            data = operation()
            for marker in required:
                if marker not in data:
                    raise AssertionError(f"missing expected marker {marker!r}")
            path.write_bytes(data)
            self.steps.append(StepResult(
                name, True, int((time.monotonic() - started) * 1000),
                file_name, f"{len(data)} response bytes",
            ))
            return data
        except BaseException as exc:
            self.steps.append(StepResult(
                name, False, int((time.monotonic() - started) * 1000),
                None, f"{type(exc).__name__}: {exc}",
            ))
            raise


def _qemu_version(qemu: str) -> str:
    completed = subprocess.run(
        [qemu, "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=5,
        check=False,
    )
    return completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else "unknown"


def run_normal(
    qemu: str,
    image: pathlib.Path,
    module: pathlib.Path,
    output: pathlib.Path,
    expected_version: str,
    deadline: float,
    request_timeout: float,
    results: SmokeRun,
) -> None:
    endpoint = QemuEndpoint(qemu, image, output, "normal", deadline)
    try:
        banner = results.step(
            "boot",
            lambda: read_until(endpoint, b"fbr34ker> ", request_timeout * 3),
            f"FBR34KER {expected_version}".encode("ascii"),
        )
        del banner
        client = fbr34kctl.FramedClient(
            endpoint, timeout=request_timeout, retries=2
        )
        results.step("hello", client.hello,
                     expected_version.encode("ascii"), b"target=qemu_virt", b"protocol=1")
        results.step("version", lambda: client.command("version"),
                     expected_version.encode("ascii"), b"source:")
        results.step("info", lambda: client.command("info"),
                     b"Current EL:", b"framed v1")
        results.step("health", lambda: client.command("health"),
                     b"Heap red zones: ok", b"Stack guards:   ok", b"Module images:  ok")
        results.step("device-tree", lambda: client.command("dt-info"),
                     b"Nodes:", b"properties:")
        results.step("memory-regions", lambda: client.command("regions"),
                     b"Known regions")
        results.step("heap", lambda: client.command("heap"), b"Integrity:")
        results.step("empty-crash", client.crash, b"No crash report.")
        payload = module.read_bytes()
        results.step("module-upload", lambda: client.upload(payload), b"OK hello-dynamic")
        results.step("module-run-1", lambda: client.module_run("hello-dynamic"),
                     b"Run count: 1")
        results.step("module-run-2", lambda: client.command("hello-dynamic-run"),
                     b"Run count: 2")
        results.step("events", client.events, b"hello-dynamic executed")
        results.step("modules", lambda: client.command("modules"),
                     b"hello-dynamic", b"command: hello-dynamic-run")
        results.step("module-unload", lambda: client.module_unload("hello-dynamic"),
                     b"unloaded dynamic module hello-dynamic")
        results.step("logs", client.logs, b"booted at EL")
    finally:
        endpoint.close()


def run_runtime_validation(
    qemu: str,
    image: pathlib.Path,
    output: pathlib.Path,
    expected_version: str,
    deadline: float,
    request_timeout: float,
    results: SmokeRun,
) -> None:
    endpoint = QemuEndpoint(qemu, image, output, "validation", deadline)
    try:
        results.step(
            "validation-boot",
            lambda: read_until(endpoint, b"fbr34ker> ", request_timeout * 3),
            f"FBR34KER {expected_version}".encode("ascii"),
        )
        client = fbr34kctl.FramedClient(endpoint, timeout=request_timeout, retries=2)
        results.step("architecture-baseline", lambda: client.command("architecture"),
                     b"ready / healthy", b"Components: 10")
        results.step("trace-json", lambda: client.command("trace-json"),
                     b'"schema":1', b'"records"')
        results.step("fault-status", lambda: client.command("fault-status"),
                     b"available", b"state=idle")
        results.step(
            "fault-arm",
            lambda: client.command(
                "fault-arm component-start 0 1 platform-catalog"
            ),
            b"armed component-start", b"platform-catalog",
        )

        def expected_rollback() -> bytes:
            try:
                return client.command("architecture-restart")
            except fbr34kctl.FBR34KCtlError as exc:
                return str(exc).encode("utf-8", errors="replace")

        results.step("transactional-rollback", expected_rollback,
                     b"architecture restart: failed", b"rollbacks=1",
                     b"last=platform-catalog")
        results.step("fault-consumed", lambda: client.command("fault-status"),
                     b"state=idle", b"injections=1")
        results.step("architecture-recovery",
                     lambda: client.command("architecture-restart"),
                     b"architecture restart: passed")
        results.step("architecture-post-recovery",
                     lambda: client.command("architecture"),
                     b"ready / healthy", b"Components: 10")
        results.step("service-version-contracts",
                     lambda: client.command("drivers"),
                     b"depends=console.output", b"depends=timer.monotonic")
    finally:
        endpoint.close()


def run_crash(
    qemu: str,
    image: pathlib.Path,
    output: pathlib.Path,
    expected_version: str,
    deadline: float,
    request_timeout: float,
    results: SmokeRun,
) -> None:
    endpoint = QemuEndpoint(qemu, image, output, "crash", deadline)
    try:
        results.step(
            "crash-boot",
            lambda: read_until(endpoint, b"fbr34ker> ", request_timeout * 3),
            f"FBR34KER {expected_version}".encode("ascii"),
        )
        client = fbr34kctl.FramedClient(
            endpoint, timeout=request_timeout, retries=2
        )

        def trigger() -> bytes:
            try:
                return client.command("test-crash")
            except fbr34kctl.FBR34KCtlError as exc:
                return str(exc).encode("utf-8", errors="replace")

        results.step("trigger-crash", trigger, b"crash mode")
        results.step("crash-report", client.crash,
                     b"FBR34KER crash report", b"BRK instruction", b"capture=1")
        results.step("crash-hello", client.hello, expected_version.encode("ascii"))
    finally:
        endpoint.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=pathlib.Path, required=True)
    parser.add_argument("--module", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--qemu", default="qemu-system-aarch64")
    parser.add_argument("--deadline", type=float, default=45.0,
                        help="maximum seconds per QEMU session")
    parser.add_argument("--request-timeout", type=float, default=3.0)
    parser.add_argument("--crash-test", action="store_true")
    parser.add_argument("--runtime-validation", action="store_true")
    arguments = parser.parse_args(argv)

    qemu = shutil.which(arguments.qemu)
    if qemu is None:
        parser.error(f"QEMU executable was not found: {arguments.qemu}")
    image = arguments.image.resolve()
    module = arguments.module.resolve()
    if not image.is_file():
        parser.error(f"monitor image does not exist: {image}")
    if not module.is_file():
        parser.error(f"module does not exist: {module}")
    if arguments.deadline <= 0 or arguments.request_timeout <= 0:
        parser.error("timeouts must be greater than zero")

    output = arguments.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    results = SmokeRun(output)
    started = time.monotonic()
    passed = False
    error: str | None = None
    try:
        run_normal(
            qemu, image, module, output, arguments.expected_version,
            arguments.deadline, arguments.request_timeout, results,
        )
        if arguments.runtime_validation:
            run_runtime_validation(
                qemu, image, output, arguments.expected_version,
                arguments.deadline, arguments.request_timeout, results,
            )
        if arguments.crash_test:
            run_crash(
                qemu, image, output, arguments.expected_version,
                arguments.deadline, arguments.request_timeout, results,
            )
        passed = True
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    summary = {
        "schema_version": 1,
        "project": "FBR34KER",
        "expected_version": arguments.expected_version,
        "passed": passed,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "qemu": _qemu_version(qemu),
        "image": {"path": display_path(image), "size": image.stat().st_size,
                  "sha256": sha256_file(image)},
        "module": {"path": display_path(module), "size": module.stat().st_size,
                   "sha256": sha256_file(module)},
        "crash_test": arguments.crash_test,
        "runtime_validation": arguments.runtime_validation,
        "error": error,
        "steps": [asdict(step) for step in results.steps],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if passed:
        print(f"FBR34KER smoke test passed; diagnostics: {output}")
        return 0
    print(f"FBR34KER smoke test failed: {error}", file=sys.stderr)
    print(f"diagnostics: {output}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
