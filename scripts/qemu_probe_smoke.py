#!/usr/bin/env python3
"""Boot the immutable physical-hardware probe through the QEMU handoff loader."""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
sys.path.insert(0, str(ROOT / "scripts"))

import fbr34kctl  # noqa: E402
from qemu_generic_smoke import Endpoint  # noqa: E402


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
        banner = endpoint.read_until(b"fbr34ker(probe)> ", 12.0)
        if f"FBR34KER {args.expected_version}".encode() not in banner:
            raise RuntimeError("version banner mismatch")
        client = fbr34kctl.FramedClient(endpoint, timeout=4.0, retries=2)
        reads = [
            ("hello", client.hello, b"defensive_mode=yes"),
            ("probe-status", lambda: client.command("probe-status"), b"immutable read-only"),
            ("compatibility", lambda: client.command("compatibility"), b"Modules"),
            ("registers", lambda: client.command("system-registers"), b"CurrentEL"),
            ("memory", lambda: client.command("memory-check"), b"Memory map: ok"),
            ("timer", lambda: client.command("timer-test 1"), b"frequency="),
            ("console", lambda: client.command("console-transports"), b"Memory ring"),
        ]
        for name, operation, marker in reads:
            started = time.monotonic()
            response = operation()
            if marker not in response:
                raise RuntimeError(f"{name} missing marker {marker!r}")
            (output / f"{name}.txt").write_bytes(response)
            results.append({"name": name, "passed": True,
                            "duration_ms": int((time.monotonic()-started)*1000)})

        blocked = [
            ("unlock", "bringup-exit unlock", b"permanently read-only"),
            ("module", "module-run hello", b"blocked"),
            ("framebuffer-write", "display-console on", b"blocked"),
            ("irq-mutation", "irq-enable", b"blocked"),
            ("watchdog-mutation", "watchdog-arm 1000", b"blocked"),
        ]
        for name, command, marker in blocked:
            started = time.monotonic()
            try:
                response = client.command(command)
            except fbr34kctl.FBR34KCtlError as exc:
                response = str(exc).encode("utf-8", errors="replace")
            if marker.lower() not in response.lower():
                raise RuntimeError(f"{name} was not demonstrably blocked: {response!r}")
            (output / f"blocked-{name}.txt").write_bytes(response)
            results.append({"name": f"blocked-{name}", "passed": True,
                            "duration_ms": int((time.monotonic()-started)*1000)})
        passed = True
    except Exception as exc:  # noqa: BLE001
        results.append({"name": "failure", "passed": False,
                        "detail": f"{type(exc).__name__}: {exc}"})
    finally:
        endpoint.close()
        raw = (output / "serial.bin").read_bytes()
        (output / "serial.txt").write_text(
            raw.decode("utf-8", errors="replace"), encoding="utf-8")
        (output / "summary.json").write_text(json.dumps({
            "schema_version": 1,
            "passed": passed,
            "immutable_probe": True,
            "steps": results,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
