from __future__ import annotations

import copy
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from handoff_schema import (  # noqa: E402
    HandoffSchemaError,
    load_and_validate,
    template,
    validate_document,
    write_template,
)


class HandoffSchemaTests(unittest.TestCase):
    def test_template_validates(self) -> None:
        normalized = validate_document(template())
        self.assertEqual(normalized["version"], 4)
        self.assertEqual(normalized["page_granule"], 16384)
        self.assertEqual(normalized["module_policy"]["dynamic_slots"], 2)

    def test_round_trip_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "handoff.json"
            write_template(path)
            normalized = load_and_validate(path)
            self.assertEqual(normalized["monitor"]["base"], "0x80000000")

    def test_rejects_overlapping_regions(self) -> None:
        document = template()
        document["regions"][1]["base"] = "0x80001000"
        with self.assertRaises(HandoffSchemaError):
            validate_document(document)

    def test_rejects_uncovered_framebuffer(self) -> None:
        document = template()
        document["framebuffer"] = {
            "base": "0x90000000",
            "size": "0x400000",
            "width": 640,
            "height": 480,
            "pixels_per_row": 640,
            "pixel_format": "xrgb8888",
        }
        with self.assertRaises(HandoffSchemaError):
            validate_document(document)

    def test_rejects_flush_without_framebuffer(self) -> None:
        document = copy.deepcopy(template())
        document["services"].append("framebuffer-flush")
        with self.assertRaises(HandoffSchemaError):
            validate_document(document)

    def test_rejects_policy_over_budget(self) -> None:
        document = template()
        document["module_policy"]["instruction_budget"] = 4097
        with self.assertRaises(HandoffSchemaError):
            validate_document(document)

    def test_rejects_duplicate_runtime_callbacks(self) -> None:
        document = template()
        document["runtime_callbacks"].append("timer")
        with self.assertRaises(HandoffSchemaError):
            validate_document(document)


if __name__ == "__main__":
    unittest.main()
