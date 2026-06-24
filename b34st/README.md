#!/usr/bin/env python3
"""B34ST (B34KER/STAR) - Project Documentation

This document provides comprehensive documentation for the B34ST (B34KER/STAR)
runtime authentication tool, part of the FBR34KER 0.2.3 Physical Validation Candidate.

## Overview

B34ST is a runtime authentication tool for FBR34KER that provides:

- Deterministic physical validation for A12/A13 iPhone hardware bring-up
- Evidence-based maturity enforcement (simulated → physical-runtime-verified)
- Persistent bridge authorization management
- Controlled failure injection and recovery testing
- Structured hardware bring-up workflows

## Architecture Overview

B34ST follows a layered architecture combining:

### Core Components

1. **Physical Validation Pipeline**
   - Evidence collection and verification
   - Profile maturity enforcement
   - Deterministic candidate generation
   - Failure matrix testing

2. **Bridge Protocol Management**
   - Persistent, sequence-checked transport layer
   - Authorization and reauthorization handling
   - Reset-driven recovery

3. **Hardware Profile Validation**
   - Exact-product matching for A12/A13
   - Required-stage enforcement
   - Console, memory-map, timer, boot-evidence testing

4. **Error Handling Framework**
   - Deterministic failure injection
   - Recovery sequence testing
   - Evidence-based failure analysis

### Evidence Classes

B34ST generates provable evidence classes:

1. **Simulator Evidence**
   - Deterministic simulator execution
   - Bridge contract proof
   - No physical device required

2. **Bridge Evidence**
   - Persistent bridge operation
   - Sequence number verification
   - Authorization proof

3. **Console Evidence**
   - Console capture and verification
   - Entry observation
   - Bound detection

4. **Boot-Evidence**
   - Boot-stage evidence collection
   - Stage verification
   - Evidence integrity

5. **Physical-Runtime Evidence**
   - Physical device execution proof
   - Memory map validation
   - Real hardware testing

## User Guide

### Quick Start

```bash
# Validate a session bundle
b34st validate-session \
  --bundle runtime-artifacts/success-session.zip \
  --profile profiles/apple-a13-iphone-recovery.json

# Generate a candidate report
b34st physical-validation candidate-report \
  --success success.zip \
  --failure failure.zip \
  --recovered recovered.zip \
  --output candidate-report.json

# Generate hardware preparation checklists
b34st hardware-prepare --save-checklists ./checklists/
```

### Command Reference

#### `b34st validate-session`

**Purpose**: Validate a session bundle against profile maturity gates.

**Arguments**:
- `--bundle`: Path to session bundle (ZIP file)
- `--profile`: Device profile JSON file (default: apple-a13-iphone-recovery.json)
- `--validate-only`: Only validate, don't require full maturity

**Example**:
```bash
b34st validate-session \
  --bundle runtime-artifacts/success-session.zip \
  --profile profiles/apple-a13-iphone-recovery.json
```

#### `b34st physical-validation candidate-report`

**Purpose**: Generate a deterministic physical validation candidate report.

**Arguments**:
- `--success`: Path to successful validation bundle
- `--failure`: Path to failure validation bundle
- `--recovered`: Path to recovered validation bundle
- `--qemu-summary`: Path to QEMU gate summary (optional)
- `--output`: Path to save the candidate report

**Example**:
```bash
b34st physical-validation candidate-report \
  --success success.zip \
  --failure failure.zip \
  --recovered recovered.zip \
  --output candidate-report.json
```

#### `b34st hardware-prepare`

**Purpose**: Read-only hardware preparation with checklists.

**Subcommands**:

**`--list-categories`**: List available hardware preparation categories

**`--save-checklists <dir>`**: Generate hardware preparation checklists

**`--validate-bundle <file>`**: Validate an existing checklist bundle

**Example (list categories)**:
```bash
b34st hardware-prepare --list-categories
```

**Example (save checklists)**:
```bash
b34st hardware-prepare --save-checklists ./checklists/
```

### Profile Maturity Enforcement

B34ST enforces profile maturity based on evidence. The maturity order is:

1. **Simulated**: Bridge-backed simulator execution
2. **Bridge-verified**: Persistent bridge authorization proof
3. **Console-verified**: Console capture and entry observation
4. **Boot-evidence-verified**: Boot-stage evidence collection
5. **Physical-runtime-verified**: Physical device execution proof

#### Maturity Promotion Rules

A profile can be promoted to the next maturity level only if the required evidence is supplied:

- **Simulated → Bridge-verified**: Requires bridge evidence
- **Bridge-verified → Console-verified**: Requires console evidence
- **Console-verified → Boot-evidence-verified**: Requires boot-evidence
- **Boot-evidence-verified → Physical-runtime-verified**: Requires physical-runtime evidence

#### Evidence Requirements

```json
{
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

## Device Support

B34ST supports the following Apple devices:

### A12 iPhones

- **CPID**: 0x8020
- **Products**: 
  - iPhone12,1
  - iPhone12,3,
  - iPhone12,5,
  - iPhone12,8
- **Profile**: `profiles/apple-a12-iphone-recovery.json`

### A13 iPhones

- **CPID**: 0x8030
- **Products**:
  - iPhone12,1,
  - iPhone12,3,
  - iPhone12,5,
  - iPhone12,8
- **Profile**: `profiles/apple-a13-iphone-recovery.json`

### A13 iPads

- **CPID**: 0x8030
- **Products**:
  - iPad7,1,
  - iPad7,2,
  - iPad7,3,
  - iPad7,4
- **Profile**: `profiles/apple-a13-ipad-recovery.json`

## Configuration

### Project Configuration (`b34st/.b34st-config`)

The B34ST project uses a configuration file (`.b34st-config`) with the following settings:

```toml
# B34ST Project Configuration

[B34ST]
Name = "B34ST (B34KER/STAR)"
Version = "0.2.3"
Status = "Physical Validation Candidate"
ReleaseChannel = "validation-candidate"
ReleaseName = "B34ST_0.2.3_Physical_Validation_Candidate"

[Build]
BuildDir = "build-b34st"
RuntimeArtifactDir = "runtime-artifacts/b34st"
PackageDir = "dist"
SourceId = "0.2.3-validation-candidate"

[Runtime]
DefaultProfile = "profiles/apple-a13-iphone-recovery.json"
DefaultDeviceInfo = "examples/a13-device-info.json"
DefaultQEMURequired = false

[Evidence]
MaturityOrder = ["simulated", "bridge-verified", "console-verified", "boot-evidence-verified", "physical-runtime-verified"]
FailureStages = ["console", "memory-map", "timer", "boot-evidence"]

[Security]
NoExploit = true
NoPhysicalDevice = true
SourcePrivate = true
AuthenticationRequired = true

[CI/CD]
CIRunsOn = "ubuntu-latest"
CITimeoutMinutes = 30
```

## Technical Specifications

### Evidence-Based Maturity Enforcement

B34ST enforces profile maturity through evidence-gated promotion:

1. **Simulated Maturity**: Requires simulator evidence only
2. **Bridge-verified Maturity**: Requires simulator and bridge evidence
3. **Console-verified Maturity**: Requires simulator, bridge, and console evidence
4. **Boot-evidence-verified Maturity**: Requires simulator, bridge, console, and boot-evidence
5. **Physical-runtime-verified Maturity**: Requires simulator, bridge, console, boot-evidence, and physical-runtime evidence

**Promotion Rules**:
- Profiles cannot be promoted beyond their evidence level
- Claims beyond supplied evidence are rejected
- Maturity promotion is deterministic and repeatable

### Profile Maturity Mapping

Each maturity level requires specific evidence:

| Maturity Level | Required Evidence | Description |
|----------------|-------------------|-------------|
| Simulated | simulator | Bridge-backed simulator execution |
| Bridge-verified | simulator, bridge | Persistent bridge authorization |
| Console-verified | simulator, bridge, console | Console capture and verification |
| Boot-evidence-verified | simulator, bridge, console, boot-evidence | Boot-stage evidence collection |
| Physical-runtime-verified | simulator, bridge, console, boot-evidence, physical-runtime | Physical device execution proof |

### Validation Pipeline

The B34ST validation process follows this pipeline:

1. **Input Validation**
   - Session bundle integrity verification
   - Profile validation against schema
   - Required stage verification

2. **Evidence Collection**
   - Console capture validation
   - Boot-evidence collection and verification
   - Failure injection and evidence generation

3. **Maturity Enforcement**
   - Profile maturity validation
   - Evidence requirement checking
   - Promotion eligibility determination

4. **Report Generation**
   - Candidate report creation
   - Success/failure analysis
   - Validation results summary

## Security and Safety

### Operational Boundaries

B34ST is designed with strict security boundaries:

1. **No Exploit Delivery**
   - No SecureROM exploit
   - No signature bypass
   - No iBoot patches
   - No DFU-entry mechanisms

2. **Controlled Environment**
   - Simulator and QEMU-based testing only
   - Simulated hardware environment
   - No physical device testing

3. **Evidence Bound**
   - Claims restricted to supplied evidence classes
   - No unverified assertions
   - Deterministic validation

4. **Read-Only Operations**
   - Hardware preparation is explicitly read-only
   - Mutation requires explicit authorization
   - Bounded external command interface

5. **Authorization Required**
   - All mutation requires authorization
   - Signed recovery sessions
   - Reset-driven reauthorization

## Usage Examples

### Basic Usage

```bash
# Install B34ST
pip install -e b34st/

# Validate a session bundle
b34st validate-session \
  --bundle runtime-artifacts/success-session.zip

# Generate hardware preparation checklists
b34st hardware-prepare --save-checklists ./checklists/
```

### Advanced Usage

```bash
# Run a complete validation workflow
b34st physical-validation candidate-report \
  --success runtime-artifacts/b34st/success-session.zip \
  --failure runtime-artifacts/b34st/failure-session.zip \
  --recovered runtime-artifacts/b34st/recovered-session.zip \
  --output runtime-artifacts/b34st/candidate-report.json \
  --qemu-summary runtime-artifacts/gate/summary.json
```

### Integration with CI/CD

B34ST integrates with CI/CD pipelines for automated validation:

```yaml
# GitHub Actions example
- name: Run B34ST validation
  run: |
    b34st physical-validation candidate-report \
      --success runtime-artifacts/b34st/success-session.zip \
      --failure runtime-artifacts/b34st/failure-session.zip \
      --recovered runtime-artifacts/b34st/recovered-session.zip \
      --output runtime-artifacts/b34st/candidate-report.json
```

## Command Line Interface

### Global Options

- `--version`: Show version information and exit
- `--quiet`: Suppress non-essential output
- `--verbose`: Enable verbose output

### Subcommands

- `validate-session`: Validate a session bundle
- `physical-validation candidate-report`: Generate candidate report
- `hardware-prepare`: Handle hardware preparation

### Help Information

Each command provides help information with:

- Required and optional arguments
- Usage examples
- Description of functionality

```bash
# Show general help
b34st --help

# Show command-specific help
b34st validate-session --help

# Show physical-validation help
b34st physical-validation --help
```

## Integration with FBR34KER

B34ST is fully integrated with the FBR34KER framework:

### Dependencies

- **Core FBR34KER**: Monitor and loader builds
- **Host Tools**: fbr34kctl, fbr34ker, physical validation scripts
- **Profiles**: Apple A12/A13 recovery profiles
- **Device Info**: A12/A13 device information examples

### Build System Integration

B34ST extends the FBR34KER Makefile with additional targets:

```makefile
# B34ST targets
b34st: $(B34ST_TARGET).bin

# Runtime artifacts
b34st-runtime: runtime-artifacts/b34st

# Validation candidate generation
b34st-candidate: runtime-artifacts/b34st-candidate

# Evidence validation
b34st-validate: runtime-artifacts/b34st-validation-summary

# Clean B34ST artifacts
clean-b34st:
	$(RM) -r $(B34ST_BUILD_DIR) $(RUNTIME_ARTIFACT_DIR)/b34st
```

### Release Process

1. **Source Repository**: Source code maintained in private GitHub repository
2. **Release Building**: Automated build process with CI/CD
3. **Package Creation**: Source or artifact-only packages based on kind
4. **Distribution**: Public releases contain only compiled artifacts

## Release Pipeline

### Source Repository (Private)

- Branch: `main` for stable releases
- Branch: `develop` for development
- Pull requests require review and approval
- Protected branches for main

### CI/CD Pipeline

1. **Build Stage**: Compile source code
2. **Test Stage**: Run unit and integration tests
3. **Validation Stage**: Run B34ST validation workflows
4. **Package Stage**: Create release artifacts
5. **Security Scan**: Validate security boundaries
6. **Deploy Stage**: Publish to artifact repository

### Release Distribution

Public releases include:

- **Executable Binaries**: `b34st` runtime authentication tool
- **Validation Evidence**: Deterministic session bundles
- **Documentation**: User guides and technical references
- **Configuration Files**: Project settings
- **Release Manifest**: Artifact inventory and checksums

**Source code is excluded** from public releases - distributed artifacts contain only compiled binaries and validation evidence.

## Development

### Building from Source

```bash
# Clone the private repository
cd /path/to/FBR34KER-0.2.3-Physical-Validation-Candidate

# Build B34ST
cd b34st
python -m pip install -e .
```

### Running Tests

```bash
# Run B34ST validation tests
make b34st-runtime

# Run FBR34KER test suite
./fbr34ker test

# Validate physical validation candidate workflow
./scripts/run_physical_validation_candidate.py --output runtime-artifacts/test
```

### Testing Requirements

- Validate bundle integrity for all evidence classes
- Test profile maturity enforcement with different evidence sets
- Verify failure injection and recovery sequences
- Ensure controlled failure matrix coverage
- Test CLI interface against all B34ST operations

## Contributing

### How to Contribute

1. **Report Issues**: Create GitHub issues for bugs or feature requests
2. **Submit Pull Requests**: Fork the repository and submit PRs
3. **Improve Documentation**: Update or add documentation
4. **Enhance Testing**: Add new test cases and improve coverage

### Code Style

- Follow existing FBR34KER code style
- Write comprehensive tests
- Ensure documentation is complete and accurate
- Implement proper error handling

## License

B34ST is part of the FBR34KER project and is licensed under the same terms.

For details, see the LICENSE file in the root of this repository.

## Status

B34ST is a **Physical Validation Candidate** release with the following characteristics:

- Deterministic candidate generation for bridge validation
- QEMU-capable CI for automated testing
- Evidence integrity and profile maturity enforcement
- Controlled failure and recovery testing
- Public ABI for validation claims (32-byte structure)
- No physical device execution proof included

Physical validation is complete only when both:

1. **A passing QEMU gate** is supplied
2. **Non-simulator physical-runtime evidence** is provided

## Contact

For questions or issues, please refer to the FBR34KER documentation or create a GitHub issue.

### Documentation Resources

- **Primary Documentation**: b34st/README.md
- **Architecture**: docs/ARCHITECTURE.md
- **Validation**: docs/PHYSICAL_VALIDATION_CANDIDATE.md
- **API Reference**: docs/PROFILE_MATURITY.md
- **Security**: docs/THREAT_MODEL.md

### Examples

- **Physical Validation**: scripts/run_physical_validation_candidate.py
- **Runtime Validation**: host/physical_validation.py
- **Bundle Generation**: host/session_bundle.py
- **Bridge Management**: host/bridge_protocol.py

## Acknowledgments

B34ST builds upon the following projects:

- **FBR34KER**: By FBR34kER team (clean-room ARM64 preboot monitor)
- **A12/A13 Developer Preview**: Foundation for hardware bring-up
- **Physical Device Integration Preview**: Persistent bridge protocol
- **Physical Validation Candidate**: Evidence-gated validation framework