#!/usr/bin/env python3
"""Verify that active FBR34KER release surfaces use one version."""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def require_pattern(path: str, pattern: str, description: str) -> str | None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if re.search(pattern, text, flags=re.MULTILINE) is None:
        return f"{path}: {description}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True)
    args = parser.parse_args(argv)
    version = args.expected
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        parser.error("--expected must be a semantic version such as 0.4.2b")

    escaped = re.escape(version)
    release_name = re.escape(f"FBR34KER_{version}_Beta")
    b34st_release_name = re.escape(f"B34ST_{version}_Beta")
    checks = (
        ("Makefile", rf"^VERSION := {escaped}$", "VERSION does not match"),
        ("Makefile", r"^RELEASE_CHANNEL := beta$", "release channel is not beta"),
        (
            "Makefile",
            r"^RELEASE_NAME := FBR34KER_\$\(VERSION\)_Beta$",
            "release-name template is inconsistent",
        ),
        (
            "Makefile",
            r"^SOURCE_ID := \$\(VERSION\)-beta$",
            "source-id template is inconsistent",
        ),
        (
            "include/fbr34ker/version.h",
            rf'^#define FBR34KER_MONITOR_VERSION "{escaped}"$',
            "monitor version does not match",
        ),
        (
            "include/fbr34ker/version.h",
            r'^#define FBR34KER_MONITOR_BUILD "beta"$',
            "monitor build channel is not beta",
        ),
        ("b34st/version.py", rf'^__version__ = "{escaped}"$', "B34ST version does not match"),
        (
            "b34st/version.py",
            rf'^__release_name__ = "{b34st_release_name}"$',
            "B34ST release name does not match",
        ),
        ("b34st/build.py", rf'^__version__ = "{escaped}"$', "B34ST build version does not match"),
        (
            "b34st/build.py",
            rf'^__release_name__ = "{b34st_release_name}"$',
            "B34ST build release name does not match",
        ),
        (
            "host/fbr34kctl.py",
            rf'^FBR34KCTL_VERSION = "{escaped}"$',
            "fbr34kctl version does not match",
        ),
        ("host/fbr34kdeploy.py", rf'^VERSION = "{escaped}"$', "deployment version does not match"),
        (
            "host/hardware_bringup.py",
            rf'^RELEASE_VERSION = "{escaped}"$',
            "bring-up release version does not match",
        ),
        (
            "host/physical_validation.py",
            rf'^RELEASE_VERSION = "{escaped}"$',
            "physical-validation release version does not match",
        ),
        (
            "modules/dynamic_hello/module.json",
            rf'"version": "{escaped}"',
            "dynamic module version does not match",
        ),
        (
            "modules/hello/hello.c",
            rf'\.version = "{escaped}"',
            "built-in module version does not match",
        ),
        (
            ".github/workflows/ci.yml",
            rf"^name: FBR34KER {escaped} Beta$",
            "CI release title does not match",
        ),
        (
            ".github/workflows/ci.yml",
            rf"dist/{release_name}_\*\.zip",
            "CI artifact pattern does not match",
        ),
        ("BRANDING.md", rf"Release: \*\*{escaped} Beta\*\*", "branding version does not match"),
        (
            "BRANDING.md",
            rf"Release root: `{release_name}`",
            "branding release root does not match",
        ),
    )

    failures = [
        failure
        for path, pattern, description in checks
        if (failure := require_pattern(path, pattern, description)) is not None
    ]
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print(f"version consistency passed ({version}-beta, {len(checks)} release surfaces)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
