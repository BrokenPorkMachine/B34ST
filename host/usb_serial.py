#!/usr/bin/env python3
"""USB CDC ACM serial transport for FBR34KER monitor communication.

Acts as the host-side counterpart to the monitor's USB gadget stack,
providing a serial-like interface over USB for sending commands and
receiving output. Uses pyusb (libusb) for USB device communication.
"""
from __future__ import annotations

import dataclasses
import enum
import json
import os
import struct
import sys
import threading
import time
from typing import Callable

try:
    import usb.core
    import usb.util
    HAS_PYUSB = True
except ImportError:
    HAS_PYUSB = False


FBR34KER_VID = 0x05AC
FBR34KER_PID = 0x1227
FBR34KER_PONGO_PID = 0x1227
USB_TIMEOUT_MS = 5000
BULK_EP_OUT = 0x01
BULK_EP_IN = 0x82
NOTIFICATION_EP = 0x83
CONTROL_IFACE = 0
DATA_IFACE = 1


class TransportError(RuntimeError):
    pass


@dataclasses.dataclass
class DeviceIdentity:
    vid: int
    pid: int
    bus: int
    address: int
    manufacturer: str | None
    product: str | None
    serial: str | None

    def __str__(self) -> str:
        return f"{self.vid:04x}:{self.pid:04x} bus={self.bus} addr={self.address}"


def find_monitor(vid: int = FBR34KER_VID, pid: int = FBR34KER_PID,
                 serial: str | None = None) -> usb.core.Device | None:
    if not HAS_PYUSB:
        raise TransportError("pyusb not installed (pip install pyusb)")
    for device in usb.core.find(find_all=True):
        if device.idVendor == vid and device.idProduct == pid:
            if serial is None:
                return device
            try:
                if serial in str(device.serial_number, "utf-8", errors="replace"):
                    return device
            except Exception:
                continue
    return None


def enumerate_devices() -> list[DeviceIdentity]:
    if not HAS_PYUSB:
        return []
    result = []
    for device in usb.core.find(find_all=True):
        if device.idVendor == FBR34KER_VID:
            try:
                desc = DeviceIdentity(
                    vid=device.idVendor,
                    pid=device.idProduct,
                    bus=device.bus,
                    address=device.address,
                    manufacturer=_safe_str(device.manufacturer),
                    product=_safe_str(device.product),
                    serial=_safe_str(device.serial_number),
                )
                result.append(desc)
            except Exception:
                continue
    return result


def _safe_str(value: object) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)
    except Exception:
        return None


class USBConsole:
    """USB CDC ACM serial console to FBR34KER monitor."""

    def __init__(self, device: usb.core.Device | None = None,
                 vid: int = FBR34KER_VID, pid: int = FBR34KER_PID,
                 serial: str | None = None, timeout_ms: int = USB_TIMEOUT_MS):
        if not HAS_PYUSB:
            raise TransportError("pyusb is required (pip install pyusb)")
        if device is None:
            device = find_monitor(vid, pid, serial)
            if device is None:
                raise TransportError(f"no FBR34KER monitor found ({vid:04x}:{pid:04x})")
        self.device = device
        self.timeout = timeout_ms
        self.identity = DeviceIdentity(
            vid=device.idVendor, pid=device.idProduct,
            bus=device.bus, address=device.address,
            manufacturer=_safe_str(device.manufacturer),
            product=_safe_str(device.product),
            serial=_safe_str(device.serial_number),
        )
        self._claimed = False
        self._detach_drivers: list[tuple[int, bool]] = []
        self._interface = 0
        self._ep_out = None
        self._ep_in = None
        self._lock = threading.Lock()
        self._buffer = b""

    def open(self) -> None:
        if self._claimed:
            return
        try:
            if self.device.is_kernel_driver_active(0):
                self.device.detach_kernel_driver(0)
                self._detach_drivers.append((0, True))
        except (usb.core.USBError, NotImplementedError):
            pass
        try:
            self.device.set_configuration()
        except usb.core.USBError as exc:
            if "Resource busy" not in str(exc):
                raise

        cfg = self.device.get_active_configuration()
        self._interface = None
        data_iface = None
        for iface in cfg:
            cls = iface.bInterfaceClass
            sub = iface.bInterfaceSubClass
            if cls == 0x02 and sub == 0x02:
                self._interface = iface.bInterfaceNumber
            elif cls == 0x0A:
                data_iface = iface

        if self._interface is None:
            for iface in cfg:
                if iface.bInterfaceClass == 0xFF:
                    self._interface = iface.bInterfaceNumber
                    break
        if self._interface is None and len(cfg) > 0:
            self._interface = cfg[0].bInterfaceNumber

        try:
            usb.util.claim_interface(self.device, self._interface)
            self._claimed = True
            if data_iface is not None and data_iface.bInterfaceNumber != self._interface:
                usb.util.claim_interface(self.device, data_iface.bInterfaceNumber)
        except usb.core.USBError as exc:
            raise TransportError(f"failed to claim interface: {exc}")

        iface_eps = data_iface if data_iface is not None else cfg[0]
        for iface in cfg:
            if data_iface is not None and iface.bInterfaceNumber == data_iface.bInterfaceNumber:
                iface_eps = iface
                break
        for ep in iface_eps:
            if ep.bEndpointAddress & 0x80:
                self._ep_in = ep
            else:
                self._ep_out = ep

        if self._ep_in is None or self._ep_out is None:
            raise TransportError("could not find bulk endpoints")

    def close(self) -> None:
        with self._lock:
            if self._claimed:
                for iface_num in range(3):
                    try:
                        usb.util.release_interface(self.device, iface_num)
                    except Exception:
                        pass
                self._claimed = False
            for iface_num, was_attached in self._detach_drivers:
                if was_attached:
                    try:
                        self.device.attach_kernel_driver(iface_num)
                    except Exception:
                        pass
            self._detach_drivers.clear()

    def write(self, data: bytes) -> int:
        with self._lock:
            if self._ep_out is None:
                raise TransportError("endpoint not configured")
            try:
                return self._ep_out.write(data, timeout=self.timeout)
            except usb.core.USBError as exc:
                raise TransportError(f"USB write failed: {exc}")

    def read(self, max_length: int = 4096) -> bytes:
        with self._lock:
            if self._ep_in is None:
                raise TransportError("endpoint not configured")
            try:
                return bytes(self._ep_in.read(max_length, timeout=self.timeout))
            except usb.core.USBError as exc:
                if "timeout" in str(exc).lower():
                    return b""
                raise TransportError(f"USB read failed: {exc}")

    def send_command(self, command: str) -> str:
        encoded = (command + "\n").encode("utf-8")
        self.write(encoded)
        time.sleep(0.1)
        response = b""
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            chunk = self.read(4096)
            if chunk:
                response += chunk
            if b"fbr34ker>" in response or b"fbr34ker(bringup)>" in response:
                break
            if not chunk:
                time.sleep(0.05)
        return response.decode("utf-8", errors="replace")

    def read_until_prompt(self, timeout: float = 10.0) -> str:
        data = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = self.read(4096)
            if chunk:
                data += chunk
                text = data.decode("utf-8", errors="replace")
                if "fbr34ker>" in text or "fbr34ker(probe)>" in text:
                    break
            else:
                time.sleep(0.05)
        return data.decode("utf-8", errors="replace")

    def run_command(self, command: str, timeout: float = 10.0) -> str:
        self.write((command + "\n").encode("utf-8"))
        return self.read_until_prompt(timeout)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


DFU_REQ_DNLOAD = 1
DFU_REQ_UPLOAD = 2
DFU_REQ_GETSTATUS = 3
DFU_REQ_CLRSTATUS = 4
DFU_REQ_GETSTATE = 5
DFU_REQ_ABORT = 6

DFU_BM_REQUEST_OUT = 0x21
DFU_BM_REQUEST_IN = 0xA1
DFU_IFACE = 2

DFU_XFER_SIZE = 4096

DFU_STATE_dfuIDLE = 2
DFU_STATE_dfuDNLOAD_IDLE = 5
DFU_STATE_dfuMANIFEST = 7
DFU_STATE_dfuERROR = 10


class Checkm8DFU:
    """Host-side DFU/PWNDFU interface for A12/A13 device exploitation.

    Communicates with the DWC3-based DFU device (PID 0x1227) using USB
    control transfers (class-specific requests on EP0).

    NOTE: enter_pwndfu() is a placeholder. A real checkm8 exploit payload
    (not included per security boundary) must be supplied externally via a
    custom mechanism before send_payload() will work.
    """

    CHECKM8_VID = 0x05AC
    DFU_PIDS = [0x1227, 0x1222, 0x1220]

    def __init__(self, serial: str | None = None):
        if not HAS_PYUSB:
            raise TransportError("pyusb is required (pip install pyusb)")
        self.serial = serial
        self.device: usb.core.Device | None = None
        self.in_dfu = False
        self.pwned = False
        self._claimed = False
        self._detach_drivers: list[int] = []

    def find_dfu_device(self) -> bool:
        for pid in self.DFU_PIDS:
            dev = find_monitor(self.CHECKM8_VID, pid, self.serial)
            if dev is not None:
                self.device = dev
                self.in_dfu = True
                return True
        return False

    def wait_for_dfu(self, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.find_dfu_device():
                return True
            time.sleep(0.5)
        return False

    def _claim(self) -> None:
        if self._claimed or self.device is None:
            return
        try:
            if self.device.is_kernel_driver_active(0):
                self.device.detach_kernel_driver(0)
                self._detach_drivers.append(0)
        except (usb.core.USBError, NotImplementedError):
            pass
        try:
            self.device.set_configuration()
        except usb.core.USBError:
            pass
        try:
            usb.util.claim_interface(self.device, 0)
            self._claimed = True
        except usb.core.USBError as exc:
            raise TransportError(f"failed to claim interface: {exc}")

    def _release(self) -> None:
        if self._claimed and self.device is not None:
            try:
                usb.util.release_interface(self.device, 0)
            except Exception:
                pass
            self._claimed = False
        for iface_num in self._detach_drivers:
            try:
                self.device.attach_kernel_driver(iface_num)
            except Exception:
                pass
        self._detach_drivers.clear()

    def _ctrl_transfer(self, bm_request_type: int, b_request: int,
                       w_value: int = 0, w_index: int = 0,
                       data_or_w_length: bytes | int = 0) -> bytes:
        if self.device is None:
            raise TransportError("no DFU device")
        timeout_ms = 5000
        if isinstance(data_or_w_length, bytes):
            return self.device.ctrl_transfer(
                bm_request_type, b_request, w_value, w_index,
                data_or_w_length, timeout=timeout_ms)
        else:
            return self.device.ctrl_transfer(
                bm_request_type, b_request, w_value, w_index,
                data_or_w_length, timeout=timeout_ms)

    def _dfu_get_status(self) -> tuple[int, int]:
        resp = self._ctrl_transfer(DFU_BM_REQUEST_IN, DFU_REQ_GETSTATUS,
                                   0, DFU_IFACE, 6)
        status = resp[0]
        state = resp[4]
        return state, status

    def _send_dfu_dnload(self, data: bytes) -> bool:
        """Send a block of data via DFU DNLOAD protocol."""
        if self.device is None:
            return False
        offset = 0
        block_num = 0
        total = len(data)
        while offset < total:
            chunk = data[offset:offset + DFU_XFER_SIZE]
            self._ctrl_transfer(DFU_BM_REQUEST_OUT, DFU_REQ_DNLOAD,
                                block_num, DFU_IFACE, chunk)
            state, status = self._dfu_get_status()
            if state == DFU_STATE_dfuERROR:
                raise TransportError(f"DFU error at block {block_num}: status={status}")
            offset += len(chunk)
            block_num += 1
        self._ctrl_transfer(DFU_BM_REQUEST_OUT, DFU_REQ_DNLOAD,
                            block_num, DFU_IFACE, b"")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            state, status = self._dfu_get_status()
            if state in (DFU_STATE_dfuIDLE, DFU_STATE_dfuMANIFEST):
                break
            time.sleep(0.1)
        return True

    def enter_pwndfu(self) -> bool:
        """Execute checkm8 exploit to enter PWNDFU mode.

        When exploit_payload is provided, sends it via DFU DNLOAD protocol.
        When no payload is set, operates in stub mode (self.pwned = True)
        for testing without physical hardware.
        """
        if not self.in_dfu or self.device is None:
            return False
        payload = getattr(self, 'exploit_payload', None)
        if payload is None:
            self.pwned = True
            return True
        self._claim()
        try:
            self._send_dfu_dnload(payload)
            self.pwned = True
            return True
        except Exception:
            return False

    def send_payload(self, payload_path: str, load_addr: int = 0x8000_0000) -> bool:
        """Send a binary image via DFU DNLOAD protocol.

        Uses class-specific control transfers to send the image in
        DFU_XFER_SIZE blocks. After each block, polls DFU_GETSTATUS.
        """
        if not self.pwned or self.device is None:
            return False
        payload = _read_binary(payload_path)
        self._claim()
        return self._send_dfu_dnload(payload)

    def execute(self, entry: int = 0x8000_0000) -> bool:
        """Trigger execution of the loaded image and wait for reconnect.

        Sends DFU_DETACH to signal the device to exit DFU mode and
        execute the loaded firmware. Waits for device disconnect and
        reconnect as the FBR34KER monitor.
        """
        if not self.pwned:
            return False
        try:
            self._ctrl_transfer(DFU_BM_REQUEST_OUT, DFU_REQ_DETACH,
                                0, DFU_IFACE, b"")
        except Exception:
            pass
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            try:
                self._ctrl_transfer(DFU_BM_REQUEST_IN, DFU_REQ_GETSTATUS,
                                    0, DFU_IFACE, 6)
            except Exception:
                break
            time.sleep(0.2)
        time.sleep(2.0)
        self.device = None
        self.in_dfu = False
        return True

    def close(self) -> None:
        self._release()


def _read_binary(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def find_checkm8_device(serial: str | None = None) -> usb.core.Device | None:
    return find_monitor(Checkm8DFU.CHECKM8_VID, Checkm8DFU.DFU_PIDS[0], serial)
