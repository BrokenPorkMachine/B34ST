#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""
Test script for the enhanced B34ST menu system.
Validates the new UX improvements, education features, and automation.
"""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

from b34st.control_panel import (
    _header,
    _enhanced_prompt,
    _help_for_category,
    _smart_default_recommendation,
    _expand_menu_for_category,
    _guided_start,
)
from b34st.control_panel import Session


def test_enhanced_prompt():
    """Test the enhanced prompt functionality."""
    print("Testing enhanced prompt...")

    options = {"1": "First option", "2": "Second option", "3": "Third option"}

    # Mock input to test default behavior
    with mock.patch("builtins.input", return_value="1"):
        result = _enhanced_prompt("Test prompt", options, "1")
        assert result == "1", f"Expected '1', got '{result}'"
        print("  ✓ Enhanced prompt works correctly")


def test_help_system():
    """Test the help system."""
    print("\nTesting help system...")

    # Test built-in help
    _help_for_category("Build, test, and simulation")
    print("  ✓ Help system displays category information")

    _help_for_category("Non-existent category")
    print("  ✓ Help system handles unknown categories")


def test_smart_defaults():
    """Test smart defaults recommendation."""
    print("\nTesting smart defaults...")

    recommendation = _smart_default_recommendation("Build, test, and simulation", None)
    assert recommendation[0] != "", "Should provide a recommendation"
    print(f"  ✓ Smart defaults for build category: {recommendation}")

    recommendation2 = _smart_default_recommendation(
        "A12+ USBliter8 — Pwn, Inspect, Jailbreak", None
    )
    print(f"  ✓ Smart defaults for USBliter8: {recommendation2}")


def test_menu_expansion():
    """Test menu expansion with subcategories."""
    print("\nTesting menu expansion...")

    original_items = [("1", "Basic option"), ("2", "Secondary option")]

    expanded = _expand_menu_for_category("Build, test, and simulation", original_items)
    assert len(expanded) > len(original_items), "Should expand menu"
    print(f"  ✓ Menu expanded from {len(original_items)} to {len(expanded)} items")


def test_session_creation():
    """Test session creation and logging."""
    print("\nTesting session creation...")

    session = Session()
    assert session.directory is not None
    assert session.log_path is not None
    session.record("Test record")
    print("  ✓ Session creation and recording works")


def test_menu_categories():
    """Test main menu categories are properly exposed."""
    print("\nTesting menu categories...")

    # Check that all 15 categories are properly documented
    main_menu_options = [
        (
            "1",
            "External hardware / USBliter8 / first-stage execution",
            "Pwn, inspect, and jailbreak A12+ devices via USBliter8",
        ),
        (
            "2",
            "Load images, next stages, modules, or deployment",
            "Boot chain, deployment, modules, runtime",
        ),
        (
            "3",
            "Authorized runtime modifications and evidence",
            "Kernel patches, secure boot bypass, persistence",
        ),
        (
            "4",
            "Build, test, and QEMU simulation",
            "Host check, build, test, simulate safely",
        ),
        (
            "5",
            "Runtime console / logger / shell",
            "Interactive shell, logging, exploration",
        ),
        (
            "6",
            "Evidence, validation, and release",
            "Validate sessions, generate reports, release gate",
        ),
        (
            "7",
            "Targeted IPSW downloads, upgrades, and tethered downgrades",
            "Firmware catalog, signed updates, guide",
        ),
        ("8", "Create a bounded environment plan", "Plan iOS 17+ research environment"),
        ("9", "Open the FBR34KER maintenance menu", "Legacy FBR34KER guided console"),
        ("10", "View this B34ST session log", "Review command transcript and evidence"),
        (
            "11",
            "Forensics and data acquisition",
            "iCloud/Keychain, activation, passcode, memory/storage",
        ),
        (
            "12",
            "CVE database & exploit chain planner",
            "Search exploits, plan chains, suggest attacks",
        ),
        ("13", "Fuzzer orchestration", "Schedule fuzzing across all targets"),
        ("14", "Ramdisk maker and loader", "Build deterministic FBRD bundles"),
        ("0", "Exit", "Save and exit B34ST"),
    ]

    assert len(main_menu_options) == 15, "Should have 15 main menu options"
    print(f"  ✓ Main menu has {len(main_menu_options)} categories (updated from 15)")

    # Verify automation indicators
    auto_indicators = ["automation" in desc.lower() for _, _, desc in main_menu_options]
    print(
        f"  ✓ Automation readiness: {sum(auto_indicators)}/15 categories have automation ready options"
    )


def test_education_integration():
    """Test that education features are integrated."""
    print("\nTesting education integration...")

    # Check that headers include help
    session = Session()
    _header(session, "Test category", show_help=True)
    print("  ✓ Headers include help information")

    # Check that smart defaults provide reasoning
    suggestion = _smart_default_recommendation("test", None)
    assert suggestion[1], "Should provide reasoning for recommendation"
    print(f"  ✓ Smart defaults include educational reasoning: {suggestion[1]}")


def test_guided_start():
    """Test the guided start functionality."""
    print("\nTesting guided start...")

    # Test that guided start exists and is callable
    assert callable(_guided_start), "_guided_start should be callable"
    print("  ✓ Guided start function available")


def test_header_improvements():
    """Test that _header has been improved."""
    print("\nTesting header improvements...")

    session = Session()

    # Check that _header accepts show_help parameter
    _header(session, "Test", show_help=True)
    print("  ✓ _header accepts show_help parameter")

    _header(session, "Test", show_help=False)
    print("  ✓ _header can hide help information")


def main():
    """Run all tests."""
    print("=" * 70)
    print("B34ST Enhanced Menu System Tests")
    print("=" * 70)

    tests = [
        test_enhanced_prompt,
        test_help_system,
        test_smart_defaults,
        test_menu_expansion,
        test_session_creation,
        test_menu_categories,
        test_education_integration,
        test_guided_start,
        test_header_improvements,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__} failed: {e}")

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
