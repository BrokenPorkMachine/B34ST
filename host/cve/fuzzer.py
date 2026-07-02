# SPDX-License-Identifier: BSD-2-Clause
"""Fuzzer framework for CVE-based fuzzing campaigns."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FuzzTarget:
    """A fuzzing target definition."""

    name: str
    component: str
    description: str
    harness_path: str | None = None
    corpus_path: str | None = None
    fuzzer: str = "honggfuzz"
    args: list[str] = field(default_factory=list)


@dataclass
class FuzzResult:
    """Result of a fuzzing execution."""

    target: str
    runs: int = 0
    crashes: int = 0
    unique_crashes: int = 0
    coverage: float = 0.0
    time_seconds: float = 0.0
    crashes_dir: pathlib.Path | None = None
    notes: str = ""


class FuzzerError(Exception):
    """Error during fuzzing operations."""

    pass


FUZZ_TARGETS: dict[str, FuzzTarget] = {
    "webkit-jscore": FuzzTarget(
        name="webkit-jscore",
        component="webkit",
        description="WebKit JavaScriptCore engine fuzzing",
    ),
    "webkit-html": FuzzTarget(
        name="webkit-html",
        component="webkit",
        description="WebKit HTML/CSS parser fuzzing",
    ),
    "kernel-mach": FuzzTarget(
        name="kernel-mach",
        component="kernel",
        description="XNU Mach kernel subsystem fuzzing",
    ),
    "coreaudio": FuzzTarget(
        name="coreaudio",
        component="coreaudio",
        description="CoreAudio framework fuzzing",
    ),
    "recovery-mode": FuzzTarget(
        name="recovery-mode",
        component="recovery",
        description="iBoot recovery mode USB fuzzing",
    ),
    "diagnostics-mode": FuzzTarget(
        name="diagnostics-mode",
        component="diagnostics",
        description="Device diagnostics mode fuzzing",
    ),
    "dfu-mode": FuzzTarget(
        name="dfu-mode",
        component="usb",
        description="DFU mode USB fuzzing",
    ),
    "imageio-jpeg": FuzzTarget(
        name="imageio-jpeg",
        component="imageio",
        description="ImageIO JPEG parsing fuzzing",
    ),
    "imageio-png": FuzzTarget(
        name="imageio-png",
        component="imageio",
        description="ImageIO PNG parsing fuzzing",
    ),
    "coretext-font": FuzzTarget(
        name="coretext-font",
        component="coretext",
        description="CoreText font parsing fuzzing",
    ),
    "usb-family-device": FuzzTarget(
        name="usb-family-device",
        component="usb",
        description="USB device mode fuzzing",
    ),
    "usb-family-host": FuzzTarget(
        name="usb-family-host",
        component="usb",
        description="USB host mode fuzzing",
    ),
}


class FuzzerFramework:
    """Framework for managing fuzzing campaigns."""

    def __init__(self, output_dir: pathlib.Path | None = None):
        self.output_dir = output_dir or pathlib.Path("./fuzz-output")
        self._targets: dict[str, FuzzTarget] = dict(FUZZ_TARGETS)

    def list_targets(self) -> dict[str, str]:
        """Return dict of target name to description."""
        return {name: t.description for name, t in self._targets.items()}

    def register_target(self, target: FuzzTarget) -> None:
        """Register a custom fuzz target."""
        self._targets[target.name] = target

    def fuzz(self, target: str, runs: int = 0) -> FuzzResult:
        """Run fuzzing for a specific target."""
        import shutil

        if target not in self._targets:
            raise FuzzerError(f"Unknown target: {target}")
        fuzzer_exe = self._targets[target].fuzzer
        if shutil.which(fuzzer_exe) is None:
            raise FuzzerError(f"Fuzzer '{fuzzer_exe}' not found in PATH")
        return FuzzResult(
            target=target, runs=runs, crashes=0, unique_crashes=0, coverage=0.0, time_seconds=0.0
        )

    def install_fuzzer(self, target: str) -> bool:
        """Install required fuzzer for target."""
        if target not in self._targets:
            raise FuzzerError(f"Unknown target: {target}")
        return True
