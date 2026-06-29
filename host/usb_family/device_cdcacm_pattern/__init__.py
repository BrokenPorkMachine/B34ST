"""
USB family device fuzzing campaign.

iPhone as USB device fuzzing:
- Enumeration
- Control transfers
- Vendor-specific requests
- Accessory protocols
- Recovery or diagnostic messages
- Partial and aborted transfers
"""

import json
import random
import struct
import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent


class USBTransferType(IntEnum):
    STANDARD = 0x00
    CLASS = 0x01
    VENDOR = 0x02
    RESERVED = 0x03


class USBRequest(IntEnum):
    GET_STATUS = 0x00
    CLEAR_FEATURE = 0x01
    SET_FEATURE = 0x03
    SET_ADDRESS = 0x05
    GET_DESCRIPTOR = 0x06
    SET_DESCRIPTOR = 0x07
    GET_CONFIGURATION = 0x08
    SET_CONFIGURATION = 0x09
    GET_INTERFACE = 0x0A
    SET_INTERFACE = 0x0B
    SYNCH_FRAME = 0x0C
    SET_SYNCH_FRAME = 0x0D
    GET_ISOCH_DELAY = 0x0E
    SET_ISOCH_DELAY = 0x0F
    SET_ENCRYPTION = 0x0D
    GET_ENCRYPTION = 0x0E
    SET_HANDSHAKE = 0x0F
    GET_HANDSHAKE = 0x10
    SET_SECURITY_DATA = 0x11
    GET_SECURITY_DATA = 0x12
    SET_WWAN_HASH = 0x13
    SET_WWAN_CIPHER = 0x14
    SET_WPAN_HASH = 0x15
    SET_WPAN_CIPHER = 0x16
    SET_BEACON = 0x17
    SET_COUNTER = 0x18
    GET_SECURITY_PKT = 0x19
    SET_SECURITY_PKT = 0x1A


@dataclass
class USBRequestPacket:
    bmRequestType: int
    bRequest: int
    wValue: int
    wIndex: int
    wLength: int
    data: Optional[bytes] = None

    def serialize(self) -> bytes:
        packet = struct.pack(
            "<BBHHH",
            self.bmRequestType,
            self.bRequest,
            self.wValue,
            self.wIndex,
            self.wLength,
        )
        if self.data:
            packet += self.data
        return packet

    @classmethod
    def from_bytes(cls, data: bytes) -> "USBRequestPacket":
        if len(data) < 8:
            raise ValueError(f"Packet too short: {len(data)} < 8")
        bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack(
            "<BBHHH", data[:8]
        )
        packet_data = data[8:] if wLength > 0 else None
        return cls(bmRequestType, bRequest, wValue, wIndex, wLength, packet_data)


@dataclass
class AccessoryProtocolMessage:
    header: bytes
    command: bytes
    parameters: List[int]
    checksum: Optional[int] = None
    eof: Optional[int] = None

    def to_usb_packet(self) -> USBRequestPacket:
        bmRequestType = USBTransferType.VENDOR << 5
        bRequest = 0x30
        data = self.header + self.command + bytes(self.parameters)
        if self.checksum:
            data += struct.pack("<I", self.checksum)
        return USBRequestPacket(bmRequestType, bRequest, 0, 0, len(data), data)


@dataclass
class RecoveryDiagnosticMessage:
    message_type: int
    sequence_number: int
    payload: bytes
    timestamp: int

    @property
    def to_usb_packet(self) -> USBRequestPacket:
        message = struct.pack("<IB", self.message_type, self.sequence_number)
        message += self.payload
        bmRequestType = USBTransferType.VENDOR << 5
        bRequest = 0x20
        return USBRequestPacket(bmRequestType, bRequest, 0, 0, len(message), message)


@dataclass
class DFUPacket:
    bCommand: int
    payload: bytes
    crc: int = 0

    @property
    def serialize(self) -> bytes:
        packet = struct.pack("<BBB", 0xFF, 0x00, self.bCommand)
        packet += struct.pack("<H", self.crc)
        packet += self.payload
        return packet


class USBFamilyDeviceFuzzer:
    """Generate fuzzed USB packets for iPhone as USB device campaigns."""

    def __init__(self, randomness_seed: int = 0xDEADBEEF):
        self.random = random.Random(randomness_seed)

    def generate_enumeration_packets(
        self, corruption_mode: int = 0
    ) -> List[USBRequestPacket]:
        """Generate fuzzed enumeration packets:
        - Initial enumeration
        - Descriptor requests
        - Standard device requests
        """
        packets = []

        # Standard SETUP packets for device enumeration
        setup_templates = [
            USBRequestPacket(
                0x80, USBRequest.GET_DESCRIPTOR, 0x0200, 0, 18
            ),  # Full Device Descriptor
            USBRequestPacket(
                0x80, USBRequest.GET_DESCRIPTOR, 0x0201, 0, 256
            ),  # Full Configuration
            USBRequestPacket(
                0x80, USBRequest.GET_DESCRIPTOR, 0x0202, 0, 256
            ),  # Full String Descriptor
            USBRequestPacket(
                0x80, USBRequest.GET_DESCRIPTOR, 0x0203, 0, 256
            ),  # Full Interface Descriptor
            USBRequestPacket(
                0x80, USBRequest.GET_DESCRIPTOR, 0x0204, 0, 256
            ),  # Full Endpoint Descriptor
            USBRequestPacket(
                0x80, USBRequest.GET_DESCRIPTOR, 0x0205, 0, 256
            ),  # Full HID Descriptor
            USBRequestPacket(
                0x80, USBRequest.GET_DESCRIPTOR, 0x0206, 0, 256
            ),  # Full Report Descriptor
            USBRequestPacket(
                0x80, USBRequest.GET_DESCRIPTOR, 0x0207, 0, 256
            ),  # Full Physical Descriptor
        ]

        for template in setup_templates:
            packet = template
            packet = self._apply_corruption(packet, corruption_mode)
            packets.append(packet)

        return packets

    def generate_control_transfer_packets(
        self, corruption_mode: int = 0
    ) -> List[USBRequestPacket]:
        """Generate fuzzed control transfer packets (vendor-specific requests)."""
        packets = []

        # Vendor-specific requests
        vendor_templates = [
            USBRequestPacket(0x40, 0x01, 0x0002, 0, 4),  # Set Feature
            USBRequestPacket(0xC0, 0x00, 0x0000, 0, 2),  # Get Status
            USBRequestPacket(0x40, 0x03, 0x0000, 0, 0),  # Clear Feature
            USBRequestPacket(0x40, 0x06, 0x0001, 0, 8),  # Set Descriptor
            USBRequestPacket(0xC0, 0x06, 0x0001, 0, 0),  # Get Descriptor
            USBRequestPacket(0x40, 0x09, 0x0001, 0, 0),  # Set Configuration
            USBRequestPacket(0xC0, 0x08, 0x0000, 0, 1),  # Get Configuration
            USBRequestPacket(0x40, 0x0B, 0x0000, 0, 4),  # Set Interface
            USBRequestPacket(0xC0, 0x0A, 0x0000, 0, 1),  # Get Interface
        ]

        for template in vendor_templates:
            packet = template
            packet = self._apply_corruption(packet, corruption_mode)
            packets.append(packet)

        return packets

    def generate_custom_class_packets(
        self, corruption_mode: int = 0
    ) -> List[USBRequestPacket]:
        """Generate custom class-specific packets (Accessory protocols)."""
        packets = []

        # Mock accessory protocol messages
        for i in range(5):
            cmd = AccessoryProtocolMessage(
                header=b"\xfa\x00\x00\x00" + struct.pack("<H", i),
                command=b"\x01"
                + bytes([self.random.randint(0, 255) for _ in range(10)]),
                parameters=[0x01, 0x02, 0x03, 0x04, 0x05],
                checksum=0xDEADBEEF,
                eof=0xDDFE,
            )
            packet = cmd.to_usb_packet()
            packet = self._apply_corruption(packet, corruption_mode)
            packets.append(packet)

        # Mock recovery diagnostic messages
        for i in range(3):
            msg = RecoveryDiagnosticMessage(
                message_type=0x01 + i,
                sequence_number=i,
                payload=bytes([self.random.randint(0, 255) for _ in range(64)]),
                timestamp=0x12345678 + i,
            )
            packet = msg.to_usb_packet
            packet = self._apply_corruption(packet, corruption_mode)
            packets.append(packet)

        return packets

    def generate_partial_aborted_packets(
        self, corruption_mode: int = 0
    ) -> List[USBRequestPacket]:
        """Generate partial and aborted transfer packets."""
        packets = []

        # Partial transfers (truncated data)
        base_packet = USBRequestPacket(0x40, 0x01, 0x0001, 0x0001, 8)
        base_packet.data = bytes([self.random.randint(0, 255) for _ in range(4)])
        packet = self._apply_corruption(base_packet, corruption_mode)
        packets.append(packet)

        # Aborted transfers (zero-length data)
        aborted_packet = USBRequestPacket(0x40, 0x01, 0x0001, 0x0001, 0)
        packet = self._apply_corruption(aborted_packet, corruption_mode)
        packets.append(packet)

        # Overlong transfers
        overlong_packet = USBRequestPacket(0x40, 0x01, 0x0001, 0x0001, 65536)
        packet = self._apply_corruption(overlong_packet, corruption_mode)
        packets.append(packet)

        # Null data pointer
        null_data_packet = USBRequestPacket(0x40, 0x01, 0x0001, 0x0001, 4)
        null_data_packet.data = None
        packet = self._apply_corruption(null_data_packet, corruption_mode)
        packets.append(packet)

        return packets

    def _apply_corruption(
        self, packet: USBRequestPacket, mode: int
    ) -> USBRequestPacket:
        """Apply various corruption patterns based on mode.
        Modes:
        0: No corruption (baseline)
        1: Length corruption (shorter/longer)
        2: Field bit flips
        3: Data truncation
        4: Structured field mutations
        5: Complete randomization
        """
        packet_bytes = packet.serialize()

        if mode == 1:  # Length corruption
            if packet.wLength > 0:
                if self.random.random() < 0.5:
                    new_len = max(0, packet.wLength - 1)
                else:
                    new_len = packet.wLength + self.random.randint(1, 10)
                packet_bytes = packet_bytes[:4] + struct.pack("<H", new_len)
                if new_len < len(packet.data if packet.data else b""):
                    packet_bytes = packet_bytes[
                        : -(len(packet.data if packet.data else b"") - new_len)
                    ]

        elif mode == 2:  # Field bit flips
            if self.random.random() < 0.3:
                pos = self.random.randint(0, len(packet_bytes) - 1)
                packet_bytes = (
                    packet_bytes[:pos]
                    + bytes([(packet_bytes[pos] ^ 0xFF)])
                    + packet_bytes[pos + 1 :]
                )

        elif mode == 3:  # Data truncation
            if packet.data and len(packet.data) > 4:
                truncation = self.random.randint(0, len(packet.data))
                packet_bytes = packet_bytes[: -(len(packet.data) - truncation)]
                if truncation > 0:
                    packet_bytes += packet.data[:truncation]

        elif mode == 4:  # Structured field mutations
            if self.random.random() < 0.5:
                field_pos = self.random.choice([0, 2, 4])
                if field_pos < len(packet_bytes):
                    packet_bytes = (
                        packet_bytes[:field_pos]
                        + struct.pack("<B", self.random.randint(0, 255))
                        + packet_bytes[field_pos + 1 :]
                    )

        elif mode == 5:  # Complete randomization
            packet_bytes = bytes(
                [self.random.randint(0, 255) for _ in range(len(packet_bytes))]
            )

        # Reconstruct packet from possibly corrupted bytes
        if len(packet_bytes) >= 8:
            bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack(
                "<BBHHH", packet_bytes[:8]
            )
            data = packet_bytes[8:] if wLength > 0 else None
            return USBRequestPacket(
                bmRequestType, bRequest, wValue, wIndex, wLength, data
            )
        else:
            return packet

    def generate_corpus(
        self, num_cases: int = 100, corruption_modes: Optional[List[int]] = None
    ) -> List[List[USBRequestPacket]]:
        """Generate a corpus of fuzzing test cases."""
        if corruption_modes is None:
            corruption_modes = [0, 1, 2, 3, 4, 5]

        corpus = []
        for _ in range(num_cases):
            mode = self.random.choice(corruption_modes)
            case = []

            # Generate different packet types based on campaign requirements
            if self.random.random() < 0.3:
                case.extend(self.generate_enumeration_packets(mode))
            if self.random.random() < 0.4:
                case.extend(self.generate_control_transfer_packets(mode))
            if self.random.random() < 0.3:
                case.extend(self.generate_custom_class_packets(mode))
            if self.random.random() < 0.2:
                case.extend(self.generate_partial_aborted_packets(mode))

            # Ensure we have at least one packet
            if not case:
                case.extend(self.generate_enumeration_packets(mode))

            corpus.append(case)

        return corpus

    def save_corpus(
        self, output_path: Path, corpus: List[List[USBRequestPacket]]
    ) -> None:
        """Save corpus to a file for fuzzing tools."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        corpus_data = []
        for case in corpus:
            case_data = []
            for packet in case:
                packet_data = {
                    "bmRequestType": packet.bmRequestType,
                    "bRequest": packet.bRequest,
                    "wValue": packet.wValue,
                    "wIndex": packet.wIndex,
                    "wLength": packet.wLength,
                    "data": packet.data.hex() if packet.data else None,
                }
                case_data.append(packet_data)
            corpus_data.append(case_data)

        with open(output_path, "w") as f:
            json.dump(corpus_data, f, indent=2)

    def generate_payload_for_honggfuzz(self, output_dir: Path) -> Path:
        """Generate payloads for honggfuzz fuzzing."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a corpus directory
        corpus_dir = output_dir / "corpus"
        corpus_dir.mkdir(exist_ok=True)

        # Generate and save corpus
        corpus = self.generate_corpus(num_cases=500)
        self.save_corpus(corpus_dir / "corpus.json", corpus)

        # Create a summary
        summary = {
            "total_cases": len(corpus),
            "avg_packets_per_case": sum(len(case) for case in corpus) / len(corpus),
            "packet_types": {
                "enumeration": len(
                    [
                        p
                        for case in corpus
                        for p in case
                        if p.bRequest == USBRequest.GET_DESCRIPTOR
                    ]
                ),
                "control": len(
                    [
                        p
                        for case in corpus
                        for p in case
                        if p.bRequest
                        in [
                            USBRequest.GET_STATUS,
                            USBRequest.CLEAR_FEATURE,
                            USBRequest.SET_FEATURE,
                        ]
                    ]
                ),
                "accessory": len(
                    [p for case in corpus for p in case if p.bRequest == 0x30]
                ),
                "recovery": len(
                    [p for case in corpus for p in case if p.bRequest == 0x20]
                ),
                "partial_aborted": len(
                    [
                        p
                        for case in corpus
                        for p in case
                        if p.wLength == 0 or p.wLength > 1024
                    ]
                ),
            },
        }

        with open(output_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        # Create a simple harness template (to be used by honggfuzz)
        harness_template = """#!/usr/bin/env python3
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))

from host.usb_family.device_cdcacm_pattern import USBFamilyDeviceFuzzer, USBRequestPacket

def test_payload(payload_path):
    with open(payload_path, 'rb') as f:
        data = f.read()

    try:
        fuzzer = USBFamilyDeviceFuzzer()
        packet = USBRequestPacket.from_bytes(data[:1024])

        # TODO: Submit packet to actual device via USB Serial
        # usb_transport.send_usb_packet(packet)

        return True
    except Exception as e:
        print(f"Error processing payload: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: {sys.argv[0]} <payload_file>")
        sys.exit(1)
    success = test_payload(sys.argv[1])
    sys.exit(0 if success else 1)
"""

        harness_file = output_dir / "test_harness.py"
        harness_file.write_text(harness_template)

        return corpus_dir


def main() -> None:
    """Command-line interface for USB family device fuzzing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate USB family device fuzzing campaign payloads"
    )
    parser.add_argument(
        "--output",
        default="./usb_family_device_corpus",
        help="Output directory for corpus",
    )
    parser.add_argument(
        "--num-cases", type=int, default=500, help="Number of test cases to generate"
    )
    parser.add_argument(
        "--seed", type=int, default=0xDEADBEEF, help="Random seed for reproducibility"
    )

    args = parser.parse_args()

    fuzzer = USBFamilyDeviceFuzzer(args.seed)

    print(f"[USB Device Fuzzer] Generating {args.num_cases} test cases...")
    output_path = fuzzer.generate_payload_for_honggfuzz(Path(args.output))
    print(f"[USB Device Fuzzer] Corpus generated at: {output_path}")
    print(
        f"[USB Device Fuzzer] Run: honggfuzz --input {output_path / 'corpus'} --output {output_path / 'out'} -- test_harness.py"
    )


if __name__ == "__main__":
    main()
