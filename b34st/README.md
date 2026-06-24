#!/usr/bin/env python3
"""B34ST Setup and Usage Guide

This guide provides comprehensive setup and usage instructions for the B34ST
(B34KER/STAR) runtime authentication tool.

## Quick Start

### Installation

```bash
# Add B34ST to your Python path
cd /path/to/FBR34KER-0.2.3-Physical-Validation-Candidate
pip install -e ./b34st
```

### Basic Usage

```bash
# Validate a session bundle
b34st validate-session --bundle runtime-artifacts/success-session.zip

# Generate a candidate report
b34st physical-validation candidate-report \
  --success success.zip \
  --failure failure.zip \
  --recovered recovered.zip \
  --output candidate-report.json

# Generate hardware preparation checklists
b34st hardware-prepare --save-checklists ./checklists/
```

### Advanced Usage

```bash
# Using PongoOS integration
./scripts/usbliter8_workflow.py --use-pongoos

# Dry run validation
./scripts/usbliterapp.py --use-pongoos --dry-run

# Custom PongoOS path
./scripts/usbliter8_workflow.py --use-pongoos --pongoos-path /path/to/pongoos
```

## Installation Instructions

### System Requirements

- **Operating System**: Linux or macOS
- **Python**: 3.13 or later
- **Build Tools**: Clang 14+, GNU Make
- **Hardware**: A12/A13 iPhone support (A4/A13 chips)

### Installation Steps

1. **Clone the Repository**

```bash
git clone https://github.com/yourusername/fbr34ker-0.2.3-private.git
```

2. **Install Dependencies**

```bash
cd FBR34KER-0.2.3-Physical-Validation-Candidate
pip install -r requirements.txt
```

3. **Install B34ST**

```bash
pip install -e ./b34st
```

4. **Verify Installation**

```bash
# Test B34ST installation
b34st --version

# Test B34ST help
b34st --help
```

## Configuration

### Default Configuration

B34ST uses the following default configuration:

- **Profile**: `profiles/apple-a13-iphone-recovery.json`
- **Device Info**: `examples/a13-device-info.json`
- **Runtime Directory**: `runtime-artifacts/b34st`
- **Build Directory**: `build-b34st`
- **Package Directory**: `dist`

### Custom Configuration

You can customize B34ST configuration by creating a `~/.b34st-config` file:

```bash
cat << EOF > ~/.b34st-config
[Default]
Profile = "profiles/apple-a13-iphone-recovery.json"
DeviceInfo = "examples/a13-device-info.json"
RuntimeDir = "/custom/path/runtime-artifacts/b34st"
BuildDir = "/custom/path/build-b34st"

[Security]
NoExploit = true
NoPhysicalDevice = true
SourcePrivate = true
EOF
```

### Environment Variables

B34ST supports the following environment variables:

- `B34ST_ENABLED`: Enable/disable B34ST validation (default: true)
- `B34ST_VALIDATION_ONLY`: Only run validation, don't compile (default: false)
- `B34ST_DRY_RUN`: Dry run mode (check paths, validate) (default: false)
- `B34ST_LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARN, ERROR) (default: INFO)
- `B34ST_VALIDATION_TIMEOUT`: Validation timeout in seconds (default: 300)
- `B34ST_EVIDENCE_TIMEOUT`: Evidence generation timeout (default: 120)
- `B34ST_STRICT_MATURITY`: Strict profile maturity enforcement (default: true)
- `B34ST_ALLOW_SIMULATOR_ONLY`: Allow simulator-only validation (default: false)
- `B34ST_REQUIRE_PHYSICAL`: Require physical device proof (default: false)

```bash
export B34ST_LOG_LEVEL=DEBUG
export B34ST_VALIDATION_TIMEOUT=600
```

## Usage Examples

### Session Validation

#### Validate a Successful Session

```bash
# Validate a successful validation session
b34st validate-session \
  --bundle runtime-artifacts/b34st/success-session \
  --profile profiles/apple-a13-iphone-recovery.json

# Output includes:
# - Bundle integrity verification
# - Profile maturity validation
# - Console entry observation
# - Required stages validation
```

#### Validate a Failure Session

```bash
# Validate a failure session with automatic recovery
b34st validate-session \
  --bundle runtime-artifacts/b34st/failure-session \
  --profile profiles/apple-a13-iphone-recovery.json \
  --validate-only
```

### Candidate Report Generation

#### Generate a Physical Validation Candidate Report

```bash
# Complete validation cycle: success → failure → recovered
b34st physical-validation candidate-report \
  --success runtime-artifacts/b34st/success-session \
  --failure runtime-artifacts/b34st/failure-session \
  --recovered runtime-artifacts/b34st/recovered-session \
  --qemu-summary runtime-artifacts/gate/summary.json \
  --output runtime-artifacts/b34st/candidate-report.json

# Output includes:
# - Candidate ready status
# - Physical validation completion
# - Failure observed validation
# - Auth invalidation after recovery
```

#### Dry Run Validation

```bash
# Dry run to check paths and requirements without execution
b34st validate-session \
  --bundle runtime-artifacts/b34st/success-session \
  --profile profiles/apple-a13-ip

# Dry run with PongoOS
b34st validate-session \
  --bundle runtime-artifacts/b34st/pongoos-session \
  --profile profiles/apple-a13-iphone-recovery.json \
  --use-pongoos \
  --dry-run
```

### Hardware Preparation

#### List Available Hardware Preparation Categories

```bash
# List available hardware preparation categories
b34st hardware-prepare --list-categories
```

Output:
```
Available hardware preparation categories:
  - console
  - board-inventory
  - memory-map
  - timer
  - interrupts
  - watchdog
  - boot-evidence
```

#### Generate Hardware Preparation Checklists

```bash
# Generate hardware preparation checklists
b34st hardware-prepare --save-checklists ./checklists/

# Validate existing checklist
b34st hardware-prepare --validate-bundle ./checklists/hardware_checklist.json
```

### PongoOS Integration

#### Basic PongoOS Usage

```bash
# Use PongoOS as the operating system
./scripts/usbliter8_workflow.py --use-pongoos

# Custom PongoOS path
./scripts/usbliter8_workflow.py --use-pongoos --pongoos-path /path/to/pongoos

# PongoOS dry run
./scripts/usbliter8_workflow.py --use-pongoos --dry-run
```

#### PongoOS CLI Commands

When in PongoOS mode, B34ST supports additional PongoOS-specific commands:

```bash
# Initialize PongoOS development environment
b34st pongoos-init

# List available PongoOS modules
b34st pongoos-modules

# Install PongoOS packages
b34st pongoos-packages install python3 linux-headers

# Configure network settings
b34st pongoos-network setup usb-tethering

# Hardware diagnostics in PongoOS
b34st pongoos-hardware scan

# List PongoOS services
b34st pongoos-services list
```

## Error Handling

B34ST provides comprehensive error handling with descriptive error messages:

### Common Errors and Solutions

1. **Bundle File Not Found**

```bash
# Error: Bundle file not found: runtime-artifacts/b34st/session.zip
# Solution: Verify the file path and ensure the bundle exists
b34st validate-session --bundle runtime-artifacts/b34st/success-session
```

2. **Invalid Profile**

```bash
# Error: Invalid profile: profiles/invalid.json
# Solution: Use a valid profile from the profiles directory
b34st validate-session --bundle runtime-artifacts/b34st/success-session \
  --profile profiles/apple-a13-iphone-recovery.json
```

3. **Missing Required Arguments**

```bash
# Error: the following arguments are required: --bundle
# Solution: Provide all required arguments
b34st validate-session --bundle runtime-artifacts/b34st/success-session
```

4. **Permission Denied**

```bash
# Error: Permission denied: ./checklists/
# Solution: Ensure the directory is writable
b34st hardware-prepare --save-checklists ./checklists/
chmod 755 ./checklists/
```

## Troubleshooting

### B34ST Validation Errors

1. **Validation Failed**
   - Check the bundle integrity and format
   - Verify the profile matches the device
   - Ensure all required stages are passed

2. **Profile Maturity Validation Failed**
   - Check the evidence class for the requested maturity level
   - Ensure all required evidence is available
   - Verify the profile maturity mapping

3. **Candidate Report Generation Failed**
   - Ensure all three bundles (success, failure, recovered) are available
   - Check the output directory permissions
   - Verify the QEMU summary file if required

### Hardware Preparation Issues

1. **Checklists Generation Failed**
   - Ensure the output directory exists and is writable
   - Check the available disk space
   - Verify the system resources

2. **Invalid Checklist**
   - Load the checklist using JSON parser
   - Verify the checklist structure
   - Ensure all required fields are present

### PongoOS Integration Issues

1. **PongoOS Not Found**
   - Ensure PongoOS is installed and accessible
   - Check the PongoOS path using `--pongoos-path`
   - Install PongoOS if necessary

2. **PongoOS Validation Failed**
   - Check the PongoOS mode compatibility
   - Verify the PongoOS version matches the requirements
   - Ensure the PongoOS configuration is correct

## Advanced Topics

### Profile Maturity Enforcement

B34ST enforces profile maturity through evidence-gated promotion:

```python
# Example maturity promotion logic
MaturityManager = {
    "simulated": {
        "required_evidence": ["simulator"],
        "description": "Bridge-backed simulator execution"
    },
    "bridge-verified": {
        "required_evidence": ["bridge", "simulator"],
        "description": "Persistent bridge authorization"
    },
    "console-verified": {
        "required_evidence": ["bridge", "simulator", "console"],
        "description": "Console capture and verification"
    },
    "boot-evidence-verified": {
        "required_evidence": ["bridge", "simulator", "boot-evidence"],
        "description": "Boot-stage evidence collection"
    },
    "physical-runtime-verified": {
        "required_evidence": ["bridge", "simulator", "physical-runtime"],
        "description": "Physical device execution proof"
    }
}
```

### Failure Matrix

B34ST supports controlled failure injection for four stages:

1. **Console Stage**: Console capture failure
2. **Memory-map Stage**: Memory-map validation failure
3. **Timer Stage**: Timer callback failure
4. **Boot-evidence Stage**: Boot-stage evidence collection failure

Each failure stage is tested deterministically, and recovery is verified after reauthorization.

### Session Bundle Format

Session bundles are ZIP files containing:

- `session.json`: Validation session metadata
- `console.log`: Console capture log
- `boot-evidence.json`: Boot-stage evidence
- (Other evidence files as needed)

Example `session.json`:

```json
{
  "schema_version": 1,
  "project": "B34ST",
  "version": "0.2.3",
  "session_id": "test-session-123",
  "profile_id": "apple-a13-iphone-recovery.json",
  "adapter_id": "simulator",
  "adapter_transport": "persistent-bridge",
  "physical_execution_verified": false,
  "stages": [
    {"stage": "console", "status": "passed"},
    {"stage": "board-inventory", "status": "passed"},
    {"stage": "memory-map", "status": "passed"},
    {"stage": "timer", "status": "passed"},
    {"stage": "boot-evidence", "status": "passed"}
  ],
  "timestamp": "2026-06-24T12:43:00Z",
  "authorization_id": "physical-validation-candidate"
}
```

## Support

### Getting Help

1. **Documentation**: Refer to this guide and the b34st/README.md file
2. **GitHub Issues**: Create GitHub issues at https://github.com/yourusername/fbr34ker
3. **Community**: Join the FBR34KER community for discussions
4. **Bug Reports**: Report bugs with detailed error messages and steps to reproduce

### Contact Information

- **GitHub**: https://github.com/yourusername/fbr34ker
- **Documentation**: https://github.com/yourusername/fbr34ker/blob/main/b34st/README.md
- **Issues**: https://github.com/yourusername/fbr34ker/issues

### Reporting Issues

When reporting issues, please include:

1. **Error messages**: Full error output
2. **Command used**: Exact command that caused the issue
3. **Environment**: Python version, OS, hardware
4. **Steps to reproduce**: Clear steps to reproduce the issue
5. **Expected behavior**: What you expected to happen
6. **Actual behavior**: What actually happened

## License

B34ST is part of the FBR34KER project and is licensed under the same terms.

For details, see the LICENSE file in the root of this repository.

## Version

- **Version**: 0.2.3
- **Release Name**: B34ST_0.2.3_Physical_Validation_Candidate
- **Status**: Physical Validation Candidate
- **Source Repository**: Private GitHub repository
- **Public Releases**: Artifact-only distribution

## Release Notes

### Current Version

- **Initial Release**: B34ST v0.2.3
- **Framework**: Deterministic runtime authentication for FBR34KER
- **Integration**: PongoOS support with FBR34KER validation workflows
- **Security**: Strict evidence-based validation with no exploit delivery

### Future Planned Features

1. **Enhanced PongoOS Integration**: Deeper PongoOS features and services
2. **Cloud Validation**: Cloud-based validation testing
3. **Attestation**: Remote attestation service integration
4. **Monitoring**: Real-time validation monitoring and alerting
5. **Automation**: CI/CD pipeline integration for continuous validation

## Contributors

This implementation is based on the original FBR34KER project and contributes to the broader FBR34KER ecosystem. Special thanks to the FBR34KER community for their contributions and support.
