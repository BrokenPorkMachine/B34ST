from __future__ import annotations

APPLE_VID = 0x05AC

CPID_A12 = 0x8015
CPID_A12X = 0x8027
CPID_A12Z = 0x8028
CPID_A13 = 0x8020
CPID_A14 = 0x8030
CPID_M1 = 0x8103
CPID_A15 = 0x8110
CPID_M2 = 0x8112

DRAM_BASE = 0x800000000
KERNEL_BASE = 0xFFFFFFF007004000
LOAD_ADDR = 0x800000000
USB_DWC3_BASE = 0x860000000

ChipsetInfo = dict


def _patch_offsets(amfi=0xA00000, task=0x500000, priv=0xE00000,
                   mount=0xC00000, codesign=0xA00040, sandbox=0xB00000):
    return dict(amfi_offset=amfi, task_for_pid_offset=task,
                privilege_offset=priv, mount_root_offset=mount,
                codesign_offset=codesign, sandbox_offset=sandbox)


def _dwc3_patch(patch_words=6, patch_data=b"\x4B\x01\x00\x36\x00\x00\x00\x14\x3F\x00\x00\x14\x08\x1A\x00\x58\xC0\x03\x5F\xD6\x1F\x20\x03\xD5"):
    return dict(patch_words=patch_words, patch_data=patch_data)


CHIPSET_DB: dict[int, ChipsetInfo] = {
    CPID_A12: {
        "cpid": CPID_A12,
        "name": "T8015",
        "model": "A12",
        "device_types": ["iPhone XS", "iPhone XS Max", "iPhone XR"],
        "dram_base": DRAM_BASE,
        "dram_size": 0x400000000,
        "kernel_base": KERNEL_BASE,
        "load_addr": LOAD_ADDR,
        "usb_dwc3_base": USB_DWC3_BASE,
        "dwc3_fw_version": "DWC3_1.0a",
        "_product_strings": ["iPhone11,2", "iPhone11,4", "iPhone11,6", "iPhone11,8"],
        "patch_offsets": _patch_offsets(),
        "dwc3_patch": _dwc3_patch(),
    },
    CPID_A12X: {
        "cpid": CPID_A12X,
        "name": "T8027",
        "model": "A12X",
        "device_types": ["iPad Pro 11\" (1st gen)", 'iPad Pro 12.9" (3rd gen)'],
        "dram_base": DRAM_BASE,
        "dram_size": 0x800000000,
        "kernel_base": KERNEL_BASE,
        "load_addr": LOAD_ADDR,
        "usb_dwc3_base": USB_DWC3_BASE,
        "dwc3_fw_version": "DWC3_1.0a",
        "_product_strings": ["iPad8,1", "iPad8,2", "iPad8,3", "iPad8,4",
                             "iPad8,5", "iPad8,6", "iPad8,7", "iPad8,8"],
        "patch_offsets": _patch_offsets(),
        "dwc3_patch": _dwc3_patch(),
    },
    CPID_A12Z: {
        "cpid": CPID_A12Z,
        "name": "T8028",
        "model": "A12Z",
        "device_types": ['iPad Pro 11" (2nd gen)', 'iPad Pro 12.9" (4th gen)'],
        "dram_base": DRAM_BASE,
        "dram_size": 0x800000000,
        "kernel_base": KERNEL_BASE,
        "load_addr": LOAD_ADDR,
        "usb_dwc3_base": USB_DWC3_BASE,
        "dwc3_fw_version": "DWC3_1.0a",
        "_product_strings": ["iPad8,9", "iPad8,10", "iPad8,11", "iPad8,12"],
        "patch_offsets": _patch_offsets(),
        "dwc3_patch": _dwc3_patch(),
    },
    CPID_A13: {
        "cpid": CPID_A13,
        "name": "T8020",
        "model": "A13",
        "device_types": ["iPhone 11", "iPhone 11 Pro", "iPhone 11 Pro Max",
                         "iPhone SE (2nd gen)"],
        "dram_base": DRAM_BASE,
        "dram_size": 0x400000000,
        "kernel_base": KERNEL_BASE,
        "load_addr": LOAD_ADDR,
        "usb_dwc3_base": USB_DWC3_BASE,
        "dwc3_fw_version": "DWC3_1.0a",
        "_product_strings": ["iPhone12,1", "iPhone12,3", "iPhone12,5",
                             "iPhone12,8"],
        "patch_offsets": _patch_offsets(),
        "dwc3_patch": _dwc3_patch(),
    },
    CPID_A14: {
        "cpid": CPID_A14,
        "name": "T8030",
        "model": "A14",
        "device_types": ["iPhone 12", "iPhone 12 Mini", "iPhone 12 Pro",
                         "iPhone 12 Pro Max",
                         'iPad Air (4th gen)'],
        "dram_base": DRAM_BASE,
        "dram_size": 0x400000000,
        "kernel_base": KERNEL_BASE,
        "load_addr": LOAD_ADDR,
        "usb_dwc3_base": USB_DWC3_BASE,
        "dwc3_fw_version": "DWC3_1.0a",
        "_product_strings": ["iPhone13,1", "iPhone13,2", "iPhone13,3",
                             "iPhone13,4", "iPad13,1", "iPad13,2"],
        "patch_offsets": _patch_offsets(),
        "dwc3_patch": _dwc3_patch(),
    },
    CPID_M1: {
        "cpid": CPID_M1,
        "name": "T8103",
        "model": "M1",
        "device_types": ["MacBook Air (M1)", "MacBook Pro 13\" (M1)",
                         "Mac mini (M1)", "iMac 24\" (M1)",
                         "iPad Pro 11\" (3rd gen)", 'iPad Pro 12.9" (5th gen)'],
        "dram_base": DRAM_BASE,
        "dram_size": 0x800000000,
        "kernel_base": KERNEL_BASE,
        "load_addr": LOAD_ADDR,
        "usb_dwc3_base": USB_DWC3_BASE,
        "dwc3_fw_version": "DWC3_1.0a",
        "_product_strings": ["MacBookAir10,1", "MacBookPro17,1",
                             "Macmini9,1", "iMac21,1", "iMac21,2",
                             "iPad13,4", "iPad13,5", "iPad13,6", "iPad13,7",
                             "iPad13,8", "iPad13,9", "iPad13,10", "iPad13,11"],
        "patch_offsets": _patch_offsets(),
        "dwc3_patch": _dwc3_patch(),
    },
    CPID_A15: {
        "cpid": CPID_A15,
        "name": "T8110",
        "model": "A15",
        "device_types": ["iPhone 13", "iPhone 13 Mini", "iPhone 13 Pro",
                         "iPhone 13 Pro Max", "iPhone SE (3rd gen)",
                         'iPad Mini (6th gen)'],
        "dram_base": DRAM_BASE,
        "dram_size": 0x400000000,
        "kernel_base": KERNEL_BASE,
        "load_addr": LOAD_ADDR,
        "usb_dwc3_base": USB_DWC3_BASE,
        "dwc3_fw_version": "DWC3_1.0a",
        "_product_strings": ["iPhone14,2", "iPhone14,3", "iPhone14,4",
                             "iPhone14,5", "iPhone14,6",
                             "iPad14,1", "iPad14,2"],
        "patch_offsets": _patch_offsets(),
        "dwc3_patch": _dwc3_patch(),
    },
    CPID_M2: {
        "cpid": CPID_M2,
        "name": "T8112",
        "model": "M2",
        "device_types": ["MacBook Air (M2)", "MacBook Pro 13\" (M2)",
                         "MacBook Pro 14\" (M2 Pro/Max)",
                         "MacBook Pro 16\" (M2 Pro/Max)",
                         "Mac mini (M2)", "iPad Pro (M2)"],
        "dram_base": DRAM_BASE,
        "dram_size": 0x800000000,
        "kernel_base": KERNEL_BASE,
        "load_addr": LOAD_ADDR,
        "usb_dwc3_base": USB_DWC3_BASE,
        "dwc3_fw_version": "DWC3_1.0a",
        "_product_strings": ["Mac14,2", "Mac14,7", "Mac14,9", "Mac14,10",
                             "Mac14,3", "Mac14,6",
                             "iPad14,3", "iPad14,4"],
        "patch_offsets": _patch_offsets(),
        "dwc3_patch": _dwc3_patch(),
    },
}


def chipset_for_cpid(cpid: int) -> ChipsetInfo | None:
    return CHIPSET_DB.get(cpid)


def chipset_for_product(product: str) -> ChipsetInfo | None:
    for info in CHIPSET_DB.values():
        if product in info.get("_product_strings", []):
            return info
    return None


def chipset_for_device_string(s: str) -> ChipsetInfo | None:
    low = s.lower().replace(" ", "")
    for info in CHIPSET_DB.values():
        for dt in info["device_types"]:
            if dt.lower().replace(" ", "") == low:
                return info
        for ps in info.get("_product_strings", []):
            if ps.lower() == low:
                return info
        if info["name"].lower() in low or info["model"].lower() in low:
            return info
    return None


def all_chipsets() -> list[ChipsetInfo]:
    return list(CHIPSET_DB.values())


def chipset_summary(info: ChipsetInfo) -> str:
    devices = ", ".join(info["device_types"][:3])
    if len(info["device_types"]) > 3:
        devices += f" (+{len(info['device_types'])-3} more)"
    return (f"{info['name']} ({info['model']}) — CPID 0x{info['cpid']:04x} — "
            f"{devices}")
