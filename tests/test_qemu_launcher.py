from __future__ import annotations

import runpy
import types
import unittest
from unittest import mock

from host import fbr34ker_cli


class QEMULauncherTests(unittest.TestCase):
    def test_root_launcher_disables_timeout_and_preserves_stdio(self) -> None:
        namespace = runpy.run_path("fbr34ker")
        make_mock = mock.Mock(
            return_value=types.SimpleNamespace(returncode=0)
        )
        namespace["cmd_run"].__globals__["make"] = make_mock
        namespace["cmd_run"].__globals__["require_qemu"] = mock.Mock()

        result = namespace["cmd_run"](
            types.SimpleNamespace(profile="direct")
        )

        self.assertEqual(result, 0)
        make_mock.assert_called_once_with(
            ["run"],
            timeout=None,
            preserve_stdio=True,
        )

    def test_installed_launcher_preserves_stdio_for_qemu(self) -> None:
        with (
            mock.patch.object(fbr34ker_cli, "require_qemu"),
            mock.patch.object(
                fbr34ker_cli, "execute", return_value=0
            ) as execute_mock,
        ):
            result = fbr34ker_cli.main(["run", "direct"])

        self.assertEqual(result, 0)
        execute_mock.assert_called_once_with(
            ["make", "--no-print-directory", "run"],
            json_mode=False,
            preserve_stdio=True,
        )


if __name__ == "__main__":
    unittest.main()
