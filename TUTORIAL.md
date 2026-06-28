# FBR34KER Tutorial

This tutorial walks through the entire FBR34KER workflow: setting up the toolchain, building firmware targets, running the monitor in QEMU, exercising the jailbreak security-bypass chain, using the loader SDK, and creating a release package. No physical Apple hardware is required — everything up to the exploit-chain step runs under QEMU.

## Prerequisites

- macOS or Linux (Windows via WSL2 with USB passthrough for device work)
- Xcode Command Line Tools (`xcode-select --install`) or equivalent LLVM/Clang
- LLVM toolchain for AArch64 (`brew install llvm` on macOS)
- QEMU system emulator for AArch64 (`brew install qemu`)
- Python 3.10+ with `pyusb` (`pip install pyusb`) for device operations
- GNU Make

### Verify your environment

```sh
./fbr34ker doctor
```

This checks for Clang, `ld.lld`, `llvm-objcopy`, `qemu-system-aarch64`, `make`, `pyusb`, `libusb`, and the chipset database. Address any `[MISSING]` items before proceeding.

## 1. Project structure

```
FBR34KER_0.3.0_Beta/
├── TUTORIAL.md            ← this file
├── README.md              ← project overview
├── CHANGELOG.md           ← version history
├── LICENSE                ← license terms
├── SECURITY.md            ← security boundary and policy
├── RELEASE_NOTES.md       ← release notes
│
├── fbr34ker               ← main CLI entry point (Python)
├── b34stctl               ← B34ST control panel
├── b34stool.py            ← B34ST legacy tool
├── Makefile               ← top-level build system
│
├── kernel/                ← monitor firmware source (EXCLUDED from public release)
│   ├── main.c             ← entry and lifecycle
│   ├── jailbreak.c        ← A12+ jailbreak chain implementation
│   ├── command.c          ← interactive shell and command dispatcher
│   ├── mmio.c             ← memory-mapped I/O abstraction
│   ├── usbliter8_exploit.c ← DWC3 USB exploit for A12+
│   └── ...
│
├── arch/arm64/            ← AArch64 architecture layer (EXCLUDED from public release)
│   ├── start.S            ← boot-time entry point
│   ├── mmu.c              ← page-table management
│   └── cpu.c              ← EL1 register access
│
├── platform/              ← hardware platform support (EXCLUDED from public release)
│   ├── qemu_virt/         ← QEMU virt machine (default)
│   └── generic_arm64/     ← generic ARM64 (physical devices)
│
├── include/fbr34ker/      ← firmware headers
├── host/                  ← host-side Python tools (EXCLUDED from public release)
├── sdk/                   ← standalone loader SDK
├── scripts/               ← build and release scripts
├── docs/                  ← full documentation (46 documents)
├── linker/                ← linker scripts per platform
├── profiles/              ← device recovery profiles
├── tests/                 ← native test harnesses
└── b34st/                 ← B34ST research runtime framework
```

### Build outputs

| Directory | Purpose |
|-----------|---------|
| `build/` | QEMU virt target (fbr34ker.bin, fbr34ker.elf) |
| `build-generic/` | Generic ARM64 monitor |
| `build-hardware-probe/` | Hardware probe image (read-only) |
| `build-loader/` | QEMU handoff loader |
| `build-sdk/` | SDK static library + examples |
| `build-apple/` | Apple A12/A13 boot images + simulations |
| `build-exploit/` | Operational (security-model-enabled) build |
| `dist/` | Release packages |

## 2. Building

### Build everything

```sh
./fbr34ker build
```

This builds 13 targets across all platforms. Equivalent to:

```sh
make all                          # QEMU virt monitor
make generic                      # generic ARM64 monitor
make hardware-probe               # hardware probe image
make modules                      # dynamic modules (hello.fmod)
make sdk                          # loader SDK
make loader-check                 # loader conformance tests
make generic-loader               # QEMU generic loader
make apple-boot-images            # A12/A13/iBridge boot images
make deployment-simulate          # deployment simulation
make apple-bringup-simulate       # bring-up simulation
make physical-validation-candidate # validation artifacts
```

Or use `make <target>` for specific builds:

```sh
make all                    # QEMU virt only
make build-operational      # security-model-enabled build
make apple-boot-images      # Apple recovery boot images
```

### Build with security model

The `build-operational` target enables the security model (memory writes):

```sh
make build-operational
# or via CLI:
./fbr34ker build --security-model
```

This produces `build-exploit/fbr34ker-operational.bin`, which is required for the exploit chain and jailbreak boot on physical devices.

## 3. Running in QEMU

### Start the monitor

```sh
./fbr34ker run direct
```

This boots `build/fbr34ker.bin` under QEMU virt. You will see the monitor's boot banner, initialization logs, and finally the shell prompt:

```
FBR34KER 0.3.0 (beta)
Target: qemu_virt; source: 0.3.0-beta
Protocol 4; handoff 4; module ABI 1; FMOD 1; FMBC 1

interactive shell ready
fbr34ker>
```

Other run profiles:

```sh
./fbr34ker run generic      # via generic loader
./fbr34ker run probe        # hardware probe simulation
```

### Using the shell

Type `help` to list all commands:

```
fbr34ker> help
```

Type `help <command>` for usage:

```
fbr34ker> help jailbreak
```

### Shell commands at a glance

| Command | Purpose |
|---------|---------|
| `help` | List commands |
| `version` | Build version info |
| `jailbreak` | A12+ jailbreak chain (see section 4) |
| `trust-cache` | Trust cache management |
| `kernel-patches` | Kernel patch application |
| `persistence` | Persistence subsystem |
| `secure-boot-bypass` | Secure boot bypass |
| `exploit-chain` | USBliter8 exploit chain |
| `mmio read <addr>` | Read MMIO register |
| `mmio write <addr> <val>` | Write MMIO register |
| `fault-arm <point>` | Fault injection test (test builds) |

### Exit QEMU

Press `Ctrl-A` then `X`, or close the terminal window.

## 4. The jailbreak command

The `jailbreak` command drives the A12+ security bypass and kernel boot chain. It is available in any build variant.

### Status

```sh
fbr34ker> jailbreak
```

Shows the current jailbreak state, security model status, bypass counts, kernel detection info, and SEP availability.

### Security model

```sh
fbr34ker> jailbreak security-model on
fbr34ker> jailbreak security-model off
```

Enable or disable the security model. When active, memory-write operations (e.g. boot-args injection) take effect immediately. In "pending" mode, operations are staged but not committed.

### Security bypasses

```sh
fbr34ker> jailbreak bypass-pac       # Disable pointer authentication
fbr34ker> jailbreak bypass-aprr      # Bypass APRR/PPL memory protections
fbr34ker> jailbreak bypass-wxn       # Clear W^X enforcement
fbr34ker> jailbreak bypass-all       # All three at once
```

### Kernel detection

```sh
fbr34ker> jailbreak detect-kernel                    # Auto-scan DRAM
fbr34ker> jailbreak detect-kernel --path <phys> [size] # Specify location
```

Scans DRAM for a kernelcache (Mach-O fat binary with `LC_MAIN` command). On QEMU no kernelcache is present, so this will report "no kernelcache found" — this is expected. On a real device after the exploit chain, the kernelcache resides at `0x800000000`+ (A12+) or can be loaded via vendor MEM_WRITE.

### KASLR detection

```sh
fbr34ker> jailbreak detect-kaslr [phys [size]]
```

Reads the first `LC_SEGMENT_64` command's `vmaddr` to compute the KASLR slide. Tries both iOS 16 (`0xFFFFFFF007000000`) and iOS 17+ (`0xFFFFFFF007800000`) kernel bases.

### Boot-args injection

```sh
fbr34ker> jailbreak inject-bootargs
fbr34ker> jailbreak inject-bootargs --args "custom arguments here"
```

By default injects:
```
-s amfi_get_out_of_my_way=1 cs_enforcement_disable=1 keepsyms=1 debug=0x2014 wdt=0
```

Boot-args are located by scanning for magic `0xBA696F53` or `0x626F6F74` in the kernelcache range, not by fixed offset.

### SEP detection

```sh
fbr34ker> jailbreak detect-sep [base]
```

Probes the SEP MMIO region. Default base: `0x82E000000` (A13), then `0x82D000000` (A12/A12X).

### Full chain

```sh
fbr34ker> jailbreak chain-all
```

Runs the complete chain: security bypasses → MMU enable → kernel detection → boot-args → SEP detection → ready to boot.

### Boot kernel

```sh
fbr34ker> jailbreak boot-kernel [entry]
```

Disables the MMU (clears `SCTLR_EL1.M` and `SCTLR_EL1.WXN`), performs a DSB+ISB barrier, and jumps to the kernel entry point with boot-args pointer in `x1` (iOS 17+ compatibility). On a real device, the console disconnects as the kernel takes over. In QEMU without a loaded kernel, this will fault — this is expected.

### Chain all (one-shot)

```sh
fbr34ker> jailbreak chain-all
```

Equivalent to running `bypass-all`, `detect-kernel`, `inject-bootargs`, `detect-sep` sequentially, plus MMU re-initialization.

## 5. Full exploit chain walkthrough (conceptual)

> **Note:** This section describes the full internal toolchain. The public operational release does not include the `kernel/`, `arch/`, `platform/`, or `host/` source code — the exploit, jailbreak, and kernel-patching internals are private. The pre-built firmware images in `build-*` contain the compiled exploit chain and can be used with the operational scripts.

The complete A12+ exploit flow requires physical hardware. Here is the flow:

```
DFU mode → DWC3 exploit → PWNDFU → vendor MEM_WRITE → monitor execute →
console connect → jailbreak chain → kernel boot
```

### Using the CLI

```sh
./fbr34ker exploit --auto
```

This builds the operational image, then runs:

1. **`step_dfu_wait`** — Wait for A12+ device in DFU mode
2. **`step_detect_chipset`** — Auto-detect SoC (A12/A13/A14/M1/etc.)
3. **`step_pwndfu`** — Send DWC3 USBliter8 exploit payload
4. **`step_send_monitor`** — Write FBR34KER monitor to DRAM via vendor MEM_WRITE
5. **`step_execute_monitor`** — Jump to monitor entry point
6. **`step_connect_console`** — Connect to CDC ACM console
7. **`step_jailbreak_chain`** — Run all jailbreak commands
8. **`step_boot_kernel`** — Detect and boot the iOS kernel

### Step-by-step with `fbr34ker`

```sh
# 1. Enter DFU mode on device, then:
./fbr34ker detect                   # Verify device is detected
./fbr34ker pwndfu                   # DWC3 exploit → PWNDFU
./fbr34ker load-monitor build-exploit/fbr34ker-operational.bin
./fbr34ker console                  # Interactive monitor shell
```

Once in the console:

```
fbr34ker> jailbreak security-model on
fbr34ker> jailbreak bypass-all
fbr34ker> jailbreak detect-kernel --path 0x800000000
fbr34ker> jailbreak inject-bootargs
fbr34ker> jailbreak chain-all
fbr34ker> jailbreak boot-kernel
```

### Key A12+ differences from checkm8 (A5-A11)

- **No bootrom exploit** — A12+ uses DWC3 USB controller firmware exploit (USBliter8)
- **Vendor requests** provide physical memory access (SET_ADDR, MEM_READ, MEM_WRITE, EXECUTE)
- **DWC3 firmware version matters** — v1 and v2 have different exploit payloads
- **iOS 17+ kernel base is 0xFFFFFFF007804000** vs iOS 16 `0xFFFFFFF007004000`
- **Boot-args must be found dynamically** by scanning for magic values
- **Kernel entry on iOS 17+ expects device tree pointer in x1**

## 6. SDK overview

The FBR34KER SDK provides a standalone, freestanding C11 library for constructing and validating handoff ABI v4 structures. It has no dependencies on monitor internals or any operating system.

### SDK contents

```
sdk/
├── include/          ← public ABI headers (7 headers)
│   ├── fbr34ker_sdk.h
│   ├── fbr34ker_boot_image.h
│   ├── fbr34ker_handoff.h
│   ├── fbr34ker_modules.h
│   ├── fbr34ker_services.h
│   ├── fbr34ker_memory.h
│   └── fbr34ker_bridge_protocol.h
├── src/              ← library source
│   ├── handoff_builder.c
│   ├── handoff_validate.c
│   └── profile_match.c
├── examples/         ← working example loaders
│   ├── minimal_loader/
│   ├── callback_console/
│   └── framebuffer_loader/
├── templates/        ← project templates
│   ├── module/
│   ├── driver/
│   ├── board/
│   └── transport/
└── tests/            ← SDK conformance tests
    └── sdk_harness.c
```

### Building the SDK

```sh
make -C sdk                    # builds libfbr34ker_sdk.a
make -C sdk test               # runs conformance tests
```

### Minimal loader example

```c
#include <fbr34ker_sdk.h>
#include <fbr34ker_handoff.h>

int main(void) {
    fbr34ker_handoff_v4_t handoff;
    fbr34ker_sdk_handoff_builder_t builder;

    fbr34ker_sdk_handoff_builder_init(&builder, &handoff);
    fbr34ker_sdk_handoff_builder_set_version(&builder, 4);
    fbr34ker_sdk_handoff_builder_set_target(&builder, "generic_arm64");

    if (fbr34ker_sdk_handoff_validate(&handoff) == 0) {
        // handoff is valid — transfer control to monitor
    }
    return 0;
}
```

See `sdk/examples/` for complete working examples.

## 7. Creating a release package

### Public operational release (recommended)

```sh
make sdk-release
```

Produces a clean public release archive in `dist/` containing everything needed to make the toolchain fully operational — B34ST research runtime, all build artifacts, scripts, tests, SDK, linker scripts, board profiles, demo modules, curated documentation, and tutorial — but **no private kernel/exploit/host source code**.

| Archive | Contents |
|---------|----------|
| `FBR34KER_0.3.0_..._operational.zip` | Public release — no private code |

### Internal full-source release

```sh
make manifest       # Build all targets + generate manifest + checksums
make verify         # Run non-QEMU verification suite
make release-gate   # Full release gate (requires QEMU)
make package
```

Produces two archives in `dist/`:

| Archive | Contents |
|---------|----------|
| `FBR34KER_0.3.0_..._source.zip` | All source code, docs, scripts (excludes build artifacts) |
| `FBR34KER_0.3.0_..._complete.zip` | Source + all build artifacts, SDK, boot images, simulations |

Each archive has a corresponding `.sha256` checksum file.

### Operational package contents

```
FBR34KER_0.3.0_Beta/
├── TUTORIAL.md                  ← this tutorial
├── README.md                    ← project overview
├── CHANGELOG.md                 ← version history
├── LICENSE                      ← license terms
├── SECURITY.md                  ← security policy
├── RELEASE_NOTES.md             ← release notes
├── fbr34ker                     ← CLI entry point
├── b34stctl                     ← B34ST control panel
├── b34st/                       ← B34ST research runtime framework
│   ├── b34st.py, engine.py, build.py, control_panel.py, ...
│   ├── device_catalog.py, research_runtime.py, environment.py
│   ├── api.py, version.py, README.md
│   └── .b34st-config
├── scripts/                     ← all operational scripts
│   ├── run_exploit.py, qemu_smoke.py, package_release.py
│   ├── doctor.py, release_gate.py, release_verify.py
│   ├── run_*.py, test_*.py, qemu_*.py, ...
│   └── install.sh, uninstall.sh, establish_persistence.sh
├── tests/                       ← SDK + operational test suite
│   ├── test_sdk_conformance.py, test_boot_image.py
│   ├── test_loader_simulator.py, test_qemu_boot.py
│   ├── test_deployment.py, test_hardware_bringup.py
│   ├── test_release_tools.py, test_research_runtime.py
│   ├── ... (30 C harnesses + 37 Python tests)
│   └── __pycache__/ (excluded)
├── docs/                        ← 46 curated documentation files
│   ├── ARCHITECTURE.md, EXPLOIT_CHAIN.md, QUICK_START.md
│   ├── A12_A13_IRECOVERY.md, A12_A13_HARDWARE_BRINGUP.md
│   ├── B34ST_DEVICE_WORKFLOW.md, B34ST_DESIGN.md, B34ST_TASKS.md
│   ├── KERNEL_PATCHING.md, SECURE_BOOT_BYPASS.md, PERSISTENCE.md
│   ├── LOADER_SDK.md, BINARY_HANDOFF.md, HANDOFF.md
│   ├── BRIDGE_PROTOCOL.md, HOST_PROTOCOL.md, DEPLOYMENT_PROTOCOL.md
│   ├── BOOT_IMAGE.md, PHYSICAL_VALIDATION_CANDIDATE.md
│   ├── THREAT_MODEL.md, PHYSICAL_HARDWARE_PROBE.md
│   ├── FIRST_STAGE_ADAPTER.md, PORTING.md, PORT_CERTIFICATION.md
│   ├── MODULE_FORMAT.md, FRAMEBUFFER_CONSOLE.md, CALLBACK_SAFETY.md
│   ├── BOARD_BRINGUP.md, HARDWARE_BRINGUP_CHECKLIST.md
│   ├── HARDWARE_DIAGNOSTICS.md, PLATFORM_SERVICES.md
│   ├── QEMU_GENERIC_LOADER.md, LOADER_CONFORMANCE.md
│   ├── LOADER_SIMULATOR.md, REAL_HARDWARE_ADAPTER.md
│   ├── MMIO.md, INTERRUPTS.md, BRINGUP_SHELL.md
│   ├── RUNTIME_ARCHITECTURE.md, RUNTIME_VALIDATION.md
│   ├── TRANSPORT_DEPLOYMENT.md, PROFILE_MATURITY.md
│   ├── BYTECODE.md, PHYSICAL_DEVICE_INTEGRATION.md
├── sdk/                         ← full SDK source distribution
│   ├── include/                 ← 7 public ABI headers
│   ├── src/                     ← library source (3 modules)
│   ├── examples/                ← 3 working loader examples
│   ├── templates/               ← 4 project templates
│   ├── tests/                   ← conformance test harness
│   ├── Makefile                 ← standalone SDK build
│   └── README.md                ← SDK documentation
├── linker/                      ← linker scripts
│   ├── qemu_virt.ld
│   └── generic_arm64.ld
├── profiles/                    ← board/recovery profiles
│   ├── qemu-virt-board.json, qemu-virt-deployment.json
│   ├── qemu-runtime-validation.json
│   ├── generic-arm64-board.json
│   ├── apple-a12-recovery.json, apple-a12x-recovery.json
│   └── apple-a13-recovery.json
├── modules/                     ← demo example modules
│   ├── hello/hello.c
│   └── dynamic_hello/module.json
├── build/                       ← QEMU virt monitor + simulations
│   ├── fbr34ker.bin, fbr34ker.elf, fbr34ker.map
│   ├── modules/hello-dynamic.fmod
│   ├── loader-simulation/       ← loader sim outputs
│   └── deployment-simulation/   ← deployment sim outputs
├── build-generic/               ← Generic ARM64 monitor
│   └── fbr34ker-generic.bin, .elf, .map
├── build-loader/                ← QEMU handoff loader
│   └── fbr34ker-qemu-loader.bin, .elf, .map
├── build-hardware-probe/        ← Hardware probe image
│   └── fbr34ker-hardware-probe.bin, .elf, .map
├── build-exploit/               ← Operational build (security model)
│   └── fbr34ker-operational.bin, .elf, .map
├── build-apple/                 ← A12/A13 boot images + simulations
│   ├── a12/boot.img, a12x/boot.img, a13/boot.img
│   ├── bringup-simulation/
│   ├── physical-integration-simulation/
│   └── physical-validation-candidate/
└── build-sdk/                   ← compiled SDK outputs
    ├── libfbr34ker_sdk.a        ← static library
    ├── examples/                ← compiled examples
    └── tests/                   ← compiled test harness
```

## 8. Troubleshooting

### Build failures

```
error: unknown target CPU 'apple-a12'
```
Ensure your LLVM is up to date: `brew upgrade llvm`.

```
fatal error: 'fbr34ker/sdk.h' file not found
```
The SDK uses its own include path. Use `make -C sdk` or `-Isdk/include`.

### QEMU issues

```
qemu-system-aarch64: command not found
```
Install QEMU: `brew install qemu` (macOS) or `apt install qemu-system-arm` (Linux).

```
KVM not supported on this host
```
QEMU will fall back to TCG emulation. This is slower but functional.

### Python issues

```
ModuleNotFoundError: No module named 'usb'
```
Install pyusb: `pip install pyusb`. This is only needed for device operations, not for building or QEMU.

```
ModuleNotFoundError: No module named 'b34st'
```
The B34ST module is part of the source tree. Ensure you are running from the project root.

### Runtime issues

```
jailbreak: no kernelcache found in DRAM
```
No kernelcache is loaded. On a real device, the exploit chain loads it via vendor MEM_WRITE. Under QEMU, this is expected.

```
Console disconnected — TransportError
```
Expected when the kernel boots — the kernel takes over the UART/USB console. The exploit framework handles this gracefully.

## 9. Further reading

| Document | Description |
|----------|-------------|
| `docs/ARCHITECTURE.md` | System architecture overview |
| `docs/EXPLOIT_CHAIN.md` | USBliter8 exploit chain design |
| `docs/LOADER_SDK.md` | SDK usage in detail |
| `docs/BINARY_HANDOFF.md` | Handoff ABI specification |
| `docs/HANDOFF.md` | Handoff protocol details |
| `docs/QEMU_GENERIC_LOADER.md` | QEMU loader details |
| `docs/PHYSICAL_VALIDATION_CANDIDATE.md` | Validation methodology |
| `docs/HARDWARE_BRINGUP_CHECKLIST.md` | Bring-up procedures |
| `docs/SECURE_BOOT_BYPASS.md` | Secure boot bypass state model |
| `docs/KERNEL_PATCHING.md` | Kernel patching state model |
| `docs/PERSISTENCE.md` | Persistence state model |
| `docs/B34ST_DEVICE_WORKFLOW.md` | Device dashboard and workflows |
| `docs/QUICK_START.md` | Quick reference |
| `sdk/README.md` | SDK documentation |
| `CHANGELOG.md` | Version history |
| `RELEASE_NOTES.md` | Release notes |
| `SECURITY.md` | Security boundary and policy |