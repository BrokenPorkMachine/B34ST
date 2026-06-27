"""
Device/SoC database for B34ST.
Maps iPhone 4→15, iPad, T2, M1/M2 to their SoC, bootrom state, and iOS ranges.
"""
from __future__ import annotations
import dataclasses
from typing import Any

__all__ = [
    "DeviceInfo", "SOC_DATABASE", "DEVICE_DATABASE",
    "get_device", "get_soc", "devices_for_version",
]


@dataclasses.dataclass(frozen=True)
class DeviceInfo:
    """Information about a specific device model."""
    model: str          # e.g. "iPhone3,1"
    marketing: str      # e.g. "iPhone 4"
    soc: str            # e.g. "A4"
    cpid: int           # e.g. 0x8930
    arch: str           # "arm32" or "arm64"
    min_ios: str
    max_ios: str


@dataclasses.dataclass(frozen=True)
class SocInfo:
    """Information about a SoC/chip."""
    name: str
    cpids: tuple[int, ...]
    arch: str
    bootrom_exploit: str          # "checkm8", "limera1n", "blackbird", "none"
    persistent_jailbreak: bool    # can survive reboot
    min_ios: str
    max_ios: str
    sep_present: bool
    description: str


SOC_DATABASE: dict[str, SocInfo] = {
    "A4": SocInfo("A4", (0x8930,), "arm32", "limera1n", True, "4.0", "7.1.2", False, "Apple A4 (s5l8930x)"),
    "A5": SocInfo("A5", (0x8940, 0x8942, 0x8945), "arm32", "limera1n", True, "5.0", "9.3.6", True, "Apple A5 (s5l8940x)"),
    "A6": SocInfo("A6", (0x8950, 0x8952), "arm32", "checkm8", True, "6.0", "10.3.4", True, "Apple A6 (s5l8950x)"),
    "A7": SocInfo("A7", (0x8960,), "arm64", "checkm8", True, "7.0", "12.5.7", True, "Apple A7 (s5l8960x)"),
    "A8": SocInfo("A8", (0x7000, 0x7001), "arm64", "checkm8", True, "8.0", "12.5.7", True, "Apple A8 (T7000)"),
    "A9": SocInfo("A9", (0x8000, 0x8001, 0x8003), "arm64", "checkm8", True, "9.0", "15.8.3", True, "Apple A9 (S8000/S8003)"),
    "A10": SocInfo("A10", (0x8010, 0x8011, 0x8015), "arm64", "checkm8", True, "10.0", "16.7.10", True, "Apple A10 (T8010)"),
    "A11": SocInfo("A11", (0x8015,), "arm64", "checkm8", True, "11.0", "16.7.10", True, "Apple A11 (T8015)"),
    "A12": SocInfo("A12", (0x8020,), "arm64", "blackbird", False, "12.0", "18.8", True, "Apple A12 (T8020)"),
    "A13": SocInfo("A13", (0x8030,), "arm64", "blackbird", False, "13.0", "19.0", True, "Apple A13 (T8030)"),
    "A14": SocInfo("A14", (0x8101,), "arm64", "blackbird", False, "14.0", "19.0", True, "Apple A14 (T8101)"),
    "A15": SocInfo("A15", (0x8110,), "arm64", "blackbird", False, "15.0", "19.5", True, "Apple A15 (T8110)"),
    "A16": SocInfo("A16", (0x8120,), "arm64", "blackbird", False, "16.0", "19.5", True, "Apple A16 (T8120)"),
    "A17": SocInfo("A17", (0x8130,), "arm64", "none", False, "17.0", "19.5", True, "Apple A17 Pro"),
    "M1": SocInfo("M1", (0x8103,), "arm64", "blackbird", False, "11.0", "19.5", True, "Apple M1 (T8103)"),
    "M2": SocInfo("M2", (0x8112,), "arm64", "blackbird", False, "12.0", "19.5", True, "Apple M2 (T8112)"),
    "T2": SocInfo("T2", (0x8012, 0x8010), "arm64", "checkm8", True, "10.0", "16.x", True, "Apple T2 (T8012, based on A10)"),
}


DEVICE_DATABASE: dict[str, DeviceInfo] = {
    # iPhone 4 (A4)
    "iPhone3,1": DeviceInfo("iPhone3,1", "iPhone 4 (GSM)", "A4", 0x8930, "arm32", "4.0", "7.1.2"),
    "iPhone3,2": DeviceInfo("iPhone3,2", "iPhone 4 (CDMA)", "A4", 0x8930, "arm32", "4.0", "7.1.2"),
    "iPhone3,3": DeviceInfo("iPhone3,3", "iPhone 4 (CDMA)", "A4", 0x8930, "arm32", "4.0", "7.1.2"),
    # iPhone 4s (A5)
    "iPhone4,1": DeviceInfo("iPhone4,1", "iPhone 4s", "A5", 0x8940, "arm32", "5.0", "9.3.6"),
    # iPhone 5 (A6)
    "iPhone5,1": DeviceInfo("iPhone5,1", "iPhone 5 (GSM)", "A6", 0x8950, "arm32", "6.0", "10.3.4"),
    "iPhone5,2": DeviceInfo("iPhone5,2", "iPhone 5 (Global)", "A6", 0x8950, "arm32", "6.0", "10.3.4"),
    # iPhone 5c (A6)
    "iPhone5,3": DeviceInfo("iPhone5,3", "iPhone 5c (GSM)", "A6", 0x8952, "arm32", "7.0", "10.3.4"),
    "iPhone5,4": DeviceInfo("iPhone5,4", "iPhone 5c (Global)", "A6", 0x8952, "arm32", "7.0", "10.3.4"),
    # iPhone 5s (A7)
    "iPhone6,1": DeviceInfo("iPhone6,1", "iPhone 5s (GSM)", "A7", 0x8960, "arm64", "7.0", "12.5.7"),
    "iPhone6,2": DeviceInfo("iPhone6,2", "iPhone 5s (Global)", "A7", 0x8960, "arm64", "7.0", "12.5.7"),
    # iPhone 6 (A8)
    "iPhone7,2": DeviceInfo("iPhone7,2", "iPhone 6", "A8", 0x7000, "arm64", "8.0", "12.5.7"),
    # iPhone 6 Plus (A8)
    "iPhone7,1": DeviceInfo("iPhone7,1", "iPhone 6 Plus", "A8", 0x7000, "arm64", "8.0", "12.5.7"),
    # iPhone 6s (A9)
    "iPhone8,1": DeviceInfo("iPhone8,1", "iPhone 6s", "A9", 0x8000, "arm64", "9.0", "15.8.3"),
    # iPhone 6s Plus (A9)
    "iPhone8,2": DeviceInfo("iPhone8,2", "iPhone 6s Plus", "A9", 0x8000, "arm64", "9.0", "15.8.3"),
    # iPhone SE (A9)
    "iPhone8,4": DeviceInfo("iPhone8,4", "iPhone SE", "A9", 0x8003, "arm64", "9.3", "15.8.3"),
    # iPhone 7 (A10)
    "iPhone9,1": DeviceInfo("iPhone9,1", "iPhone 7 (Global)", "A10", 0x8010, "arm64", "10.0", "15.8.3"),
    "iPhone9,2": DeviceInfo("iPhone9,2", "iPhone 7 Plus (Global)", "A10", 0x8010, "arm64", "10.0", "15.8.3"),
    "iPhone9,3": DeviceInfo("iPhone9,3", "iPhone 7 (GSM)", "A10", 0x8010, "arm64", "10.0", "15.8.3"),
    "iPhone9,4": DeviceInfo("iPhone9,4", "iPhone 7 Plus (GSM)", "A10", 0x8010, "arm64", "10.0", "15.8.3"),
    # iPhone 8 (A11)
    "iPhone10,1": DeviceInfo("iPhone10,1", "iPhone 8 (Global)", "A11", 0x8015, "arm64", "11.0", "16.7.10"),
    "iPhone10,2": DeviceInfo("iPhone10,2", "iPhone 8 Plus (Global)", "A11", 0x8015, "arm64", "11.0", "16.7.10"),
    "iPhone10,4": DeviceInfo("iPhone10,4", "iPhone 8 (GSM)", "A11", 0x8015, "arm64", "11.0", "16.7.10"),
    "iPhone10,5": DeviceInfo("iPhone10,5", "iPhone 8 Plus (GSM)", "A11", 0x8015, "arm64", "11.0", "16.7.10"),
    # iPhone X (A11)
    "iPhone10,3": DeviceInfo("iPhone10,3", "iPhone X (Global)", "A11", 0x8015, "arm64", "11.0", "16.7.10"),
    "iPhone10,6": DeviceInfo("iPhone10,6", "iPhone X (GSM)", "A11", 0x8015, "arm64", "11.0", "16.7.10"),
    # iPhone XR (A12)
    "iPhone11,8": DeviceInfo("iPhone11,8", "iPhone XR", "A12", 0x8020, "arm64", "12.0", "18.8"),
    # iPhone XS (A12)
    "iPhone11,2": DeviceInfo("iPhone11,2", "iPhone XS", "A12", 0x8020, "arm64", "12.0", "18.8"),
    "iPhone11,4": DeviceInfo("iPhone11,4", "iPhone XS Max (China)", "A12", 0x8020, "arm64", "12.0", "18.8"),
    "iPhone11,6": DeviceInfo("iPhone11,6", "iPhone XS Max", "A12", 0x8020, "arm64", "12.0", "18.8"),
    # iPhone 11 (A13)
    "iPhone12,1": DeviceInfo("iPhone12,1", "iPhone 11", "A13", 0x8030, "arm64", "13.0", "19.0"),
    "iPhone12,3": DeviceInfo("iPhone12,3", "iPhone 11 Pro", "A13", 0x8030, "arm64", "13.0", "19.0"),
    "iPhone12,5": DeviceInfo("iPhone12,5", "iPhone 11 Pro Max", "A13", 0x8030, "arm64", "13.0", "19.0"),
    # iPhone SE 2nd Gen (A13)
    "iPhone12,8": DeviceInfo("iPhone12,8", "iPhone SE (2nd gen)", "A13", 0x8030, "arm64", "13.0", "19.0"),
    # iPhone 12 / 12 Pro (A14)
    "iPhone13,1": DeviceInfo("iPhone13,1", "iPhone 12 mini", "A14", 0x8101, "arm64", "14.1", "19.0"),
    "iPhone13,2": DeviceInfo("iPhone13,2", "iPhone 12", "A14", 0x8101, "arm64", "14.1", "19.0"),
    "iPhone13,3": DeviceInfo("iPhone13,3", "iPhone 12 Pro", "A14", 0x8101, "arm64", "14.1", "19.0"),
    "iPhone13,4": DeviceInfo("iPhone13,4", "iPhone 12 Pro Max", "A14", 0x8101, "arm64", "14.1", "19.0"),
    # iPhone 13 / 13 Pro (A15)
    "iPhone14,2": DeviceInfo("iPhone14,2", "iPhone 13 Pro", "A15", 0x8110, "arm64", "15.0", "19.5"),
    "iPhone14,3": DeviceInfo("iPhone14,3", "iPhone 13 Pro Max", "A15", 0x8110, "arm64", "15.0", "19.5"),
    "iPhone14,4": DeviceInfo("iPhone14,4", "iPhone 13 mini", "A15", 0x8110, "arm64", "15.0", "19.5"),
    "iPhone14,5": DeviceInfo("iPhone14,5", "iPhone 13", "A15", 0x8110, "arm64", "15.0", "19.5"),
    # iPhone SE 3rd Gen (A15)
    "iPhone14,6": DeviceInfo("iPhone14,6", "iPhone SE (3rd gen)", "A15", 0x8110, "arm64", "15.4", "19.5"),
    # iPhone 14 / 14 Pro (A16)
    "iPhone14,7": DeviceInfo("iPhone14,7", "iPhone 14", "A16", 0x8120, "arm64", "16.0", "19.5"),
    "iPhone14,8": DeviceInfo("iPhone14,8", "iPhone 14 Plus", "A16", 0x8120, "arm64", "16.0", "19.5"),
    "iPhone15,2": DeviceInfo("iPhone15,2", "iPhone 14 Pro", "A16", 0x8120, "arm64", "16.0", "19.5"),
    "iPhone15,3": DeviceInfo("iPhone15,3", "iPhone 14 Pro Max", "A16", 0x8120, "arm64", "16.0", "19.5"),
    # iPhone 15 / 15 Pro (A17)
    "iPhone15,4": DeviceInfo("iPhone15,4", "iPhone 15", "A17", 0x8130, "arm64", "17.0", "19.5"),
    "iPhone15,5": DeviceInfo("iPhone15,5", "iPhone 15 Plus", "A17", 0x8130, "arm64", "17.0", "19.5"),
    "iPhone16,1": DeviceInfo("iPhone16,1", "iPhone 15 Pro", "A17", 0x8130, "arm64", "17.0", "19.5"),
    "iPhone16,2": DeviceInfo("iPhone16,2", "iPhone 15 Pro Max", "A17", 0x8130, "arm64", "17.0", "19.5"),
}


def get_device(model: str) -> DeviceInfo | None:
    """Look up device by model identifier (e.g. 'iPhone10,1')."""
    return DEVICE_DATABASE.get(model)


def get_soc(name: str) -> SocInfo | None:
    """Look up SoC by name (e.g. 'A11')."""
    return SOC_DATABASE.get(name)


def devices_for_version(ios_version: str) -> list[tuple[str, DeviceInfo]]:
    """Return all (model, DeviceInfo) pairs that support this iOS version."""
    result = []
    for model, dev in DEVICE_DATABASE.items():
        soc = SOC_DATABASE.get(dev.soc)
        if not soc:
            continue
        if _ver_cmp(ios_version, dev.min_ios) >= 0 and _ver_cmp(ios_version, dev.max_ios) <= 0:
            result.append((model, dev))
    return result


def socs_for_version(ios_version: str) -> list[SocInfo]:
    """Return all SoCs that support this iOS version."""
    result = []
    for soc in SOC_DATABASE.values():
        if _ver_cmp(ios_version, soc.min_ios) >= 0 and _ver_cmp(ios_version, soc.max_ios) <= 0:
            result.append(soc)
    return result


def checkm8_compatible(ios_version: str) -> bool:
    """Returns True if a checkm8-compatible SoC is available for this iOS version."""
    for soc in socs_for_version(ios_version):
        if soc.bootrom_exploit == "checkm8":
            return True
    return False


def _ver_cmp(a: str, b: str) -> int:
    def _parse(v):
        parts = v.split(".")
        result = []
        for p in parts:
            if p.replace(".", "").isdigit():
                result.append(int(p))
            elif "x" in p.lower():
                result.append(999)  # "x" = any, treat as max
            else:
                result.append(0)
        return tuple(result)
    pa, pb = _parse(a), _parse(b)
    if pa < pb: return -1
    if pa > pb: return 1
    return 0
