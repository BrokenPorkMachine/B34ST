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

SECURITY_MODEL_CONFIG_PATH = pathlib.Path("~/.config/fbr34ker/security-model").expanduser()

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = ROOT / "runtime-artifacts" / "b34st" / "control-panel"
AUTHORIZATION_TEXT = "I OWN OR AM AUTHORIZED TO TEST THIS DEVICE"


class Colors:
    if os.isatty(1):
        BOLD = "\033[1m"
        DIM = "\033[2m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        CYAN = "\033[36m"
        RESET = "\033[0m"
    else:
        BOLD = DIM = RED = GREEN = YELLOW = BLUE = CYAN = RESET = ""


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
                    transcript = (
                        self.directory / f"{safe_label or 'interactive'}.typescript"
                    )
                    return_code = subprocess.run(
                        [script_tool, "-q", str(transcript), *command],
                        cwd=ROOT,
                        check=False,
                    ).returncode
                    self.record(
                        f"Interactive transcript: {transcript.relative_to(ROOT)}"
                    )
                else:
                    return_code = subprocess.run(
                        command, cwd=ROOT, check=False
                    ).returncode
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
        print(
            f"\nResult: {'passed' if return_code == 0 else f'failed ({return_code})'}"
        )
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
        _header(session, "A12+ USBliter8 — Pwn, Inspect, Jailbreak")
        print("  1. Pwn & Inspect  — USBliter8 exploit + full protection audit")
        print(
            "  2. USBliter8 jailbreak  — full A12+ chain (PWNDFU -> monitor -> exploit)"
        )
        print("  3. Guided evidence-gated research runtime")
        print("  4. Read-only connected-device inspection")
        print("  5. Query iRecovery device state")
        print("  6. Verify an image/profile for iRecovery")
        print("  7. Run an authorized adapter/bridge bring-up")
        print("  8. Collect from an existing adapter/bridge session")
        print("  9. Recover/reset an authorized adapter session")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            _usbliter8_pwn_and_inspect(session)
        elif choice == "2":
            _usbliter8_jailbreak(session)
        elif choice == "3":
            _physical_flow(session)
        elif choice == "4":
            session.run(["device"], label="Device inspection")
            _pause()
        elif choice == "5":
            session.run(["irecovery", "query"], label="iRecovery query")
            _pause()
        elif choice == "6":
            _run_prompted(
                session,
                ["irecovery", "verify"],
                label="iRecovery verification",
                example="--profile profiles/apple-a13-iphone-recovery.json",
            )
        elif choice == "7":
            _run_prompted(
                session,
                ["bringup", "run"],
                label="Authorized first-stage bring-up",
                example="--state-dir runtime-artifacts/device --device-info device.json --profile profiles/apple-a13-iphone-recovery.json --image build-apple/a13/boot.img --bridge-command '...' --authorized-session --authorization-id SESSION --acknowledge-unsigned-code --evidence session.zip",
                interactive=True,
            )
        elif choice == "8":
            _run_prompted(
                session,
                ["bringup", "collect"],
                label="Collect adapter evidence",
                example="--state-dir runtime-artifacts/device --device-info device.json --bridge-command '...' --output collected.zip",
            )
        elif choice == "9":
            _run_prompted(
                session,
                ["bringup", "recover"],
                label="Authorized adapter reset",
                example="--state-dir runtime-artifacts/device --device-info device.json --bridge-command '...' --authorized-session --authorization-id SESSION",
            )
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
                print(
                    "Back up the device first. Restore operations can cause irreversible data loss."
                )
                owner = _prompt(
                    f'Type "{AUTHORIZATION_TEXT.replace("TEST", "RESTORE")}"'
                )
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
                owner = _prompt(
                    f'Type "{AUTHORIZATION_TEXT.replace("TEST", "RESTORE")}"'
                )
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
        print(
            "Modifications are only promoted when exact-target evidence verifies them."
        )
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
            print(
                "Run workflow option 1 to generate an audit for the current source tree."
            )
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
            "1": (
                ["physical-validation", "validate-session"],
                "Validate session",
                "session.zip",
            ),
            "2": (
                ["physical-validation", "explain-failure"],
                "Explain failure",
                "failure.zip",
            ),
            "3": (["evidence-compare"], "Compare evidence", "first.zip second.zip"),
            "4": (
                ["physical-validation", "candidate-report"],
                "Candidate report",
                "--success success.zip --failure failure.zip --recovered recovered.zip --output report.json",
            ),
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


def _usbliter8_jailbreak(session: Session) -> int:
    _clear()
    _header(session, "A12+ USBliter8 Jailbreak")
    print("Targets A12+ devices (CPID 0x8015 and above) in DFU mode.")
    print("Exploit: DWC3 USB controller firmware patch (USBliter8)")
    print("Payload: FBR34KER monitor + full post-exploit chain")
    print("Chain:  PWNDFU  ->  rogue DWC3 chain  ->  kernel patches")
    print("        ->  secure-boot bypass  ->  trust-cache injection")
    print("        ->  persistence  ->  evasion  ->  runtime shell")
    print()
    print("Evidence will be written to this session directory.")
    print()

    owner = _prompt(
        f'Type "{AUTHORIZATION_TEXT}" to confirm device ownership',
        "",
    )
    if owner != AUTHORIZATION_TEXT:
        print("Authorization not confirmed. Aborting.")
        session.record("USBliter8 jailbreak aborted: authorization not confirmed")
        _pause()
        return 1

    exploit_script = ROOT / "scripts" / "run_exploit.py"
    if not exploit_script.is_file():
        print(f"Exploit script not found: {exploit_script}", file=sys.stderr)
        session.record(f"USBliter8 jailbreak aborted: script missing: {exploit_script}")
        _pause()
        return 1

    evidence_path = session.directory / "usbliter8-jailbreak.json"
    label = "USBliter8 A12+ jailbreak"
    command = [
        sys.executable,
        str(exploit_script),
        "--auto",
        "--evidence",
        str(evidence_path),
        "--timeout",
        "60",
    ]
    printable = shlex.join(command)
    session.record(f"START {label}: {printable}")
    print(f"\n[{label}]")
    print(f"$ {printable}\n")
    try:
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
            with session.log_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
        return_code = process.wait()
    except OSError as exc:
        session.record(f"ERROR {label}: {exc}")
        print(f"Unable to start exploit: {exc}", file=sys.stderr)
        _pause()
        return 1

    session.record(f"END {label}: exit={return_code}")
    print(f"\nResult: {'passed' if return_code == 0 else f'failed ({return_code})'}")

    if return_code == 0 and evidence_path.exists():
        print(f"Evidence: {evidence_path.relative_to(ROOT)}")
        session.record(f"Evidence written: {evidence_path}")
    elif return_code != 0:
        print(
            f"\n{Colors.YELLOW}Jailbreak did not complete successfully.{Colors.RESET}"
        )
        print("Troubleshooting:")
        print("  - Ensure the device is in DFU mode (not Recovery)")
        print("  - Confirm CPID is 0x8015 or above (A12 or newer)")
        print("  - Check USB cable and host port are functioning")
        print("  - Review session log for detailed error output")
        session.record("USBliter8 jailbreak FAILED")

    if return_code == 0 and _confirm("Connect to FBR34KER runtime console"):
        _runtime_console(session)

    _pause()
    return return_code


def _usbliter8_pwn_and_inspect(session: Session) -> int:
    _clear()
    _header(session, "A12+ USBliter8 Pwn & Inspect")
    print("Exploits the device via USBliter8 DWC3, boots FBR34KER, then")
    print("dumps hardware details, protection schemes, and attack surface.")
    print()
    print("Outputs a verbose JSON report to the session directory.")
    print()

    owner = _prompt(
        f'Type "{AUTHORIZATION_TEXT}" to confirm device ownership',
        "",
    )
    if owner != AUTHORIZATION_TEXT:
        print("Authorization not confirmed. Aborting.")
        session.record("USBliter8 pwn-and-inspect aborted: authorization not confirmed")
        _pause()
        return 1

    try:
        from scripts.run_exploit import BootChain, ExploitError
    except ImportError:
        print("run_exploit.py not found in scripts/", file=sys.stderr)
        session.record("USBliter8 pwn-and-inspect aborted: run_exploit.py missing")
        _pause()
        return 1

    exploit_script = ROOT / "scripts" / "run_exploit.py"
    evidence_path = session.directory / "usbliter8-inspect.json"
    report_path = session.directory / "pwn-inspect-report.json"

    pwndfu_ok = False
    chipset_info = None
    chain_results = {}
    console_inspection: dict[str, str] = {}

    pwndfu_label = "USBliter8 PWNDFU + monitor boot"
    pwndfu_cmd = [
        sys.executable,
        str(exploit_script),
        "--auto",
        "--evidence",
        str(evidence_path),
        "--timeout",
        "90",
    ]
    session.record(f"START {pwndfu_label}: {shlex.join(pwndfu_cmd)}")
    print(f"\n[{pwndfu_label}]")
    print(f"$ {shlex.join(pwndfu_cmd)}\n")
    try:
        proc = subprocess.Popen(
            pwndfu_cmd,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            with session.log_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
        rc = proc.wait()
    except OSError as exc:
        session.record(f"ERROR {pwndfu_label}: {exc}")
        print(f"Unable to start exploit: {exc}", file=sys.stderr)
        _pause()
        return 1

    session.record(f"END {pwndfu_label}: exit={rc}")
    pwndfu_ok = rc == 0

    if not pwndfu_ok:
        print(f"\n{Colors.RED}PWNDFU / monitor boot failed (exit {rc}).{Colors.RESET}")
        print("Inspection cannot proceed without an active FBR34KER console.")
        _pause()
        return 1

    print(f"\n{Colors.GREEN}Device pwned and monitor active.{Colors.RESET}")

    if evidence_path.exists():
        try:
            ev = json.loads(evidence_path.read_text(encoding="utf-8"))
            chipset_info = ev.get("chipset")
            chain_results = ev.get("results", {})
            session.record(f"Loaded exploit evidence from {evidence_path}")
        except Exception as exc:
            session.record(f"WARNING: could not parse evidence file: {exc}")

    console = None
    try:
        from usb_serial import USBConsole, TransportError

        print(f"\n[*] Connecting to FBR34KER console for inspection...")
        console = USBConsole()
        console.open()
        banner = console.read_until_prompt(timeout=10.0)
        print(f"[+] Console connected")
        session.record("Console connected for inspection")

        inspection_commands = [
            ("exploit-chain status", "Protection scheme state"),
            ("usb-status", "USB DWC3 controller status"),
            (
                "hardware-prepare --list-categories",
                "Available hardware inspection categories",
            ),
            ("chipsets", "Supported A12+ SoC database"),
            ("boot-evidence status", "Boot evidence collection status"),
        ]

        print(f"\n[*] Running {len(inspection_commands)} inspection commands...\n")
        for cmd, description in inspection_commands:
            session.record(f"INSPECT: {cmd}")
            print(f"  {Colors.BOLD}── {description} ──{Colors.RESET}")
            try:
                out = console.run_command(cmd, timeout=15.0)
                console_inspection[cmd] = out
                print(out)
            except Exception as exc:
                err = f"<inspection command failed: {exc}>"
                console_inspection[cmd] = err
                print(f"  {Colors.YELLOW}{err}{Colors.RESET}")
            print()

    except ImportError:
        session.record("INSPECT SKIPPED: pyusb not available for console connection")
        print(
            f"\n{Colors.YELLOW}pyusb not available; skipping live inspection.{Colors.RESET}"
        )
    except Exception as exc:
        session.record(f"INSPECT ERROR: {exc}")
        print(f"\n{Colors.YELLOW}Console inspection error: {exc}{Colors.RESET}")
    finally:
        if console is not None:
            try:
                console.close()
            except Exception:
                pass

    try:
        from host.chipset_db import all_chipsets, chipset_summary

        all_socs = {c["cpid"]: c for c in all_chipsets()}
    except Exception:
        all_socs = {}

    known_protections = [
        "Image4 signature validation",
        "Certificate chain verification",
        "AP Ticket validation",
        "SHSH blob acceptance",
        "iBoot image authentication",
        "Boot manifest trust evaluation",
        "AMFI code signing enforcement",
        "Sandbox policy enforcement",
        "codesign requirement",
        "task_for_pid access control",
        "Root filesystem mount (read-only)",
        "Kernel extension signing",
        "Kernel patch protection (kpp)",
        "PAC (Pointer Authentication)",
        "Secure Enclave Bridge",
    ]

    bypass_status: dict[str, str] = {}
    for entry in console_inspection.get("exploit-chain status", "").splitlines():
        stripped = entry.strip()
        for kw in (
            "Image4",
            "cert",
            "APTicket",
            "SHSH",
            "iBoot",
            "AMFI",
            "sandbox",
            "codesign",
            "task_for_pid",
            "mount",
            "bypass",
        ):
            if kw.lower() in stripped.lower():
                bypass_status[kw] = stripped
                break

    report = {
        "schema_version": 1,
        "project": "FBR34KER",
        "version": "0.3.0",
        "operation": "usbliter8-pwn-and-inspect",
        "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "authorization": "confirmed",
        "pwndfu": {
            "succeeded": pwndfu_ok,
            "target": "A12+ (CPID >= 0x8015)",
            "exploit": "DWC3 USBliter8 firmware patch",
        },
        "chipset": chipset_info,
        "known_protections": known_protections,
        "protection_state": bypass_status,
        "live_console_inspection": console_inspection,
        "exploit_chain_results": chain_results,
        "evidence_files": {
            "exploit_evidence": str(evidence_path.relative_to(ROOT))
            if evidence_path.exists()
            else None,
            "this_report": str(report_path.relative_to(ROOT)),
        },
        "supported_chipsets": list(all_socs.values()),
        "session_directory": str(session.directory.relative_to(ROOT)),
    }

    try:
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        print(f"{Colors.GREEN}Inspection report written:{Colors.RESET}")
        print(f"  {report_path.relative_to(ROOT)}")
        session.record(f"PWN-INSPECT report written: {report_path}")
    except Exception as exc:
        session.record(f"ERROR writing report: {exc}")
        print(f"{Colors.RED}Failed to write report: {exc}{Colors.RESET}")

    print(f"\n{'=' * 60}")
    print(f"  {Colors.BOLD}Inspection Summary{Colors.RESET}")
    print(f"{'=' * 60}")

    if chipset_info:
        ci = chipset_info
        print(f"  Chipset:   {ci.get('name', '?')} ({ci.get('model', '?')})")
        print(f"  CPID:      0x{ci.get('cpid', 0):04x}")
        print(f"  DRAM:      0x{ci.get('dram_base', 0):x}")
        print(f"  Kernel:    0x{ci.get('kernel_base', 0):x}")

    print(f"\n  {Colors.BOLD}Protection State (from live console){Colors.RESET}")
    if bypass_status:
        for kw, state in bypass_status.items():
            active = "BYPASSED" in state.upper() or "ACTIVE" in state.upper()
            mark = (
                f"{Colors.GREEN}✗{Colors.RESET}"
                if active
                else f"{Colors.YELLOW}?{Colors.RESET}"
            )
            print(f"    {mark} {state.strip()}")
    else:
        print(
            f"    {Colors.DIM}(no protection state captured — check report){Colors.RESET}"
        )

    print(f"\n  {Colors.BOLD}Known Protections (attack surface){Colors.RESET}")
    for p in known_protections:
        print(f"    - {p}")

    print(f"\n  Exploit chain steps:")
    for step, result in chain_results.items():
        ok = isinstance(result, bool) and result
        mark = (
            f"{Colors.GREEN}PASS{Colors.RESET}"
            if ok
            else f"{Colors.RED}FAIL{Colors.RESET}"
        )
        print(f"    [{mark}] {step}")
    print(f"{'=' * 60}")

    if _confirm("Connect to FBR34KER runtime console for live exploration"):
        _runtime_console(session)

    _pause()
    return 0


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


def _forensics_workflow(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Forensics and data acquisition")
        print("  1. List built-in acquisition profiles")
        print("  2. Run quick acquisition (filesystem + network)")
        print("  3. Run full acquisition (memory + storage + filesystem + network)")
        print("  4. Run memory-only acquisition")
        print("  5. Run storage-only acquisition")
        print("  6. Run filesystem-only acquisition")
        print("  7. Run network-only acquisition")
        print("  8. Verify an evidence bundle")
        print("  9. iCloud/Keychain/Keybag acquisition  (via SEP/exploit)")
        print(" 10. Activation/FMI/Baseband operations  (bypass, FMI on/off, baseband unlock)")
        print(" 11. Passcode management  (on/off/change/bypass)")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            session.run(["forensics", "list-profiles"], label="List acquisition profiles")
            _pause()
        elif choice in {"2", "3", "4", "5", "6", "7"}:
            profile_map = {
                "2": "quick", "3": "full", "4": "memory-only",
                "5": "storage-only", "6": "filesystem-only", "7": "network-only",
            }
            profile = profile_map[choice]
            device_id = _prompt("Device identifier", "unknown")
            operator = _prompt("Operator name")
            bundle_path = session.directory / f"forensics-{profile}.zip"
            session.run(
                [
                    "forensics", "acquire",
                    "--profile", profile,
                    "--device-id", device_id,
                    "--operator", operator or "",
                    "--bundle", str(bundle_path),
                ],
                label=f"Acquisition: {profile}",
            )
            if bundle_path.exists():
                print(f"\nEvidence bundle: {bundle_path.relative_to(ROOT)}")
            _pause()
        elif choice == "8":
            path = _prompt("Evidence bundle path")
            if path and path != "q":
                session.run(["forensics", "verify", path], label="Verify evidence bundle")
            _pause()
        elif choice == "9":
            _forensics_secrets_menu(session)
        elif choice == "10":
            _forensics_activation_menu(session)
        elif choice == "11":
            _forensics_passcode_menu(session)
        elif choice in {"0", "q", ""}:
            return


def _forensics_secrets_menu(session: Session) -> None:
    _clear()
    _header(session, "iCloud / Keychain / Keybag acquisition")
    print("Extracts iCloud tokens, Keychain items, and Keybag protection-class keys.")
    print("Keychain/Keybag extraction requires SEP unlock (passcode or exploit).\n")
    passcode = _prompt("Device passcode (leave blank for SEP exploit)")
    output = session.directory / "secrets"
    args = ["forensics", "secrets", "--output", str(output)]
    if passcode:
        args += ["--passcode", passcode]
    else:
        if _confirm("Attempt SEP exploit-based unlock"):
            args.append("--sep-exploit")
    session.run(args, label="Secrets acquisition")
    _pause()


def _forensics_activation_menu(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Activation / FMI / Baseband / mobileactivationd")
        print("  1. Query activation state")
        print("  2. Apply full activation bypass (clear records + patch daemon + inject ticket)")
        print("  3. Clear activation records")
        print("  4. Query FMI state (Find My iPhone)")
        print("  5. Turn FMI OFF")
        print("  6. Turn FMI ON")
        print("  7. Clear FMI activation lock")
        print("  8. Baseband status")
        print("  9. Baseband unlock (SIM lock bypass)")
        print(" 10. Query all activation/baseband/FMI state")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            session.run(["forensics", "activation", "status"],
                        label="Activation status")
            _pause()
        elif choice == "2":
            if _confirm("Apply full activation bypass"):
                session.run(["forensics", "activation", "bypass"],
                            label="Activation bypass")
            _pause()
        elif choice == "3":
            if _confirm("Clear activation records"):
                session.run(["forensics", "activation", "clear-records"],
                            label="Clear records")
            _pause()
        elif choice == "4":
            session.run(["forensics", "activation", "fmi", "status"],
                        label="FMI status")
            _pause()
        elif choice == "5":
            if _confirm("Turn FMI OFF"):
                session.run(["forensics", "activation", "fmi", "off"],
                            label="FMI off")
            _pause()
        elif choice == "6":
            if _confirm("Turn FMI ON"):
                session.run(["forensics", "activation", "fmi", "on"],
                            label="FMI on")
            _pause()
        elif choice == "7":
            if _confirm("Clear FMI activation lock"):
                session.run(["forensics", "activation", "fmi", "clear-activation-lock"],
                            label="Clear FMI lock")
            _pause()
        elif choice == "8":
            session.run(["forensics", "activation", "baseband", "status"],
                        label="Baseband status")
            _pause()
        elif choice == "9":
            if _confirm("Unlock baseband (SIM lock)"):
                session.run(["forensics", "activation", "baseband", "unlock"],
                            label="Baseband unlock")
            _pause()
        elif choice == "10":
            output = session.directory / "activation-query"
            session.run(["forensics", "activation", "query-all", "--output", str(output)],
                        label="Query all activation state")
            _pause()
        elif choice in {"0", "q", ""}:
            return


def _forensics_passcode_menu(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Passcode management")
        print("  1. Query passcode state (on/off)")
        print("  2. Query passcode policy")
        print("  3. Remove passcode (requires current passcode or exploit)")
        print("  4. Set new passcode")
        print("  5. Change passcode")
        print("  6. Attempt passcode bypass")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            session.run(["forensics", "passcode", "status"],
                        label="Passcode status")
            _pause()
        elif choice == "2":
            session.run(["forensics", "passcode", "policy"],
                        label="Passcode policy")
            _pause()
        elif choice == "3":
            passcode = _prompt("Current passcode (leave blank for exploit)")
            args = ["forensics", "passcode", "remove"]
            if passcode:
                args += ["--passcode", passcode]
            else:
                args.append("--exploit")
            if _confirm("Remove device passcode"):
                session.run(args, label="Remove passcode")
            _pause()
        elif choice == "4":
            new = _prompt("New passcode")
            if new and len(new) >= 4:
                session.run(["forensics", "passcode", "set", new],
                            label="Set passcode")
            else:
                print("Passcode must be at least 4 characters.")
            _pause()
        elif choice == "5":
            current = _prompt("Current passcode")
            new = _prompt("New passcode")
            if current and new and len(new) >= 4:
                session.run(["forensics", "passcode", "change", current, new],
                            label="Change passcode")
            else:
                print("Both passcodes required; new must be at least 4 characters.")
            _pause()
        elif choice == "6":
            if _confirm("Attempt passcode bypass"):
                session.run(["forensics", "passcode", "bypass"],
                            label="Passcode bypass")
            _pause()
        elif choice in {"0", "q", ""}:
            return


def _cve_workflow(session: Session) -> None:
    while True:
        _clear()
        _header(session, "CVE database & exploit chain planner")
        print("  1. Show database statistics")
        print("  2. Search CVEs by keyword")
        print("  3. Query CVEs for a specific iOS version")
        print("  4. Plan exploit chain for a goal")
        print("  5. Suggest achievable goals for a version")
        print("  6. List available exploit goals")
        print("  7. Filter CVEs by criteria")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            session.run(["cve", "stats"], label="CVE database statistics")
            _pause()
        elif choice == "2":
            query = _prompt("Search query")
            if query:
                session.run(["cve", "search", query], label=f"Search CVEs: {query}")
            _pause()
        elif choice == "3":
            version = _prompt("iOS version", "16.5")
            if version:
                session.run(["cve", "query", version], label=f"CVEs for iOS {version}")
            _pause()
        elif choice == "4":
            version = _prompt("Target iOS version", "16.5")
            print("\nAvailable goals: jailbreak, userland-jailbreak, extraction,")
            print("  activation-bypass, passcode-bypass, forensics-ready,")
            print("  tethered-jailbreak, jailbreak-remote")
            goal = _prompt("Exploit goal", "jailbreak")
            if version and goal:
                session.run(["cve", "chain", goal, version],
                            label=f"Chain: {goal} on iOS {version}")
            _pause()
        elif choice == "5":
            version = _prompt("Target iOS version", "16.5")
            if version:
                session.run(["cve", "suggest", version],
                            label=f"Suggest goals for iOS {version}")
            _pause()
        elif choice == "6":
            session.run(["cve", "goals"], label="List exploit goals")
            _pause()
        elif choice == "7":
            version = _prompt("iOS version filter (blank for all)", "")
            goal = _prompt("Goal filter (blank for all)", "")
            component = _prompt("Component filter (blank for all)", "")
            args = ["cve", "filter"]
            if version:
                args += ["--version", version]
            if goal:
                args += ["--goal", goal]
            if component:
                args += ["--component", component]
            session.run(args, label="Filter CVEs")
            _pause()
        elif choice in {"0", "q", ""}:
            return


def _fuzzer_workflow(session: Session) -> None:
    _clear()
    _header(session, "Fuzzer orchestration")
    print("  1. List available fuzz targets")
    print("  0. Back")
    choice = _prompt("Selection", "1")
    if choice == "1":
        session.run(["cve", "fuzz", "list"], label="List fuzz targets")
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


def _resolve_security_model() -> bool:
    """Prompt for FBR34KER_ENABLE_SECURITY_MODEL on first run, cache decision."""
    if SECURITY_MODEL_CONFIG_PATH.exists():
        stored = SECURITY_MODEL_CONFIG_PATH.read_text(encoding="utf-8").strip()
        return stored == "1"

    _clear()
    print("=" * 64)
    print("  FBR34KER_SECURITY_MODEL — First-time setup")
    print("=" * 64)
    print()
    from b34st.environment import SECURITY_MODEL_DESCRIPTION
    print(SECURITY_MODEL_DESCRIPTION)
    print()

    while True:
        choice = _prompt("Select [1] State model (default)  [2] Active security model", "1")
        if choice == "1":
            enable = False
            break
        elif choice == "2":
            if not _confirm("WARNING: Active security model WILL write to kernel memory. Continue"):
                continue
            owner = _prompt('Type "I OWN OR AM AUTHORIZED TO TEST THIS DEVICE"')
            if owner != "I OWN OR AM AUTHORIZED TO TEST THIS DEVICE":
                print("Authorization not confirmed.")
                continue
            enable = True
            print(f"\n{Colors.RED}Active security model selected. Writes to kernel memory are enabled.{Colors.RESET}")
            break
        else:
            print("Invalid selection.")

    SECURITY_MODEL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECURITY_MODEL_CONFIG_PATH.write_text("1" if enable else "0")
    print(f"Security model preference saved to {SECURITY_MODEL_CONFIG_PATH}")
    _pause()
    return enable


def _show_log(session: Session) -> None:
    _clear()
    _header(session, "Session log")
    print(session.log_path.read_text(encoding="utf-8"), end="")
    _pause()


def _device_snapshot(session: Session) -> dict:
    from host.device_dashboard import build_snapshot

    args = argparse.Namespace(
        device_info=pathlib.Path(os.environ["B34ST_DEVICE_INFO"])
        if os.environ.get("B34ST_DEVICE_INFO")
        else None,
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
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
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
    print(
        f"Device:          {device.get('name') or device.get('device_name') or 'Unknown'}"
    )
    print(f"Product:         {device.get('product') or 'Unknown'}")
    print(f"Mode:            {device.get('mode') or 'Unknown'}")
    print(f"Board/model:     {device.get('model') or 'Unknown'}")
    print(
        f"Launch firmware: {device.get('launch_version') or 'Not in reviewed database'}"
    )
    print(
        f"Current version: {device.get('current_version') or 'Unavailable in this mode'}"
    )
    print(
        f"Current build:   {device.get('current_build') or 'Unavailable in this mode'}"
    )
    print(
        f"Latest signed:   {latest.get('version') or 'Catalog unavailable'}{latest_build}"
    )
    print(
        f"Exact profiles:  {sum(1 for item in snapshot.get('profiles', []) if item.get('exact'))}"
    )
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
            "ipsw",
            "download",
            "--product",
            product,
            "--version",
            latest["version"],
            "--build",
            latest["build"],
            "--signed-only",
            "--output-dir",
            str(session.directory / "ipsw"),
            "--manifest",
            str(session.directory / "latest-ipsw.json"),
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
            "--owner-authorization",
            owner,
            "--confirm",
            confirm,
            "--evidence",
            str(session.directory / "signed-restore.json"),
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
            "ipsw",
            "tethered-downgrade",
            "--product",
            product,
            "--ipsw",
            path,
            "--evidence",
            str(session.directory / "tethered-downgrade.json"),
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
            plan
            + [
                "--adapter-command",
                adapter,
                "--execute",
                "--owner-authorization",
                owner,
                "--confirm",
                confirm,
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
    security_model = _resolve_security_model()
    session.record(f"Security model: {'ACTIVE' if security_model else 'STATE MODEL'}")
    if security_model:
        session.run(["build", "--security-model"], label="Build with security model")
        print(f"\n{Colors.RED}SECURITY MODEL ACTIVE: memory writes enabled{Colors.RESET}")
    else:
        session.run(["build"], label="Build (state model only)")
        print(f"\n{Colors.GREEN}State model only: no kernel memory writes{Colors.RESET}")
    _pause()

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
        print(" 11. Forensics and data acquisition")
        print(" 12. CVE database & exploit chain planner")
        print(" 13. Fuzzer orchestration")
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
        elif choice == "11":
            _forensics_workflow(session)
        elif choice == "12":
            _cve_workflow(session)
        elif choice == "13":
            _fuzzer_workflow(session)
        elif choice in {"0", "q", ""}:
            session.record("B34ST control-panel session ended")
            print(f"Session log: {session.log_path.relative_to(ROOT)}")
            return 0


if __name__ == "__main__":
    raise SystemExit(run_control_panel())
