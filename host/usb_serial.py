#!/usr/bin/env python3
"""USB CDC ACM serial transport for FBR34KER monitor communication.

Acts as the host-side counterpart to the monitor's USB gadget stack,
providing a serial-like interface over USB for sending commands and
receiving output. Uses pyusb (libusb) for USB device communication.
"""

from __future__ import annotations

import dataclasses
import struct
import sys
import threading
import time

try:
    import usb.core
    import usb.util

    HAS_PYUSB = True
except ImportError:
    HAS_PYUSB = False

try:
    from host.usbliter8_payload import get_exploit_payload_tuples, is_cpid_supported

    HAS_PAYLOAD = True
except ImportError:
    HAS_PAYLOAD = False


FBR34KER_VID = 0x05AC
FBR34KER_PID = 0x1227
FBR34KER_PONGO_PID = 0x1227
USB_TIMEOUT_MS = 5000
CHIPSET_DB: dict | None = None
ChipsetInfo: type | None = None
chipset_for_cpid = None
chipset_for_device_string = None
_chipset_lock = threading.Lock()


def _load_chipset_db():
    global CHIPSET_DB, ChipsetInfo, chipset_for_cpid, chipset_for_device_string
    with _chipset_lock:
        if CHIPSET_DB is not None:
            return
        from host.chipset_db import (
            CHIPSET_DB as _DB,
            chipset_for_cpid as _cfc,
            chipset_for_device_string as _cfds,
            ChipsetInfo as _CI,
        )

        CHIPSET_DB = _DB
        ChipsetInfo = _CI
        chipset_for_cpid = _cfc
        chipset_for_device_string = _cfds


_load_chipset_db()
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


def find_monitor(
    vid: int = FBR34KER_VID, pid: int = FBR34KER_PID, serial: str | None = None
) -> usb.core.Device | None:
    if not HAS_PYUSB:
        raise TransportError("pyusb not installed (pip install pyusb)")
    for device in usb.core.find(find_all=True):
        if device.idVendor == vid and device.idProduct == pid:
            if serial is None:
                return device
            try:
                if serial in str(device.serial_number, "utf-8", errors="replace"):
                    return device
            except (usb.core.USBError, ValueError, TypeError):
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
            except (usb.core.USBError, ValueError, TypeError):
                pass
            finally:
                try:
                    usb.util.dispose(device)
                except Exception:
                    pass
    return result


def _safe_str(value: object) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)
    except (UnicodeError, TypeError, ValueError):
        return None


class USBConsole:
    """USB CDC ACM serial console to FBR34KER monitor."""

    def __init__(
        self,
        device: usb.core.Device | None = None,
        vid: int = FBR34KER_VID,
        pid: int = FBR34KER_PID,
        serial: str | None = None,
        timeout_ms: int = USB_TIMEOUT_MS,
    ):
        if not HAS_PYUSB:
            raise TransportError("pyusb is required (pip install pyusb)")
        if device is None:
            device = find_monitor(vid, pid, serial)
            if device is None:
                raise TransportError(f"no FBR34KER monitor found ({vid:04x}:{pid:04x})")
        self.device = device
        self.timeout = timeout_ms
        self.identity = DeviceIdentity(
            vid=device.idVendor,
            pid=device.idProduct,
            bus=device.bus,
            address=device.address,
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
            if (
                data_iface is not None
                and data_iface.bInterfaceNumber != self._interface
            ):
                usb.util.claim_interface(self.device, data_iface.bInterfaceNumber)
        except usb.core.USBError as exc:
            raise TransportError(f"failed to claim interface: {exc}")

        iface_eps = data_iface if data_iface is not None else cfg[0]
        for iface in cfg:
            if (
                data_iface is not None
                and iface.bInterfaceNumber == data_iface.bInterfaceNumber
            ):
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
                    except (usb.core.USBError, OSError):
                        pass
                self._claimed = False
            for iface_num, was_attached in self._detach_drivers:
                if was_attached:
                    try:
                        self.device.attach_kernel_driver(iface_num)
                    except (usb.core.USBError, OSError):
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


class USBDevice:
    """Evidence-gated A12+ access through DWC3 vendor control requests.

    A reviewed target-specific first stage may expose vendor-specific EP0
    requests for physical-memory access and code execution. The bundled
    transfer corpus is experimental and must be followed by a successful
    vendor-request probe.

    This class sends those vendor requests and orchestrates the exploit chain:

    1. Find the device (in DFU mode via buttons, or already-booted iOS)
    2. Send the experimental USBliter8 transfer corpus
    3. Load FBR34KER monitor image via vendor MEM_WRITE to physical DRAM
    4. Execute FBR34KER via vendor EXECUTE request
    5. Device re-enumerates as composite CDC ACM + DFU (PID 0x1227)

    A transfer sequence is never treated as proof without the verification
    probe in ``verify_vendor_requests``.
    """

    APPLE_VID = 0x05AC
    DEVICE_PIDS = [0x1227, 0x1222, 0x1220]

    VENDOR_OUT = 0x40
    VENDOR_IN = 0xC0
    VENDOR_REQ_SET_ADDR = 0x01
    VENDOR_REQ_MEM_READ = 0x02
    VENDOR_REQ_MEM_WRITE = 0x03
    VENDOR_REQ_EXECUTE = 0x04

    MAX_XFER_SIZE = 0x8000

    def __init__(
        self, serial: str | None = None, vid: int = APPLE_VID, pid: int | None = None
    ):
        if not HAS_PYUSB:
            raise TransportError("pyusb is required (pip install pyusb)")
        self.serial = serial
        self.vid = vid
        self.pid = pid
        self.device: usb.core.Device | None = None
        self.chipset: ChipsetInfo | None = None
        self.pwned = False
        self._claimed = False
        self._detach_drivers: list[int] = []

    def find_device(self) -> bool:
        for d in self._enumerate():
            self.device = d
            self.chipset = detect_device_chipset(d)
            if self.chipset is not None:
                return True
            self.device = None
        self.device = None
        return False

    @property
    def chipset_name(self) -> str:
        if self.chipset is None:
            return "unknown"
        return f"{self.chipset['name']} ({self.chipset['model']})"

    def _enumerate(self):
        seen = set()
        if self.pid is not None:
            d = find_monitor(self.vid, self.pid, self.serial)
            if d is not None:
                seen.add(d.bus * 1000 + d.address)
                yield d
        for pid in self.DEVICE_PIDS:
            d = find_monitor(self.vid, pid, self.serial)
            if d is not None and (d.bus * 1000 + d.address) not in seen:
                seen.add(d.bus * 1000 + d.address)
                yield d
        if self.serial is None:
            for d in usb.core.find(find_all=True):
                if d.idVendor == self.vid:
                    key = d.bus * 1000 + d.address
                    if key not in seen:
                        seen.add(key)
                        yield d

    def wait_for_device(self, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.find_device():
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
        self._claimed = True

    def _release(self) -> None:
        if self.device is not None:
            for iface_num in self._detach_drivers:
                try:
                    self.device.attach_kernel_driver(iface_num)
                except (usb.core.USBError, OSError):
                    pass
            self._detach_drivers.clear()
        self._claimed = False

    def _ctrl_xfer(
        self,
        bmrt: int,
        breq: int,
        wval: int = 0,
        widx: int = 0,
        data: bytes | int = b"",
    ) -> bytes | int:
        if self.device is None:
            raise TransportError("no device")
        return self.device.ctrl_transfer(bmrt, breq, wval, widx, data, timeout=5000)

    def vendor_set_addr(self, addr: int) -> None:
        self._ctrl_xfer(
            self.VENDOR_OUT, self.VENDOR_REQ_SET_ADDR, 0, 0, struct.pack("<Q", addr)
        )

    def vendor_read(self, size: int) -> bytes:
        result = self._ctrl_xfer(self.VENDOR_IN, self.VENDOR_REQ_MEM_READ, 0, 0, size)
        if isinstance(result, int):
            raise TransportError("vendor read returned a byte count instead of data")
        return bytes(result)

    def vendor_write(self, data: bytes) -> None:
        self._ctrl_xfer(self.VENDOR_OUT, self.VENDOR_REQ_MEM_WRITE, 0, 0, data)

    def verify_vendor_requests(self) -> bool:
        dram = (self.chipset or {}).get("dram_base", 0x800000000)
        try:
            self.vendor_set_addr(dram)
            result = self.vendor_read(4)
            if len(result) != 4:
                raise TransportError(
                    f"vendor read returned {len(result)} bytes; expected 4"
                )
            self.pwned = True
            return True
        except usb.core.USBError as exc:
            print(f"[!] vendor request verification failed: {exc}", file=sys.stderr)
            return False
        except TransportError as exc:
            print(f"[!] vendor request verification failed: {exc}", file=sys.stderr)
            return False

    def enter_pwndfu(self) -> bool:
        """Send the experimental USBliter8 corpus and verify vendor requests.

        Automatically selects the correct exploit payload based on the
        detected device's CPID. Raises an error if CPID is not supported.
        """
        if self.device is None:
            return False
        if self.chipset is None:
            raise TransportError("chipset not detected; cannot select exploit payload")
        cpid = self.chipset.get("cpid")
        if cpid is None:
            raise TransportError("CPID not available in chipset info")
        if not HAS_PAYLOAD:
            raise TransportError("usbliter8_payload module not available")
        if not is_cpid_supported(cpid):
            raise TransportError(
                f"CPID 0x{cpid:04x} not supported by USBliter8 exploit database"
            )
        payload = get_exploit_payload_tuples(cpid)
        if payload is None:
            raise TransportError(f"no exploit payload available for CPID 0x{cpid:04x}")
        self._claim()
        try:
            for xfer in payload:
                self._ctrl_xfer(*xfer)
            if not self.verify_vendor_requests():
                return False
            self.pwned = True
            return True
        except usb.core.USBError as exc:
            print(f"[!] USBliter8 exploit transfer failed: {exc}", file=sys.stderr)
            return False
        except TransportError as exc:
            print(f"[!] USBliter8 exploit transfer failed: {exc}", file=sys.stderr)
            return False

    def send_payload(self, payload_path: str, load_addr: int | None = None) -> bool:
        """Send a binary image via vendor MEM_WRITE requests.

        Uses SET_ADDR + repeated MEM_WRITE to write the image to physical
        DRAM. The firmware auto-increments the target address after each write.
        If load_addr is None, uses chipset's default load_addr.
        """
        if not self.pwned or self.device is None:
            return False
        if load_addr is None:
            if self.chipset is None:
                raise TransportError("chipset not available; load_addr required")
            load_addr = self.chipset.get("load_addr", 0x800000000)
        payload = _read_binary(payload_path)
        self._claim()
        try:
            self.vendor_set_addr(load_addr)
            offset = 0
            total = len(payload)
            while offset < total:
                chunk = payload[offset : offset + self.MAX_XFER_SIZE]
                self.vendor_write(chunk)
                offset += len(chunk)
            return True
        except usb.core.USBError as exc:
            print(f"[!] payload transfer failed: {exc}", file=sys.stderr)
            return False
        except TransportError as exc:
            print(f"[!] payload transfer failed: {exc}", file=sys.stderr)
            return False

    def execute(self, entry: int | None = None) -> bool:
        """Execute code at entry via vendor EXECUTE request.

        The device jumps to entry and begins running FBR34KER, which
        re-enumerates as a composite CDC ACM + DFU device (PID 0x1227).
        If entry is None, uses chipset's default load_addr.
        """
        if not self.pwned:
            return False
        if entry is None:
            if self.chipset is None:
                raise TransportError("chipset not available; entry address required")
            entry = self.chipset["load_addr"]
        previous_identity = (
            getattr(self.device, "bus", None),
            getattr(self.device, "address", None),
        )
        try:
            self.vendor_set_addr(entry)
            self._ctrl_xfer(self.VENDOR_OUT, self.VENDOR_REQ_EXECUTE, 0, 0, b"")
        except Exception as exc:
            print(f"[!] EXECUTE vendor request failed: {exc}", file=sys.stderr)
            return False
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            try:
                self._ctrl_xfer(self.VENDOR_IN, self.VENDOR_REQ_MEM_READ, 0, 0, 4)
            except (usb.core.USBError, TransportError):
                break
            time.sleep(0.2)
        self.device = None
        self.pwned = False
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            candidate = find_monitor(self.vid, 0x1227, self.serial)
            if candidate is not None:
                identity = (
                    getattr(candidate, "bus", None),
                    getattr(candidate, "address", None),
                )
                if identity != previous_identity:
                    self.device = candidate
                    return True
            time.sleep(0.25)
        print("[!] monitor did not re-enumerate after EXECUTE", file=sys.stderr)
        return False

    def close(self) -> None:
        self._release()
        dev = self.device
        self.device = None
        if dev is not None:
            try:
                usb.util.dispose(dev)
            except Exception:
                pass


def _read_binary(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def find_a12_device(serial: str | None = None) -> usb.core.Device | None:
    return find_monitor(USBDevice.APPLE_VID, USBDevice.DEVICE_PIDS[0], serial)


def _readable_cpid(device: usb.core.Device) -> int | None:
    try:
        import subprocess

        r = subprocess.run(
            ["irecovery", "-q"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        for line in r.stdout.splitlines():
            if "CPID" in line:
                return int(line.split(":")[1].strip(), 16)
    except (OSError, ValueError):
        pass
    return None


def detect_device_chipset(device: usb.core.Device) -> ChipsetInfo | None:
    try:
        prod = str(device.product or "")
    except (UnicodeError, TypeError, ValueError):
        prod = ""
    cpid = _readable_cpid(device)
    if cpid is not None:
        ci = chipset_for_cpid(cpid)
        if ci is not None:
            return ci
    if prod:
        ci = chipset_for_device_string(prod)
        if ci is not None:
            return ci
        for ci in CHIPSET_DB.values():
            for ps in ci.get("_product_strings", []):
                if ps.lower() in prod.lower():
                    return ci
    return None
