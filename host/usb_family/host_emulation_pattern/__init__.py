"""Test harness for USB family host fuzzing campaigns.

iPhone as USB host fuzzing:
- Emulating malicious or malformed peripherals
- HID
- Audio
- Storage
- Network adapter
- Hub
- Composite device
- Rapidly changing descriptors and configurations
"""

import array
import json
import pathlib
import random
import struct
import subprocess
import sys
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Union

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


class USBDeviceTypes(IntEnum):
    HID = 0x03
    AUDIO = 0x01
    AUDIO_INTERFACE = 0x0B
    AUDIO_STREAMING = 0x0B
    CDC_DATA = 0x0A
    MASS_STORAGE = 0x08
    NETWORK = 0x0D
    HUB = 0x09
    COMPOSITE = 0xEF
    CUSTOM = 0xFF


class USBStandardDescriptors(IntEnum):
    DEVICE = 0x00
    CONFIGURATION = 0x02
    STRING = 0x03
    INTERFACE = 0x04
    ENDPOINT = 0x05
    CLASS_SPECIFIC = 0x21


@dataclass
class USBDescriptor:
    bLength: int
    bDescriptorType: int
    bData: bytes

    def serialize(self) -> bytes:
        return struct.pack("<BB", self.bLength, self.bDescriptorType) + self.bData


@dataclass
class USBDeviceConfig:
    device_descriptor: USBDescriptor
    configuration_descriptor: USBDescriptor
    interface_descriptors: List[USBDescriptor]
    endpoint_descriptors: List[USBDescriptor]
    class_specific_descriptors: List[USBDescriptor]

    @property
    def total_size(self) -> int:
        total = self.device_descriptor.bLength + self.configuration_descriptor.bLength
        for desc in self.interface_descriptors:
            total += desc.bLength
        for desc in self.endpoint_descriptors:
            total += desc.bLength
        for desc in self.class_specific_descriptors:
            total += desc.bLength
        return total


@dataclass
class USBInterfaceDescriptor:
    bInterfaceNumber: int
    bAlternateSetting: int
    bNumEndpoints: int
    bInterfaceClass: int
    bInterfaceSubClass: int
    bInterfaceProtocol: int
    iInterface: int


@dataclass
class USBMaliciousPeripheral:
    device_type: int
    interface_count: int
    descriptor_corruption_rate: float
    packet_corruption_rate: float
    sequence_replay_rate: float
    rapid_config_change_rate: float

    def generate_malicious_config(self) -> USBDeviceConfig:
        """Generate a malicious USB device configuration with various attack vectors."""
        configs = []

        # Device Descriptor
        device_desc_data = bytes(
            [
                0x12,
                0x00,  # bLength, bDescriptorType
                0x00,
                0x02,  # bcdUSB (USB 2.0)
                0x00,  # Device Class (use class from interface)
                0x00,  # Device SubClass
                0x00,  # Device Protocol
                0x40,  # MaxPacketSize0 (64)
                0xAB,
                0x01,  # IdVendor (Apple Mock Vendor)
                0xCD,
                0xEF,  # IdProduct (Malicious Product)
                0x01,
                0x00,  # bcdDevice
                0x01,  # iManufacturer
                0x02,  # iProduct
                0x00,
                0x00,  # Serial Number
                0x01,  # Number of Configurations
            ]
        )
        device_descriptor = USBDescriptor(
            18, USBStandardDescriptors.DEVICE, device_desc_data
        )

        # Configuration Descriptor
        config_desc_data = bytes(
            [
                0x09,
                0x02,  # bLength, bDescriptorType
                0xCD,
                0x00,  # wTotalLength (variable, to be overridden)
                0x01,  # bNumInterfaces (malicious, often non-zero)
                0x01,  # bConfigurationValue
                0x00,  # iConfiguration
                0x80,  # bmAttributes (self-powered, remote wakeup)
                0x32,  # bMaxPower
            ]
        )
        configuration_descriptor = USBDescriptor(
            9, USBStandardDescriptors.CONFIGURATION, config_desc_data
        )

        # Interface Descriptors (malicious)
        interface_descriptors = []
        for i in range(self.interface_count):
            corrupt = self.random.random() < self.descriptor_corruption_rate

            if corrupt and self.device_type == USBDeviceTypes.MASS_STORAGE:
                # CDS/CDC protocol descriptors
                desc_data = bytes(
                    [
                        0x09,  # bLength
                        0x04,  # bDescriptorType (Interface)
                        0x00 + i,  # bInterfaceNumber
                        0x00,  # bAlternateSetting
                        0x02,  # bNumEndpoints
                        0x08,  # bInterfaceClass (Mass Storage)
                        0x06,  # bInterfaceSubClass (SCSI)
                        0x50,  # bInterfaceProtocol (Bot)
                        0x00,  # iInterface
                    ]
                )
                interface_desc = USBDescriptor(
                    9, USBStandardDescriptors.INTERFACE, desc_data
                )
            elif corrupt and self.device_type == USBDeviceTypes.HID:
                # HID descriptor
                desc_data = bytes(
                    [
                        0x09,  # bLength
                        0x04,  # bDescriptorType (Interface)
                        0x00 + i,  # bInterfaceNumber
                        0x00,  # bAlternateSetting
                        0x01,  # bNumEndpoints
                        0x03,  # bInterfaceClass (HID)
                        0x01,  # bInterfaceSubClass (Boot)
                        0x01,  # bInterfaceProtocol (Keyboard)
                        0x00,  # iInterface
                    ]
                )
                interface_desc = USBDescriptor(
                    9, USBStandardDescriptors.INTERFACE, desc_data
                )
            else:
                # Normal interface descriptor
                desc_data = bytes(
                    [
                        0x09,  # bLength
                        0x04,  # bDescriptorType (Interface)
                        0x00 + i,  # bInterfaceNumber
                        0x00,  # bAlternateSetting
                        0x01,  # bNumEndpoints
                        self.device_type,  # bInterfaceClass
                        0x00,  # bInterfaceSubClass
                        0x00,  # bInterfaceProtocol
                        0x00,  # iInterface
                    ]
                )
                interface_desc = USBDescriptor(
                    9, USBStandardDescriptors.INTERFACE, desc_data
                )

            interface_descriptors.append(interface_desc)

        # Endpoint Descriptors
        endpoint_descriptors = []
        for i in range(self.interface_count):
            corrupt = self.random.random() < self.packet_corruption_rate

            if corrupt:
                # Malicious endpoint descriptor
                desc_data = bytes(
                    [
                        0x07,  # bLength (invalid, should be 6+ or 7+)
                        0x05,  # bDescriptorType (Endpoint)
                        0x83 + (i * 0x04),  # bEndpointAddress (double assign)
                        0x03,  # bmAttributes (Interrupt, invalid for mass storage)
                        0x00,
                        0x08,  # wMaxPacketSize (malicious)
                        0xFF,  # bInterval (maximum, cause excessive interrupts)
                    ]
                )
                endpoint_desc = USBDescriptor(
                    7, USBStandardDescriptors.ENDPOINT, desc_data
                )
            else:
                # Normal endpoint descriptor
                desc_data = bytes(
                    [
                        0x07,  # bLength
                        0x05,  # bDescriptorType (Endpoint)
                        0x81 + (i * 0x04),  # bEndpointAddress
                        0x02,  # bmAttributes (Bulk)
                        0x40,
                        0x00,  # wMaxPacketSize (64)
                        0x00,  # bInterval
                    ]
                )
                endpoint_desc = USBDescriptor(
                    7, USBStandardDescriptors.ENDPOINT, desc_data
                )

            endpoint_descriptors.append(endpoint_desc)

        # Class-specific descriptors (malicious)
        class_specific_descriptors = []
        if self.device_type == USBDeviceTypes.HID:
            # HID descriptor (malicious)
            report_desc_data = bytes(
                [
                    0x06,
                    0x00,
                    0xFF,  # Usage Page (Generic Desktop)
                    0x05,
                    0x80,  # Usage (Reserved)
                    0xC0,  # End Collection
                    0x09,
                    0x80,  # Usage (Reserved for system control)
                    0xA1,
                    0x01,  # Collection (Application)
                    0x05,
                    0x08,  # Usage Page (LEDs)
                    0x19,
                    0x00,  # Usage Minimum (0)
                    0x29,
                    0x0B,  # Usage Maximum (11)
                    0x15,
                    0x00,  # Logical Minimum (0)
                    0x25,
                    0x01,  # Logical Maximum (1)
                    0x75,
                    0x01,  # Report Size (1)
                    0x95,
                    0x0C,  # Report Count (12)
                    0x81,
                    0x02,  # Input (Data, Variable, Absolute)
                    0x95,
                    0x01,  # Report Count (1)
                    0x81,
                    0x01,  # Input (Constant)
                    0x05,
                    0x08,  # Usage Page (LEDs)
                    0x19,
                    0x00,  # Usage Minimum (0)
                    0x29,
                    0x0B,  # Usage Maximum (11)
                    0x91,
                    0x02,  # Output (Data, Variable, Absolute)
                    0x95,
                    0x01,  # Report Count (1)
                    0x91,
                    0x01,  # Output (Constant)
                    0xC0,  # End Collection
                ]
            )
            hid_desc = USBDescriptor(
                len(report_desc_data),
                USBStandardDescriptors.CLASS_SPECIFIC,
                report_desc_data,
            )
            class_specific_descriptors.append(hid_desc)

        # Update configuration descriptor with actual total length
        total_len = sum(
            d.bLength
            for d in [device_descriptor, configuration_descriptor]
            + interface_descriptors
            + endpoint_descriptors
            + class_specific_descriptors
        )
        config_desc_data = (
            config_desc_data[:2] + struct.pack("<H", total_len) + config_desc_data[4:]
        )
        configuration_descriptor = USBDescriptor(
            9, USBStandardDescriptors.CONFIGURATION, config_desc_data
        )

        return USBDeviceConfig(
            device_descriptor=device_descriptor,
            configuration_descriptor=configuration_descriptor,
            interface_descriptors=interface_descriptors,
            endpoint_descriptors=endpoint_descriptors,
            class_specific_descriptors=class_specific_descriptors,
        )

    def generate_rapid_descriptor_changes(
        self, num_changes: int = 5
    ) -> List[Dict[str, Union[int, bytes]]]:
        """Generate rapid descriptor changes to confuse the host driver."""
        changes = []
        for i in range(num_changes):
            corrupt = self.random.random() < self.descriptor_corruption_rate

            change = {
                "sequence_id": i,
                "timestamp_us": i * 100000,
                "action": "set_configuration" if not corrupt else "change_config",
                "config_number": self.random.randint(0, 1),
                "original_length": self.random.randint(9, 256),
                "corrupted_length": 9 if corrupt else self.random.randint(9, 256),
                "descriptor": bytes([self.random.randint(0, 255) for _ in range(32)]),
                "invalid_crc": struct.pack(
                    "<I", self.random.randint(0x00000001, 0xFFFFFFFF)
                ),
            }
            changes.append(change)
        return changes

    def generate_repeated_sequences(self, num_packets: int = 10) -> List[bytes]:
        """Generate repeated packet sequences to trigger replay attacks."""
        sequences = []
        base_packet = bytes([self.random.randint(0, 255) for _ in range(64)])

        for i in range(num_packets):
            if self.random.random() < self.sequence_replay_rate:
                # Replay previous packet
                replay_index = self.random.randint(0, min(i, 5))
                sequences.append(base_packet)
            else:
                # New packet with mutations
                mutated = bytearray(base_packet)

                # Apply mutations
                for _ in range(10):
                    pos = self.random.randint(0, len(mutated) - 1)
                    mutated[pos] ^= 0xFF

                sequences.append(bytes(mutated))

        return sequences


class USBHostEmulationFuzzer:
    """Generate malicious USB host fuzzing payloads for iPhone as USB host."""

    def __init__(self, randomness_seed: int = 0xDEADBEEF):
        self.random = random.Random(randomness_seed)

    def generate_device_type_configs(self) -> Dict[int, USBDeviceConfig]:
        """Generate configurations for various malicious device types."""
        device_configs = {}

        # HID device (e.g., malicious keyboard)
        hid_device = USBMaliciousPeripheral(
            device_type=USBDeviceTypes.HID,
            interface_count=1,
            descriptor_corruption_rate=0.3,
            packet_corruption_rate=0.4,
            sequence_replay_rate=0.5,
            rapid_config_change_rate=0.3,
        )
        device_configs[USBDeviceTypes.HID] = hid_device.generate_malicious_config()

        # Mass Storage device (e.g., malicious USB drive)
        mass_storage_device = USBMaliciousPeripheral(
            device_type=USBDeviceTypes.MASS_STORAGE,
            interface_count=2,
            descriptor_corruption_rate=0.4,
            packet_corruption_rate=0.5,
            sequence_replay_rate=0.6,
            rapid_config_change_rate=0.2,
        )
        device_configs[USBDeviceTypes.MASS_STORAGE] = (
            mass_storage_device.generate_malicious_config()
        )

        # Network adapter device
        net_device = USBMaliciousPeripheral(
            device_type=USBDeviceTypes.NETWORK,
            interface_count=2,
            descriptor_corruption_rate=0.2,
            packet_corruption_rate=0.3,
            sequence_replay_rate=0.4,
            rapid_config_change_rate=0.5,
        )
        device_configs[USBDeviceTypes.NETWORK] = net_device.generate_malicious_config()

        # Audio device
        audio_device = USBMaliciousPeripheral(
            device_type=USBDeviceTypes.AUDIO,
            interface_count=2,
            descriptor_corruption_rate=0.25,
            packet_corruption_rate=0.35,
            sequence_replay_rate=0.5,
            rapid_config_change_rate=0.3,
        )
        device_configs[USBDeviceTypes.AUDIO] = audio_device.generate_malicious_config()

        # Hub device
        hub_device = USBMaliciousPeripheral(
            device_type=USBDeviceTypes.HUB,
            interface_count=0,
            descriptor_corruption_rate=0.5,
            packet_corruption_rate=0.6,
            sequence_replay_rate=0.7,
            rapid_config_change_rate=0.4,
        )
        device_configs[USBDeviceTypes.HUB] = hub_device.generate_malicious_config()

        # Composite device
        composite_device = USBMaliciousPeripheral(
            device_type=USBDeviceTypes.COMPOSITE,
            interface_count=3,
            descriptor_corruption_rate=0.6,
            packet_corruption_rate=0.7,
            sequence_replay_rate=0.8,
            rapid_config_change_rate=0.5,
        )
        device_configs[USBDeviceTypes.COMPOSITE] = (
            composite_device.generate_malicious_config()
        )

        return device_configs

    def generate_ep_packets(self, device_config: USBDeviceConfig) -> List[bytes]:
        """Generate packets for enumeration and communication with the emulated device."""
        packets = []

        # USB enumeration packets
        enum_packets = [
            b"\x00\x01\x00\x00\x00\x00\x00\x00",  # Reset
            b"\x80\x06\x00\x00\x00\x00\x00\x00\x0c\x00",  # Get Descriptor (Device)
            b"\x80\x06\x00\x01\x00\x00\x00\x00\x09\x00",  # Get Descriptor (Config)
            b"\x80\x06\x00\x04\x00\x01\x00\x00\x09\x00",  # Get Descriptor (Interface)
        ]

        packets.extend(enum_packets)

        # Device-specific command packets
        for _ in range(10):
            corrupt = self.random.random() < 0.4

            if corrupt:
                # Malicious packet with buffer overflow
                malicious = bytearray(b"\x40\x01\x00\x01\x01\x00\x00\x00")
                malicious.extend(b"\x90" * 1000)  # Excessive data
                packets.append(bytes(malicious))
            else:
                # Normal command packet
                normal = bytearray(b"\x40\x01\x00\x01\x04\x00\x00\x00")
                normal.extend(b"\x02" * 64)  # Normal data
                packets.append(bytes(normal))

        # Rapid descriptor changes
        for _ in range(5):
            change = bytearray(b"\x40\x06\x00\x00\x00\x01\x00\x00\x20\x00")
            change.extend(bytes([self.random.randint(0, 255) for _ in range(64)]))
            packets.append(bytes(change))

        # Replay attacks
        for _ in range(3):
            replay = bytearray(b"\xc0\x00\x00\x00\x00\x00\x00\x00\x02\x00")
            replay.extend(b"\x01" * 64)  # Replayed data
            packets.append(bytes(replay))

        return packets

    def generate_exploit_payloads(
        self, device_configs: Dict[int, USBDeviceConfig]
    ) -> Dict[int, Dict[str, List[bytes]]]:
        """Generate exploit payloads for different device types."""
        exploits = {}

        for device_type, config in device_configs.items():
            device_exploits = {
                "config_changes": self.generate_rapid_descriptor_changes(),
                "seq_replays": self.generate_repeated_sequences(),
                "ep_packets": self.generate_ep_packets(config),
                "malformed_descriptors": [config.serialize() for _ in range(10)],
            }
            exploits[device_type] = device_exploits

        return exploits

    def generate_corpus(
        self, num_cases: int = 100
    ) -> Dict[int, Dict[str, List[bytes]]]:
        """Generate a corpus of fuzzing test cases for host emulation."""
        corpus = {}

        device_configs = self.generate_device_type_configs()
        device_types = list(device_configs.keys())

        for _ in range(num_cases):
            device_type = self.random.choice(device_types)

            exploits = self.generate_exploit_payloads(
                {device_type: device_configs[device_type]}
            )

            if device_type not in corpus:
                corpus[device_type] = {}

            for category, payloads in exploits.items():
                if category not in corpus[device_type]:
                    corpus[device_type][category] = []
                corpus[device_type][category].extend(payloads)

        return corpus

    def save_corpus(
        self, output_path: pathlib.Path, corpus: Dict[int, Dict[str, List[bytes]]]
    ) -> None:
        """Save corpus to files for fuzzing tools."""
        output_path.mkdir(parents=True, exist_ok=True)

        for device_type in corpus:
            device_dir = output_path / f"device_{device_type:02x}"
            device_dir.mkdir(exist_ok=True)

            for category, payloads in corpus[device_type].items():
                category_file = device_dir / f"{category}.bin"
                with open(category_file, "wb") as f:
                    for payload in payloads:
                        f.write(payload)
                        f.write(b"\n")

        # Create a summary
        summary = {
            "total_cases": sum(len(corpus[d]) for d in corpus),
            "device_types": {
                name: list(corpus.get(device_type, {}).keys())
                for name, device_type in USBDeviceTypes.__members__.items()
            },
        }

        with open(output_path / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

    def generate_payload_for_honggfuzz(self, output_dir: pathlib.Path) -> pathlib.Path:
        """Generate payloads for honggfuzz fuzzing."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a corpus directory
        corpus_dir = output_dir / "corpus"
        corpus_dir.mkdir(exist_ok=True)

        # Generate and save corpus
        corpus = self.generate_corpus(num_cases=500)
        self.save_corpus(corpus_dir, corpus)

        # Create a summary
        summary = {
            "total_cases": sum(len(corpus[d]) for d in corpus),
            "avg_packets_per_case": sum(
                len(corpus[d][cat] for cat in corpus[d]) for d in corpus
            )
            / sum(len(corpus[d]) for d in corpus),
        }

        with open(output_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        # Create a simple harness template
        harness_template = f"""#!/usr/bin/env python3
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))

def test_payload(payload_path):
    with open(payload_path, 'rb') as f:
        data = f.read()

    try:
        # Process payload as USB descriptor/endpoint data
        # TODO: Submit to device via USB transport
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <payload_file>")
        sys.exit(1)
    success = test_payload(sys.argv[1])
    sys.exit(0 if success else 1)
"""

        harness_file = output_dir / "test_harness.py"
        harness_file.write_text(harness_template)

        return corpus_dir


def main() -> None:
    """Command-line interface for USB host emulation fuzzing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate USB host emulation fuzzing campaign payloads"
    )
    parser.add_argument(
        "--output",
        default="./usb_host_emulation_corpus",
        help="Output directory for corpus",
    )
    parser.add_argument(
        "--num-cases", type=int, default=500, help="Number of test cases to generate"
    )
    parser.add_argument(
        "--seed", type=int, default=0xDEADBEEF, help="Random seed for reproducibility"
    )

    args = parser.parse_args()

    fuzzer = USBHostEmulationFuzzer(args.seed)

    print(f"[USB Host Emulation Fuzzer] Generating {args.num_cases} test cases...")
    output_path = fuzzer.generate_payload_for_honggfuzz(pathlib.Path(args.output))
    print(f"[USB Host Emulation Fuzzer] Corpus generated at: {output_path}")
    print(
        f"[USB Host Emulation Fuzzer] Run: honggfuzz --input {output_path / 'corpus'} --output {output_path / 'out'} -- {fuzzer.honggfuzz_command}"
    )


if __name__ == "__main__":
    main()
