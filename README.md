# FBR34KER usbliter8 Integration

This directory contains the integration of usbliter8 with FBR34kER to create a checkra1n/palera1n-like jailbreak and bootflow for A12/A13 iPhones.

## Overview

This integration combines:
- **usbliter8**: A tethered bootrom exploit for Apple A12, S4/S5 & A13 SoCs
- **FBR34kER**: A clean-room, freestanding ARM64 preboot research monitor and loader

Together, they provide:
1. A jailbreak mechanism for A12/A13 iPhones via usbliter8
2. A pwnd recovery channel for loading FBR34kER
3. A structured hardware bringup workflow for validation
4. Physical validation candidate evidence generation

## Getting Started

### Prerequisites

**Hardware Requirements**:
- Waveshare RP2350 USB-A board (or equivalent RP2350-based board)
- Waveshare RP2350 Zero (or equivalent)
- Pimoroni TINY2350 (or equivalent)
- Raspberry Pi Pico 2 (or equivalent)
- Lightning to USB-A cable
- R13 resistor (optionally removed)

**Software Requirements**:
- FBR34kER 0.2.3 source code (current directory)
- Compiled usbliter8 firmware (build/usbliter8.uf2 available in releases)
- picotool for flashing usbliter8 firmware to RP2350
- A12/A13 iPhone (any generation)

### Hardware Preparation

1. **Prepare the RP2350 board**:
   - Flash the usbliter8 firmware using picotool or mass storage protocol
   - Configure GPIO12/13 for D+ & D- signals (typically on RP2350 USB-A)
   - Test LED indicators (RGB or single-color)

2. **Prepare the iPhone**:
   - Put the device in DFU mode
   - Ensure device is connected to your computer
   - DO NOT enter DFU by breaking LLB - this will not work

### Running the Workflow

**Basic Usage**:
```bash
# Run the workflow (requires hardware preparation)
./scripts/usbliter8_workflow.py

# For dry-run validation (check paths and requirements)
./scripts/usbliter8_workflow.py --dry-run
```

**Options**:
- `--output DIR` - Output directory for artifacts (default: runtime-artifacts/usbliter8-workflow)
- `--usbliter8-path PATH` - Path to usbliter8 directory (if not in default location)
- `--dry-run` - Validate without executing (dry run)
- `--continue-on-failure` - Continue workflow even if stages fail
- `--skip-hardware-prep` - Skip hardware preparation checklist (assumes hardware is ready)
- `--skip-bringup` - Skip hardware bringup workflow
- `--verbose` - Verbose output

## Key Features

### Workflow Stages

1. **usbliter8 Exploit Execution**
   - Executes the usbliter8 tethered bootrom exploit
   - Creates pwnd recovery device with "PWND:[usbliter8]" marker
   - Supports A12/A13 iPhone models

2. **FBR34kER Recovery Boot**
   - Loads FBR34kER boot image through pwnd recovery channel
   - Uses authorized iRecovery sessions
   - Establishes first-stage bridge connection

3. **Hardware Bringup Workflow**
   - Executes console, board-inventory, memory-map, timer, interrupts, watchdog, boot-evidence stages
   - Collects evidence for physical validation candidate
   - Generates session bundles for validation

4. **Evidence Generation**
   - Creates comprehensive workflow artifacts
   - Generates physical validation candidate evidence
   - Supports profile maturity gates

### Integration Architecture

The integration follows a layered architecture:

1. **Hardware Interface**: usbliter8 firmware on RP2350 board
2. **Exploit Execution**: usbliter8 on iPhone bootrom
3. **Bootloader Interface**: FBR34kER recovery boot infrastructure
4. **Hardware Validation**: Authorized hardware bringup workflow
5. **Evidence Generation**: Physical validation candidate system

## Technical Specifications

### Device Support

**A12 iPhones**:
- CPID: 0x8020
- Products: iPhone12,1, iPhone12,3, iPhone12,5, iPhone12,8
- Profile: apple-a12-iphone-recovery.json

**A13 iPhones**:
- CPID: 0x8030
- Products: iPhone12,1, iPhone12,3, iPhone12,5, iPhone12,8
- Profile: apple-a13-iphone-recovery.json

**A13 iPads**:
- CPID: 0x8030
- Products: iPad7,1, iPad7,2, iPad7,3, iPad7,4
- Profile: apple-a13-ipad-recovery.json

### File Structure

```
FBR34KER usbliter8 Integration
├── scripts/
│   ├── usbliter8_workflow.py          # Main workflow script
│   ├── USBLITER8_WORKFLOW.md           # Workflow documentation
│   └── INSTALLATION.md                 # Installation and setup guide
├── usbliter8/
│   ├── README.md                       # usbliter8 documentation
│   └── INTIGRATION_GUIDE.md            # Integration guide
└── SCRIPT.md                           # Setup and usage guide
```

## Running Tests

### Dry Run Mode

Validate the workflow setup without executing:

```bash
./scripts/usbliter8_workflow.py --dry-run
```

### Integration Tests

Run the FBR34kER test suite:

```bash
./fbr34ker test
```

### Workflow Tests

Run the physical validation candidate workflow:

```bash
./scripts/run_physical_validation_candidate.py --output runtime-artifacts/test
```

## Documentation

### Primary Documentation

- **SCRIPT.md** - Setup and usage guide
- **scripts/USBLITER8_WORKFLOW.md** - Complete workflow documentation
- **usbliter8/README.md** - usbliter8 setup and usage
- **usbliter8/INTIGRATION_GUIDE.md** - Technical integration guide

### Technical References

- **usbliter8**: https://ps.tc/pages/blog-usbliter8.html
- **checkra1n**: https://checkra.in/
- **palera1n**: https://palera.in/
- **FBR34kER**: https://github.com/fbr34ker

## Contributing

### How to Contribute

1. **Report Issues**: Create GitHub issues for bugs or feature requests
2. **Submit Pull Requests**: Fork the repository and submit PRs
3. **Improve Documentation**: Update or add documentation
4. **Enhance Testing**: Add new test cases and improve coverage

### Code Style

- Follow existing code style and conventions
- Write comprehensive tests
- Ensure documentation is complete and accurate

## License

This integration is part of the FBR34kER project and is licensed under the same terms as the rest of the FBR34kER codebase.

## Acknowledgments

This integration builds upon the following projects:

- **usbliter8**: By Paradigm Shift
- **checkra1n**: By checkra1n team
- **palera1n**: By palera1n team
- **FBR34kER**: By FBR34kER team

## Contact

For questions or issues, please refer to the FBR34kER documentation or create a GitHub issue.
