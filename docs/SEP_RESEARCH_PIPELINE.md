# SEP Research Pipeline

The SEP Research Pipeline is an evidence-gated automated fuzzing framework that systematically tests iOS/system/kernel security boundaries through 126 test variations across 7 stages. It provides a comprehensive approach to discovering vulnerabilities in Apple's Secure Enclave Processor (SEP) and sepOS.

## Overview

This pipeline implements a complete research workflow for finding security vulnerabilities in Apple's Secure Enclave Processor (SEP) and sepOS. It systematically tests security boundaries through a structured 7-stage process, with each stage building upon evidence from previous stages.

All operations work exclusively with synthetic test objects. No real credentials, passkeys, payment keys, or personal data are touched.

## 7 Research Stages

### Stage 1: Architectural Mapping (6 tests)
Document the AP→SEP boundary by exercising documented APIs and recording:
- API call and parameters
- Process context
- Request/response sizes
- Authentication state
- Timing measurements
- Error codes and crash indicators
- Persistence behavior after reboot

**Test variations:**
1. Key generation (standard)
2. Key generation (biometry)
3. Key generation (user presence)
4. Key restoration
5. Message signing (64 bytes)
6. Message signing (4KB)
7. Message signing (64KB)
8. Key deletion
9. Key listing
10. Key information
11. Public key export
12. Authentication cancel
13. Authentication evaluation

### Stage 2: Corpus Generation (10 tests)
Build a valid-request corpus with synthetic objects that can be replayed during testing.

### Stage 3: Differential Analysis (20 variations)
Test each API with modified parameters to find edge cases and unexpected behaviors. Each variation changes one property at a time and compares outcomes to baseline.

### Stage 4: Structural Fuzzing (20 variations)
Test API inputs with:
- Length errors
- Integer overflows
- Type confusion
- Buffer boundary violations
- Invalid request structures

### Stage 5: Stateful Fuzzing (20 variations)
Test sequential operations and their interactions:
- Create → Use → Delete → Use
- State preservation after operations
- Cleanup failures
- Resource exhaustion

### Stage 6: Concurrency Fuzzing (20 variations)
Test race conditions and timing attacks:
- Delete vs Sign operations
- Cancel vs Complete scenarios
- Handle reuse after invalidation
- Concurrent authentication

### Stage 7: Crash Triage (10 tests)
Classify faults into layers:
- Application layer failures
- Daemon crashes
- Kernel panics
- SEP OS resets
- Bootrom failures

## Evidence-Gated Execution

The pipeline enforces strict evidence requirements before stage progression:

1. **Entry Validation** - Evidence required before pipeline execution
2. **Stage Dependencies** - Each stage validated before progression
3. **Canary Validation** - Canary value configurations validated before testing
4. **Boundary Crossing** - Security boundary crossing requires explicit evidence
5. **Artifact Validation** - All evidence artifacts validated against schemas

## Transport Adapter Integration

The pipeline integrates with live FBR34KER hardware through the deployment transport module:

### Supported Transport Backends:
- **USBConsole** - Live USB CDC ACM connection to the FBR34KER monitor
- **Serial** - Raw POSIX serial port via FBDP framed streams
- **TCP** - TCP socket communication via FBDP
- **Simulator** - In-memory simulated SEP service for testing
- **FBDP** - Full FBR34KER Bounded Deployment Protocol for artifact deployment

## Usage Examples

### Live device SEP Research Pipeline with USB adapter
```bash
b34st sep-research run --transport usb \
  --transport-args '{"vid": 0x05AC, "pid": 0x1234}' \
  --profile full \
  --canary single_fault \
  --output-dir ./sep-research-campaign
```

### Serial port device testing
```bash
b34st sep-research run --transport serial \
  --transport-args '{"port": "/dev/ttyUSB0", "baud": 115200}' \
  --profile full \
  --output-dir ./sep-serial-campaign
```

### Remote testing via TCP
```bash
b34st sep-research run --transport tcp \
  --transport-args '{"host": "192.168.1.100", "port": 9999}' \
  --profile full \
  --output-dir ./sep-tcp-campaign
```

### In-memory simulation for development/testing
```bash
b34st sep-research run --transport simulator \
  --profile test \
  --output-dir ./sep-simulator-campaign
```

## API Integration

```python
from host.forensics.sep_deploy import make_research_api, make_fuzzer_submit
from host.forensics.sep_research_pipeline import SEPResearchPipeline

# Initialize with live device transport
api = make_research_api("usb", vid=0x05AC, pid=0x1234)
pipeline = SEPResearchPipeline(device_model="iPhone14,2", api_fn=api, evidence_gated=True)

# Execute evidence-gated research
research_results = pipeline.run(output_dir="sep-research-campaign")
```

## Output Format

The pipeline produces comprehensive campaign reports with:

- **Architectural map** - Documented AP→SEP boundaries with full observations
- **Request corpus** - Valid API requests for reproducible testing
- **Differential analysis** - Comparative results showing divergent behaviors
- **Fuzzing results** - Anomalies detected across structural, stateful, and concurrency fuzzing
- **Crash triage** - Classified fault artifacts by layer and severity
- **Chain-of-custody** - Evidence validation logs
- **Bounty report** - Markdown summary with bounty significance classifications

## Testing Strategy

1. **Start with Simulator** - For initial validation and proof of concept
2. **Canary Value Sequencing** - Begin with baseline, add fault injection gradually
3. **Component Isolation** - Test each 6 SEP components independently
4. **Evidence Collection** - Use comprehensive chain-of-custody logging
5. **Canary Value Automation** - Automated canary sequencing for systematic testing

## Key Features

- Evidence-gated execution with strict validation before stage progression
- Chain-of-custody logging at every stage
- Transport adapter integration (USB, serial, TCP, simulator, FBDP)
- Machine-readable evidence validation before progression
- Automated bounty significance classification
- Synthetic test object usage only
- Comprehensive crash triage and classification
- Canary-based memory disclosure detection
