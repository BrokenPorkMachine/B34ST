# SPDX-License-Identifier: BSD-2-Clause
"""Canonical FBR34KER release version for host-side tooling."""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(
    r'^#define FBR34KER_MONITOR_VERSION "([^"]+)"$',
    re.MULTILINE,
)


def _read_release_version() -> str:
    match = VERSION_RE.search(
        (ROOT / "include" / "fbr34ker" / "version.h").read_text(encoding="utf-8")
    )
    if match is None:
        raise RuntimeError("FBR34KER_MONITOR_VERSION is missing from version.h")
    return match.group(1)


RELEASE_VERSION = _read_release_version()
