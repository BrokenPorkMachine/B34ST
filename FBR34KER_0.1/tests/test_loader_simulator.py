from __future__ import annotations

import json
import pathlib
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from handoff_schema import template  # noqa: E402
from loader_simulator import (  # noqa: E402
    HANDOFF_SIZE,
    LoaderSimulationError,
    format_report,
    load_report,
    simulate_loader,
)


def write_minimal_elf(path: pathlib.Path, *, machine: int = 183) -> None:
    ident = bytearray(16)
    ident[:4] = b"\x7fELF"
    ident[4] = 2
    ident[5] = 1
    ident[6] = 1
    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        bytes(ident), 2, machine, 1, 0x80000000, 64, 0, 0,
        64, 56, 1, 0, 0, 0,
    )
    payload = b"\x00\x00\x80\xd2\xc0\x03\x5f\xd6"
    program = struct.pack(
        "<IIQQQQQQ",
        1, 7, 0x1000, 0x80000000, 0x80000000,
        len(payload), 0x1000, 0x1000,
    )
    image = bytearray(0x1000 + len(payload))
    image[:64] = header
    image[64:120] = program
    image[0x1000:] = payload
    path.write_bytes(image)


class LoaderSimulatorTests(unittest.TestCase):
    def test_constructs_packed_handoff_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            handoff = root / "handoff.json"
            image = root / "monitor.elf"
            module = root / "hello.fmod"
            output = root / "simulation"
            handoff.write_text(json.dumps(template()), encoding="utf-8")
            write_minimal_elf(image)
            module.write_bytes(b"FMOD-test")
            report = simulate_loader(handoff, image, output,
                                     module_paths=[module])
            self.assertEqual(report["result"], "pass")
            self.assertEqual((output / "handoff-v4.bin").stat().st_size,
                             HANDOFF_SIZE)
            loaded = load_report(output / "loader-conformance.json")
            self.assertIn("PASS", format_report(loaded))
            names = {item["name"] for item in report["placements"]}
            self.assertIn("handoff-v4", names)
            self.assertIn("callback-stubs", names)

    def test_rejects_non_aarch64_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            handoff = root / "handoff.json"
            image = root / "monitor.elf"
            handoff.write_text(json.dumps(template()), encoding="utf-8")
            write_minimal_elf(image, machine=62)
            with self.assertRaises(LoaderSimulationError):
                simulate_loader(handoff, image, root / "out")

    def test_executable_usable_region_is_classified_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            document = template()
            document["regions"][1]["attributes"].append("execute")
            handoff = root / "handoff.json"
            image = root / "monitor.elf"
            handoff.write_text(json.dumps(document), encoding="utf-8")
            write_minimal_elf(image)
            report = simulate_loader(handoff, image, root / "out")
            self.assertEqual(report["result"], "fail")
            self.assertTrue(any(item["status"] == "unsafe"
                                for item in report["checks"]))


if __name__ == "__main__":
    unittest.main()
