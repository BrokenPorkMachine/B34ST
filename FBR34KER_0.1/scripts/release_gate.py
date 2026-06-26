#!/usr/bin/env python3
"""Run the FBR34KER release gate and preserve evidence on every outcome."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict, dataclass

ROOT = pathlib.Path(__file__).resolve().parents[1]


@dataclass
class StageResult:
    name: str
    status: str
    returncode: int | None
    duration_ms: int
    command: list[str]
    log: str | None
    detail: str


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-")


def display_command(command: list[str]) -> list[str]:
    """Remove host-specific absolute executable paths from persisted evidence."""
    displayed: list[str] = []
    for index, value in enumerate(command):
        path = pathlib.Path(value)
        if index == 0 and path.is_absolute():
            displayed.append(path.name)
        else:
            displayed.append(value)
    return displayed


def sanitize_output(value: str) -> str:
    sanitized = value.replace(str(ROOT), ".")
    home = pathlib.Path.home()
    if str(home) not in {"", "/"}:
        sanitized = sanitized.replace(str(home), "~")
    return sanitized


def run_stage(
    name: str,
    command: list[str],
    output: pathlib.Path,
    timeout: float,
    *,
    environment: dict[str, str] | None = None,
) -> StageResult:
    started = time.monotonic()
    log_name = f"{safe_name(name)}.log"
    log_path = output / log_name
    process: subprocess.Popen[str] | None = None
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                returncode = process.wait(timeout=timeout)
                status = "passed" if returncode == 0 else "failed"
                detail = f"exit={returncode}"
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=2.0)
                returncode = None
                status = "failed"
                detail = f"timeout after {timeout:g}s"
                log.write(f"\nTimed out after {timeout:g} seconds.\n")
                log.flush()
        # Compiler command lines can contain the absolute checkout path through
        # reproducibility flags. Normalize the completed log in place.
        log_path.write_text(
            sanitize_output(log_path.read_text(encoding="utf-8", errors="replace")),
            encoding="utf-8",
        )
        return StageResult(
            name,
            status,
            returncode,
            int((time.monotonic() - started) * 1000),
            display_command(command),
            log_name,
            detail,
        )
    except OSError as exc:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        log_path.write_text(
            sanitize_output(f"{type(exc).__name__}: {exc}\n"),
            encoding="utf-8",
        )
        return StageResult(
            name,
            "failed",
            None,
            int((time.monotonic() - started) * 1000),
            display_command(command),
            log_name,
            f"{type(exc).__name__}: {exc}",
        )


def blocked_stage(name: str, command: list[str], reason: str) -> StageResult:
    return StageResult(name, "blocked", None, 0, display_command(command), None, reason)


def write_summary(
    output: pathlib.Path,
    version: str,
    release_stage: str,
    stages: list[StageResult],
    started: float,
) -> pathlib.Path:
    required = ("host-readiness", "verify", "integration", "smoke", "generic-smoke", "probe-smoke", "diagnostics")
    by_name = {stage.name: stage for stage in stages}
    passed = all(by_name.get(name) is not None and by_name[name].status == "passed"
                 for name in required)
    summary = {
        "schema_version": 1,
        "project": "FBR34KER",
        "version": version,
        "release_stage": release_stage,
        "passed": passed,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "stages": [asdict(stage) for stage in stages],
    }
    path = output / "summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def refresh_diagnostics_archive(diagnostics: pathlib.Path, gate: pathlib.Path) -> None:
    if not diagnostics.is_dir():
        return
    destination = diagnostics / "gate"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(gate, destination)
    archive = diagnostics.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(diagnostics.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(diagnostics.parent))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--release-stage", default="development")
    parser.add_argument("--output", type=pathlib.Path,
                        default=pathlib.Path("runtime-artifacts/gate"))
    parser.add_argument("--diagnostics", type=pathlib.Path,
                        default=pathlib.Path("runtime-artifacts/diagnostics"))
    parser.add_argument("--verify-timeout", type=float, default=300.0)
    parser.add_argument("--integration-timeout", type=float, default=180.0)
    parser.add_argument("--smoke-timeout", type=float, default=180.0)
    parser.add_argument("--diagnostics-timeout", type=float, default=120.0)
    arguments = parser.parse_args(argv)

    for value in (
        arguments.verify_timeout,
        arguments.integration_timeout,
        arguments.smoke_timeout,
        arguments.diagnostics_timeout,
    ):
        if value <= 0:
            parser.error("timeouts must be greater than zero")

    output = arguments.output.resolve()
    diagnostics = arguments.diagnostics.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    stages: list[StageResult] = []

    readiness_command = [sys.executable, "scripts/doctor.py", "--require-qemu"]
    readiness = run_stage(
        "host-readiness", readiness_command, output, 30.0,
        environment={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    stages.append(readiness)

    verify_command = ["make", "verify"]
    verify = run_stage("verify", verify_command, output, arguments.verify_timeout)
    stages.append(verify)

    qemu_ready = readiness.status == "passed"
    build_ready = verify.status == "passed"
    if qemu_ready and build_ready:
        stages.append(run_stage(
            "integration", ["make", "integration"], output,
            arguments.integration_timeout,
        ))
        stages.append(run_stage(
            "smoke", ["make", "smoke"], output,
            arguments.smoke_timeout,
        ))
        stages.append(run_stage(
            "generic-smoke", ["make", "generic-qemu-smoke"], output,
            arguments.smoke_timeout,
        ))
        stages.append(run_stage(
            "probe-smoke", ["make", "probe-qemu-smoke"], output,
            arguments.smoke_timeout,
        ))
    else:
        reasons: list[str] = []
        if not qemu_ready:
            reasons.append("QEMU host readiness failed")
        if not build_ready:
            reasons.append("non-QEMU verification failed")
        reason = "; ".join(reasons)
        stages.append(blocked_stage("integration", ["make", "integration"], reason))
        stages.append(blocked_stage("smoke", ["make", "smoke"], reason))
        stages.append(blocked_stage("generic-smoke", ["make", "generic-qemu-smoke"], reason))
        stages.append(blocked_stage("probe-smoke", ["make", "probe-qemu-smoke"], reason))

    # Write gate evidence before diagnostics so partial results survive even if
    # diagnostics collection itself cannot complete.
    write_summary(output, arguments.version, arguments.release_stage, stages, started)

    diagnostics_stage = run_stage(
        "diagnostics", ["make", "diagnostics"], output,
        arguments.diagnostics_timeout,
    )
    stages.append(diagnostics_stage)
    summary_path = write_summary(output, arguments.version, arguments.release_stage, stages, started)
    refresh_diagnostics_archive(diagnostics, output)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["passed"]:
        print(f"FBR34KER {arguments.version} release gate passed")
        print(output)
        print(diagnostics.with_suffix(".zip"))
        return 0

    print(f"FBR34KER {arguments.version} release gate failed", file=sys.stderr)
    for stage in stages:
        if stage.status != "passed":
            print(f"- {stage.name}: {stage.status} ({stage.detail})", file=sys.stderr)
    print(f"gate evidence: {output}", file=sys.stderr)
    if diagnostics.exists():
        print(f"diagnostics: {diagnostics.with_suffix('.zip')}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
