from __future__ import annotations

import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from b34st.control_panel import (
    _explain_tethered_downgrade,
    _guided_tethered_downgrade,
)


class RecordingSession:
    def __init__(self, directory: pathlib.Path) -> None:
        self.directory = directory
        self.arguments: list[str] | None = None
        self.label: str | None = None
        self.interactive = False

    def run(
        self,
        arguments: list[str],
        *,
        label: str,
        interactive: bool = False,
    ) -> int:
        self.arguments = arguments
        self.label = label
        self.interactive = interactive
        return 0


class TetheredDowngradeControlPanelTests(unittest.TestCase):
    def test_explanation_defines_adapter_and_non_examples(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            _explain_tethered_downgrade()
        rendered = output.getvalue()
        self.assertIn("What the tether adapter is", rendered)
        self.assertIn("separately installed, target-specific executable", rendered)
        self.assertIn("It is not the IPSW", rendered)
        self.assertIn("idevicerestore", rendered)
        self.assertIn(
            "None is a verified drop-in adapter",
            rendered,
        )

    def test_device_context_is_forwarded_to_the_single_guide(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = RecordingSession(pathlib.Path(directory))
            result = _guided_tethered_downgrade(
                session,
                product="iPhone12,1",
                ecid="1234",
            )

            self.assertEqual(result, 0)
            self.assertEqual(session.label, "Guided tethered downgrade")
            self.assertTrue(session.interactive)
            self.assertEqual(
                session.arguments,
                [
                    "ipsw",
                    "tethered-downgrade-guide",
                    "--evidence",
                    str(pathlib.Path(directory) / "tethered-downgrade.json"),
                    "--product",
                    "iPhone12,1",
                    "--ecid",
                    "1234",
                ],
            )


if __name__ == "__main__":
    unittest.main()
