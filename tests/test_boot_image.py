# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from host.boot_image import BootImageError, Component, build_image, inspect_image

ROOT = pathlib.Path(__file__).resolve().parents[1]


class BootImageTests(unittest.TestCase):
    def test_build_is_deterministic_and_inspectable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            monitor = root / "monitor.bin"
            handoff = root / "handoff.bin"
            module = root / "hello.fmod"
            monitor.write_bytes(b"MONITOR" * 257)
            handoff.write_bytes(b"HANDOFF" * 31)
            module.write_bytes(b"MODULE" * 17)
            first = root / "first.img"
            second = root / "second.img"
            profile = ROOT / "profiles/apple-a12-recovery.json"
            components = [
                Component("monitor", monitor),
                Component("handoff", handoff),
                Component("module", module),
            ]
            first_info = build_image(first, profile, components, raw_output=root / "boot.raw")
            second_info = build_image(second, profile, components)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first_info["family"], "a12")
            self.assertEqual(first_info["component_count"], 3)
            self.assertTrue((root / "boot.raw.json").is_file())
            self.assertEqual(inspect_image(first)["sha256"], second_info["sha256"])

    def test_corruption_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            monitor = root / "monitor.bin"
            monitor.write_bytes(b"A" * 8192)
            image = root / "boot.img"
            build_image(image, ROOT / "profiles/apple-a13-recovery.json",
                        [Component("monitor", monitor)])
            value = bytearray(image.read_bytes())
            value[-1] ^= 0x80
            image.write_bytes(value)
            with self.assertRaises(BootImageError):
                inspect_image(image)

    def test_profile_and_sidecar_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            monitor = root / "monitor.bin"
            monitor.write_bytes(b"B" * 1024)
            image = root / "boot.img"
            build_image(image, ROOT / "profiles/apple-a12x-recovery.json",
                        [Component("monitor", monitor)])
            sidecar = json.loads((root / "boot.img.json").read_text())
            self.assertEqual(sidecar["family"], "a12x")
            self.assertFalse(sidecar["direct_stock_iboot_compatible"])


if __name__ == "__main__":
    unittest.main()
