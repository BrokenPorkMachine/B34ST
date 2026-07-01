from __future__ import annotations

import unittest
from unittest import mock

ROOT = None

try:
    from host import device_jailbreak as dj
    from host.chipset_db import CHIPSET_DB
except ImportError:
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "host"))
    import device_jailbreak as dj
    from chipset_db import CHIPSET_DB


class LookupExploitForCpidTests(unittest.TestCase):
    def test_limera1n_a4(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8930), "limera1n")

    def test_limera1n_a5(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8940), "limera1n")

    def test_checkm8_a6(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8950), "checkm8")

    def test_checkm8_a7(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8960), "checkm8")

    def test_checkm8_a8(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x7000), "checkm8")

    def test_checkm8_a9(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8000), "checkm8")

    def test_checkm8_a10(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8010), "checkm8")

    def test_checkm8_a11(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8015), "checkm8")

    def test_checkm8_t2(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8012), "checkm8")

    def test_dwc3_a12(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8020), "dwc3")

    def test_dwc3_a13(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8030), "dwc3")

    def test_dwc3_a14(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8101), "dwc3")

    def test_dwc3_m1(self) -> None:
        self.assertEqual(dj._lookup_exploit_for_cpid(0x8103), "dwc3")

    def test_unknown_returns_none(self) -> None:
        self.assertIsNone(dj._lookup_exploit_for_cpid(0x9999))


class FindDeviceCpidTests(unittest.TestCase):
    @mock.patch.object(dj, "HAS_PYUSB", False)
    def test_returns_none_when_no_pyusb(self) -> None:
        result = dj.find_device_cpid(timeout=0.1)
        self.assertIsNone(result)

    @mock.patch("usb.core.find", return_value=[])
    def test_returns_none_when_no_devices(self, mock_find) -> None:
        result = dj.find_device_cpid(timeout=0.1)
        self.assertIsNone(result)


class JailbreakDeviceTests(unittest.TestCase):
    def test_returns_error_when_no_pyusb(self) -> None:
        with mock.patch.object(dj, "HAS_PYUSB", False):
            result = dj.jailbreak_device(timeout=0.1)
            self.assertFalse(result["success"])
            self.assertIn("pyusb", result["error"])

    def test_returns_error_when_device_not_found(self) -> None:
        with (
            mock.patch.object(dj, "HAS_PYUSB", True),
            mock.patch("usb.core.find", return_value=[]),
        ):
            result = dj.jailbreak_device(timeout=0.1)
            self.assertFalse(result["success"])
            self.assertIn("no apple device found in dfu mode", result["error"].lower())

    def test_returns_error_when_unknown_cpid_and_no_force(self) -> None:
        mock_device = mock.MagicMock()
        mock_device.idVendor = 0x05AC
        mock_device.idProduct = 0x1227
        mock_device.product = "Apple Mobile Device (DFU Mode)"
        mock_device.serial_number = None
        mock_device.bus = 1
        mock_device.address = 2

        with (
            mock.patch.object(dj, "HAS_PYUSB", True),
            mock.patch("usb.core.find", return_value=[mock_device]),
            mock.patch("subprocess.run", return_value=mock.MagicMock(
                stdout="CPID: 0x9999\n", returncode=0
            )),
        ):
            result = dj.jailbreak_device(timeout=0.5, force=False)
            self.assertFalse(result["success"])
            self.assertIn("not in the exploit database", result["error"])

    def test_proceeds_with_force_even_with_unknown_cpid(self) -> None:
        mock_device = mock.MagicMock()
        mock_device.idVendor = 0x05AC
        mock_device.idProduct = 0x1227
        mock_device.product = "Apple Mobile Device (DFU Mode)"
        mock_device.serial_number = None
        mock_device.bus = 1
        mock_device.address = 2

        with (
            mock.patch.object(dj, "HAS_PYUSB", True),
            mock.patch("usb.core.find", return_value=[mock_device]),
            mock.patch("subprocess.run", return_value=mock.MagicMock(
                stdout="CPID: 0x9999\n", returncode=0
            )),
        ):
            result = dj.jailbreak_device(timeout=0.5, force=True)
            self.assertFalse(result["success"])
            self.assertEqual(result["cpid"], 0x9999)
            self.assertEqual(result["exploit_type"], "dwc3")

    def test_exploit_override_uses_specified_type(self) -> None:
        mock_device = mock.MagicMock()
        mock_device.idVendor = 0x05AC
        mock_device.idProduct = 0x1227
        mock_device.product = "Apple Mobile Device (DFU Mode)"
        mock_device.serial_number = None
        mock_device.bus = 1
        mock_device.address = 2

        with (
            mock.patch.object(dj, "HAS_PYUSB", True),
            mock.patch("usb.core.find", return_value=[mock_device]),
            mock.patch("subprocess.run", return_value=mock.MagicMock(
                stdout="CPID: 0x8020\n", returncode=0
            )),
        ):
            result = dj.jailbreak_device(
                timeout=0.5, force=True, exploit_override="checkm8"
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["exploit_type"], "checkm8")


class RunCheckm8Tests(unittest.TestCase):
    def test_raises_on_unsupported_cpid(self) -> None:
        with mock.patch.object(dj, "HAS_CHECKM8", True):
            with self.assertRaises(RuntimeError):
                dj._run_checkm8(mock.MagicMock(), 0x8930)

    def test_raises_when_checkm8_module_missing(self) -> None:
        with mock.patch.object(dj, "HAS_CHECKM8", False):
            with self.assertRaises(RuntimeError):
                dj._run_checkm8(mock.MagicMock(), 0x8960)

    def test_sends_transfers_for_supported_cpid(self) -> None:
        mock_dev = mock.MagicMock()
        with (
            mock.patch.object(dj, "HAS_CHECKM8", True),
            mock.patch.object(
                dj.CHECKM8_MODULE, "get_exploit_transfers",
                return_value=[(0x21, 6, 0x0100, 0, b"payload")],
            ),
        ):
            result = dj._run_checkm8(mock_dev, 0x8960)
            self.assertTrue(result)
            mock_dev.ctrl_transfer.assert_called_once_with(
                0x21, 6, 0x0100, 0, b"payload", timeout=5000
            )


class RunLimera1nTests(unittest.TestCase):
    def test_raises_on_unsupported_cpid(self) -> None:
        with mock.patch.object(dj, "HAS_LIMERA1N", True):
            with self.assertRaises(RuntimeError):
                dj._run_limera1n(mock.MagicMock(), 0x8960)

    def test_raises_when_limera1n_module_missing(self) -> None:
        with mock.patch.object(dj, "HAS_LIMERA1N", False):
            with self.assertRaises(RuntimeError):
                dj._run_limera1n(mock.MagicMock(), 0x8930)

    def test_sends_transfers_for_supported_cpid(self) -> None:
        mock_dev = mock.MagicMock()
        with (
            mock.patch.object(dj, "HAS_LIMERA1N", True),
            mock.patch.object(
                dj.LIMERA1N_MODULE, "get_exploit_transfers",
                return_value=[(0x21, 0, 0, 0, b"\x00" * 0x8000)],
            ),
        ):
            result = dj._run_limera1n(mock_dev, 0x8930)
            self.assertTrue(result)
            mock_dev.ctrl_transfer.assert_called_once()
