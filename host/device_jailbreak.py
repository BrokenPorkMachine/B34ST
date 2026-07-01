"""Multi-device jailbreak orchestrator.

Auto-detects an Apple device in DFU mode, selects the correct BootROM
exploit (limera1n, checkm8, or DWC3 USBliter8), sends the exploit payload,
and returns a uniform JailbreakResult dict.

Usage:
    result = jailbreak_device()
    if result["success"]:
        print(f"Exploited via {result['exploit_type']}")
    else:
        print(f"Failed: {result['error']}")
"""

from __future__ import annotations

import time
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

USB_IMPORT_ERROR: ImportError | None = None
try:
    import usb.core
    import usb.util

    HAS_PYUSB = True
except ImportError as exc:
    USB_IMPORT_ERROR = exc
    HAS_PYUSB = False

HAS_CHECKM8 = False
CHECKM8_MODULE = None
try:
    from host import checkm8_payload as CHECKM8_MODULE

    HAS_CHECKM8 = True
except ImportError:
    pass

HAS_LIMERA1N = False
LIMERA1N_MODULE = None
try:
    from host import limera1n_payload as LIMERA1N_MODULE

    HAS_LIMERA1N = True
except ImportError:
    pass

try:
    from host.chipset_db import (
        CHIPSET_DB,
        chipset_for_cpid,
        chipset_for_device_string,
    )

    HAS_CHIPSET_DB = True
except ImportError:
    HAS_CHIPSET_DB = False

try:
    from host.cve.devices import SOC_DATABASE as SOC_DB

    HAS_CVE_DB = True
except ImportError:
    HAS_CVE_DB = False


def _lookup_exploit_for_cpid(cpid: int) -> str | None:
    """Determine the BootROM exploit type for a given CPID.

    Checks cve/devices.py first, falls back to chipset_db.py.
    Returns 'limera1n', 'checkm8', 'dwc3', or None.

    Normalises 'blackbird' → 'dwc3' (same DWC3 USB controller exploit
    family, different CVE naming).
    """
    if HAS_CVE_DB:
        for soc in SOC_DB.values():
            if cpid in soc.cpids:
                e = soc.bootrom_exploit
                if e == "blackbird":
                    return "dwc3"
                return e
    if HAS_CHIPSET_DB:
        ci = chipset_for_cpid(cpid)
        if ci is not None:
            return ci.get("bootrom_exploit")
    return None


def find_device_cpid(
    vid: int = 0x05AC, timeout: float = 30.0, product: str | None = None
) -> tuple[int, str | None] | None:
    """Find an Apple device in DFU and return (cpid, exploit_type).

    If *product* is given, skip USB enumeration and look up the chipset
    directly from the product string.

    Polls USB for devices matching Apple VID, reads CPID from iRecovery
    or chipset product string.  Returns None if no device found within
    *timeout* seconds.
    """
    if not HAS_PYUSB:
        return None

    if product is not None and HAS_CHIPSET_DB:
        ci = chipset_for_product(product)
        if ci is not None:
            return (ci["cpid"], ci.get("bootrom_exploit"))
        ci = chipset_for_device_string(product)
        if ci is not None:
            return (ci["cpid"], ci.get("bootrom_exploit"))

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for device in usb.core.find(find_all=True):
            if device.idVendor != vid:
                continue
            cpid = _read_cpid(device)
            if cpid is not None:
                exploit_type = _lookup_exploit_for_cpid(cpid)
                return (cpid, exploit_type)
            prod = _safe_str(device.product)
            if prod and HAS_CHIPSET_DB:
                ci = chipset_for_device_string(prod)
                if ci is not None:
                    cpid = ci["cpid"]
                    exploit_type = ci.get("bootrom_exploit")
                    return (cpid, exploit_type)
                for ci in CHIPSET_DB.values():
                    for ps in ci.get("_product_strings", []):
                        if ps.lower() in prod.lower():
                            cpid = ci["cpid"]
                            exploit_type = ci.get("bootrom_exploit")
                            return (cpid, exploit_type)
        time.sleep(0.5)
    return None


def _read_cpid(device: usb.core.Device) -> int | None:
    """Try to read CPID from a device using iRecovery if available."""
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
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def _safe_str(value: object) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)
    except (UnicodeError, TypeError, ValueError):
        return None


def _device_reports_pwndfu(device: usb.core.Device, marker: str) -> bool:
    """Require positive PWNDFU evidence from USB identity or iRecovery."""
    values = (
        _safe_str(getattr(device, "serial_number", None)),
        _safe_str(getattr(device, "product", None)),
    )
    wanted = marker.lower()
    if any(value and "pwnd" in value.lower() and wanted in value.lower()
           for value in values):
        return True
    try:
        import subprocess

        result = subprocess.run(
            ["irecovery", "-q"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    output = (
        f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}"
    ).lower()
    return result.returncode == 0 and "pwnd" in output and wanted in output


def _run_checkm8(device: usb.core.Device, cpid: int) -> bool:
    """Send the checkm8 exploit sequence to *device*.

    Returns True if the device accepted the exploit transfers
    (becomes pwned / enters PWNDFU).
    """
    if not HAS_CHECKM8:
        raise RuntimeError("checkm8_payload module not available")

    if not CHECKM8_MODULE.is_cpid_supported(cpid):
        raise RuntimeError(f"CPID 0x{cpid:04x} not supported by checkm8")

    transfers = CHECKM8_MODULE.get_exploit_transfers()

    try:
        if device.is_kernel_driver_active(0):
            device.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError):
        pass
    try:
        device.set_configuration()
    except usb.core.USBError:
        pass

    for bmrt, breq, wval, widx, data in transfers:
        try:
            device.ctrl_transfer(bmrt, breq, wval, widx, data, timeout=5000)
        except usb.core.USBError as exc:
            print(f"  [!] checkm8 transfer failed: {exc}", file=sys.stderr)
            return False

    time.sleep(1.0)
    if not _device_reports_pwndfu(device, "checkm8"):
        print("  [!] checkm8 transfers completed without verified PWNDFU evidence",
              file=sys.stderr)
        return False
    return True


def _run_limera1n(device: usb.core.Device, cpid: int) -> bool:
    """Send the limera1n exploit sequence to *device*.

    Returns True if the device accepted the exploit transfers
    (becomes pwned / enters PWNDFU).
    """
    if not HAS_LIMERA1N:
        raise RuntimeError("limera1n_payload module not available")

    if not LIMERA1N_MODULE.is_cpid_supported(cpid):
        raise RuntimeError(f"CPID 0x{cpid:04x} not supported by limera1n")

    transfers = LIMERA1N_MODULE.get_exploit_transfers(cpid)

    try:
        if device.is_kernel_driver_active(0):
            device.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError):
        pass
    try:
        device.set_configuration()
    except usb.core.USBError:
        pass

    for bmrt, breq, wval, widx, data in transfers:
        try:
            device.ctrl_transfer(bmrt, breq, wval, widx, data, timeout=5000)
        except usb.core.USBError as exc:
            print(f"  [!] limera1n transfer failed: {exc}", file=sys.stderr)
            return False

    time.sleep(1.0)
    if not _device_reports_pwndfu(device, "limera1n"):
        print("  [!] limera1n transfers completed without verified PWNDFU evidence",
              file=sys.stderr)
        return False
    return True


def _run_dwc3(device: usb.core.Device, cpid: int) -> bool:
    """Send the DWC3 USBliter8 exploit via USBDevice.enter_pwndfu()."""
    try:
        from usb_serial import USBDevice
    except ImportError as exc:
        raise RuntimeError(f"USBDevice not available: {exc}")

    ud = USBDevice()
    ud.device = device
    ud.chipset = chipset_for_cpid(cpid) if HAS_CHIPSET_DB else None
    return ud.enter_pwndfu()


def jailbreak_device(
    product: str | None = None,
    force: bool = False,
    timeout: float = 30.0,
    exploit_override: str | None = None,
) -> dict:
    """Auto-detect a device and jailbreak it using the appropriate exploit.

    Parameters
    ----------
    product : str, optional
        Override the product identifier (e.g. 'iPhone10,6') to skip
        auto-detection.
    force : bool
        If True, attempt the exploit even if the exploit type is unknown
        or unsupported.
    timeout : float
        Seconds to wait for a device to appear in DFU mode.
    exploit_override : str, optional
        Force a specific exploit type ('limera1n', 'checkm8', 'dwc3').

    Returns
    -------
    dict with keys:
        success : bool
        exploit_type : str or None
        cpid : int or None
        error : str (empty on success)
    """
    result: dict = {
        "success": False,
        "exploit_type": None,
        "cpid": None,
        "error": "",
    }

    if not HAS_PYUSB:
        result["error"] = "pyusb not available (pip install pyusb)"
        return result

    device_info = find_device_cpid(product=product, timeout=timeout)

    if device_info is None:
        result["error"] = (
            f"No Apple device found in DFU mode within {timeout}s.\n"
            "  Ensure the device is connected and in DFU mode."
        )
        return result

    cpid, auto_exploit_type = device_info
    result["cpid"] = cpid

    exploit_type = exploit_override or auto_exploit_type

    if exploit_type is None:
        result["error"] = (
            f"CPID 0x{cpid:04x} is not in the exploit database.\n"
            "  Use --force to attempt anyway or --device to specify a product."
        )
        if not force:
            return result
        exploit_type = "dwc3"

    result["exploit_type"] = exploit_type

    device = _get_usb_device()
    if device is None:
        result["error"] = "Could not find USB device for exploit transfer"
        return result

    exploit_success = False
    try:
        if exploit_type == "checkm8":
            exploit_success = _run_checkm8(device, cpid)
        elif exploit_type == "limera1n":
            exploit_success = _run_limera1n(device, cpid)
        elif exploit_type == "dwc3":
            exploit_success = _run_dwc3(device, cpid)
        else:
            result["error"] = f"Unknown exploit type: {exploit_type}"
            return result
    except (RuntimeError, usb.core.USBError) as exc:
        result["error"] = str(exc)
        return result

    if not exploit_success:
        result["error"] = f"{exploit_type} exploit sequence failed"
        return result

    result["success"] = True
    return result


def _get_usb_device() -> usb.core.Device | None:
    """Return the first Apple DFU device found, or None."""
    for d in usb.core.find(find_all=True):
        if d.idVendor == 0x05AC and d.idProduct in (0x1222, 0x1227, 0x1220):
            return d
    return None
