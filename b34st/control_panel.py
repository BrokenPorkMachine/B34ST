#!/usr/bin/env python3
"""Interactive B34ST control plane for FBR34KER workflows."""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import shlex
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = ROOT / "runtime-artifacts" / "b34st" / "control-panel"
AUTHORIZATION_TEXT = "I OWN OR AM AUTHORIZED TO TEST THIS DEVICE"


class Session:
    def __init__(self) -> None:
        stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        self.directory = ARTIFACT_ROOT / stamp
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log_path = self.directory / "session.log"
        self.record("B34ST control-panel session started")

    def record(self, message: str) -> None:
        timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{timestamp}] {message}\n")

    def run(
        self,
        arguments: list[str],
        *,
        label: str,
        interactive: bool = False,
    ) -> int:
        command = [str(ROOT / "fbr34ker"), *arguments]
        printable = shlex.join(command)
        self.record(f"START {label}: {printable}")
        print(f"\n[{label}]")
        print(f"$ {printable}\n")
        try:
            if interactive:
                return_code = subprocess.run(command, cwd=ROOT, check=False).returncode
            else:
                process = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    print(line, end="")
                    with self.log_path.open("a", encoding="utf-8") as stream:
                        stream.write(line)
                return_code = process.wait()
        except OSError as exc:
            self.record(f"ERROR {label}: {exc}")
            print(f"Unable to start command: {exc}", file=sys.stderr)
            return 1
        self.record(f"END {label}: exit={return_code}")
        print(f"\nResult: {'passed' if return_code == 0 else f'failed ({return_code})'}")
        return return_code


def _clear() -> None:
    if os.isatty(sys.stdout.fileno()):
        print("\033[2J\033[H", end="")


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{label}{suffix}: ").strip() or default
    except (EOFError, KeyboardInterrupt):
        return "q"


def _confirm(label: str) -> bool:
    return _prompt(f"{label} (y/N)").lower() in {"y", "yes"}


def _pause() -> None:
    if os.isatty(sys.stdin.fileno()):
        _prompt("Press Enter to continue")


def _header(session: Session, subtitle: str = "Operator control plane") -> None:
    print("B34ST // FBR34KER")
    print(subtitle)
    print(f"Session: {session.directory.relative_to(ROOT)}")
    print("-" * 64)


def _show_flow() -> None:
    print("  1. Verify host and target")
    print("  2. Build or select a validated monitor")
    print("  3. Establish an explicitly authorized execution session")
    print("  4. Run the existing USBliter8 backend")
    print("  5. Attach the logged FBR34KER runtime console")
    print("  6. Preserve evidence; do not infer stock-runtime state")


def _environment_plan(session: Session, mode: str) -> int:
    ios_version = _prompt("Target iOS version", "17.6.1")
    product = _prompt("Apple product identifier", "iPhone12,1")
    output = session.directory / "environment-plan.json"
    return session.run(
        [
            "b34st",
            "environment-plan",
            "--ios",
            ios_version,
            "--product",
            product,
            "--mode",
            mode,
            "--owner-authorized",
            "--output",
            str(output),
        ],
        label="Environment plan",
    )


def _run_prompted(
    session: Session,
    prefix: list[str],
    *,
    label: str,
    example: str,
    interactive: bool = False,
) -> None:
    print(f"Example arguments: {example}")
    extra = _prompt("Arguments")
    if not extra or extra == "q":
        return
    try:
        arguments = shlex.split(extra)
    except ValueError as exc:
        print(f"Invalid arguments: {exc}")
        _pause()
        return
    session.run(prefix + arguments, label=label, interactive=interactive)
    _pause()


def _simulation(session: Session) -> None:
    _clear()
    _header(session, "Safe simulation workflow")
    print("This path validates the host and starts the monitor under QEMU.")
    if session.run(["doctor"], label="Host readiness") != 0:
        _pause()
        return
    if not _confirm("Build and run the direct QEMU profile"):
        return
    session.run(["run", "direct"], label="QEMU runtime")
    _pause()


def _build_and_verify(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Build, test, and simulation")
        print("  1. Check host readiness")
        print("  2. Build all supported artifacts")
        print("  3. Run non-QEMU verification")
        print("  4. Run full verification with QEMU")
        print("  5. Start direct QEMU runtime")
        print("  6. Start generic-loader QEMU runtime")
        print("  7. Run hardware-probe QEMU profile")
        print("  8. Clean generated artifacts")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        actions = {
            "1": (["doctor"], "Host readiness"),
            "2": (["build"], "Build all artifacts"),
            "3": (["test"], "Project verification"),
            "4": (["test", "--qemu"], "QEMU verification"),
            "5": (["run", "direct"], "Direct QEMU runtime"),
            "6": (["run", "generic"], "Generic-loader QEMU runtime"),
            "7": (["run", "probe"], "Hardware-probe QEMU runtime"),
            "8": (["clean"], "Clean build artifacts"),
        }
        if choice in actions:
            command, label = actions[choice]
            session.run(command, label=label, interactive=choice in {"5", "6"})
            _pause()
        elif choice in {"0", "q", ""}:
            return


def _external_hardware(session: Session) -> None:
    while True:
        _clear()
        _header(session, "External hardware and first-stage execution")
        print("  1. Guided evidence-gated research runtime")
        print("  2. Read-only connected-device inspection")
        print("  3. Query iRecovery device state")
        print("  4. Verify an image/profile for iRecovery")
        print("  5. Run an authorized adapter/bridge bring-up")
        print("  6. Collect from an existing adapter/bridge session")
        print("  7. Recover/reset an authorized adapter session")
        print("  8. Legacy USBliter8 backend (experimental, not evidence)")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            _physical_flow(session)
        elif choice == "2":
            session.run(["device"], label="Device inspection")
            _pause()
        elif choice == "3":
            session.run(["irecovery", "query"], label="iRecovery query")
            _pause()
        elif choice == "4":
            _run_prompted(
                session,
                ["irecovery", "verify"],
                label="iRecovery verification",
                example="--profile profiles/apple-a13-iphone-recovery.json",
            )
        elif choice == "5":
            _run_prompted(
                session,
                ["bringup", "run"],
                label="Authorized first-stage bring-up",
                example="--state-dir runtime-artifacts/device --device-info device.json --profile profiles/apple-a13-iphone-recovery.json --image build-apple/a13/boot.img --bridge-command '...' --authorized-session --authorization-id SESSION --acknowledge-unsigned-code --evidence session.zip",
                interactive=True,
            )
        elif choice == "6":
            _run_prompted(
                session,
                ["bringup", "collect"],
                label="Collect adapter evidence",
                example="--state-dir runtime-artifacts/device --device-info device.json --bridge-command '...' --output collected.zip",
            )
        elif choice == "7":
            _run_prompted(
                session,
                ["bringup", "recover"],
                label="Authorized adapter reset",
                example="--state-dir runtime-artifacts/device --device-info device.json --bridge-command '...' --authorized-session --authorization-id SESSION",
            )
        elif choice == "8":
            print("This legacy path is not accepted as proof of a modified runtime.")
            if _confirm("Open the legacy device-operation menu"):
                session.run(["menu"], label="Legacy maintenance menu", interactive=True)
        elif choice in {"0", "q", ""}:
            return


def _next_stages(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Images, next stages, and deployment")
        print("  1. Build all Apple-family boot images")
        print("  2. Inspect an FBRI boot image")
        print("  3. Build a custom FBRI image")
        print("  4. Dry-run or send through iRecovery")
        print("  5. Run bounded deployment workflow")
        print("  6. Inspect deployment/evidence")
        print("  7. Module compile, inspect, upload, or execute")
        print("  8. Open runtime console/shell")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            session.run(["boot-image", "--help"], label="Boot-image help")
            session.run(["build"], label="Build image artifacts")
            _pause()
        elif choice == "2":
            _run_prompted(
                session,
                ["boot-image", "inspect"],
                label="Inspect boot image",
                example="build-apple/a13/boot.img --json",
            )
        elif choice == "3":
            _run_prompted(
                session,
                ["boot-image", "build"],
                label="Build custom boot image",
                example="--profile profiles/apple-a13-iphone-recovery.json --monitor build-generic/fbr34ker-generic.bin --monitor-load 0x80000000 --monitor-entry 0x80000000 --output custom.img",
            )
        elif choice == "4":
            _run_prompted(
                session,
                ["irecovery", "send"],
                label="iRecovery transfer",
                example="--profile profiles/apple-a13-iphone-recovery.json --image build-apple/a13/boot.img --dry-run",
            )
        elif choice == "5":
            _run_prompted(
                session,
                ["deploy"],
                label="Deployment workflow",
                example="--help",
                interactive=True,
            )
        elif choice == "6":
            _run_prompted(
                session,
                ["inspect"],
                label="Inspect deployment",
                example="--help",
            )
        elif choice == "7":
            _run_prompted(
                session,
                ["module"],
                label="Module workflow",
                example="--help",
                interactive=True,
            )
        elif choice == "8":
            _runtime_console(session)
        elif choice in {"0", "q", ""}:
            return


def _modification_workflows(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Authorized modification workflows")
        print("Modifications are only promoted when exact-target evidence verifies them.")
        print("  1. Evidence-gated kernel/bootstrap workflow")
        print("  2. Validate external modification evidence")
        print("  3. Generate a runtime-stage evidence template")
        print("  4. Load or run a bounded monitor module")
        print("  5. Open the logged runtime shell")
        print("  6. Review legacy mutation-model audit")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            _physical_flow(session)
        elif choice == "2":
            _run_prompted(
                session,
                ["research-runtime", "validate-evidence"],
                label="Validate modification evidence",
                example="evidence.json --stage KERNEL_PATCH_VERIFIED --kernelcache-sha256 HASH",
            )
        elif choice == "3":
            _run_prompted(
                session,
                ["research-runtime", "evidence-template"],
                label="Create evidence template",
                example="KERNEL_PATCH_VERIFIED --kernelcache-sha256 HASH --output patch-evidence.json",
            )
        elif choice == "4":
            _run_prompted(
                session,
                ["module"],
                label="Runtime module workflow",
                example="upload module.fmod --device /dev/ttyACM0 --run",
                interactive=True,
            )
        elif choice == "5":
            _runtime_console(session)
        elif choice == "6":
            print("The research-runtime workflow writes legacy-component-audit.json.")
            print("Run workflow option 1 to generate an audit for the current source tree.")
            _pause()
        elif choice in {"0", "q", ""}:
            return


def _evidence_and_release(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Evidence, validation, and release")
        print("  1. Validate a session bundle")
        print("  2. Explain a failed physical session")
        print("  3. Compare two evidence bundles")
        print("  4. Generate a physical-validation report")
        print("  5. Inspect or replay a session")
        print("  6. Decode crash or trace evidence")
        print("  7. Run release gate")
        print("  8. Package release")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        routes = {
            "1": (["physical-validation", "validate-session"], "Validate session", "session.zip"),
            "2": (["physical-validation", "explain-failure"], "Explain failure", "failure.zip"),
            "3": (["evidence-compare"], "Compare evidence", "first.zip second.zip"),
            "4": (["physical-validation", "candidate-report"], "Candidate report", "--success success.zip --failure failure.zip --recovered recovered.zip --output report.json"),
            "5": (["session"], "Session tools", "--help"),
            "6": (["trace"], "Trace tools", "--help"),
        }
        if choice in routes:
            prefix, label, example = routes[choice]
            _run_prompted(session, prefix, label=label, example=example)
        elif choice == "7":
            session.run(["gate"], label="Release gate")
            _pause()
        elif choice == "8":
            session.run(["package"], label="Package release")
            _pause()
        elif choice in {"0", "q", ""}:
            return


def _physical_flow(session: Session) -> None:
    _clear()
    _header(session, "Guided research-runtime workflow")
    print("This launches the evidence-gated B34ST orchestrator.")
    print("It uses an operator-supplied authorized first-stage adapter and")
    print("requires exact-kernel evidence for patch, policy, trust-cache,")
    print("bootstrap, and userspace-shell states.")
    session.run(
        [
            "research-runtime",
            "guided",
            "--output",
            str(session.directory / "research-runtime"),
        ],
        label="B34ST research-runtime orchestrator",
        interactive=True,
    )
    _pause()


def _runtime_console(session: Session) -> None:
    _clear()
    _header(session, "Runtime console")
    print("Connects to an already-running FBR34KER monitor.")
    print("Console input and output will be saved in this session directory.")
    if _confirm("Connect"):
        session.run(
            ["console", "--log", str(session.directory / "runtime-console.log")],
            label="FBR34KER runtime console",
            interactive=True,
        )
    _pause()


def _show_log(session: Session) -> None:
    _clear()
    _header(session, "Session log")
    print(session.log_path.read_text(encoding="utf-8"), end="")
    _pause()


def run_control_panel() -> int:
    if not os.isatty(sys.stdin.fileno()) or not os.isatty(sys.stdout.fileno()):
        print("B34ST control panel requires an interactive TTY", file=sys.stderr)
        return 1

    session = Session()
    while True:
        _clear()
        _header(session)
        print("What are you trying to achieve?\n")
        print("  1. External hardware / USBliter8 / first-stage execution")
        print("  2. Load images, next stages, modules, or deployment")
        print("  3. Authorized runtime modifications and evidence")
        print("  4. Build, test, and QEMU simulation")
        print("  5. Runtime console / logger / shell")
        print("  6. Evidence, validation, and release")
        print("  7. Create a bounded environment plan")
        print("  8. Open the FBR34KER maintenance menu")
        print("  9. View this B34ST session log")
        print("  0. Exit")
        choice = _prompt("Selection", "1")
        if choice == "1":
            _external_hardware(session)
        elif choice == "2":
            _next_stages(session)
        elif choice == "3":
            _modification_workflows(session)
        elif choice == "4":
            _build_and_verify(session)
        elif choice == "5":
            _runtime_console(session)
        elif choice == "6":
            _evidence_and_release(session)
        elif choice == "7":
            _clear()
            _header(session, "Environment planning")
            mode = _prompt("Mode (simulation/research-runtime)", "simulation")
            if mode not in {"simulation", "research-runtime"}:
                print("Invalid mode.")
            else:
                _environment_plan(session, mode)
            _pause()
        elif choice == "8":
            session.run(
                ["menu"],
                label="FBR34KER maintenance menu",
                interactive=True,
            )
        elif choice == "9":
            _show_log(session)
        elif choice in {"0", "q", ""}:
            session.record("B34ST control-panel session ended")
            print(f"Session log: {session.log_path.relative_to(ROOT)}")
            return 0


if __name__ == "__main__":
    raise SystemExit(run_control_panel())
