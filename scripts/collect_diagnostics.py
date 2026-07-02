#!/usr/bin/env python3

"""Collect a privacy-conscious FBR34KER build and runtime diagnostics bundle."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import platform
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def sanitize_text(value: str) -> str:
    sanitized = value.replace(str(ROOT), ".")
    home = pathlib.Path.home()
    if str(home) not in {"", "/"}:
        sanitized = sanitized.replace(str(home), "~")
    return sanitized


def display_command(command: list[str]) -> list[str]:
    displayed: list[str] = []
    for index, value in enumerate(command):
        path = pathlib.Path(value)
        displayed.append(path.name if index == 0 and path.is_absolute() else value)
    return displayed


def hash_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], timeout: float = 15.0) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return {
            "command": display_command(command),
            "returncode": completed.returncode,
            "output": sanitize_text(completed.stdout),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": display_command(command), "returncode": None, "output": sanitize_text(str(exc))}


def copy_if_present(source: pathlib.Path, destination: pathlib.Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    elif source.is_dir():
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=pathlib.Path,
        default=pathlib.Path("runtime-artifacts/diagnostics"),
    )
    parser.add_argument(
        "--smoke-dir", type=pathlib.Path,
        default=pathlib.Path("runtime-artifacts/smoke"),
        help="optional QEMU smoke-test directory to include",
    )
    parser.add_argument(
        "--gate-dir", type=pathlib.Path,
        default=pathlib.Path("runtime-artifacts/gate"),
        help="optional release-gate evidence directory to include",
    )
    parser.add_argument(
        "--skip-tool-probes", action="store_true", help=argparse.SUPPRESS,
    )
    arguments = parser.parse_args(argv)

    output = arguments.output.resolve()
    smoke_dir = arguments.smoke_dir.resolve()
    gate_dir = arguments.gate_dir.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    commands = {
        "doctor": [sys.executable, "scripts/doctor.py", "--json"],
        "python": [sys.executable, "--version"],
        "clang": ["clang", "--version"],
        "lld": ["ld.lld", "--version"],
        "objcopy": ["llvm-objcopy", "--version"],
        "qemu": ["qemu-system-aarch64", "--version"],
        "make": ["make", "--version"],
    }
    if arguments.skip_tool_probes:
        command_results = {
            name: {"command": display_command(command), "returncode": 0,
                   "output": "skipped by deterministic unit-test mode"}
            for name, command in commands.items()
        }
    else:
        command_results = {name: run(command) for name, command in commands.items()}
    (output / "tool-commands.json").write_text(
        json.dumps(command_results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    system = {
        "schema_version": 1,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }
    (output / "system.json").write_text(
        json.dumps(system, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    artifact_paths = [
        ROOT / "build/fbr34ker.bin",
        ROOT / "build/fbr34ker.elf",
        ROOT / "build/fbr34ker.map",
        ROOT / "build-generic/fbr34ker-generic.bin",
        ROOT / "build-generic/fbr34ker-generic.elf",
        ROOT / "build-generic/fbr34ker-generic.map",
        ROOT / "build/modules/hello-dynamic.fmod",
        ROOT / "build-integration/fbr34ker-test.bin",
        ROOT / "build-integration/fbr34ker-test.elf",
        ROOT / "build-integration/modules/hello-dynamic.fmod",
        ROOT / "build-loader/fbr34ker-qemu-loader.bin",
        ROOT / "build-loader/fbr34ker-qemu-loader.elf",
        ROOT / "build-loader/fbr34ker-qemu-loader.map",
        ROOT / "build-hardware-probe/fbr34ker-hardware-probe.bin",
        ROOT / "build-hardware-probe/fbr34ker-hardware-probe.elf",
        ROOT / "build-hardware-probe/fbr34ker-hardware-probe.map",
    ]
    artifacts = []
    for path in artifact_paths:
        if path.is_file():
            artifacts.append({
                "path": path.relative_to(ROOT).as_posix(),
                "size": path.stat().st_size,
                "sha256": hash_file(path),
            })
    (output / "artifacts.json").write_text(
        json.dumps(artifacts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    layout_commands = {
        "qemu": [sys.executable, "scripts/verify_layout.py", "build/fbr34ker.elf",
                 "--expected-entry", "0x40080000"],
        "generic": [sys.executable, "scripts/verify_layout.py",
                    "build-generic/fbr34ker-generic.elf",
                    "--expected-entry", "0x80000000"],
        "qemu-loader": [sys.executable, "scripts/verify_layout.py",
                        "build-loader/fbr34ker-qemu-loader.elf",
                        "--expected-entry", "0x40080000",
                        "--profile", "loader"],
        "hardware-probe": [sys.executable, "scripts/verify_layout.py",
                           "build-hardware-probe/fbr34ker-hardware-probe.elf",
                           "--expected-entry", "0x80000000"],
    }
    if arguments.skip_tool_probes:
        layouts = {
            name: {
                "command": display_command(command),
                "returncode": 0,
                "output": "skipped by deterministic unit-test mode",
            }
            for name, command in layout_commands.items()
        }
    else:
        layouts = {name: run(command) for name, command in layout_commands.items()}
    (output / "layout.json").write_text(
        json.dumps(layouts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for name in (
        "README.md", "RELEASE_NOTES.md", "AUDIT_REPORT.md",
        "BUILD_VALIDATION.md", "SECURITY.md", "RELEASE_MANIFEST.json",
        "CHECKSUMS.sha256",
    ):
        copy_if_present(ROOT / name, output / "project" / name)
    copy_if_present(smoke_dir, output / "smoke")
    copy_if_present(ROOT / "runtime-artifacts/generic-smoke", output / "generic-smoke")
    copy_if_present(ROOT / "runtime-artifacts/probe-smoke", output / "probe-smoke")
    # Avoid recursive copying when diagnostics are collected from inside the
    # gate runner. The gate directory is always a sibling of diagnostics in
    # the standard layout.
    if gate_dir != output and output not in gate_dir.parents:
        copy_if_present(gate_dir, output / "gate")

    archive = output.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(output.parent))
    print(output)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
