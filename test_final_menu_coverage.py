#!/usr/bin/env python3
"""
Final integration test for B34ST menu system with all capabilities exposed.
This validates that the enhanced menu system provides comprehensive access
to all B34ST capabilities while maintaining good UX.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from b34st.control_panel import (
    _header,
    _help_for_category,
    _smart_default_recommendation,
    Session,
    _main_menu_options,
)


def test_comprehensive_menu_capabilities():
    """Test that all major B34ST capabilities are exposed in the menu system."""
    print("Comprehensive B34ST Menu Capabilities Test")
    print("=" * 70)

    # Get current menu options
    menu_options = _main_menu_options()
    categories = {label for _, label, _ in menu_options}

    print(f"\nCurrent Categories ({len(categories)}):")
    for category in sorted(categories):
        print(f"  ✓ {category}")

    print("\nExpected Categories (minimum):")

    # All the major categories that should be exposed
    essential_categories = {
        "External hardware / USBliter8 / first-stage execution",
        "Build, test, and QEMU simulation",
        "Runtime console / logger / shell",
        "Evidence, validation, and release",
        "Targeted IPSW downloads, upgrades, and tethered downgrades",
        "Forensics and data acquisition",
        "CVE database & exploit chain planner",
        "Fuzzer orchestration",
        "Ramdisk maker and loader",
        "Load images, next stages, modules, or deployment",
        "Authorized runtime modifications and evidence",
        "Create a bounded environment plan",
        "Open the FBR34KER maintenance menu",
        "View this B34ST session log",
        "Exit",
    }

    # Check for essential coverage
    covered_categories = categories.intersection(essential_categories)
    missing_categories = essential_categories - categories

    print(
        f"  Categories Covered: {len(covered_categories)}/{len(essential_categories)}"
    )
    for cat in sorted(covered_categories):
        print(f"    ✓ {cat}")

    if missing_categories:
        print(f"\n  Categories Missing ({len(missing_categories)}):")
        for cat in sorted(missing_categories):
            print(f"    ✗ {cat}")

    return len(missing_categories) == 0


def test_help_system_coverage():
    """Test that the help system covers all categories."""
    print("\n" + "=" * 70)
    print("Help System Coverage Test")
    print("=" * 70)

    menu_options = _main_menu_options()
    categories = {label for _, label, _ in menu_options}

    tested_categories = 0
    passed_categories = 0

    for category in sorted(categories):
        print(f"\nTesting help for: {category}")
        try:
            _help_for_category(category)
            passed_categories += 1
            print(f"  ✓ Help system provides guidance for {category}")
        except Exception as e:
            print(f"  ✗ Help test failed for {category}: {e}")

        tested_categories += 1

    print("\nHelp System Results:")
    print(f"  Tested Categories: {tested_categories}")
    print(f"  Successfully Provided Help: {passed_categories}")
    print(f"  Success Rate: {passed_categories / tested_categories * 100:.1f}%")

    return passed_categories == tested_categories


def test_smart_defaults_coverage():
    """Test smart defaults for all categories."""
    print("\n" + "=" * 70)
    print("Smart Defaults Coverage Test")
    print("=" * 70)

    menu_options = _main_menu_options()
    categories = {label for _, label, _ in menu_options}

    tested_categories = 0
    passed_categories = 0

    for category in sorted(categories):
        print(f"\nTesting smart defaults for: {category}")
        try:
            # Extract category name from "Category (more text)"
            clean_category = category.split(" (")[0]

            recommendation = _smart_default_recommendation(clean_category, None)

            if recommendation[0]:
                passed_categories += 1
                print(f"  ✓ Smart defaults: {recommendation[0]} - {recommendation[1]}")
            else:
                print(f"  ✗ No recommendation for {category}")

            tested_categories += 1
        except Exception as e:
            print(f"  ✗ Smart defaults test failed for {category}: {e}")
            tested_categories += 1

    print("\nSmart Defaults Results:")
    print(f"  Tested Categories: {tested_categories}")
    print(f"  Successfully Generated: {passed_categories}")
    print(f"  Success Rate: {passed_categories / tested_categories * 100:.1f}%")

    return (
        passed_categories >= tested_categories * 0.8
    )  # Allow some categories to have no defaults


def test_automation_exposure():
    """Test that automation features are properly exposed."""
    print("\n" + "=" * 70)
    print("Automation Exposure Test")
    print("=" * 70)

    menu_options = _main_menu_options()

    automation_keywords = [
        "automation",
        "scriptable",
        "guided",
        "planner",
        "orchestration",
        "suggest",
        "assist",
        "default",
        "recommended",
        "quick",
    ]

    categories_with_automation = 0
    total_categories = len(menu_options)

    for key, label, desc in menu_options:
        desc_lower = desc.lower()
        has_automation = any(keyword in desc_lower for keyword in automation_keywords)

        if has_automation:
            categories_with_automation += 1
            status = "✓"
        else:
            status = "  "

        print(f"{status} {key}. {label}")
        print(f"   {desc}")

    automation_coverage = categories_with_automation / total_categories * 100

    print("\nAutomation Coverage:")
    print(
        f"  Categories with Automation: {categories_with_automation}/{total_categories}"
    )
    print(f"  Automation Coverage: {automation_coverage:.1f}%")

    if automation_coverage >= 60:
        print(f"  ✓ Good automation exposure ({automation_coverage:.1f}%)")
        return True
    else:
        print(f"  ⚠ Low automation exposure ({automation_coverage:.1f}%)")
        return False


def test_education_features():
    """Test educational components of the menu system."""
    print("\n" + "=" * 70)
    print("Education Features Test")
    print("=" * 70)

    menu_options = _main_menu_options()

    education_keywords = [
        "guide",
        "plan",
        "validate",
        "explain",
        "illustrate",
        "demonstrate",
        "step-by-step",
        "tutorial",
        "walkthrough",
        "how to",
        "what is",
    ]

    educational_categories = 0
    tested_headers = 0
    successful_headers = 0

    for key, label, desc in menu_options:
        desc_lower = desc.lower()
        has_education = any(keyword in desc_lower for keyword in education_keywords)

        if has_education:
            educational_categories += 1

        print(f"Testing header for category {key}: {label}")
        try:
            session = Session()

            # Test with help enabled
            _header(session, label, show_help=True)
            successful_headers += 1
            print("  ✓ Help header provides education")

            # Test without help
            _header(session, label, show_help=False)
            print("  ✓ Clean header also available")

            tested_headers += 1
        except Exception as e:
            print(f"  ✗ Header test failed: {e}")
            tested_headers += 1

    education_coverage = educational_categories / len(menu_options) * 100
    header_success_rate = (
        successful_headers / tested_headers * 100 if tested_headers > 0 else 0
    )

    print("\nEducation Features Coverage:")
    print(
        f"  Categories with Educational Content: {educational_categories}/{len(menu_options)}"
    )
    print(f"  Education Coverage: {education_coverage:.1f}%")

    print("\nHeader System Success Rate:")
    print(f"  Headers Tested: {tested_headers}")
    print(f"  Successful Headers: {successful_headers}")
    print(f"  Success Rate: {header_success_rate:.1f}%")

    return education_coverage >= 70 and header_success_rate >= 90


def main():
    """Run all comprehensive tests."""
    print("B34ST Enhanced Menu System - Comprehensive Coverage Test")
    print("=" * 70)
    print("This test validates that ALL B34ST capabilities are properly")
    print("exposed in the enhanced menu system with good UX features.")
    print("=" * 70)

    tests = [
        ("Menu Capabilities Coverage", test_comprehensive_menu_capabilities),
        ("Help System Coverage", test_help_system_coverage),
        ("Smart Defaults Coverage", test_smart_defaults_coverage),
        ("Automation Exposure", test_automation_exposure),
        ("Education Features", test_education_features),
    ]

    passed_tests = 0
    failed_tests = 0

    for test_name, test_func in tests:
        print(f"\n{'=' * 70}")
        print(f"Running: {test_name}")
        print(f"{'=' * 70}")

        try:
            if test_func():
                print(f"\n✓ {test_name}: PASSED")
                passed_tests += 1
            else:
                print(f"\n✗ {test_name}: FAILED")
                failed_tests += 1
        except Exception as e:
            print(f"\n⚠ {test_name}: ERROR - {e}")
            failed_tests += 1

    print(f"\n{'=' * 70}")
    print("FINAL RESULTS")
    print(f"{'=' * 70}")
    print(f"Tests Passed: {passed_tests}")
    print(f"Tests Failed: {failed_tests}")
    print(f"Total Tests: {len(tests)}")

    if failed_tests == 0:
        print("\n✓ SUCCESS: All B34ST menu capabilities are properly exposed!")
        print("  The enhanced menu system provides comprehensive coverage")
        print("  of all available features with excellent UX support.")
    else:
        print(f"\n⚠ WARNING: {failed_tests} test(s) failed.")
        print("  Some B34ST capabilities may not be fully exposed.")

    return 1 if failed_tests > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
