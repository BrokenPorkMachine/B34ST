#!/usr/bin/env python3
"""Interactive B34ST control plane for FBR34KER workflows."""

from __future__ import annotations

import datetime as dt
import argparse
import json
import os
import pathlib
import re
import shlex
import shutil
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
                script_tool = shutil.which("script")
                if script_tool:
                    safe_label = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
                    transcript = self.directory / f"{safe_label or 'interactive'}.typescript"
                    return_code = subprocess.run(
                        [script_tool, "-q", str(transcript), *command],
                        cwd=ROOT,
                        check=False,
                    ).returncode
                    self.record(f"Interactive transcript: {transcript.relative_to(ROOT)}")
                else:
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


def _ipsw_workflows(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Targeted IPSW and restore workflows")
        print("  1. List firmware for a product")
        print("  2. List currently signed firmware")
        print("  3. Download a targeted IPSW")
        print("  4. Inspect and verify a local IPSW")
        print("  5. Plan a signed update preserving data")
        print("  6. Execute a signed update preserving data")
        print("  7. Plan or execute an erase restore")
        print("  8. Plan a tethered downgrade")
        print("  9. Execute through an external tether adapter")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice in {"1", "2"}:
            product = _prompt("Apple product identifier", "iPhone12,1")
            command = ["ipsw", "catalog", "--product", product]
            if choice == "2":
                command.append("--signed-only")
            session.run(command, label="IPSW firmware catalog")
            _pause()
        elif choice == "3":
            product = _prompt("Apple product identifier", "iPhone12,1")
            version = _prompt("Exact iOS version (blank to select by build)")
            build = _prompt("Exact build (blank if version is unique)")
            command = ["ipsw", "download", "--product", product]
            if version:
                command += ["--version", version]
            if build:
                command += ["--build", build]
            if _confirm("Require currently signed firmware"):
                command.append("--signed-only")
            command += [
                "--output-dir",
                str(session.directory / "ipsw"),
                "--manifest",
                str(session.directory / "ipsw-download.json"),
            ]
            session.run(command, label="Targeted IPSW download", interactive=True)
            _pause()
        elif choice == "4":
            _run_prompted(
                session,
                ["ipsw", "inspect"],
                label="Inspect IPSW",
                example="downloads/ipsw/file.ipsw --product iPhone12,1",
            )
        elif choice in {"5", "6", "7"}:
            product = _prompt("Apple product identifier", "iPhone12,1")
            path = _prompt("Local IPSW path")
            command = ["ipsw", "upgrade", "--product", product, "--ipsw", path]
            if choice == "7" and _confirm("Erase all device data"):
                command.append("--erase")
            if choice in {"6", "7"}:
                print("Back up the device first. Restore operations can cause irreversible data loss.")
                owner = _prompt(f'Type "{AUTHORIZATION_TEXT.replace("TEST", "RESTORE")}"')
                confirm = _prompt('Type "START SIGNED IPSW RESTORE"')
                command += [
                    "--execute",
                    "--owner-authorization",
                    owner,
                    "--confirm",
                    confirm,
                    "--evidence",
                    str(session.directory / "signed-restore.json"),
                ]
            session.run(command, label="Signed IPSW restore", interactive=True)
            _pause()
        elif choice in {"8", "9"}:
            product = _prompt("Apple product identifier", "iPhone12,1")
            path = _prompt("Unsigned target IPSW path")
            command = [
                "ipsw",
                "tethered-downgrade",
                "--product",
                product,
                "--ipsw",
                path,
                "--evidence",
                str(session.directory / "tethered-downgrade.json"),
            ]
            if choice == "9":
                adapter = _prompt("External tether adapter command")
                owner = _prompt(f'Type "{AUTHORIZATION_TEXT.replace("TEST", "RESTORE")}"')
                confirm = _prompt('Type "START TETHERED DOWNGRADE"')
                command += [
                    "--adapter-command",
                    adapter,
                    "--execute",
                    "--owner-authorization",
                    owner,
                    "--confirm",
                    confirm,
                ]
            session.run(command, label="Tethered downgrade", interactive=True)
            _pause()
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


def _device_snapshot(session: Session) -> dict:
    from host.device_dashboard import build_snapshot

    args = argparse.Namespace(
        device_info=pathlib.Path(os.environ["B34ST_DEVICE_INFO"])
        if os.environ.get("B34ST_DEVICE_INFO") else None,
        recovery_only=False,
        udid=None,
        ecid=None,
        ideviceinfo="ideviceinfo",
        idevice_id="idevice_id",
        irecovery="irecovery",
        catalog=os.environ.get(
            "B34ST_IPSW_CATALOG",
            "https://api.ipsw.me/v4/device/{product}?type=ipsw",
        ),
        timeout=8.0,
        catalog_timeout=5.0,
    )
    try:
        snapshot = build_snapshot(args)
    except Exception as exc:
        session.record(f"Dashboard refresh failed: {exc}")
        return {
            "connected": False,
            "device": None,
            "firmware": {"available": False, "error": str(exc)},
            "profiles": [],
            "actions": [],
        }
    path = session.directory / "device-dashboard.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    session.record(f"Dashboard refreshed: connected={snapshot.get('connected')}")
    return snapshot


def _print_dashboard(snapshot: dict) -> None:
    if not snapshot.get("connected"):
        print("Device: not detected")
        print("Connect an unlocked normal-mode device, or place it in Recovery/DFU.")
        error = snapshot.get("firmware", {}).get("error")
        if error:
            print(f"Catalog/device note: {error}")
        return
    device = snapshot["device"]
    firmware = snapshot.get("firmware", {})
    latest = firmware.get("latest_signed") or {}
    latest_build = f" ({latest['build']})" if latest.get("build") else ""
    print(f"Device:          {device.get('name') or device.get('device_name') or 'Unknown'}")
    print(f"Product:         {device.get('product') or 'Unknown'}")
    print(f"Mode:            {device.get('mode') or 'Unknown'}")
    print(f"Board/model:     {device.get('model') or 'Unknown'}")
    print(f"Launch firmware: {device.get('launch_version') or 'Not in reviewed database'}")
    print(f"Current version: {device.get('current_version') or 'Unavailable in this mode'}")
    print(f"Current build:   {device.get('current_build') or 'Unavailable in this mode'}")
    print(f"Latest signed:   {latest.get('version') or 'Catalog unavailable'}{latest_build}")
    print(f"Exact profiles:  {sum(1 for item in snapshot.get('profiles', []) if item.get('exact'))}")
    if not firmware.get("available") and firmware.get("error"):
        print(f"Firmware note:   {firmware['error']}")


def _action_details(action: dict) -> None:
    from host.device_dashboard import procedure, required_materials

    print(action["title"])
    print("-" * 64)
    print(f"Available: {'YES' if action['available'] else 'NO'}")
    print(f"Reason: {action['reason']}")
    print("\nRequired materials:")
    for item in required_materials(action["id"]):
        print(f"  - {item}")
    print("\nStep-by-step:")
    for index, step in enumerate(procedure(action["id"]), 1):
        print(f"  {index}. {step}")
    print("\nHow to proceed:")
    if action["available"]:
        print("  Confirm the prerequisites, continue below, and B34ST will launch")
        print("  the external operation. When it exits, B34ST records the result")
        print("  and returns to the refreshed device dashboard.")
    else:
        print("  Resolve the stated requirement, then refresh the dashboard.")


def _run_device_action(session: Session, snapshot: dict, action: dict) -> None:
    _clear()
    _header(session, "Device-specific workflow")
    _action_details(action)
    if not action["available"] or not _confirm("Proceed with this workflow"):
        _pause()
        return
    device = snapshot["device"]
    product = device.get("product")
    firmware = snapshot.get("firmware", {})
    latest = firmware.get("latest_signed") or {}
    action_id = action["id"]
    if action_id == "inspect":
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        _pause()
        return
    if action_id == "download-latest":
        command = [
            "ipsw", "download", "--product", product,
            "--version", latest["version"], "--build", latest["build"],
            "--signed-only",
            "--output-dir", str(session.directory / "ipsw"),
            "--manifest", str(session.directory / "latest-ipsw.json"),
        ]
        session.run(command, label="Download latest signed IPSW", interactive=True)
        _pause()
        return
    if action_id in {"upgrade", "signed-restore"}:
        path = _prompt("Verified local IPSW path")
        if not path:
            return
        command = ["ipsw", "upgrade", "--product", product, "--ipsw", path]
        if action_id == "signed-restore":
            command.append("--erase")
        print("\nB34ST will first run idevicerestore in no-action planning mode.")
        plan_result = session.run(command, label="Restore preflight", interactive=True)
        if plan_result != 0 or not _confirm("Preflight completed. Execute the restore"):
            _pause()
            return
        owner = _prompt('Type "I OWN OR AM AUTHORIZED TO RESTORE THIS DEVICE"')
        confirm = _prompt('Type "START SIGNED IPSW RESTORE"')
        command += [
            "--execute",
            "--owner-authorization", owner,
            "--confirm", confirm,
            "--evidence", str(session.directory / "signed-restore.json"),
        ]
        session.run(command, label="Signed IPSW restore", interactive=True)
        _pause()
        return
    if action_id == "research-runtime":
        _physical_flow(session)
        return
    if action_id == "tethered-downgrade":
        path = _prompt("Verified unsigned target IPSW path")
        if not path:
            return
        plan = [
            "ipsw", "tethered-downgrade",
            "--product", product,
            "--ipsw", path,
            "--evidence", str(session.directory / "tethered-downgrade.json"),
        ]
        if session.run(plan, label="Tethered downgrade plan") != 0:
            _pause()
            return
        if not _confirm("Plan reviewed. Continue to external tether adapter"):
            _pause()
            return
        adapter = _prompt("External tether adapter command")
        owner = _prompt('Type "I OWN OR AM AUTHORIZED TO RESTORE THIS DEVICE"')
        confirm = _prompt('Type "START TETHERED DOWNGRADE"')
        session.run(
            plan + [
                "--adapter-command", adapter,
                "--execute",
                "--owner-authorization", owner,
                "--confirm", confirm,
            ],
            label="External tethered downgrade",
            interactive=True,
        )
        _pause()
        return
    if action_id == "runtime-console":
        _runtime_console(session)


def _device_dashboard(session: Session) -> None:
    snapshot = _device_snapshot(session)
    while True:
        _clear()
        _header(session, "Connected device dashboard")
        _print_dashboard(snapshot)
        print("\nAvailable device-specific actions:")
        actions = snapshot.get("actions", [])
        for index, action in enumerate(actions, 1):
            marker = "READY" if action["available"] else "BLOCKED"
            print(f"  {index}. [{marker}] {action['title']}")
        print("  R. Refresh device and firmware information")
        print("  T. Open all project tools")
        print("  L. View B34ST session log")
        print("  0. Exit")
        default = "1" if actions else "T"
        choice = _prompt("Selection", default)
        if choice.lower() == "r":
            snapshot = _device_snapshot(session)
        elif choice.lower() == "t":
            return
        elif choice.lower() == "l":
            _show_log(session)
        elif choice in {"0", "q", ""}:
            raise SystemExit(0)
        elif choice.isdigit() and 1 <= int(choice) <= len(actions):
            _run_device_action(session, snapshot, actions[int(choice) - 1])
            snapshot = _device_snapshot(session)


def run_control_panel() -> int:
    if not os.isatty(sys.stdin.fileno()) or not os.isatty(sys.stdout.fileno()):
        print("B34ST control panel requires an interactive TTY", file=sys.stderr)
        return 1

    session = Session()
    try:
        _device_dashboard(session)
    except SystemExit:
        session.record("B34ST control-panel session ended")
        print(f"Session log: {session.log_path.relative_to(ROOT)}")
        return 0
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
        print("  7. Targeted IPSW downloads, upgrades, and tethered downgrades")
        print("  8. Create a bounded environment plan")
        print("  9. Open the FBR34KER maintenance menu")
        print(" 10. View this B34ST session log")
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
            _ipsw_workflows(session)
        elif choice == "8":
            _clear()
            _header(session, "Environment planning")
            mode = _prompt("Mode (simulation/research-runtime)", "simulation")
            if mode not in {"simulation", "research-runtime"}:
                print("Invalid mode.")
            else:
                _environment_plan(session, mode)
            _pause()
        elif choice == "9":
            session.run(
                ["menu"],
                label="FBR34KER maintenance menu",
                interactive=True,
            )
        elif choice == "10":
            _show_log(session)
        elif choice in {"0", "q", ""}:
            session.record("B34ST control-panel session ended")
            print(f"Session log: {session.log_path.relative_to(ROOT)}")
            return 0


if __name__ == "__main__":
    raise SystemExit(run_control_panel())
