# SEP Deployment Transport Adapters

The SEP deployment transport module provides a unified interface for bridging the SEP Research Pipeline and Key Fuzzer with live FBR34KER hardware. It supports multiple transport backends and provides consistent APIs for both research and fuzzing operations.

## Overview

This module implements transport adapters that bridge the abstract `api_fn` (`Callable[[str], str]`) and `submit` (`Callable[[bytes, dict], dict]`) interfaces used by the SEP research pipeline and key fuzzer to the real FBR34KER deployment transport. Each transport backend provides consistent APIs for both forward (research pipeline) and reverse (key fuzzer) communication patterns.

## Supported Transport Backends

### 1. USBConsole
**Description:** Live USB CDC ACM connection to the FBR34KER monitor (`usb_serial.py`)

**Capabilities:**
- Send commands to the monitor via USB
- Receive JSON responses
- Full-duplex communication with automatic framing
- Timeout handling (default: 10s for research, 30s for fuzzing)

**Usage:**
```python
from host.forensics.sep_deploy import make_research_api, make_fuzzer_submit

# Research pipeline via USB console
api = make_research_api("usb", vid=0x05AC, pid=0x1234)
pipeline = SEPResearchPipeline(device_model="iPhone14,2", api_fn=api)

# Key fuzzer via USB
fnsubmit = make_fuzzer_submit("usb", vid=0x05AC, pid=0x1234)
campaign_results = run_campaign(fnsubmit, output_dir="sep-fuzzing-campaign")
```

**Error Handling:**
- `TransportError` for connection/communication issues
- JSON parsing for key fuzzer responses
- Automatic retry for transient errors

### 2. Serial
**Description:** Raw POSIX serial port via the FBDP ``FramedStreamTransport``

**Capabilities:**
- Full FBDP frame encoding/decoding
- Automatic framing and error detection
- Configurable baud rate and timeout
- Binary-safe communication

**Protocol:**
- Serial transport uses FBDP framed streams
- Commands are framed as DATA frames
- Responses are framed and parsed automatically
- Supports binary payload data for key fuzzing

**Usage:**
```python
# Serial port via FBDP
fnsubmit = make_fuzzer_submit("serial", port="/dev/ttyUSB0", baud=115200)
campaign_results = run_campaign(fnsubmit, output_dir="sep-serial-campaign")
```

### 3. TCP
**Description:** TCP socket communication via FBDP ``FramedStreamTransport``

**Capabilities:**
- Network-based communication
- Persistent TCP connections
- Automatic framing and error recovery
- Configurable host/port and timeout

**Usage:**
```python
# For development, you might use:
transport = make_research_api("tcp", host="127.0.0.1", port=9999)
```

### 4. Simulator
**Description:** In-memory simulated SEP service (no device required)

**Capabilities:**
- Zero-latency responses
- Reproducible test scenarios
- Error injection and panic simulation
- Full API compatibility with real devices

**Error Simulation:**
- `simulated error` for malformed requests
- `simulated SEP panic` for crashes
- `simulated SEP reset` for watchdog timeouts

**Usage:**
```python
# In-memory simulation for development/testing
api = make_research_api("simulator")
```

### 5. FBDP
**Description:** Full FBR34KER Bounded Deployment Protocol for artifact deployment

**Capabilities:**
- Secure, authenticated deployment of artifacts
- Chunked transfer with integrity verification
- Authorization and session management
- Atomic deployment operations

**Integration:**
- Used for deploying Swift harnesses
- Provides evidence collection
- Supports resume operations
- Maintains deployment session state

## API Adapters

### Research Pipeline API Adapters
The ``api_fn`` interface (`Callable[[str], str]`) is used by `SEPResearchPipeline.execute_operation()` to:

1. Send commands to the device/SEP
2. Receive textual responses
3. Capture timing and error information
4. Build architectural maps

**Adapter Implementations:**
- ``_make_usb_api`` - USB CDC ACM console adapter
- ``_make_serial_api`` - FBDP serial adapter
- ``_make_tcp_api`` - FBDP TCP adapter
- ``_simulated_api`` - In-memory simulator

### Key Fuzzer Submit Adapters
The ``submit`` interface (`Callable[[bytes, dict], dict]`) is used by `SEPKeyFuzzer.run_fuzz_variation()` to:

1. Send mutated key wrappers to the device
2. Receive fuzzing test results
3. Capture validation outcomes
4. Build campaign manifests

**Adapter Implementations:**
- ``_make_usb_fuzzer_submit`` - USB console adapter
- ``_make_serial_fuzzer_submit`` - FBDP serial adapter
- ``_simulated_submit`` - In-memory simulator

## Deployment Tools

### Swift Harness Deployment
```python
from host.forensics.sep_deploy import deploy_swift_harness

# Deploy SEP key baseline harness to target device
result = deploy_swift_harness(
    profile_path=pathlib.Path("profiles/qemu-virt-deployment.json"),
    harness_path=pathlib.Path("build/BaselineHarness"),
    transport="serial", 
    transport_args={"port": "/dev/ttyUSB0"},
    start=True,
    authorize=True,
)
```

**Parameters:**
- `profile_path` - JSON deployment profile (e.g., ``profiles/qemu-virt-deployment.json``)
- `harness_path` - Compiled Swift harness binary
- `transport` - ``"simulator"``, ``"tcp"``, or ``"serial"``
- `transport_args` - Backend-specific arguments
- `start` - Whether to start execution after deployment
- `authorize` - Whether to authorize the deployment session

**Returns:** Deployment result dict with success status, result data, and evidence.

## Platform Abstraction

### End-to-End Flow

1. **Transport Selection:** Choose backend via ``make_research_api()`` or ``make_fuzzer_submit()``
2. **Adapter Creation:** Backend-specific adapter factory is invoked
3. **Connection Establishment:** Adapter opens connection to target
4. **Operation Execution:** Research pipeline or fuzzer calls adapter
5. **Response Processing:** Adapter parses and returns structured data
6. **Resource Management:** Adapter closes connection on completion

### Error Propagation

All transport adapters follow a consistent error model:

- **TransportError** - Connection/communication failures
- **RuntimeError** - Parsed from adapter-level exceptions
- **JSONDecodeError** - Malformed responses (for fuzzing)
- **Timeout** - Operation timeout exceeded

Errors are wrapped with context (e.g., ``USB transport error: [original error]``)
for debugging while maintaining the original error details.

## Configuration Options

### Research Pipeline Configuration
```python
api = make_research_api(
    backend="usb",
    vid=0x05AC,
    pid=0x1234,
    serial="optional_serial_number",
    timeout=10.0,  # seconds
)

api = make_research_api(
    backend="serial", 
    port="/dev/ttyUSB0",
    baud=115200,
    timeout=10.0,
)

api = make_research_api(
    backend="tcp",
    host="192.168.1.100",
    port=9999,
    timeout=10.0,
)
```

### Key Fuzzer Configuration
```python
fnsubmit = make_fuzzer_submit(
    backend="usb",
    vid=0x05AC,
    pid=0x1234,
    timeout=30.0,  # seconds
)

fnsubmit = make_fuzzer_submit(
    backend="serial",
    port="/dev/ttyUSB0", 
    baud=115200,
    timeout=30.0,
)
```

## Backwards Compatibility

The transport module provides a stable API for both research pipeline and key fuzzer usage:

- **Consistent Interface:** All backends expose identical method signatures
- **Default Values:** Sensible defaults reduce configuration burden
- **Error Consistency:** Standardized error types and messages
- **Extensibility:** New backends can be added without breaking changes

## Testing Strategy

1. **Simulator First:** Always test with simulator for isolated unit testing
2. **Sequential Integration:** Test with serial/TCP after simulator validation
3. **Live Hardware:** Only test with USB/serial on validated hardware
4. **Canary Monitoring:** Monitor canary values for memory disclosure detection
5. **Evidence Collection:** Maintain chain-of-custody for all transport operations

## Key Features

- Unified interface across multiple transport backends
- Transport-agnostic research pipeline execution
- Comprehensive error handling and recovery
- Evidence collection and chain-of-custody logging
- Canary-based security monitoring
- Full FBDP integration for secure deployment
- Reproducible simulator environment for development
- Real hardware support for production testing
