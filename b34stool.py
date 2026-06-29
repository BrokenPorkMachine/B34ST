#!/usr/bin/env python3
"""B34ST unified interactive multi-tool for FBR34KER workflows."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
ARTIFACT_ROOT = ROOT / "runtime-artifacts" / "b34st" / "b34stool"


class Colors:
    if os.isatty(1):
        BOLD = "\033[1m"
        DIM = "\033[2m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        CYAN = "\033[36m"
        RESET = "\033[0m"
        CLEAR = "\033[2J\033[H"
    else:
        BOLD = DIM = RED = GREEN = YELLOW = CYAN = RESET = CLEAR = ""


@dataclasses.dataclass(frozen=True)
class Action:
    key: str
    label: str
    command: tuple[str, ...]
    prompt: str = ""
    evidence_arg: str = ""
    interactive: bool = False


@dataclasses.dataclass(frozen=True)
class Category:
    key: str
    label: str
    actions: tuple[Action, ...]


class Session:
    def __init__(self, session_dir: pathlib.Path | None = None) -> None:
        stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        self.directory = session_dir or ARTIFACT_ROOT / stamp
        self.evidence_dir = self.directory / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.directory / "session.log"
        self.sequence = 0
        self.record("B34ST unified multi-tool session started")

    def record(self, message: str) -> None:
        timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{timestamp}] {message}\n")

    def evidence_path(self, operation: str, suffix: str = ".json") -> pathlib.Path:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", operation).strip("-").lower()
        self.sequence += 1
        return self.evidence_dir / f"{self.sequence:03d}-{safe or 'operation'}{suffix}"

    def run(self, action: Action, extra_args: list[str] | None = None) -> int:
        extra_args = extra_args or []
        command = [expand_token(token, self, action) for token in action.command]
        command.extend(extra_args)
        return self.run_command(command, action.key, interactive=action.interactive)

    def run_command(
        self,
        command: list[str],
        operation: str,
        *,
        interactive: bool = False,
    ) -> int:
        started = dt.datetime.now().astimezone()
        start_time = time.monotonic()
        printable = shlex.join(command)
        self.record(f"START {operation}: {printable}")
        print(f"\n{Colors.BOLD}[{operation}]{Colors.RESET}")
        print(f"{Colors.DIM}$ {printable}{Colors.RESET}\n")
        output = ""
        try:
            if interactive:
                result = subprocess.run(command, cwd=ROOT, check=False)
                exit_code = result.returncode
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
                chunks: list[str] = []
                for line in process.stdout:
                    print(line, end="")
                    chunks.append(line)
                    with self.log_path.open("a", encoding="utf-8") as stream:
                        stream.write(line)
                exit_code = process.wait()
                output = "".join(chunks)
        except OSError as exc:
            output = str(exc)
            exit_code = 127
            print(f"Unable to start command: {exc}", file=sys.stderr)
        duration_ms = int((time.monotonic() - start_time) * 1000)
        self.record(f"END {operation}: exit={exit_code} duration_ms={duration_ms}")
        evidence = {
            "schema_version": 1,
            "operation": operation,
            "timestamp": started.isoformat(timespec="seconds"),
            "command": command,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "output_summary": summarize_output(output, exit_code),
        }
        path = self.evidence_path(operation)
        path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"\n{Colors.GREEN if exit_code == 0 else Colors.RED}"
            f"Exit code: {exit_code}{Colors.RESET}"
        )
        print(f"{Colors.DIM}Evidence: {display_path(path)}{Colors.RESET}")
        return exit_code


def fbr34ker(*args: str) -> tuple[str, ...]:
    return (str(ROOT / "fbr34ker"), *args)


def script(name: str, *args: str) -> tuple[str, ...]:
    return (sys.executable, str(ROOT / "scripts" / name), *args)


def host(name: str, *args: str) -> tuple[str, ...]:
    return (sys.executable, str(ROOT / "host" / name), *args)


def expand_token(token: str, session: Session, action: Action) -> str:
    if token == "{evidence}":
        return str(session.evidence_path(action.key, "-tool-output.json"))
    if token == "{session}":
        return str(session.directory)
    return token


def summarize_output(output: str, exit_code: int) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return (
            "completed without captured output"
            if exit_code == 0
            else "failed without captured output"
        )
    summary = lines[-1]
    return summary[:240]


def display_path(path: pathlib.Path) -> pathlib.Path:
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


CATEGORIES: tuple[Category, ...] = (
    Category(
        "system",
        "System",
        (
            Action("system.version", "Version", fbr34ker("version")),
            Action("system.doctor", "Doctor", fbr34ker("doctor")),
            Action("system.build", "Build", fbr34ker("build")),
            Action("system.test", "Test", fbr34ker("test")),
            Action("system.clean", "Clean", fbr34ker("clean")),
        ),
    ),
    Category(
        "device",
        "Device",
        (
            Action("device.info", "Device info", fbr34ker("device")),
            Action("device.detect", "Detect", fbr34ker("detect")),
            Action("device.console", "Console", fbr34ker("console"), interactive=True),
            Action("device.pwndfu", "PWNDFU", fbr34ker("pwndfu")),
            Action(
                "device.exploit",
                "Exploit chain",
                fbr34ker("exploit", "--auto", "--evidence", "{evidence}"),
            ),
        ),
    ),
    Category(
        "usbliter8",
        "USBliter8",
        (
            Action(
                "usbliter8.pwn-inspect",
                "Pwn & Inspect",
                script("run_exploit.py", "--auto", "--evidence", "{evidence}"),
            ),
            Action(
                "usbliter8.jailbreak",
                "Jailbreak",
                fbr34ker("exploit", "--auto", "--evidence", "{evidence}"),
            ),
            Action(
                "usbliter8.chain",
                "Chain command",
                fbr34ker("exploit"),
                "Extra exploit arguments",
            ),
        ),
    ),
    Category(
        "ipsw",
        "IPSW",
        (
            Action(
                "ipsw.catalog",
                "Catalog",
                fbr34ker("ipsw", "catalog"),
                "Catalog arguments",
            ),
            Action(
                "ipsw.download",
                "Download",
                fbr34ker("ipsw", "download"),
                "Download arguments",
            ),
            Action(
                "ipsw.inspect",
                "Inspect",
                fbr34ker("ipsw", "inspect"),
                "Inspect arguments",
            ),
            Action(
                "ipsw.upgrade",
                "Upgrade",
                fbr34ker("ipsw", "upgrade"),
                "Upgrade arguments",
            ),
            Action(
                "ipsw.tethered-downgrade",
                "Guided tethered downgrade",
                fbr34ker(
                    "ipsw",
                    "tethered-downgrade-guide",
                    "--evidence",
                    "{evidence}",
                ),
                interactive=True,
            ),
        ),
    ),
    Category(
        "boot-image",
        "Boot Image",
        (
            Action(
                "boot-image.build",
                "Build",
                fbr34ker("boot-image", "build"),
                "Build arguments",
            ),
            Action(
                "boot-image.inspect",
                "Inspect",
                fbr34ker("boot-image", "inspect"),
                "Image path and arguments",
            ),
            Action(
                "boot-image.verify",
                "Verify",
                fbr34ker("boot-image", "verify"),
                "Verify arguments",
            ),
            Action(
                "boot-image.send",
                "Send to device",
                fbr34ker("irecovery", "send"),
                "Send arguments",
                interactive=True,
            ),
        ),
    ),
    Category(
        "ramdisk",
        "Ramdisk Maker / Loader",
        (
            Action(
                "ramdisk.guide",
                "Guided maker / loader",
                fbr34ker("ramdisk", "guide", "--evidence", "{evidence}"),
                interactive=True,
            ),
            Action(
                "ramdisk.targets",
                "List compatible targets",
                fbr34ker("ramdisk", "list-targets"),
            ),
            Action(
                "ramdisk.plan",
                "Compatibility plan",
                fbr34ker("ramdisk", "plan"),
                "Target plan arguments",
            ),
            Action(
                "ramdisk.build",
                "Build FBRD bundle",
                fbr34ker("ramdisk", "build"),
                "Build arguments",
            ),
            Action(
                "ramdisk.inspect",
                "Inspect FBRD bundle",
                fbr34ker("ramdisk", "inspect"),
                "Bundle path and arguments",
            ),
            Action(
                "ramdisk.load",
                "Plan or load through adapter",
                fbr34ker("ramdisk", "load"),
                "Bundle path and adapter arguments",
                interactive=True,
            ),
        ),
    ),
    Category(
        "deployment",
        "Deployment",
        (
            Action(
                "deployment.deploy",
                "Deploy",
                fbr34ker("deploy"),
                "Deploy arguments",
                interactive=True,
            ),
            Action(
                "deployment.recover",
                "Recover",
                fbr34ker("recover"),
                "Recover arguments",
            ),
            Action(
                "deployment.inspect",
                "Inspect",
                fbr34ker("inspect"),
                "Inspect arguments",
            ),
            Action(
                "deployment.modules", "Modules", fbr34ker("module"), "Module arguments"
            ),
        ),
    ),
    Category(
        "hardware",
        "Hardware",
        (
            Action(
                "hardware.prepare",
                "Prepare",
                fbr34ker("b34st", "hardware-prepare", "--list-categories"),
            ),
            Action(
                "hardware.bringup", "Bringup", fbr34ker("bringup"), "Bringup arguments"
            ),
            Action(
                "hardware.profile",
                "Profile management",
                fbr34ker("hardware"),
                "Hardware/profile arguments",
            ),
        ),
    ),
    Category(
        "session",
        "Session",
        (
            Action(
                "session.tools",
                "Session tools",
                fbr34ker("session"),
                "Session arguments",
            ),
            Action("session.console", "Console", fbr34ker("console"), interactive=True),
            Action(
                "session.logs",
                "Log management",
                fbr34ker("session", "logs"),
                "Log arguments",
            ),
        ),
    ),
    Category(
        "validation",
        "Validation",
        (
            Action(
                "validation.physical",
                "Physical validation",
                fbr34ker("physical-validation"),
                "Validation arguments",
            ),
            Action(
                "validation.candidate-report",
                "Candidate report",
                fbr34ker("physical-validation", "candidate-report"),
                "Report arguments",
            ),
            Action(
                "validation.evidence",
                "Evidence validation",
                fbr34ker("evidence-compare"),
                "Evidence arguments",
            ),
        ),
    ),
    Category(
        "release",
        "Release",
        (
            Action("release.package", "Package", fbr34ker("package")),
            Action("release.gate", "Gate", fbr34ker("gate")),
            Action("release.permissions", "Permissions", fbr34ker("permissions")),
            Action(
                "release.abi-check", "ABI check", fbr34ker("abi-check"), "ABI arguments"
            ),
        ),
    ),
    Category(
        "module",
        "Module",
        (
            Action(
                "module.compile",
                "Compile",
                fbr34ker("module", "compile"),
                "Compile arguments",
            ),
            Action(
                "module.inspect",
                "Inspect",
                fbr34ker("module", "inspect"),
                "Inspect arguments",
            ),
            Action(
                "module.upload",
                "Upload",
                fbr34ker("module", "upload"),
                "Upload arguments",
            ),
            Action(
                "module.execute",
                "Execute",
                fbr34ker("module", "execute"),
                "Execute arguments",
                interactive=True,
            ),
        ),
    ),
    Category(
        "research-runtime",
        "Research Runtime",
        (
            Action(
                "research-runtime.guided",
                "Guided workflow",
                fbr34ker("research-runtime", "workflow"),
                "Workflow arguments",
                interactive=True,
            ),
            Action(
                "research-runtime.validate-evidence",
                "Evidence validation",
                fbr34ker("research-runtime", "validate-evidence"),
                "Evidence arguments",
            ),
        ),
    ),
    Category(
        "frontier",
        "Frontier",
        (
            Action(
                "frontier.guided",
                "Guided research",
                fbr34ker("research-runtime", "guided"),
                interactive=True,
            ),
            Action(
                "frontier.chipsets",
                "Chipset catalog",
                fbr34ker("chipsets"),
            ),
            Action(
                "frontier.cve-suggest",
                "CVE goal suggestion",
                fbr34ker("b34st", "cve", "suggest"),
                "iOS version (e.g. 18.0)",
            ),
            Action(
                "frontier.cve-search",
                "CVE search",
                fbr34ker("b34st", "cve", "search"),
                "CVE ID or query",
            ),
        ),
    ),
    Category(
        "b34st",
        "B34ST",
        (
            Action(
                "b34st.environment-plan",
                "Environment plan",
                fbr34ker("b34st", "environment-plan"),
                "Plan arguments",
            ),
            Action(
                "b34st.toolkit-info", "Toolkit info", fbr34ker("b34st", "--version")
            ),
            Action(
                "b34st.control-panel",
                "Control panel",
                fbr34ker("control-panel"),
                interactive=True,
            ),
        ),
    ),
    Category(
        "forensics",
        "Forensics",
        (
            Action(
                "forensics.guided",
                "Guided acquisition",
                fbr34ker("b34st", "forensics", "guided"),
                "Acquisition arguments",
            ),
            Action(
                "forensics.acquire",
                "Run acquisition",
                fbr34ker("b34st", "forensics", "acquire"),
                "Acquire arguments",
            ),
            Action(
                "forensics.verify",
                "Verify bundle",
                fbr34ker("b34st", "forensics", "verify"),
                "Bundle path",
            ),
            Action(
                "forensics.list-profiles",
                "List profiles",
                fbr34ker("b34st", "forensics", "list-profiles"),
            ),
        ),
    ),
)

ACTION_MAP = {
    action.key: action for category in CATEGORIES for action in category.actions
}


def clear() -> None:
    if os.isatty(1):
        print(Colors.CLEAR, end="")


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{Colors.BOLD}{label}{Colors.RESET}{suffix}: ").strip() or default
    except (EOFError, KeyboardInterrupt):
        return "q"


def pause() -> None:
    if os.isatty(0):
        prompt("Press Enter to continue")


def print_header(session: Session, subtitle: str = "Unified multi-tool") -> None:
    print(f"{Colors.BOLD}B34ST // FBR34KER{Colors.RESET}")
    print(subtitle)
    print(f"{Colors.DIM}Session: {display_path(session.directory)}{Colors.RESET}")
    print("-" * 64)


def select_extra_args(action: Action) -> list[str]:
    if not action.prompt:
        return []
    print(f"{Colors.DIM}Leave blank to run the default command.{Colors.RESET}")
    value = prompt(action.prompt)
    if value in {"", "q"}:
        return []
    try:
        return shlex.split(value)
    except ValueError as exc:
        print(f"{Colors.RED}Invalid arguments: {exc}{Colors.RESET}")
        return []


def run_category(session: Session, category: Category) -> int:
    last_code = 0
    while True:
        clear()
        print_header(session, category.label)
        for index, action in enumerate(category.actions, start=1):
            print(f"  {index}. {action.label}  {Colors.DIM}{action.key}{Colors.RESET}")
        print("  0. Back")
        choice = prompt("Selection", "0")
        if choice in {"0", "q", ""}:
            return last_code
        if not choice.isdigit() or not 1 <= int(choice) <= len(category.actions):
            continue
        action = category.actions[int(choice) - 1]
        extra = select_extra_args(action)
        last_code = session.run(action, extra)
        pause()


def interactive(session: Session) -> int:
    if not os.isatty(0) or not os.isatty(1):
        print(
            "B34ST unified multi-tool interactive mode requires a TTY", file=sys.stderr
        )
        return 1
    last_code = 0
    while True:
        clear()
        print_header(session)
        for index, category in enumerate(CATEGORIES, start=1):
            print(f"  {index:2d}. {category.label}")
        print("   0. Exit")
        choice = prompt("Category", "0")
        if choice in {"0", "q", ""}:
            session.record("B34ST unified multi-tool session ended")
            return last_code
        if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
            last_code = run_category(session, CATEGORIES[int(choice) - 1])


def list_commands() -> None:
    for category in CATEGORIES:
        print(f"{category.label}:")
        for action in category.actions:
            print(f"  {action.key:<36} {action.label}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="b34stool",
        description="Unified B34ST multi-tool with session instrumentation.",
    )
    parser.add_argument(
        "--list", action="store_true", help="List non-interactive command keys"
    )
    parser.add_argument("--command", help="Run one command key non-interactively")
    parser.add_argument(
        "--session-dir", type=pathlib.Path, help="Use a specific session directory"
    )
    parser.add_argument(
        "--json", action="store_true", help="Print final session result as JSON"
    )
    parser.add_argument(
        "--args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Arguments appended to --command",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.list:
        list_commands()
        return 0
    session = Session(args.session_dir)
    if args.command:
        action = ACTION_MAP.get(args.command)
        if action is None:
            print(f"Unknown B34ST tool command: {args.command}", file=sys.stderr)
            print("Run b34stool --list to see available commands.", file=sys.stderr)
            return 2
        exit_code = session.run(action, list(args.args))
    else:
        exit_code = interactive(session)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": exit_code == 0,
                    "exit_code": exit_code,
                    "session": str(session.directory),
                    "log": str(session.log_path),
                },
                sort_keys=True,
            )
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
