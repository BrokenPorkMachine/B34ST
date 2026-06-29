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

from b34st.version import __version__

SECURITY_MODEL_CONFIG_PATH = pathlib.Path(
    "~/.config/fbr34ker/security-model"
).expanduser()

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
        self._log_lock = threading.Lock()
        self._log_buffer: list[str] = []
        self._log_thread: threading.Thread | None = None
        self._log_stop = threading.Event()
        self._start_log_flusher()
        self.record("B34ST control-panel session started")

    def _start_log_flusher(self) -> None:
        def _flush():
            while not self._log_stop.wait(timeout=0.5):
                with self._log_lock:
                    if self._log_buffer:
                        try:
                            with self.log_path.open("a", encoding="utf-8") as stream:
                                stream.writelines(self._log_buffer)
                                stream.flush()
                        except OSError:
                            pass
                        self._log_buffer.clear()
            with self._log_lock:
                if self._log_buffer:
                    try:
                        with self.log_path.open("a", encoding="utf-8") as stream:
                            stream.writelines(self._log_buffer)
                            stream.flush()
                    except OSError:
                        pass
                    self._log_buffer.clear()

        self._log_thread = threading.Thread(target=_flush, daemon=True)
        self._log_thread.start()

    def record(self, message: str) -> None:
        timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        line = f"[{timestamp}] {message}\n"
        with self._log_lock:
            self._log_buffer.append(line)

    def close(self) -> None:
        self._log_stop.set()
        if self._log_thread is not None:
            self._log_thread.join(timeout=2.0)

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
                try:
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            print(line, end="")
                            self.record(line.rstrip("\n"))
                except (OSError, IOError) as exc:
                    print(f"\n[WARN] subprocess stream error: {exc}", file=sys.stderr)
                rc = process.returncode
                if rc is None:
                    try:
                        process.wait(timeout=5)
                        rc = process.returncode
                    except (subprocess.TimeoutExpired, OSError):
                        process.kill()
                        try:
                            process.wait(timeout=5)
                        except (OSError, subprocess.TimeoutExpired):
                            pass
                        rc = getattr(process, "returncode", -9)
                return_code = rc
        except OSError as exc:
            self.record(f"ERROR {label}: {exc}")
            print(f"Unable to start command: {exc}", file=sys.stderr)
            return 1
        self.record(f"END {label}: exit={return_code}")
        print(
            f"\nResult: {'passed' if return_code == 0 else f'failed ({return_code})'}"
        )
        return return_code

    def run_command(
        self,
        arguments: list[str],
        *,
        label: str,
        interactive: bool = False,
    ) -> int:
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
                try:
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            print(line, end="")
                            self.record(line.rstrip("\n"))
                except (OSError, IOError) as exc:
                    print(f"\n[WARN] subprocess stream error: {exc}", file=sys.stderr)
                rc = process.returncode
                if rc is None:
                    try:
                        process.wait(timeout=5)
                        rc = process.returncode
                    except (subprocess.TimeoutExpired, OSError):
                        process.kill()
                        try:
                            process.wait(timeout=5)
                        except (OSError, subprocess.TimeoutExpired):
                            pass
                        rc = getattr(process, "returncode", -9)
                return_code = rc
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


def _header(
    session: Session, subtitle: str = "Operator control plane", show_help: bool = True
) -> None:
    print("B34ST // FBR34KER")
    print(subtitle)
    print(f"Session: {session.directory.relative_to(ROOT)}")
    print("-" * 64)
    if show_help:
        _help_for_category(subtitle)


def _main_menu_options() -> list[tuple[str, str, str]]:
    """
    Returns the enhanced main menu options with descriptions and automation indicators.

    Returns:
        List of tuples (key, label, description) for main menu options
    """
    return [
        (
            "1",
            "External hardware / USBliter8 / first-stage execution",
            "Pwn, inspect, and jailbreak A12+ devices via USBliter8 (guided automation available)",
        ),
        (
            "2",
            "Load images, next stages, modules, or deployment",
            "Boot chain, deployment, modules, runtime (guided deployment plan with default options)",
        ),
        (
            "3",
            "Authorized runtime modifications and evidence",
            "Kernel patches, secure boot bypass, persistence (validate evidence-gated workflows)",
        ),
        (
            "4",
            "Build, test, and QEMU simulation",
            "Host check, build, test, simulate safely (guided validation with full scriptable automation)",
        ),
        (
            "5",
            "Runtime console / logger / shell",
            "Interactive shell, logging, exploration (guided runtime inspection and log export)",
        ),
        (
            "6",
            "Evidence, validation, and release",
            "Validate sessions, generate reports, release gate (full automation)",
        ),
        (
            "7",
            "Targeted IPSW downloads, upgrades, and tethered downgrades",
            "Firmware catalog, signed updates, guide (guided with interactive planning)",
        ),
        (
            "8",
            "Create a bounded environment plan",
            "Plan iOS 17+ research environment (structured with defaults)",
        ),
        (
            "9",
            "Open the FBR34KER maintenance menu",
            "Legacy FBR34KER guided console (original workflow walkthrough)",
        ),
        (
            "10",
            "View this B34ST session log",
            "Review command transcript and explain evidence flow (auto-generate summaries)",
        ),
        (
            "11",
            "Forensics and data acquisition",
            "iCloud/Keychain, activation, passcode, memory/storage (profile-based)",
        ),
        (
            "12",
            "CVE database & exploit chain planner",
            "Search exploits, plan chains, suggest attacks (guidance provided)",
        ),
        (
            "13",
            "Fuzzer orchestration",
            "Schedule fuzzing across all targets (automated with presets)",
        ),
        (
            "14",
            "Ramdisk maker and loader",
            "Build deterministic FBRD bundles (guided for common use cases)",
        ),
        (
            "0",
            "Exit",
            "Save, validate session state, and exit B34ST (with confirmation)",
        ),
    ]


def get_category_description(category: str) -> str:
    """
    Get a detailed description of a menu category for educational purposes.

    Args:
        category: The category name to get description for

    Returns:
        Detailed description of the category
    """
    descriptions = {
        "External hardware / USBliter8 / first-stage execution": (
            "This workflow targets A12+ iPhone/iPad devices via the DWC3 USB controller "
            "exploit chain. It includes hardware preparation, exploitation, "
            "jailbreak, and evidence collection. Requires physical hardware "
            "and explicit authorization."
        ),
        "Load images, next stages, modules, or deployment": (
            "Manage the boot chain, including deployment of components, module "
            "interaction, and runtime workflows. This covers everything from "
            "building boot images to executing deployed components with "
            "evidence validation."
        ),
        "Authorized runtime modifications and evidence": (
            "Perform kernel patches, secure boot bypass, and persistence "
            "operations. These modifications require exact-kernel evidence "
            "verification and are gated by evidence requirements."
        ),
        "Build, test, and QEMU simulation": (
            "Verify host environment, build firmware artifacts, run tests, "
            "and simulate in QEMU. This provides a safe sandbox for testing "
            "and validation without physical hardware."
        ),
        "Runtime console / logger / shell": (
            "Interactive shell for exploration, debugging, and logging. "
            "Connect to running FBR34KER instances and interact with "
            "protection schemes and runtime systems."
        ),
        "Evidence, validation, and release": (
            "Validate session evidence, generate physical-validation reports, "
            "run release gates, and create release packages. This ensures "
            "all operations meet evidence and security requirements."
        ),
        "Targeted IPSW downloads, upgrades, and tethered downgrades": (
            "Manage iOS firmware, including firmware catalog browsing, "
            "signed updates, and guided tethered downgrades. Includes "
            "data preservation workflows and guided planning."
        ),
        "Create a bounded environment plan": (
            "Plan iOS 17+ research environments with exact specifications. "
            "Includes iOS version, device targets, and research parameters "
            "for evidence-gated research."
        ),
        "Open the FBR34KER maintenance menu": (
            "Legacy guided console interface. Maintains compatibility with "
            "previous B34ST versions while providing the full 15-category "
            "menu system."
        ),
        "View this B34ST session log": (
            "Review complete command transcript and evidence. Provides "
            "searchable access to all operations, with auto-generated "
            "summaries and structured reports."
        ),
        "Forensics and data acquisition": (
            "Extract data from devices including iCloud tokens, Keychain "
            "items, Keybag protection-class keys, activation bypass, "
            "baseband unlock, and passcode management."
        ),
        "CVE database & exploit chain planner": (
            "Search the CVE database, query by iOS version, and plan "
            "exploit chains for specific security objectives. Provides "
            "automata guided chain selection and compatibility checking."
        ),
        "Fuzzer orchestration": (
            "Schedule and manage fuzzing campaigns across multiple targets. "
            "Includes target discovery, scheduling, and result aggregation "
            "for vulnerability research."
        ),
        "Ramdisk maker and loader": (
            "Create deterministic FBRD bundles for iOS testing and "
            "validation. Includes guided workflows for building, "
            "inspecting, and loading iOS components."
        ),
        "Exit": (
            "Save session state and exit gracefully. Confirmation required "
            "to prevent accidental termination."
        ),
    }

    return descriptions.get(category, f"Documentation for {category} not available.")


def _load_augmented_help() -> dict[str, dict]:
    """
    Load augmented help with detailed explanations for each menu option.

    Returns:
        Dictionary with detailed help information
    """
    return {
        "External hardware / USBliter8 / first-stage execution": {
            "overview": "Targets A12+ iPhone/iPad via the DWC3 USB controller exploit",
            "automation": "Guided workflows with automatic hardware validation",
            "best_for": "First-time hardware exploitation, automated evidence collection",
            "risk_level": "High - requires physical device",
            "estimated_time": "10-30 minutes depending on setup",
        },
        "Load images, next stages, modules, or deployment": {
            "overview": "Manage boot chain components, modules, and deployment workflows",
            "automation": "Predefined deployment scripts with evidence validation",
            "best_for": "Controlled deployment with audit trails",
            "risk_level": "Medium - requires authorization",
            "estimated_time": "5-15 minutes",
        },
        "Authorized runtime modifications and evidence": {
            "overview": "Perform kernel patches, secure boot bypass, persistence operations",
            "automation": "Evidence-gated with mandatory verification",
            "best_for": "Research environments with strict evidence requirements",
            "risk_level": "High - memory writes enabled",
            "estimated_time": "15-45 minutes",
        },
        "Build, test, and QEMU simulation": {
            "overview": "Verify host readiness, build artifacts, run tests, simulate",
            "automation": "Complete automation with all builds and test suites",
            "best_for": "Continuous integration, initial setup, verification",
            "risk_level": "Low - no hardware required",
            "estimated_time": "30-120 minutes depending on build size",
        },
        "Runtime console / logger / shell": {
            "overview": "Interactive shell for exploration, logging, and debugging",
            "automation": "Live recording with export capabilities",
            "best_for": "Real-time investigation and forensic analysis",
            "risk_level": "Low - read-only by default",
            "estimated_time": "As needed",
        },
        "Evidence, validation, and release": {
            "overview": "Validate sessions, generate reports, package releases",
            "automation": "Full automation with validation gates",
            "best_for": "Release management with audit requirements",
            "risk_level": "High - high-privilege operations",
            "estimated_time": "10-30 minutes",
        },
        "Targeted IPSW downloads, upgrades, and tethered downgrades": {
            "overview": "Manage iOS firmware with signed updates and guided workflows",
            "automation": "Guided with configurable preserve-data options",
            "best_for": "iOS firmware management with data preservation",
            "risk_level": "Medium - requires device authorization",
            "estimated_time": "20-60 minutes",
        },
        "Create a bounded environment plan": {
            "overview": "Plan iOS 17+ research environments with exact configuration",
            "automation": "Structured planning with validation",
            "best_for": "Research environment setup with documentation",
            "risk_level": "Low - planning only",
            "estimated_time": "5-10 minutes",
        },
        "Open the FBR34KER maintenance menu": {
            "overview": "Legacy guided console with 15-category menu system",
            "automation": "Original guided workflows preserved",
            "best_for": "Existing users familiar with legacy interface",
            "risk_level": "Same as original",
            "estimated_time": "As needed",
        },
        "View this B34ST session log": {
            "overview": "Review complete command transcript with evidence summaries",
            "automation": "Auto-generated reports and searchable logs",
            "best_for": "Audit trails and investigation documentation",
            "risk_level": "Low - read-only access",
            "estimated_time": "5-20 minutes",
        },
        "Forensics and data acquisition": {
            "overview": "Comprehensive data collection from connected devices",
            "automation": "Profile-based acquisition with validation",
            "best_for": "Systematic forensic data collection",
            "risk_level": "High - read device state",
            "estimated_time": "30-120 minutes",
        },
        "CVE database & exploit chain planner": {
            "overview": "Plan and suggest exploit chains for specific goals",
            "automation": "AI-assisted suggestion with version compatibility",
            "best_for": "Strategic exploitation planning",
            "risk_level": "Medium - planning only",
            "estimated_time": "5-15 minutes",
        },
        "Fuzzer orchestration": {
            "overview": "Schedule and manage fuzzing campaigns across targets",
            "automation": "Automated scheduling with predefined targets",
            "best_for": "Security research and vulnerability discovery",
            "risk_level": "High - may generate crashes",
            "estimated_time": "Variable",
        },
        "Ramdisk maker and loader": {
            "overview": "Create deterministic FBRD bundles with iOS compatibility",
            "automation": "Guided production with template support",
            "best_for": "Deterministic iOS image creation",
            "risk_level": "High - requires approved components",
            "estimated_time": "30-90 minutes",
        },
        "Exit": {
            "overview": "Save and exit with session confirmation",
            "automation": "Auto-save and cleanup",
            "best_for": "Graceful teardown of interactive sessions",
            "risk_level": "Low - safe operation",
            "estimated_time": "Immediately",
        },
    }


def _help_for_category(subtitle: str) -> None:
    categories = {
        "Safe simulation workflow": {
            "1": "Validate host, build QEMU profile, run test",
            "2": "Standard simulation (QEMU virt)",
            "3": "Guided simulation with validation",
        },
        "Build, test, and simulation": {
            "1": "System diagnostics (doctor check)",
            "2": "Complete project build (13 targets)",
            "3": "Run firmware tests",
            "4": "QEMU integration tests",
            "5": "Non-QEMU verification",
            "6": "Full verification with QEMU",
            "7": "Hardware-probe QEMU test",
            "8": "Clean build artifacts",
        },
        "Build, test, and QEMU simulation": {
            "1": "System diagnostics (doctor check)",
            "2": "Complete project build (13 targets)",
            "3": "Run firmware tests",
            "4": "QEMU integration tests",
            "5": "Non-QEMU verification",
            "6": "Full verification with QEMU",
            "7": "Hardware-probe QEMU test",
            "8": "Clean build artifacts",
        },
        "A12+ USBliter8 — Pwn, Inspect, Jailbreak": {
            "1": "Run hardware guide and checklist",
            "2": "Prepare hardware/firmware (guided)",
            "3": "Pwn & Inspect — full protection audit",
            "4": "USBliter8 jailbreak chain",
            "5": "Connect to runtime console for exploration",
            "6": "iRecovery device state query",
            "7": "iRecovery firmware verification",
            "8": "Authorized first-stage bring-up",
            "9": "Collect adapter evidence",
            "10": "Authorized adapter reset",
        },
        "External hardware / USBliter8 / first-stage execution": {
            "1": "Run hardware guide and checklist",
            "2": "Prepare hardware and firmware",
            "3": "Pwn and inspect an authorized device",
            "4": "Run the USBliter8 jailbreak chain",
            "5": "Connect to the runtime console",
            "6": "Query iRecovery device state",
            "7": "Verify firmware compatibility",
            "8": "Perform authorized first-stage bring-up",
            "9": "Collect adapter evidence",
            "10": "Reset the adapter session",
        },
        "Guided research-runtime workflow": {
            "1": "Launch evidence-gated B34ST orchestrator",
            "2": "Generate runtime-stage evidence template",
            "3": "Create exact-kernel evidence template",
        },
        "Authorized modification workflows": {
            "1": "Evidence-gated kernel/bootstrap workflow",
            "2": "Validate external modification evidence",
            "3": "Generate evidence template",
        },
        "Authorized runtime modifications and evidence": {
            "1": "Kernel patch workflow with evidence gates",
            "2": "Secure boot bypass workflow",
            "3": "Persistence workflow",
            "4": "Validate external modification evidence",
            "5": "Generate evidence templates",
        },
        "Evidence, validation, and release": {
            "1": "Validate a session bundle",
            "2": "Explain a failed physical session",
            "3": "Compare two evidence bundles",
            "4": "Generate a physical-validation report",
            "5": "Release gate checks",
            "6": "Package release",
        },
        "Targeted IPSW and restore workflows": {
            "1": "List firmware for a product",
            "2": "List currently signed firmware",
            "3": "Download a targeted IPSW",
            "4": "Inspect and verify a local IPSW",
            "5": "Plan signed update preserving data",
            "6": "Execute signed update preserving data",
            "7": "Erase restore",
            "8": "Guided tethered downgrade",
            "9": "Explain tethered downgrade requirements",
        },
        "Targeted IPSW downloads, upgrades, and tethered downgrades": {
            "1": "List firmware for a product",
            "2": "List currently signed firmware",
            "3": "Download a targeted IPSW",
            "4": "Inspect and verify a local IPSW",
            "5": "Plan a signed update preserving data",
            "6": "Execute a signed update preserving data",
            "7": "Perform an erase restore",
            "8": "Guided tethered downgrade",
            "9": "Explain tethered downgrade requirements",
        },
        "Load images, next stages, modules, or deployment": {
            "1": "Plan or execute deployment workflows",
            "2": "Manage runtime modules",
            "3": "Build or inspect boot images",
            "4": "Review loader and next-stage flows",
        },
        "Ramdisk maker and loader": {
            "1": "Guided maker/loader (recommended)",
            "2": "Explain components, compatibility, adapter",
            "3": "List exact profiled targets",
            "4": "Create target/build compatibility plan",
            "5": "Build deterministic FBRD bundle",
            "6": "Inspect and verify an FBRD bundle",
            "7": "Plan or execute external adapter load",
        },
        "Forensics and data acquisition": {
            "1": "List built-in acquisition profiles",
            "2": "Quick acquisition (filesystem + network)",
            "3": "Full acquisition (memory + storage + filesystem + network)",
            "4": "Memory-only acquisition",
            "5": "Storage-only acquisition",
            "6": "Filesystem-only acquisition",
            "7": "Network-only acquisition",
            "8": "Verify an evidence bundle",
            "9": "iCloud/Keychain/Keybag acquisition",
            "10": "Activation/FMI/Baseband operations",
            "11": "Passcode management",
        },
        "CVE database & exploit chain planner": {
            "1": "Show database statistics",
            "2": "Search CVEs by keyword",
            "3": "Query CVEs for a version",
            "4": "Plan exploit chain for a goal",
            "5": "Suggest achievable goals for a version",
            "6": "List available exploit goals",
            "7": "Filter CVEs by criteria",
        },
        "Fuzzer orchestration": {"1": "List available fuzz targets"},
        "Runtime console / logger / shell": {
            "1": "Open an interactive runtime console",
            "2": "Capture and export logs",
            "3": "Inspect runtime state safely",
        },
        "Create a bounded environment plan": {
            "simulation": "Create a safe simulation plan",
            "research-runtime": "Create an evidence-gated runtime plan",
        },
        "Open the FBR34KER maintenance menu": {
            "1": "Launch the legacy guided maintenance console"
        },
        "View this B34ST session log": {
            "1": "Review the session transcript",
            "2": "Inspect collected evidence paths",
        },
        "Exit": {"0": "Save the session log and exit the control panel"},
        "Environment planning": {
            "simulation": "Review, verify, and launch virtualization",
            "research-runtime": "Guide for evidence-gated orchestration",
        },
    }

    if subtitle in categories:
        print("  Help - " + subtitle + ":")
        for key, desc in categories[subtitle].items():
            print(f"    {key}. {desc}")
        print("    h or ? - Show this help again")
        print("    q - Return to previous menu")
    else:
        print(f"  Help for '{subtitle}' not available")
        print("  Press q to continue")


def _help_for_whole_menu() -> None:
    """
    Display comprehensive help for the entire main menu system.
    """
    print("\n" + "=" * 70)
    print("B34ST MENU SYSTEM - COMPREHENSIVE HELP")
    print("=" * 70)

    print("\nThe B34ST (B34KER/STAR) unified control panel provides 15 main workflow")
    print("categories for conducting authorized physical validation and")
    print("research on A12+ iPhone/iPad hardware.\n")

    print("Each category contains guided workflows with:")
    print("  • Interactive step-by-step instructions")
    print("  • Smart defaults for common use cases")
    print("  • Comprehensive help documentation")
    print("  • Evidence-gated operations for security")
    print("  • Session logging and audit trails\n")

    menu_options = _main_menu_options()

    print("Main Workflow Categories:")
    print("-" * 70)

    for key, label, desc in menu_options:
        print(f"\n  {key}. {label}")
        print(f"     {desc}")

    print("\n" + "-" * 70)
    print("\nNavigation:")
    print("  • Press number to select a workflow")
    print("  • Press 'h' or '?' at prompts for detailed help")
    print("  • Press 'q' at any time to return to previous menu")
    print("  • Default selections are suggested for optimal first-time usage\n")

    print("Special Features:")
    print("  • Session logging — All operations recorded with timestamps")
    print("  • Evidence collection — Structured results with validation")
    print("  • Smart defaults — Context-aware recommendations")
    print("  • Help system — Category-specific guidance")
    print("  • Automation ready — Scriptable workflows available")
    print("  • Educational content — Step-by-step instructions")

    print("\n" + "=" * 70)


def _enhanced_prompt(
    label: str,
    options: dict[str, str],
    default: str | None = None,
    help_text: str | None = None,
) -> str:
    """
    Enhanced interactive prompt with comprehensive help and validation.

    Args:
        label: Prompt label
        options: Dictionary mapping choices to descriptions
        default: Default option (optional)
        help_text: Additional help information (optional)

    Returns:
        User's choice
    """
    if help_text:
        print(f"  {help_text}")
        print()

    print("  Available options:")
    for key, desc in options.items():
        marker = " (recommended)" if default and key == default else ""
        print(f"    {key}. {desc}{marker}")

    if default:
        prompt_text = f"{label} ({default})"
    else:
        prompt_text = label

    choice = _prompt(prompt_text, "")

    if choice == "?" or choice == "h":
        print("\n  Option details:")
        for key, desc in options.items():
            print(f"    {key}: {desc}")
        print("    Press Enter to use default or available choice")
        return _enhanced_prompt(label, options, default, help_text)

    return choice


def _smart_default_recommendation(
    category: str, device_info: dict | None = None
) -> tuple[str, str]:
    """
    Provide intelligent default recommendations based on category and device info.

    Args:
        category: Menu category
        device_info: Device information (optional)

    Returns:
        Tuple of (recommended_choice, reason)
    """
    if category == "Build, test, and simulation":
        if device_info and device_info.get("chipset", "").startswith("A12"):
            return (
                "6",
                "QEMU verification tests provide safe simulation for A12+ hardware",
            )
        return "1", "Start with system diagnostics to verify host environment"

    elif category == "Build, test, and QEMU simulation":
        if device_info and device_info.get("chipset", "").startswith("A12"):
            return "6", "QEMU verification gives the safest first pass for A12+ targets"
        return "1", "Start with host diagnostics before building or testing"

    elif category == "A12+ USBliter8 — Pwn, Inspect, Jailbreak":
        if device_info and device_info.get("chipset", "").startswith("A12"):
            return (
                "3",
                "Start with Pwn & Inspect for full protection audit of detected A12+ chipset",
            )
        return "2", "Begin with hardware preparation for USBliter8"

    elif category == "External hardware / USBliter8 / first-stage execution":
        if device_info and device_info.get("chipset", "").startswith("A12"):
            return (
                "3",
                "Inspect the detected hardware before attempting a full exploit chain",
            )
        return (
            "2",
            "Begin with hardware and firmware preparation before live device work",
        )

    elif category == "Load images, next stages, modules, or deployment":
        return (
            "1",
            "Start with deployment planning to verify image and module choices safely",
        )

    elif category == "Authorized runtime modifications and evidence":
        return (
            "1",
            "Begin with the evidence-gated kernel workflow before higher-risk modifications",
        )

    elif category == "Runtime console / logger / shell":
        return "1", "Open the console first to inspect live state before making changes"

    elif category == "Evidence, validation, and release":
        return (
            "1",
            "Validate the session bundle first before generating reports or release artifacts",
        )

    elif category == "Targeted IPSW and restore workflows":
        return "5", "Guided tethered downgrade is recommended for A12+ with validation"

    elif category == "Targeted IPSW downloads, upgrades, and tethered downgrades":
        return (
            "1",
            "List available firmware first so the plan uses a valid signed or cached target",
        )

    elif category == "Ramdisk maker and loader":
        return "1", "Guided maker/loader provides the most robust workflow"

    elif category == "Forensics and data acquisition":
        return (
            "2",
            "Quick acquisition is ideal for initial investigation with lower overhead",
        )

    elif category == "CVE database & exploit chain planner":
        return "4", "Plan exploit chain to achieve specific security objectives"

    elif category == "Fuzzer orchestration":
        return "1", "List available fuzz targets first to understand scope"

    elif category == "Environment planning":
        return "simulation", "Safe simulation workflow requires no physical hardware"

    elif category == "Create a bounded environment plan":
        return (
            "simulation",
            "A bounded simulation plan is the safest default starting point",
        )

    elif category == "Open the FBR34KER maintenance menu":
        return (
            "1",
            "Launch the legacy console only when you specifically need the older workflow surface",
        )

    elif category == "View this B34ST session log":
        return (
            "1",
            "Review the transcript first to understand command flow and evidence capture",
        )

    elif category == "Exit":
        return (
            "0",
            "Exit only after the current session transcript and evidence are reviewed",
        )

    return "", "No specific recommendation available"


def _guided_start(device_info: dict | None = None) -> tuple[str, str]:
    """
    Provide a single guided-start recommendation for first-time control-panel use.

    The control panel no longer has a separate guided-start screen, but callers and
    test helpers still rely on a stable recommendation hook.
    """
    return _smart_default_recommendation("Build, test, and simulation", device_info)


def _expand_menu_for_category(
    title: str, items: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """
    Intelligently expand menu items with additional subcategories.

    Args:
        title: Menu title
        items: Original menu items

    Returns:
        Expanded menu items with subcategories
    """
    expanded_items = list(items)

    category_expansions = {
        "Build, test, and simulation": [
            ("1a", "Host readiness verification only"),
            ("2a", "Build only QEMU virt monitor"),
            ("3a", "Build with security model (active validation)"),
            ("4a", "Quick job count setup"),
            ("5a", "Clean generated artifacts"),
        ],
        "A12+ USBliter8 — Pwn, Inspect, Jailbreak": [
            ("1a", "Review hardware guide and checklist"),
            ("2a", "Hardware preparation step-by-step"),
            ("3a", "Pwn & Inspect with live console"),
            ("4a", "Complete jailbreak chain (A12+ only)"),
            ("5a", "Runtime console with logging"),
            ("6a", "iRecovery status and debugging"),
            ("7a", "Guide for external adapter bring-up"),
            ("8a", "Evidence collection workflow"),
            ("9a", "Adapter session recovery"),
            ("10a", "Hardware reset procedure"),
        ],
        "Targeted IPSW and restore workflows": [
            ("8a", "Plan only (no-execution mode)"),
            ("9a", "Tutorial on tethered downgrade requirements"),
        ],
        "Ramdisk maker and loader": [
            ("6a", "Verify bundle integrity and compatibility"),
            ("7a", "Plan-only load (no execution)"),
        ],
        "Forensics and data acquisition": [
            ("2a", "Quick with network connectivity"),
            ("3a", "Full with minimal overhead"),
            ("8a", "Verify extracted artifacts"),
        ],
    }

    if title in category_expansions:
        for item in category_expansions[title]:
            expanded_items.append(item)

    return expanded_items


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

        print("\n  A12+ USBliter8 — Pwn, Inspect, Jailbreak")
        print("=" * 64)
        print("\n  This workflow targets A12+ devices (CPID 0x8015 and above)")
        print("  using the DWC3 USB controller exploit chain.")
        print()
        print("  Hardware Requirements:")
        print("    • Waveshare RP2350 USB-A adapter (~$15-25)")
        print("    • High-quality USB-A to Lightning cable (Apple OEM recommended)")
        print("    • Device in DFU mode (A12+ only)")
        print("    • pyusb/libusb installed on host")
        print()
        print("  Security Model:")
        print("    • State model: No kernel memory writes (default, safe)")
        print(
            "    • Active model: Memory writes enabled (requires explicit authorization)"
        )
        print()
        print("  Workflow Overview:")
        print("    1. Hardware preparation and validation")
        print("    2. DWC3 exploit chain (PWNDFU → monitor → jailbreak)")
        print("    3. Evidence collection and research runtime")
        print("    4. Console exploration and evidence validation")
        print()

        print("  Available operations:")
        print("    H. USBliter8 hardware guide — detailed setup and compatibility")
        print("    P. Prepare hardware/firmware — guided checklist (skip if done)")
        print()
        print("  Exploitation:")
        print("    1. Pwn & Inspect — Complete protection audit and system inspection")
        print("    2. USBliter8 jailbreak — Full A12+ chain with kernel boot")
        print("    3. Guided research runtime — Evidence-gated orchestration")
        print("    4. Device inspection — Read-only hardware information")
        print("    5. iRecovery query — Connected device state")
        print("    6. iRecovery verification — Profile validation")
        print("    7. Adapter bring-up — First-stage authorized execution")
        print("    8. Collect evidence — Adapter session capture")
        print("    9. Adapter reset — Authorized session recovery")
        print("    0. Return to main menu")
        print()

        choice = _prompt("  Selection", "2")

        if choice.lower() == "h":
            _usbliter8_hardware_guide(session)
        elif choice.lower() == "p":
            _usbliter8_prepare_hardware(session)
        elif choice == "1":
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
        print("  8. Guided tethered downgrade (recommended)")
        print("  9. Explain tethered downgrade requirements")
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
        elif choice == "8":
            _guided_tethered_downgrade(session)
            _pause()
        elif choice == "9":
            _explain_tethered_downgrade()
            _pause()
        elif choice in {"0", "q", ""}:
            return


def _explain_tethered_downgrade() -> None:
    print(
        "\nTethered downgrade: what it means\n"
        "---------------------------------\n"
        "• The target IPSW is unsigned and cannot use Apple's stock restore path.\n"
        "• The result is temporary. The external boot stage must run after every restart.\n"
        "• B34ST validates the IPSW, records the plan, and invokes an adapter.\n"
        "• B34ST does not bundle the target-specific external tether adapter.\n"
        "• The adapter reads request JSON on stdin and writes response JSON on stdout.\n"
        "\nWhat the tether adapter is:\n"
        "  A separately installed, target-specific executable—a program, script,\n"
        "  or reviewed wrapper around lab boot tooling. It communicates with the\n"
        "  device in DFU/recovery mode and performs the external boot sequence\n"
        "  B34ST cannot perform itself.\n"
        "\nWhat it is not:\n"
        "  It is not the IPSW, a USB cable, idevicerestore, or a generic component\n"
        "  bundled with B34ST.\n"
        "\nPublic options and compatibility:\n"
        "  Semaphorin and other checkm8-era tools target A11 and earlier hardware.\n"
        "  palera1n is a jailbreak, futurerestore is a blob-based restore workflow,\n"
        "  and libirecovery/idevicerestore are components rather than adapters.\n"
        "  None is a verified drop-in adapter for B34ST's current A12+ profiles.\n"
        "\nRecommended path:\n"
        "  1. Select Guided tethered downgrade.\n"
        "  2. Choose a local IPSW or an Apple catalog download.\n"
        "  3. Provide the reviewed adapter command, or leave it blank for plan-only.\n"
        "  4. Review the exact target and SHA-256 before authorizing execution.\n"
        "\nAdapter configuration:\n"
        "  export B34ST_TETHER_ADAPTER='/absolute/path/to/adapter [arguments]'\n"
        "\nFull guide: docs/TETHERED_DOWNGRADE.md"
    )


def _guided_tethered_downgrade(
    session: Session,
    *,
    product: str | None = None,
    ecid: str | None = None,
) -> int:
    command = [
        "ipsw",
        "tethered-downgrade-guide",
        "--evidence",
        str(session.directory / "tethered-downgrade.json"),
    ]
    if product:
        command += ["--product", product]
    if ecid:
        command += ["--ecid", ecid]
    return session.run(
        command,
        label="Guided tethered downgrade",
        interactive=True,
    )


def _explain_ramdisk_workflow() -> None:
    print(
        "\nRamdisk maker / loader: what it does\n"
        "------------------------------------\n"
        "• The maker packages a prepared ramdisk, kernelcache, DeviceTree, and\n"
        "  optional boot-chain files into one deterministic, hash-verified .fbrd.\n"
        "• It verifies an exact iPhone, iPad, or Apple silicon Mac profile and\n"
        "  records the exact iOS/iPadOS/macOS version and build.\n"
        "• It does not decrypt, patch, or Apple-sign firmware components.\n"
        "• The loader validates every bundled byte before creating a load request.\n"
        "\nWhat the ramdisk adapter is:\n"
        "  A separately installed, target- and OS-build-specific executable or\n"
        "  reviewed wrapper around authorized lab boot tooling. B34ST sends it\n"
        "  one bounded JSON request; the adapter owns DFU/recovery transport and\n"
        "  returns one JSON evidence result. It is not bundled with B34ST.\n"
        "\nCompatibility:\n"
        "  B34ST profiles A12, A12X/Z, A13, A14, A15, M1, and M2 products listed\n"
        "  by 'fbr34ker ramdisk list-targets'. These profiles are simulated, not\n"
        "  proof that a particular OS build boots. Exact adapter evidence remains\n"
        "  mandatory. Intel Macs and unlisted products are rejected.\n"
        "\nRecommended path:\n"
        "  1. Select the guided workflow and enter the exact product and OS build.\n"
        "  2. Review the compatibility plan.\n"
        "  3. Provide already prepared core components and build the .fbrd.\n"
        "  4. Inspect the bundle; load remains plan-only by default.\n"
        "  5. Configure B34ST_RAMDISK_ADAPTER and authorize execution separately.\n"
        "\nFull guide: docs/RAMDISK_MAKER_LOADER.md"
    )


def _guided_ramdisk(
    session: Session,
    *,
    product: str | None = None,
    ecid: str | None = None,
) -> int:
    command = [
        "ramdisk",
        "guide",
        "--evidence",
        str(session.directory / "ramdisk-workflow.json"),
    ]
    if product:
        command += ["--product", product]
    if ecid:
        command += ["--ecid", ecid]
    return session.run(command, label="Guided ramdisk maker / loader", interactive=True)


def _ramdisk_workflows(session: Session) -> None:
    while True:
        _clear()
        _header(session, "Ramdisk maker and loader")
        print("  1. Guided maker / loader (recommended)")
        print("  2. Explain components, compatibility, and adapter")
        print("  3. List exact profiled iPhone, iPad, and Mac targets")
        print("  4. Create a target/build compatibility plan")
        print("  5. Build a deterministic FBRD bundle")
        print("  6. Inspect and verify an FBRD bundle")
        print("  7. Plan or execute an external adapter load")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            _guided_ramdisk(session)
            _pause()
        elif choice == "2":
            _explain_ramdisk_workflow()
            _pause()
        elif choice == "3":
            session.run(["ramdisk", "list-targets"], label="Ramdisk target catalog")
            _pause()
        elif choice == "4":
            _run_prompted(
                session,
                ["ramdisk", "plan"],
                label="Ramdisk compatibility plan",
                example="--product iPhone12,1 --os-version 18.5 --build 22F76",
            )
        elif choice == "5":
            _run_prompted(
                session,
                ["ramdisk", "build"],
                label="Build ramdisk bundle",
                example="--product iPhone12,1 --os-version 18.5 --build 22F76 --ramdisk ramdisk.dmg --kernelcache kernelcache --devicetree DeviceTree.dtb --trustcache trustcache --output build/ramdisk/iphone12-1.fbrd",
            )
        elif choice == "6":
            _run_prompted(
                session,
                ["ramdisk", "inspect"],
                label="Inspect ramdisk bundle",
                example="build/ramdisk/iphone12-1.fbrd --json",
            )
        elif choice == "7":
            _run_prompted(
                session,
                ["ramdisk", "load"],
                label="Ramdisk adapter load",
                example="build/ramdisk/iphone12-1.fbrd --evidence ramdisk-load.json",
                interactive=True,
            )
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


def _usbliter8_hardware_guide(session: Session) -> None:
    _clear()
    _header(session, "USBliter8 Hardware Guide")
    print("Recommended hardware: Waveshare RP2350 USB-A")
    print("  - RP2350 dual-core Cortex-M33/RISC-V")
    print("  - Native USB-A host port — no adapter needed")
    print("  - USB 2.0 High Speed (480 Mbps)")
    print("  - Price: ~$15-25 USD")
    print("  - Open source SDK (Pico SDK, MicroPython, CircuitPython)")
    print()
    print("Full guide: docs/USBLITER8_HARDWARE_GUIDE.md")
    print()
    print("Quick hardware checklist:")
    items = [
        "USB host: xHCI, ASMedia xHCI, or RP2350 PIO-based USB (avoid VIA USB 3.0)",
        "Cable: high-quality USB-A to Lightning data sync cable (Apple OEM or Anker)",
        "Power: host port provides at least 500 mA",
        "Device: A12+ (CPID >= 0x8015) in DFU mode",
    ]
    for item in items:
        print(f"  - {item}")
    print()
    print("Skip options at each stage:")
    print("  --skip-hardware-prep  Skip hardware preparation checklist")
    print("  --skip-build          Skip operational image build")
    print("  --no-dfu-wait         Skip DFU wait (device already in DFU)")
    print("  --no-console          Skip console connection after exploit")
    print()
    session.record("USBliter8 hardware guide viewed")
    _pause()


def _usbliter8_prepare_hardware(session: Session) -> int:
    _clear()
    _header(session, "USBliter8 Hardware & Firmware Preparation")
    print("Guided preparation checklist. Each item can be skipped if already done.\n")

    items = [
        ("Host USB controller", "Check xHCI/ASMedia/RP2350"),
        ("Cable and power", "Data cable, adequate power"),
        ("Device in DFU mode", "Verify A12+ device in DFU"),
        ("pyusb/libusb", "Host dependencies installed"),
        ("Operational image", "build-exploit/fbr34ker-operational.bin"),
    ]

    statuses = {}
    for i, (item, desc) in enumerate(items, 1):
        skip = _prompt(f"  [{i}/{len(items)}] {item} ({desc}) — done? (Y/skip)", "Y")
        if skip.lower() in ("s", "skip"):
            statuses[item] = "skipped"
            print(f"    -> Skipped")
        else:
            statuses[item] = "done"
            print(f"    -> Done")

    prep_record = session.directory / "hardware-prep.json"
    import json

    prep_record.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "stage": "hardware_preparation",
                "status": "completed",
                "items": [{"item": k, "status": v} for k, v in statuses.items()],
                "session": str(session.directory),
            },
            indent=2,
        )
        + "\n"
    )
    session.record(f"Hardware preparation record: {prep_record}")

    build_skip = _prompt("Build operational image? (Y/skip)", "Y")
    if not build_skip.lower() in ("s", "skip"):
        session.run_command(
            ["make", "build-operational"], label="Build operational image"
        )
    else:
        session.record("Operational image build skipped by user")
        print("Skipped build. Ensure build-exploit/fbr34ker-operational.bin exists.")

    print(f"\nPreparation record saved: {prep_record.relative_to(ROOT)}")
    session.record("Hardware preparation completed")
    _pause()
    return 0


def _usbliter8_jailbreak(session: Session) -> int:
    _clear()
    _header(session, "A12+ USBliter8 Jailbreak")
    print("Targets A12+ devices (CPID 0x8015 and above) in DFU mode.")
    print("Exploit: DWC3 USB controller firmware patch (USBliter8)")
    print("Payload: FBR34KER monitor + full post-exploit chain")
    print()
    print("Step 1 — Hardware preparation")
    prep_skip = _prompt("Run hardware preparation checklist? (Y/skip)", "Y")
    if not prep_skip.lower() in ("s", "skip"):
        _usbliter8_prepare_hardware(session)
    else:
        session.record("USBliter8 jailbreak: hardware prep skipped by user")
        print("Hardware preparation skipped.")

    print("\nStep 2 — Firmware preparation")
    operational_bin = ROOT / "build-exploit" / "fbr34ker-operational.bin"
    if operational_bin.is_file():
        rebuild = _prompt(
            f"Found existing image ({operational_bin.stat().st_size} bytes). Rebuild? (y/N)",
            "N",
        )
        if rebuild.lower() in ("y", "yes"):
            session.run_command(
                ["make", "build-operational"], label="Build operational image"
            )
        else:
            session.record("USBliter8 jailbreak: image build skipped (exists)")
            print("Using existing operational image.")
    else:
        build = _prompt("No operational image found. Build now? (Y/n)", "Y")
        if not build.lower() in ("n", "no"):
            session.run_command(
                ["make", "build-operational"], label="Build operational image"
            )
        else:
            print("Cannot proceed without operational image.")
            _pause()
            return 1

    _clear()
    _header(session, "A12+ USBliter8 Jailbreak — Execution")
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
        "--monitor",
        str(operational_bin),
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
        try:
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    print(line, end="")
                    session.record(line.rstrip("\n"))
        except (OSError, IOError) as exc:
            print(f"\n[WARN] subprocess stream error: {exc}", file=sys.stderr)
        return_code = process.returncode
        if return_code is None:
            try:
                process.wait(timeout=5)
                return_code = process.returncode
            except (subprocess.TimeoutExpired, OSError):
                process.kill()
                try:
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                rc = process.returncode
                if rc is None:
                    rc = -9
                return_code = rc
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

    if return_code == 0 and _confirm("Return to B34ST main menu"):
        return 0

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
        from scripts.run_exploit import ExploitError
    except ImportError:
        print("run_exploit.py not found in scripts/", file=sys.stderr)
        session.record("USBliter8 pwn-and-inspect aborted: run_exploit.py missing")
        _pause()
        return 1

    exploit_script = ROOT / "scripts" / "run_exploit.py"
    evidence_path = session.directory / "usbliter8-inspect.json"
    report_path = session.directory / "pwn-inspect-report.json"
    operational_bin = ROOT / "build-exploit" / "fbr34ker-operational.bin"

    if not operational_bin.is_file():
        print("No operational image found. Building now...")
        build_rc = session.run_command(
            ["make", "build-operational"],
            label="Build operational image",
        )
        if build_rc != 0:
            print("Inspection cannot proceed without an operational image.")
            _pause()
            return 1

    pwndfu_ok = False
    chipset_info = None
    chain_results = {}
    console_inspection: dict[str, str] = {}

    pwndfu_label = "USBliter8 PWNDFU + monitor boot"
    pwndfu_cmd = [
        sys.executable,
        str(exploit_script),
        "--monitor",
        str(operational_bin),
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
            ("board-info", "Selected board and device inventory"),
            ("boot-evidence", "Boot evidence collection status"),
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
            except OSError:
                pass

    try:
        from host.chipset_db import all_chipsets, chipset_summary

        all_socs = {c["cpid"]: c for c in all_chipsets()}
    except ImportError:
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
        "version": __version__,
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
        print(
            " 10. Activation/FMI/Baseband operations  (bypass, FMI on/off, baseband unlock)"
        )
        print(" 11. Passcode management  (on/off/change/bypass)")
        print("  0. Back")
        choice = _prompt("Selection", "1")
        if choice == "1":
            session.run(
                ["forensics", "list-profiles"], label="List acquisition profiles"
            )
            _pause()
        elif choice in {"2", "3", "4", "5", "6", "7"}:
            profile_map = {
                "2": "quick",
                "3": "full",
                "4": "memory-only",
                "5": "storage-only",
                "6": "filesystem-only",
                "7": "network-only",
            }
            profile = profile_map[choice]
            device_id = _prompt("Device identifier", "unknown")
            operator = _prompt("Operator name")
            bundle_path = session.directory / f"forensics-{profile}.zip"
            session.run(
                [
                    "forensics",
                    "acquire",
                    "--profile",
                    profile,
                    "--device-id",
                    device_id,
                    "--operator",
                    operator or "",
                    "--bundle",
                    str(bundle_path),
                ],
                label=f"Acquisition: {profile}",
            )
            if bundle_path.exists():
                print(f"\nEvidence bundle: {bundle_path.relative_to(ROOT)}")
            _pause()
        elif choice == "8":
            path = _prompt("Evidence bundle path")
            if path and path != "q":
                session.run(
                    ["forensics", "verify", path], label="Verify evidence bundle"
                )
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
        print(
            "  2. Apply full activation bypass (clear records + patch daemon + inject ticket)"
        )
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
            session.run(
                ["forensics", "activation", "status"], label="Activation status"
            )
            _pause()
        elif choice == "2":
            if _confirm("Apply full activation bypass"):
                session.run(
                    ["forensics", "activation", "bypass"], label="Activation bypass"
                )
            _pause()
        elif choice == "3":
            if _confirm("Clear activation records"):
                session.run(
                    ["forensics", "activation", "clear-records"], label="Clear records"
                )
            _pause()
        elif choice == "4":
            session.run(
                ["forensics", "activation", "fmi", "status"], label="FMI status"
            )
            _pause()
        elif choice == "5":
            if _confirm("Turn FMI OFF"):
                session.run(["forensics", "activation", "fmi", "off"], label="FMI off")
            _pause()
        elif choice == "6":
            if _confirm("Turn FMI ON"):
                session.run(["forensics", "activation", "fmi", "on"], label="FMI on")
            _pause()
        elif choice == "7":
            if _confirm("Clear FMI activation lock"):
                session.run(
                    ["forensics", "activation", "fmi", "clear-activation-lock"],
                    label="Clear FMI lock",
                )
            _pause()
        elif choice == "8":
            session.run(
                ["forensics", "activation", "baseband", "status"],
                label="Baseband status",
            )
            _pause()
        elif choice == "9":
            if _confirm("Unlock baseband (SIM lock)"):
                session.run(
                    ["forensics", "activation", "baseband", "unlock"],
                    label="Baseband unlock",
                )
            _pause()
        elif choice == "10":
            output = session.directory / "activation-query"
            session.run(
                ["forensics", "activation", "query-all", "--output", str(output)],
                label="Query all activation state",
            )
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
            session.run(["forensics", "passcode", "status"], label="Passcode status")
            _pause()
        elif choice == "2":
            session.run(["forensics", "passcode", "policy"], label="Passcode policy")
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
                session.run(["forensics", "passcode", "set", new], label="Set passcode")
            else:
                print("Passcode must be at least 4 characters.")
            _pause()
        elif choice == "5":
            current = _prompt("Current passcode")
            new = _prompt("New passcode")
            if current and new and len(new) >= 4:
                session.run(
                    ["forensics", "passcode", "change", current, new],
                    label="Change passcode",
                )
            else:
                print("Both passcodes required; new must be at least 4 characters.")
            _pause()
        elif choice == "6":
            if _confirm("Attempt passcode bypass"):
                session.run(
                    ["forensics", "passcode", "bypass"], label="Passcode bypass"
                )
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
                session.run(
                    ["cve", "chain", goal, version],
                    label=f"Chain: {goal} on iOS {version}",
                )
            _pause()
        elif choice == "5":
            version = _prompt("Target iOS version", "16.5")
            if version:
                session.run(
                    ["cve", "suggest", version],
                    label=f"Suggest goals for iOS {version}",
                )
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
        choice = _prompt(
            "Select [1] State model (default)  [2] Active security model", "1"
        )
        if choice == "1":
            enable = False
            break
        elif choice == "2":
            if not _confirm(
                "WARNING: Active security model WILL write to kernel memory. Continue"
            ):
                continue
            owner = _prompt('Type "I OWN OR AM AUTHORIZED TO TEST THIS DEVICE"')
            if owner != "I OWN OR AM AUTHORIZED TO TEST THIS DEVICE":
                print("Authorization not confirmed.")
                continue
            enable = True
            print(
                f"\n{Colors.RED}Active security model selected. Writes to kernel memory are enabled.{Colors.RESET}"
            )
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
        device = snapshot.get("device") or {}
        _guided_tethered_downgrade(
            session,
            product=product,
            ecid=str(device.get("ecid")) if device.get("ecid") else None,
        )
        _pause()
        return
    if action_id == "ramdisk":
        device = snapshot.get("device") or {}
        _guided_ramdisk(
            session,
            product=product,
            ecid=str(device.get("ecid")) if device.get("ecid") else None,
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
        print(
            f"\n{Colors.RED}SECURITY MODEL ACTIVE: memory writes enabled{Colors.RESET}"
        )
    else:
        session.run(["build"], label="Build (state model only)")
        print(
            f"\n{Colors.GREEN}State model only: no kernel memory writes{Colors.RESET}"
        )
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

        print("\n  What are you trying to achieve? (Choose a workflow)")
        print("\n" + "-" * 64)

        main_menu_options = _main_menu_options()

        print("  Main workflow selection:")
        for key, label, desc in main_menu_options:
            print(f"    {key}. {label}")
            print(f"       {Colors.DIM}{desc}{Colors.RESET}")
        print()

        choice = _enhanced_prompt(
            "\n  Selection", {key: label for key, label, _ in main_menu_options}, "1"
        )

        choice = choice.lower()

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
            mode = _enhanced_prompt(
                "Mode",
                {
                    "simulation": "Safe simulation - no hardware required, full observability",
                    "research-runtime": "Evidence-gated - requires adapter and exact kernel evidence",
                },
                "simulation",
            )
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
        elif choice == "14":
            _ramdisk_workflows(session)
        elif choice == "0":
            session.record("B34ST control-panel session ended")
            print(f"\nSession log: {session.log_path.relative_to(ROOT)}")
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(run_control_panel())
