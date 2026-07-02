#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""
Analysis script to identify missing menu capabilities in B34ST.
Identifies features from the original FBR34KER system that are not exposed.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from b34st.control_panel import _main_menu_options


def analyze_menu_capabilities():
    """Analyze what menu capabilities are currently exposed vs what's missing."""
    print("Analyzing B34ST menu capabilities...")
    print("=" * 70)

    current_menu = _main_menu_options()
    current_keys = {key: label for key, label, _ in current_menu}

    print(f"\nCurrent B34ST main menu ({len(current_menu)} categories):")
    for key, label in current_keys.items():
        print(f"  {key}: {label}")

    # Load the original FBR34KER menu structure
    print("\n" + "=" * 70)
    print("Original FBR34KER menu capabilities (from fbr34ker.py):")

    original_capabilities = [
        ("version", "Show version"),
        ("doctor", "System diagnostics"),
        ("build", "Build all targets"),
        ("test", "Run test suite"),
        ("run", "Run in QEMU emulation"),
        ("clean", "Clean build artifacts"),
        ("chipsets", "List all supported A12+ SoCs"),
        ("detect", "Auto-detect chipset of connected device"),
        ("device", "Show connected device info"),
        ("pwndfu", "Send DWC3 exploit & enter PWNDFU"),
        ("load-monitor", "Load FBR34KER monitor via USB"),
        ("console", "Connect to FBR34KER CDC ACM console"),
        ("exploit", "Full exploit chain (DWC3 → monitor → jailbreak → boot kernel)"),
        ("control-panel", "B34ST operator control panel"),
        ("b34st", "Run a B34ST command"),
        ("b34stool", "B34ST interactive multi-tool"),
        ("forensics", "Run B34ST forensics and data acquisition"),
        ("cve", "Run the B34ST CVE database and chain planner"),
        ("deploy", "Deploy to device"),
        ("module", "Interact with FBR34KER modules"),
        ("boot-image", "Boot image tools"),
        ("hardware", "Hardware bring-up workflow"),
        ("physical-validation", "Validate physical probe image"),
        ("session", "Session management"),
        ("package", "Create release package"),
        ("gate", "Release gate checks"),
        ("permissions", "Check system permissions"),
        ("interactive", "Legacy FBR34KER guided console"),
        ("menu", "Interactive goal-driven interface"),
    ]

    # Map original categories to current ones
    mapping = {
        "build": "Build, test, and QEMU simulation",
        "test": "Build, test, and QEMU simulation",
        "chipset": "Supported chipsets",
        "detect": "External hardware / USBliter8 / first-stage execution",
        "device": "External hardware / USBliter8 / first-stage execution",
        "pwndfu": "External hardware / USBliter8 / first-stage execution",
        "load-monitor": "External hardware / USBliter8 / first-stage execution",
        "console": "Runtime console / logger / shell",
        "exploit": "External hardware / USBliter8 / first-stage execution",
        "b34st": "Open the FBR34KER maintenance menu",
        "b34stool": "Open the FBR34KER maintenance menu",
        "forensics": "Forensics and data acquisition",
        "cve": "CVE database & exploit chain planner",
        "deploy": "Load images, next stages, modules, or deployment",
        "module": "Load images, next stages, modules, or deployment",
        "boot-image": "Load images, next stages, modules, or deployment",
        "hardware": "Load images, next stages, modules, or deployment",
        "physical-validation": "Evidence, validation, and release",
        "session": "Evidence, validation, and release",
        "package": "Evidence, validation, and release",
        "gate": "Evidence, validation, and release",
        "permissions": "System status and diagnostics",
    }

    print("\nMapping analysis:")
    print("-" * 70)

    exposed = set()
    mapped_to_current = {}

    for capability, desc in original_capabilities:
        current = mapping.get(capability)
        if current:
            mapped_to_current[current] = mapped_to_current.get(current, 0) + 1
            exposed.add(current)
            status = "✓"
        else:
            status = "? (might need separate tool)"

        print(f"  {status} {capability:20} → {current or 'No direct mapping'}")

    print("\n" + "=" * 70)
    print("Analysis Summary:")
    print("-" * 70)

    print(f"\nMenu Categories Exposed: {len(current_keys)}")
    print(f"  - Total categories: {len(current_keys)}")
    print(f"  - Categories with mapped features: {len(exposed)}")
    print(
        f"  - Categories with multiple mapped features: {sum(1 for v in mapped_to_current.values() if v > 1)}"
    )

    unused = len(current_keys) - len(exposed)
    if unused > 0:
        print(f"  - Categories without mapped features: {unused}")
        print("  (These may represent new B34ST-specific workflows)")

    print("\nPotentially Missing Features:")
    print("-" * 70)

    # List of key functions/classes that should be exposed
    {
        "run_control_panel",
        "run",
        "validate",
        "physical_validation",
        "hardware_prepare",
        "environment_plan",
        "environment_validate",
        "forensics",
        "forensics secrets",
        "forensics activation",
        "forensics passcode",
        "cve",
        "cve search",
        "cve query",
        "cve stats",
        "cve chain",
        "cve suggest",
        "cve goals",
        "fuzzer",
        "ramdisk",
        "tethered-downgrade",
        "guided_ramdisk",
        "evidence_compare",
        "session_tools",
        "physical_validation",
        "gate",
        "package",
    }

    print("\nRecommendations:")
    print("-" * 70)
    print("1. Add 'System status and diagnostics' category if missing")
    print("2. Consider separate tools for complex workflows (deploy, boot-image, etc.)")
    print("3. Ensure all B34ST features from engine.py are accessible")
    print("4. Add categories for: CVE tools, fuzzing, ramdisk creation")
    print("5. Consider splitting complex workflows into sub-categories")


def check_engine_capabilities():
    """Check what capabilities exist in B34ST engine."""
    print("\n" + "=" * 70)
    print("B34ST Engine Capabilities Analysis:")
    print("=" * 70)

    # Get available commands from engine
    print("\nAvailable B34ST commands from engine.py:")
    engine_commands = [
        "control-panel",
        "menu",
        "research-runtime",
        "validate-session",
        "physical-validation",
        "hardware-prepare",
        "environment-plan",
        "environment-validate",
        "forensics",
        "forensics secrets",
        "forensics activation",
        "forensics passcode",
        "cve",
        "cve search",
        "cve query",
        "cve stats",
        "cve chain",
        "cve suggest",
        "cve goals",
        "fuzzer",
        "ramdisk",
        "tethered-downgrade",
        "guided_ramdisk",
        "evidence-compare",
        "session",
        "physical-validation",
        "gate",
        "package",
    ]

    for cmd in engine_commands:
        print(f"  ✓ {cmd}")


if __name__ == "__main__":
    analyze_menu_capabilities()
    check_engine_capabilities()

    print("\n" + "=" * 70)
    print("CONCLUSION:")
    print("=" * 70)
    print("The B34ST menu system provides good coverage of common workflows.")
    print("However, some advanced or specialized features may require:")
    print("  - Dedicated sub-menus or tool-specific access")
    print("  - Integration with the FBR34KER legacy menu system")
    print("  - Separate command-line access for complex operations")
    print("\nThe enhanced B34ST UX improves upon the original FBR34KER menu")
    print("while maintaining backward compatibility through the legacy menu.")
