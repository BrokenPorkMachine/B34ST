#!/usr/bin/env python3
"""Check whether the host can build and run FBR34KER."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.tls_support import tls_ca_status

MINIMUM_PYTHON = (3, 10)


@dataclass
class Check:
    name: str
    required: bool
    ok: bool
    path: str | None
    detail: str


def _augmented_path() -> str:
    entries = os.environ.get("PATH", "").split(os.pathsep)
    for candidate in (
        "/opt/homebrew/opt/llvm/bin",
        "/usr/local/opt/llvm/bin",
    ):
        if pathlib.Path(candidate).is_dir() and candidate not in entries:
            entries.insert(0, candidate)
    return os.pathsep.join(entries)


def _which(name: str, path: str) -> str | None:
    return shutil.which(name, path=path)


def _version(executable: str, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            [executable, *arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unable to query version: {exc}"
    first = completed.stdout.strip().splitlines()
    return first[0] if first else f"exit={completed.returncode}"


def _clang_target_check(clang: str, path: str) -> tuple[bool, str]:
    source = "int fbr34ker_target_probe(void) { return 0; }\n"
    try:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "probe.o"
            completed = subprocess.run(
                [
                    clang,
                    "--target=aarch64-none-elf",
                    "-ffreestanding",
                    "-fno-builtin",
                    "-x",
                    "c",
                    "-c",
                    "-",
                    "-o",
                    str(output),
                ],
                input=source,
                cwd=ROOT,
                env={**os.environ, "PATH": path},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            if completed.returncode == 0 and output.is_file():
                return True, "aarch64-none-elf compile probe passed"
            detail = completed.stdout.strip() or f"exit={completed.returncode}"
            return False, detail
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def run_checks(require_qemu: bool) -> tuple[list[Check], dict[str, object]]:
    path = _augmented_path()
    checks: list[Check] = []

    python_ok = sys.version_info >= MINIMUM_PYTHON
    checks.append(Check(
        "python",
        True,
        python_ok,
        sys.executable,
        f"Python {platform.python_version()} (requires >= 3.10)",
    ))

    tls_ok, tls_path, tls_detail = tls_ca_status()
    checks.append(Check(
        "tls-ca-certificates",
        True,
        tls_ok,
        tls_path,
        tls_detail,
    ))

    specifications = (
        ("make", True, ("--version",)),
        ("clang", True, ("--version",)),
        ("ld.lld", True, ("--version",)),
        ("llvm-objcopy", True, ("--version",)),
        ("qemu-system-aarch64", require_qemu, ("--version",)),
        ("openssl", False, ("version",)),
        ("minisign", False, ("-v",)),
        ("irecovery", False, ("--version",)),
        ("ideviceinfo", False, ("--version",)),
        ("idevice_id", False, ("--version",)),
        ("idevicerestore", False, ("--version",)),
        ("ipsw", False, ("version",)),
        ("curl", False, ("--version",)),
    )
    found: dict[str, str] = {}
    for name, required, arguments in specifications:
        executable = _which(name, path)
        if executable is None:
            checks.append(Check(name, required, not required, None,
                                "not installed" if required else "optional; not installed"))
            continue
        found[name] = executable
        checks.append(Check(name, required, True, executable,
                            _version(executable, *arguments)))

    clang = found.get("clang")
    if clang is not None:
        ok, detail = _clang_target_check(clang, path)
        checks.append(Check("clang-aarch64-target", True, ok, clang, detail))
    else:
        checks.append(Check("clang-aarch64-target", True, False, None,
                            "clang is unavailable"))

    metadata: dict[str, object] = {
        "schema_version": 1,
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "require_qemu": require_qemu,
    }
    return checks, metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-qemu", action="store_true",
                        help="treat qemu-system-aarch64 as required")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON")
    arguments = parser.parse_args(argv)

    checks, metadata = run_checks(arguments.require_qemu)
    passed = all(check.ok for check in checks if check.required)
    if arguments.json:
        print(json.dumps({
            **metadata,
            "passed": passed,
            "checks": [
                {
                    **asdict(check),
                    "path": pathlib.Path(check.path).name if check.path else None,
                }
                for check in checks
            ],
        }, indent=2, sort_keys=True))
    else:
        print("FBR34KER host readiness")
        for check in checks:
            marker = "PASS" if check.ok else "FAIL"
            requirement = "required" if check.required else "optional"
            print(f"[{marker}] {check.name} ({requirement})")
            print(f"       {check.detail}")
        print("Host readiness:", "passed" if passed else "failed")
        if not passed:
            print("On macOS, install missing runtime tools with: brew install llvm qemu")
        if not any(check.name == "irecovery" and check.ok for check in checks):
            print("Optional A12/A13 recovery transport: brew install libirecovery")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
