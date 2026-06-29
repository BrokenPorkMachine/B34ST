# SEP Key Fuzzer

The SEP Key Fuzzer provides automated discovery of SEP-specific vulnerabilities through 40 differential tests organized across 6 canary values. It systematically tests Secure Enclave key wrapper security boundaries and produces bounty-ready reports.

## Overview

The SEP Key Fuzzer is a research harness for discovering SEP (Secure Enclave Processor) vulnerabilities through differential testing. It evaluates the security properties of synthetic key wrappers against real iOS devices, focusing on:

- Key generation, storage, and access control validation
- Symmetric/asymmetric encryption operation testing  
- Boot chain integrity and firmware verification
- Configuration read/write privilege boundaries
- Debug enablement and session boundary testing
- Key storage encryption, access control, and error handling

The framework uses 6 canary values for systematic fault injection and boundary testing across 40 differential test variations.

## Test Categories

### 1. Key Generation (8 tests)
- Wrapper validity before/after device reboot
- Before/after First Unlock (BFU/AFU)
- Lock/unlock state testing
- Passcode change effects
- Biometry enrollment/removal
- OS update compatibility
- Erase and restore
- Cross-device testing (same model, different SoC)

### 2. Authenticated Encryption (7 tests)
- Signatures with various contexts
- Performance under load (64B, 4KB, 64KB)
- Error handling with invalid inputs
- Authentication bypass attempts

### 3. Secure Boot Validation (6 tests)
- Image4 signature verification bypass
- Certificate chain validation
- APTicket validation
- SHSH blob verification
- iBoot authentication bypass
- Boot manifest validation

### 4. Configuration Access (5 tests)
- Read/write privilege boundaries
- ACL validation
- Application group isolation
- Metadata manipulation

### 5. Debug Access (6 tests)
- Debug enablement testing
- Session boundary validation
- Developer mode bypass
- JTAG/soldering detection

### 6. Key Storage (8 tests)
- Encryption validation
- Access control enforcement
- Error handling
- Persistence after state changes

## Canary Values

Six canary values are embedded into synthetic key wrappers at known offsets for memory disclosure detection:

| Canary | Hex Value | Purpose |
|--------|-----------|---------|
| INPUT_A | DFKEY_INPUT_A_000001 | Input region poison |
| POLICY_B | DFKEY_POLICY_B_000001 | Policy region poison |
| PADDING_C | DFKEY_PADDING_C_000001 | Padding region poison |
| LABEL_D | DFKEY_LABEL_D_000001 | Label region poison |
| TAG_E | DFKEY_TAG_E_000001 | Tag region poison |
| NONCE_F | DFKEY_NONCE_F_000001 | Nonce region poison |

All canary values are scanned in output buffers after each operation to detect memory disclosure.

## Bounty Significance Levels

The framework classifies results against Apple's Security Bounty significance levels:

| Level | Score | Eligible | Description |
|-------|-------|----------|-------------|
| Expected behavior | 0 | No | Operation completed as documented |
| Research info | 1 | No | Wrapper version/size identified |
| Access-control | 3 | Yes | Unauthorized access achieved |
| Integrity | 4 | Yes | Modified wrapper accepted |
| Device-binding | 7 | Yes | Cross-device wrapper operation |
| Policy-enforcement | 8 | Yes | Key after ACL revocation |
| Signing-oracle | 9 | Yes | Unauthorized signing operation |
| Key-extraction | 10 | Yes | Private scalar material disclosure |
| Memory-disclosure | 6 | Yes | Canary values in output buffers |

## Test Methodology

### Differential Testing
The fuzzer operates as a differential testing framework:
1. Generate baseline harness and synthetic key wrapper
2. Apply mutations to create test variations
3. Submit mutated wrapper to device/SRP endpoint
4. Compare results against expected behavior
5. Classify based on outcome and bounty significance

### Mutation Categories

1. **Device/Lifecycle:** State-dependent behavior validation
2. **Access-Control:** ACL and authorization testing
3. **Wrapper-Integrity:** Parser robustness and boundary checking

### Canary Monitoring
Distinctive canary values are placed into synthetic wrapper buffers before mutation. Output buffers are scanned for unexpected canary presence as a memory-disclosure indicator and security boundary crossing detector.

## Usage Examples

### Live device SEP Key Fuzzer with USB
```bash
b34st sep-fuzz run --transport usb \
  --transport-args '{"vid": 0x05AC, "pid": 0x1234}' \
  --profile full \
  --canary fault_injection \
  --output-dir ./sep-fuzzing-campaign
```

### Serial port device fuzzing
```bash
b34st sep-fuzz run --transport serial \
  --transport-args '{"port": "/dev/ttyUSB0", "baud": 115200}' \
  --profile full \
  --output-dir ./sep-serial-campaign
```

### Canary value sequencing for systematic testing
```bash
b34st sep-fuzz run --transport simulator \
  --profile test \
  --canary baseline \
  --canary fault_injection \
  --canary race_condition \
  --output-dir ./sep-test-campaign
```

## API Integration

```python
from host.forensics.sep_key_fuzzer import SEPKeyFuzzer, run_campaign
from host.forensics.sep_deploy import make_fuzzer_submit

# Initialize with live device transport
fnsubmit = make_fuzzer_submit("usb", vid=0x05AC, pid=0x1234)
submitter = SEPKeyFuzzer(device_model="iPhone14,2", os_build="21A123", chipset="A15", fnsubmit=fnsubmit)

# Run comprehensive fuzzing campaign
results = submitter.run_campaign(output_dir="sep-fuzzing-campaign")

# Or use the convenience API
result = run_campaign(
    submit_fn=fnsubmit,
    output_dir=pathlib.Path("./output"),
    device_model="iPhone14,2",
    os_build="21A123",
    chipset="A15",
)
```

## Evidence Collection

The framework maintains comprehensive chain-of-custody logging:

- **Test Results:** Each test variation with full metadata
- **Anomalies:** Security-relevant findings with classification
- **Canary Hits:** Memory disclosure indicators
- **Timing:** Operation duration tracking
- **Evidence Chains:** Component boundary violations

This produces a complete evidence bundle suitable for security bounty submissions with structured output matching Apple's bounty reporting requirements.

## Output Format

The framework produces multiple output files:

1. **sep-fuzz-campaign.json** - Full campaign manifest with all results
2. **SEP_Key_Fuzzing_Bounty_Report.md** - Markdown bounty report
3. **chain-of-custody.json** - Evidence validation logs
4. **BaselineHarness.swift** - Swift test harness template

**Key Output Fields:**
- Test variation metadata
- Expected vs actual behavior
- Bounty significance classification
- Canary hits and memory disclosure alerts
- Error details and stack traces
- Timing measurements
- Device state information

## Test Engineering

### Synthetic Key Wrapper
The base wrapper is a 256-byte buffer with canary values placed at known offsets, simulating a realistic CryptoKit ``dataRepresentation`` structure.

### Fuzzing Variations
- **40 total variations** across 3 categories
- **6 canary values** for systematic fault injection
- **9 bounty significance levels** for classification
- **Component boundaries** tested (Device, Authentication, Subsystem, Boot, Key, Firmware)

### Mutation Strategy
Mutations are applied based on variation names:

- **Integrity tests:** Bit flips, truncations, duplications, field tampering
- **Device lifecycle:** State-dependent wrapper validity
- **Access control:** ACL configuration testing

## Security Testing Focus

The framework targets specific SEP security boundaries:

1. **Memory Protection:** Canaries detect disclosure of sensitive data
2. **Access Control:** Unauthorized wrapper usage detection
3. **Parser Robustness:** Modified wrapper acceptance
4. **Device Binding:** Cross-device wrapper operation
5. **Policy Enforcement:** Post-revocation key usage
6. **Signing Oracle:** Unauthorized signing operations
7. **Key Extraction:** Private scalar material disclosure

## Testing Strategy

1. **Simulator First:** Validate test harness and fuzzing logic
2. **Device Validation:** Test against real hardware
3. **Canary Sequencing:** Start with baseline, add fault injection gradually
4. **Component Isolation:** Test each 6 SEP components independently
5. **Regression Testing:** Validate fixes don't break expected behavior
6. **Bounty Validation:** Ensure anomalies meet bounty significance criteria

## Key Features

- **Comprehensive Coverage:** 40 test variations across 6 canary values
- **Bounty-Ready Output:** Automatically generates security bounty reports
- **Evidence-Gated:** Strict validation of security boundary crossings
- **Transport Integration:** USB, serial, TCP, and simulator support
- **Chain-of-Custody:** Comprehensive logging and validation
- **Systematic Testing:** Canary value sequencing for edge case discovery
- **Component Isolation:** Tests each SEP component independently
- **Realistic Harness:** Baseline Swift harness matches production expectations

## Integration with SEP Research Pipeline

The SEP Key Fuzzer integrates with the broader SEP Research Pipeline:

1. **Shared Transport:** Both use deployment transport adapters
2. **Evidence Collection:** Chain-of-custody logging is shared
3. **Canary Monitoring:** Memory disclosure detection works across both
4. **Bounty Significance:** Consistent classification across the two modules
5. **API Pattern:** Both use similar Callable interfaces for device communication

This integration provides a complete forensic research framework that systematically discovers SEP vulnerabilities while maintaining rigorous evidence collection and security boundary validation.