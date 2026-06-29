# FBR34KER Tutorial — 0.4.4b Beta

## 1. Introduction

This tutorial walks through the complete FBR34KER 0.4.4b Beta workflow: toolchain setup, building all targets, running the monitor in QEMU, exercising the jailbreak security-bypass chain, launching the B34ST unified control panel, navigating the 16-category menu system, using the CVE database and exploit chain planner, performing forensic acquisition, running the evidence-gated research-runtime orchestrator, planning and validating research environments, managing sessions, using the loader SDK, creating release packages, and understanding the full boot chain integration. No physical Apple hardware is required for sections 1-6 and most of 7, 9, 10, 12-16, and 18-19 — everything up to the exploit chain runs under QEMU.

Key features covered include:
- Guided tethered downgrade with exact firmware selection and external adapter contracts
- Ramdisk maker/loader for deterministic FBRD bundle creation
- USBliter8 exploit chain for A12+ (T8015-T8112)
- Kernel patching with per-SoC offset tables
- Secure boot bypass subsystem
- Persistence deployment engine
- CVE database and exploit chain planning
- Forensic acquisition and evidence bundle verification
- SEP vulnerability research pipeline and fuzzing

## 2. Prerequisites and environment setup

### Required toolchain

| Dependency | macOS | Linux |
|---|---|---|
| Xcode CLT / LLVM/Clang | `xcode-select --install` | `apt install build-essential` |
| LLVM AArch64 target | `brew install llvm` | `apt install llvm` |
| QEMU system emulator | `brew install qemu` | `apt install qemu-system-arm` |
| Python 3.10+ | `brew install python` | `apt install python3` |
| pyusb (device ops only) | `pip install pyusb` | `pip install pyusb` |
| GNU Make | Included with Xcode CLT | `apt install make` |

Windows users should use WSL2 with USB passthrough for device operations.

### Verify your environment

```sh
./fbr34ker doctor
```

This checks for Clang, `ld.lld`, `llvm-objcopy`, `qemu-system-aarch64`, `make`, `pyusb`, `libusb`, and the chipset database. Output example:

```
FBR34KER 0.4.4b-beta — environment diagnostics
  [OK]   clang — found
  [OK]   ld.lld — found
  [OK]   llvm-objcopy — found
  [OK]   qemu-system-aarch64 — found
  [OK]   make — found
  [OK]   pyusb — found
  [OK]   libusb — found
  [OK]   chipset database — 8 SoCs registered
  [INFO] 0 devices connected
```

Address any `[MISSING]` items before proceeding.

## 3. Project structure

```
B34ST_0.4.4b_Beta/
├── TUTORIAL.md            ← this file
├── README.md              ← project overview
├── CHANGELOG.md           ← version history
├── LICENSE                ← license terms
├── SECURITY.md            ← security boundary and policy
├── RELEASE_NOTES.md       ← release notes
│
├── fbr34ker               ← main CLI entry point (Python)
├── b34stctl               ← B34ST control panel
├── b34stool.py            ← B34ST legacy multi-tool
├── Makefile               ← top-level build system
│
├── kernel/                ← monitor firmware source (EXCLUDED from public release)
│   ├── main.c             ← entry and lifecycle
│   ├── jailbreak.c        ← A12+ jailbreak chain implementation
│   ├── command.c          ← interactive shell and command dispatcher
│   ├── mmio.c             ← memory-mapped I/O abstraction
│   ├── usbliter8_exploit.c ← DWC3 USB exploit for A12+
│   ├── kernel_patches.c   ← kernel patch state machine
│   ├── secure_boot_bypass.c ← secure boot bypass state model
│   ├── persistence.c      ← persistence hook state model
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
│   ├── cve/               ← CVE database and exploit chain planner
│   │   ├── data/cve_database.json  ← 1155 CVE records
│   │   ├── cve_db.py               ← CVE database engine
│   │   ├── exploit_chain.py         ← chain planner
│   │   └── devices.py              ← device/SoC database
│   └── forensics/         ← forensic acquisition framework
├── sdk/                   ← standalone loader SDK
│   ├── include/           ← 7 public ABI headers
│   ├── src/               ← library source (3 modules)
│   ├── examples/          ← working loader examples
│   ├── templates/         ← project templates
│   └── tests/             ← conformance test harness
├── scripts/               ← build, release, and operational scripts
│   ├── B34ST              ← unified control panel launcher
│   ├── run_exploit.py     ← exploit chain orchestrator
│   ├── doctor.py          ← diagnostics harness
│   └── ...
├── b34st/                 ← B34ST research runtime framework
│   ├── engine.py          ← CLI engine with all command routing
│   ├── research_runtime.py ← evidence-gated orchestrator (16 stages)
│   ├── environment.py     ← research environment planning
│   ├── forensics.py       ← data acquisition CLI
│   ├── control_panel.py   ← interactive menu system
│   ├── build.py           ← build orchestration
│   └── ...
├── docs/                  ← 46 documentation files
├── linker/                ← linker scripts per platform
├── profiles/              ← device recovery profiles (A12/A13/QEMU)
├── tests/                 ← native and Python test suites
├── modules/               ← example FMOD dynamic modules
│
├── build/                 ← build output directories
├── build-generic/
├── build-hardware-probe/
├── build-loader/
├── build-sdk/
├── build-apple/
├── build-exploit/
└── dist/                  ← release packages
```

### Build output directories

| Directory | Purpose |
|---|---|
| `build/` | QEMU virt target (`fbr34ker.bin`, `fbr34ker.elf`) |
| `build-generic/` | Generic ARM64 monitor |
| `build-hardware-probe/` | Hardware probe image (read-only) |
| `build-loader/` | QEMU handoff loader |
| `build-sdk/` | SDK static library + examples |
| `build-apple/` | Apple A12/A13 boot images + simulations |
| `build-exploit/` | Operational (security-model-enabled) build |
| `dist/` | Release packages |

## 4. Building everything

### Quick build

```sh
./fbr34ker build
```

This builds 13 targets across all platforms. Equivalent to running all of these:

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

### Selective builds

```sh
make all                          # QEMU virt only (fastest)
make build-operational            # security-model-enabled build
make apple-boot-images            # Apple recovery boot images
make sdk                          # loader SDK only
make generic                      # generic ARM64 monitor only
```

### Build with security model

The `build-operational` target enables the security model (memory writes):

```sh
make build-operational
# or via CLI:
./fbr34ker build --security-model
```

This produces `build-exploit/fbr34ker-operational.bin`, which is required for the exploit chain and jailbreak boot on physical devices. In default builds, mutation paths (kernel-patches apply, secure-boot-bypass activate, etc.) return failure — they are read-only state models.

## 5. Running in QEMU

### Start the monitor

```sh
./fbr34ker run direct
```

This boots `build/fbr34ker.bin` under QEMU virt. You will see the monitor's boot banner, initialization logs, and finally the shell prompt:

```
FBR34KER 0.4.4b (beta)
Target: qemu_virt; source: 0.4.4b-beta
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
|---|---|
| `help` | List commands or show usage |
| `version` | Build version info |
| `jailbreak` | A12+ jailbreak chain |
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

## 6. B34ST unified control panel

### Launching B34ST

```sh
./scripts/B34ST
```

This launches the B34ST interactive menu system. The initial screen shows the 15-category menu:

```
FBR34KER B34ST v0.4.4b — Unified Multi-Tool Control Panel

 1.  System           6.  Deployment      11.  Module
 2.  Device           7.  Hardware        12.  Research Runtime
 3.  USBliter8        8.  Session         13.  Frontier
 4.  IPSW             9.  Validation      14.  B34ST
 5.  Boot Image      10.  Release         15.  Forensics

Select category (1-15, q quit, h help):
```

### Session logging

Every operation in B34ST is logged to:

```
runtime-artifacts/b34st/b34stool/YYYYMMDD-HHMMSS-microseconds/
```

Each session directory contains:
- `session.log` — full command transcript
- `evidence/*.json` — structured operation results with timestamps, exit codes, and duration tracking

### Interactive vs non-interactive mode

Interactive mode (default):

```sh
./scripts/B34ST
# or
./fbr34ker b34stool
```

Non-interactive mode (for automation):

```sh
./fbr34ker b34st --command <category> --args <subcommand> [options]
```

### Example: run a build via B34ST

```sh
./scripts/B34ST
# Select 1 (System) → 2 (Build all targets)
```

Check version:

```sh
./fbr34ker version
# → FBR34KER 0.4.4b-beta
```

## 7. The jailbreak command walkthrough

The `jailbreak` command drives the A12+ security bypass and kernel boot chain. It is available in any build variant.

### Status

```sh
fbr34ker> jailbreak
```

Shows the current jailbreak state, security model status, bypass counts, kernel detection info, and SEP availability. Expected output (QEMU):

```
Jailbreak state:
  status: MODEL_READY
  security_model: PENDING
  bypasses: 0/3 active
  kernel: none
  sep: none
  boot_args: none
```

### Security model

```sh
fbr34ker> jailbreak security-model on
fbr34ker> jailbreak security-model off
```

Enable or disable the security model. When active, memory-write operations (e.g. boot-args injection) take effect immediately. In "pending" mode, operations are staged but not committed.

Output:

```
security-model: on — memory writes active
# or
security-model: off — read-only state model
```

### Security bypasses

```sh
fbr34ker> jailbreak bypass-pac       # Disable pointer authentication
fbr34ker> jailbreak bypass-aprr      # Bypass APRR/PPL memory protections
fbr34ker> jailbreak bypass-wxn       # Clear W^X enforcement
fbr34ker> jailbreak bypass-all       # All three at once
```

Output for each:

```
PAC bypass: active — SCTLR_EL1.EnIA/EnIB cleared
APRR bypass: active — TCR_EL1 NFD0/NFD1 set
WXN bypass: active — SCTLR_EL1.WXN cleared
```

### Kernel detection

```sh
fbr34ker> jailbreak detect-kernel                    # Auto-scan DRAM
fbr34ker> jailbreak detect-kernel --path <phys> [size] # Specify location
```

Scans DRAM for a kernelcache (Mach-O fat binary with `LC_MAIN` command). On QEMU no kernelcache is present, so this will report:

```
kernel detection: no kernelcache found in DRAM range [0x800000000 - 0x900000000]
```

This is expected. On a real device after the exploit chain, the kernelcache resides at `0x800000000`+ (A12+) or can be loaded via vendor MEM_WRITE.

### KASLR detection

```sh
fbr34ker> jailbreak detect-kaslr [phys [size]]
```

Reads the first `LC_SEGMENT_64` command's `vmaddr` to compute the KASLR slide. Tries both iOS 16 (`0xFFFFFFF007000000`) and iOS 17+ (`0xFFFFFFF007800000`) kernel bases.

Output on QEMU:

```
KASLR detection: no kernelcache found — KASLR slide unknown
```

On a real device:

```
KASLR slide: 0xBC4000 — kernel base: 0xFFFFFFF007804000 + 0xBC4000 = 0xFFFFFFF0083C4000
```

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

Output:

```
boot-args injection: scanning for boot-args region
  magic 0xBA696F53 found at offset 0x1234
  injected 86 bytes at 0xFFFFFFF0083C0000 + 0x1234
  new boot-args: -s amfi_get_out_of_my_way=1 cs_enforcement_disable=1 keepsyms=1 debug=0x2014 wdt=0
```

### SEP detection

```sh
fbr34ker> jailbreak detect-sep [base]
```

Probes the SEP MMIO region. Default base: `0x82E000000` (A13), then `0x82D000000` (A12/A12X). On QEMU:

```
SEP detection: no SEP MMIO region detected at 0x82E000000 or 0x82D000000
```

On a real device:

```
SEP detected at 0x82E000000 (A13) — alive and responding
```

### Full chain

```sh
fbr34ker> jailbreak chain-all
```

Runs the complete chain: security bypasses → MMU enable → kernel detection → boot-args → SEP detection → ready to boot. Output:

```
chain-all: starting full jailbreak chain
  bypass-all: OK (PAC, APRR, WXN)
  MMU re-initialized
  kernel detection: OK (kernelcache at 0x812000000)
  boot-args injected: OK
  SEP detected: OK at 0x82E000000
chain-all: complete — ready to boot kernel
```

### Boot kernel

```sh
fbr34ker> jailbreak boot-kernel [entry]
```

Disables the MMU (clears `SCTLR_EL1.M` and `SCTLR_EL1.WXN`), performs a DSB+ISB barrier, and jumps to the kernel entry point with boot-args pointer in `x1` (iOS 17+ compatibility). On a real device, the console disconnects as the kernel takes over. In QEMU without a loaded kernel, this will fault:

```
boot-kernel: disabling MMU and jumping to 0xFFFFFFF0083C4000
  SCTLR_EL1.M cleared (cache+MMU off)
  x0 = 0xFFFFFFF0083C4000 (entry)
  x1 = 0xFFFFFFF0083C0000 (boot-args)
  DSB+ISB complete — jumping...
  [QEMU fault — no kernel loaded]
```

This is expected under QEMU.

## 8. USBliter8 exploit chain walkthrough

> This section describes the full exploit chain for physical devices. The
> public operational release excludes `kernel/`, `arch/`, and `platform/`
> firmware source, while retaining the public `host/` runtime required by the
> packaged CLI. Pre-built firmware images in `build-*` contain the compiled
> monitor.

### Hardware guide

Before attempting the exploit, review `docs/USBLITER8_HARDWARE_GUIDE.md` for
recommended hardware (the **Waveshare RP2350 USB-A** is strongly recommended),
cable selection, power considerations, and troubleshooting. B34ST's USBliter8
workflow (`b34st usbliter8`) includes a guided hardware preparation step that
can be skipped if already completed.

### The complete A12+ exploit flow

```
DFU mode
  └─ DWC3 USB controller firmware exploit (USBliter8)
       └─ PWNDFU — vendor SET_ADDR/MEM_READ/MEM_WRITE/EXECUTE active
            └─ Write FBR34KER monitor binary to physical DRAM via MEM_WRITE
                 └─ Execute monitor via EXECUTE — FBR34KER boots
                      └─ CDC ACM console connects
                           └─ Jailbreak chain (bypass-all, detect-kernel, inject-bootargs, detect-sep)
                                └─ Boot kernel — console disconnects
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

### Step-by-step with fbr34ker

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
- **SoC-specific patch words** — A12/A13/A14/A12Z/M1/A15/M2 each require different DWC3 firmware patch sequences (6-8 words each)

### USB device model

After the exploit, FBR34KER presents as a composite USB device (VID 0x05AC, PID 0x1227):

| Interface | Class | Description |
|---|---|---|
| 0 | CDC ACM (0x02/0x02/0x01) | Serial console (control) |
| 1 | CDC Data (0x0A/0x00/0x00) | Serial console (data) |
| 2 | DFU (0xFE/0x01/0x02) | Firmware upload (control) |

### Vendor-specific requests (after DWC3 exploit)

| bRequest | Name | Direction | Data stage |
|---|---|---|---|
| 0x01 | SET_ADDR | OUT | 8-byte target address (LE) |
| 0x02 | MEM_READ | IN | Returns wLength bytes from target |
| 0x03 | MEM_WRITE | OUT | Writes data to target |
| 0x04 | EXECUTE | OUT | Jumps to target (no data) |

## 9. Kernel patching subsystem

### Overview

The kernel patching subsystem provides per-SoC kernel patch offset tables for Apple A12/A13/A14/A12Z/A15/M1/M2 across iOS 16 and iOS 17+. It supports registration, application, reversion, and privilege escalation operations.

### Supported SoCs and offsets

| SoC | Target | iOS versions | Patch types |
|---|---|---|---|
| T8015 | A12 | 16, 17+ | 8 patches |
| T8020 | A13 | 16, 17+ | 8 patches |
| T8030 | A14 | 16, 17+ | 8 patches |
| T8028 | A12Z | 16, 17+ | 8 patches |
| T8103 | M1 | 16, 17+ | 8 patches |
| T8110 | A15 | 16, 17+ | 8 patches |
| T8112 | M2 | 16, 17+ | 8 patches |

The 8 patch types are: `amfi`, `task_for_pid`, `privilege`, `mount_root`, `codesign`, `sandbox`, `pe_debugger`, `cs_enforcement`.

### Shell commands

```
fbr34ker> kernel-patches status
fbr34ker> kernel-patches apply
fbr34ker> kernel-patches revert
fbr34ker> kernel-patches escalate
```

#### status

In a default build:

```
Kernel-patches state:
  build: release (security model: disabled)
  SoC target: qemu_virt
  patches registered: 8
    amfi:            pending
    task_for_pid:    pending
    privilege:       pending
    mount_root:      pending
    codesign:        pending
    sandbox:         pending
    pe_debugger:     pending
    cs_enforcement:  pending
  mutation: DISABLED (release build)
```

#### apply (operational build only)

```
kernel-patches: applying 8 patches
  amfi:            APPLIED
  task_for_pid:    APPLIED
  privilege:       APPLIED
  mount_root:      APPLIED
  codesign:        APPLIED
  sandbox:         APPLIED
  pe_debugger:     APPLIED
  cs_enforcement:  APPLIED
  event: kernel-patch-apply published
```

#### escalate (operational build only)

```
kernel-patches: escalating privileges via privilege_offset
  privilege: ESCALATED
  event: kernel-patch-escalate published
```

#### revert (operational build only)

```
kernel-patches: reverting all applied patches
  amfi:            REVERTED
  task_for_pid:    REVERTED
  privilege:       REVERTED
  ...
  event: kernel-patch-revert published
```

### Build mode behavior

| Build | kernel-patches apply/revert/escalate |
|---|---|
| `make all` | Returns failure (read-only state model) |
| `make build-operational` | Performs full state transitions |

## 10. Secure boot bypass and persistence

### Secure boot bypass

The secure boot bypass subsystem provides six bypass types for modeling Apple secure boot policy evasion.

#### Bypass types

| Type | Description |
|---|---|
| `image4-sig` | Image4 signature verification bypass |
| `cert-chain` | Certificate chain validation bypass |
| `ap-ticket` | APTicket validation bypass |
| `shsh-blob` | SHSH blob verification bypass |
| `iboot-auth` | iBoot authentication bypass |
| `boot-manifest` | Boot manifest validation bypass |

#### Shell commands

```sh
fbr34ker> secure-boot-bypass status
```

Output (release build):

```
Secure boot bypass state:
  build: release (security model: disabled)
  image4-sig:     disabled
  cert-chain:     disabled
  ap-ticket:      disabled
  shsh-blob:      disabled
  iboot-auth:     disabled
  boot-manifest:  disabled
  mutation: DISABLED (release build)
```

```sh
fbr34ker> secure-boot-bypass activate image4-sig
fbr34ker> secure-boot-bypass forgive image4-sig
fbr34ker> secure-boot-bypass manifest
```

`manifest` shows the full boot manifest state:

```
Boot manifest state:
  image4-sig:     enabled
  cert-chain:     disabled
  ap-ticket:      disabled
  shsh-blob:      disabled
  iboot-auth:     enabled
  boot-manifest:  disabled
```

### Persistence

The persistence subsystem provides eight hook types for modeling post-exploit persistence deployment. Maximum hidden storage: 64KB.

#### Hook types

| Type | Description |
|---|---|
| `boot-hook` | Boot-time execution hook |
| `launchd-plist` | Launchd property list persistence |
| `kext` | Kernel extension loading |
| `hidden-storage` | Concealed storage allocation |
| `payload-deploy` | Payload deployment mechanism |
| `tamper-resist` | Tamper detection resistance |
| `ota-persist` | OTA update survivability |
| `evasion` | Detection evasion |

#### Shell commands

```sh
fbr34ker> persistence status
```

Output:

```
Persistence state:
  capacity: 16 hooks (max), 64 KB hidden storage
  hooks registered: 0
  active: 0
  mutation: DISABLED (release build)
```

In an operational build:

```sh
fbr34ker> persistence deploy boot-hook
fbr34ker> persistence deploy launchd-plist
fbr34ker> persistence activate
fbr34ker> persistence evade
```

## 11. Device dashboard and connected-device workflow

### Launching the dashboard

```sh
./scripts/B34ST
```

B34ST automatically inspects any connected device and displays the dashboard.

### Dashboard fields

When a device is connected, the dashboard shows:

- Device name and product identifier (e.g., "iPhone12,1")
- Connection mode (DFU / recovery / normal)
- Board model
- Current firmware and build (from lockdownd in normal mode, labelled "unavailable" in DFU/recovery)
- Latest signed firmware from the configured IPSW catalog
- Matching exact recovery profiles
- Available actions and why blocked actions are unavailable

### Available actions

Every device action opens a preparation page containing:

1. Availability and the device-specific reason
2. Required hardware, software, storage, backup, and authorization materials
3. The complete operational sequence
4. A how-to-proceed note
5. An explicit confirmation before execution

#### Upgrade

```sh
# Within B34ST: select Device → Upgrade
```

B34ST runs an `idevicerestore --no-action` preflight before offering execution. A data-preserving update is requested by default.

#### Erase restore

```sh
# Within B34ST: select Device → Erase Restore
```

Adds `idevicerestore --erase`. Backups and Find My requirements are shown before execution.

#### Tethered downgrade

```sh
# Within B34ST: select the device action → Guided tethered downgrade
```

The guided flow accepts a local IPSW or an Apple catalog download, validates
the exact target and SHA-256, preflights the separately installed external
adapter, saves a plan, and only then offers execution. Without an adapter it
stops safely after planning. A tethered runtime is not persistent—the external
boot chain must run again after every restart. The adapter is a separately
installed target-specific executable or reviewed wrapper that performs the
DFU/recovery boot sequence; it is not the IPSW, cable, or `idevicerestore`. See
`docs/TETHERED_DOWNGRADE.md`.

#### Ramdisk maker and loader

```sh
# Within B34ST: select Ramdisk maker and loader → Guided maker / loader
./fbr34ker ramdisk guide
```

The guide supports every exact-profile A12–A15/M1–M2 iPhone, iPad, and Apple
silicon Mac product listed by `ramdisk list-targets`. It records the exact
iOS/iPadOS/macOS version and build, packages prepared components into a
deterministic `.fbrd`, verifies all hashes, and stops at a plan-only load by
default. Physical loading requires a separately installed target/build-specific
adapter. See `docs/RAMDISK_MAKER_LOADER.md`.

#### Failure and return behavior

B34ST guarantees:
- No hidden fallback from signed restore to unsigned restore
- No target-changing operation without confirmation
- External exit status is captured
- Logs remain in the B34ST session directory
- Control always returns to B34ST after the external process exits

## 12. IPSW firmware workflows

### Catalog browsing

```sh
./fbr34ker ipsw catalog --product iPhone12,1
```

This queries the configured IPSW catalog for the given product and returns all available firmware versions with their signing status:

```
IPSW catalog for iPhone12,1:
  17.6.1 (21G93)         — signed
  17.6   (21G115)        — signed
  17.5.1 (21F91)         — signed
  17.5   (21F84)         — unsigned
  17.4.1 (21D61)         — unsigned
  ...
  17.0   (21A328)        — unsigned
```

### Downloading

```sh
./fbr34ker ipsw download --product iPhone12,1 --version 17.6.1
```

Downloads the IPSW from Apple's HTTPS servers. Progress is shown:

```
Downloading iPhone12,1_17.6.1_21G93_Restore.ipsw...
  [====================] 100% (6.2 GB / 6.2 GB)
  SHA-256: a1b2c3d4...
  Saved to: downloads/iPhone12,1_17.6.1_21G93_Restore.ipsw
```

### Upgrade

```sh
./fbr34ker ipsw upgrade --product iPhone12,1 --ipsw path/to/file.ipsw
```

Requires `idevicerestore`. B34ST runs a preflight check first, then performs the data-preserving update.

### Tethered downgrade

```sh
./fbr34ker ipsw tethered-downgrade-guide
```

The guide creates a validated plan and optionally invokes a reviewed external
tether adapter. B34ST does not bundle that target-specific adapter. After
every restart, the external boot chain must be re-run.

### Ramdisk bundles

```sh
./fbr34ker ramdisk list-targets
./fbr34ker ramdisk plan \
  --product iPhone12,1 --os-version 18.5 --build 22F76
./fbr34ker ramdisk build \
  --product iPhone12,1 --os-version 18.5 --build 22F76 \
  --ramdisk ramdisk.dmg --kernelcache kernelcache \
  --devicetree DeviceTree.dtb --output target.fbrd
./fbr34ker ramdisk inspect target.fbrd
./fbr34ker ramdisk load target.fbrd --evidence ramdisk-plan.json
```

The final operation is plan-only unless `--execute`, both exact authorization
phrases, and a reviewed external adapter are supplied. See
`docs/RAMDISK_MAKER_LOADER.md`.

## 13. CVE database and exploit chain planner

### Overview

FBR34KER ships a CVE database (`host/cve/data/cve_database.json`) with 1,155 vulnerability records covering Apple iOS, iPadOS, macOS, and associated components. The database supports device-aware exploit chain planning, goal suggestion, and fuzz target enumeration.

### Database statistics

```sh
B34ST cve stats
```

```json
{
  "total_cves": 1155,
  "critical": 312,
  "high": 485,
  "medium": 281,
  "low": 77,
  "with_exploit": 298,
  "ios_versions_covered": [
    "13.0", "13.1", ..., "14.0", ..., "15.0", ..., "16.0", ..., "17.0", "17.1", "17.2"
  ],
  "components": ["Kernel", "WebKit", "WiFi", "Bluetooth", "ImageIO", ...],
  "exploit_types": ["UAF", "OOB", "Type confusion", "Integer overflow", ...]
}
```

### Search CVEs

```sh
B34ST cve search CVE-2023-28204
```

```
Found 1 CVE matching 'CVE-2023-28204':
  CVE-2023-28204 | critical | WebKit memory corruption leading to arbitrary code execution
```

### Query by iOS version

```sh
B34ST cve query 17.0
```

```
CVEs affecting iOS 17.0: 42

  [✓] CVE-2023-32373     critical  Kernel           Memory corruption in XNU
  [✓] CVE-2023-32429     high      IOMobileFrame... Use-after-free
  [ ] CVE-2023-32439     critical  WebKit           Type confusion
  ...
```

`[✓]` indicates a public exploit is available.

### Chain planning

```sh
B34ST cve chain jailbreak 17.0
```

```
Exploit chains for goal 'jailbreak' on iOS 17.0:

  Chain #1 [PARTIAL (57%)] — moderate, ~48-60%
    Step 1: CVE-2023-32373     [Kernel]          ✓  Memory corruption in XNU
    Step 2: CVE-2023-32429     [IOMobileFram...] ✓  Use-after-free in IOMobileFrameBuffer
    Step 3: CVE-2023-32439     [WebKit]             Type confusion in WebKit
    → Provides: memory-access, kernel-rw, code-execution

  Chain #2 [COMPLETE] — hard, ~35-45%
    Step 1: CVE-2023-32373     [Kernel]          ✓  Memory corruption in XNU
    Step 2: CVE-2023-41991     [AppleAVD]        ✓  OOB write in AppleAVD
    Step 3: CVE-2023-42853     [Sandbox]            Sandbox escape
    → Provides: memory-access, kernel-rw, code-execution, sandbox-escape
```

### Device-aware chain planning

```sh
B34ST cve device-chain jailbreak 17.0 iPhone12,1
```

This produces a chain filtered to CVEs that affect A13 (iPhone12,1's SoC).

### List built-in goals

```sh
B34ST cve goals
```

```
Built-in exploit goals:

  jailbreak               Full kernel jailbreak chain
                          requires: kernel-rw, code-execution, pac-bypass
                          difficulty: hard

  sandbox-escape          Break out of iOS sandbox
                          requires: memory-access
                          difficulty: medium

  boot-persist            Achieve boot-persistent code execution
                          requires: kernel-rw, code-execution, persistent-storage
                          difficulty: very-hard
  ...
```

### Suggest achievable goals for a version

```sh
B34ST cve suggest 17.0
```

### Fuzz targets

```sh
B34ST cve fuzz list
```

## 14. Forensics acquisition

### Standard evidence acquisition

```sh
B34ST forensics acquire
```

Guided interactive acquisition:

```
B34ST guided forensic acquisition
Type "I OWN OR AM AUTHORIZED TO FORENSICALLY ACQUIRE FROM THIS DEVICE" to continue

Available acquisition profiles:
  quick           Quick evidence collection
  full            Full forensic acquisition
  memory-only     RAM and volatile data
  storage-only    Storage partition dump
  filesystem-only Live filesystem snapshot
  network-only    Network state and connections

Acquisition profile [quick]: full
Device ID: iPhone12,1
Operator name: researcher
Product: iPhone12,1
Model: D321AP
iOS version: 17.6.1
Chipset: T8020
Device mode: normal

Acquisition session: runtime-artifacts/b34st/forensics/20240915-142230-123456
Operations: 47
Passed: 47
Failed: 0
```

### Secrets extraction

```sh
B34ST forensics secrets
```

### Activation bypass and FMI

```sh
B34ST forensics activation
```

### Passcode operations

```sh
B34ST forensics passcode
```

All forensics operations produce evidence bundles with chain-of-custody logging:

```sh
B34ST forensics acquire --profile full --bundle evidence-bundle.zip
```

Verify a bundle:

```sh
B34ST forensics verify evidence-bundle.zip
```

## 15. Research runtime orchestrator

### Overview

The research runtime orchestrator implements an evidence-gated approach. It does not generate exploit payloads, kernel patches, or bootstrap installers — those remain external inputs that must provide machine-readable evidence before the 16-stage state machine advances.

### Guided mode

```sh
B34ST research-runtime guided
```

This runs the interactive orchestrator. Here is the full flow:

```
B34ST guided research-runtime orchestrator
Evidence directory: runtime-artifacts/b34st/research-runtime/20240915-143000-123456

Type "I OWN OR AM AUTHORIZED TO TEST THIS DEVICE" to continue
```

### The 16-stage state machine

The orchestrator advances through these ordered stages:

```
 1. HOST_READY                 ← Diagnostics pass (scripts/doctor.py)
 2. TARGET_PROFILE_VALIDATED   ← Profile matches device info
 3. KERNEL_IDENTIFIED          ← Kernel identity manifest reviewed and approved
 4. MONITOR_IMAGE_VALIDATED    ← Boot image profile matches
 5. MONITOR_RUNTIME            ← First-stage adapter runs monitor in RAM
 6. SAFE_RESET_VERIFIED        ← Reset invalidates authorization
 7. KERNEL_PATCH_ATTEMPTED     ← External evidence required
 8. KERNEL_PATCH_VERIFIED      ← External evidence required
 9. CODE_SIGNING_POLICY_VERIFIED ← External evidence required
10. TRUST_CACHE_ACCEPTED       ← External evidence required
11. WRITABLE_RESEARCH_ENVIRONMENT ← External evidence required
12. BOOTSTRAP_VERIFIED         ← Bootstrap archive SHA-256 verified
13. BOOTSTRAP_ACTIVE           ← External evidence required
14. USERSPACE_SHELL_RESPONDING ← External evidence required
15. RESEARCH_RUNTIME_READY     ← All requirements verified
16. JAILBREAK_ATTESTED         ← Operator attestation signed
```

### What it verifies at each stage

Each stage has specific evidence requirements. Stages 7-14 marked as "External evidence required" need a JSON evidence file conforming to `schema_version: 1` with the correct `stage` field, `status: "verified"`, matching kernelcache SHA-256, and non-empty observations. Stages 8-9 additionally require `rollback.available: true`.

The orchestrator generates evidence templates:

```
Evidence templates written to:
  runtime-artifacts/b34st/research-runtime/.../evidence-templates/
    kernel_patch_attempted.json
    kernel_patch_verified.json
    code_signing_policy_verified.json
    trust_cache_accepted.json
    writable_research_environment.json
    bootstrap_active.json
    userspace_shell_responding.json
```

### Legacy component audit

The orchestrator audits existing in-tree components:

```
Legacy component audit:
  kernel/kernel_patches.c:          UNVERIFIED_MUTATION_MODEL
  kernel/secure_boot_bypass.c:      UNVERIFIED_STATE_MODEL
  kernel/persistence.c:             IN_MEMORY_MODEL
  kernel/usbliter8_exploit.c:       UNVERIFIED_TARGET_MODEL
  scripts/run_exploit.py:           LEGACY_ORCHESTRATOR
  Result: external-reviewed-adapters-required
  Accepted as runtime evidence: false
```

This means the built-in models are not accepted as runtime evidence — external, independently-reviewed adapters are required.

### Final attestation

When all requirements are met, the orchestrator creates a jailbreak attestation:

```
Create final operator attestation for this evidence set (y/N): y
Operator name: researcher

Attestation written to:
  runtime-artifacts/b34st/research-runtime/.../jailbreak-attestation.json
Runtime state: runtime-artifacts/b34st/research-runtime/.../runtime-state.json
```

## 16. Environment planning

### Plan an iOS 17+ research environment

```sh
B34ST environment-plan --version 17.6 --product iPhone12,1 --mode research-runtime
```

This generates a bounded environment manifest:

```json
{
  "schema_version": 1,
  "kind": "b34st-ios-research-environment",
  "target": {
    "os": "iOS",
    "version": "17.6.0",
    "product": "iPhone12,1",
    "family": "iPhone",
    "generation": 12,
    "profile_candidates": ["profiles/apple-a13-recovery.json"]
  },
  "mode": "research-runtime",
  "owner_authorized": true,
  "requested_capabilities": ["kernel-patching", "secure-boot-bypass"],
  "provided_capabilities": ["activation-bypass", "kernel-patching", ...],
  "security_boundary": {
    "kernel_patching_included": true,
    "signature_bypass_included": true,
    ...
  },
  "readiness": {
    "plan_valid": true,
    "simulation_ready": false,
    "physical_execution_ready": false,
    "blockers": [
      "A reviewed first-stage adapter must already exist.",
      "The target must accept the research runtime through an authorized path.",
      "B34ST does not provide an exploit or bypass stock Apple secure boot.",
      "Kernel patch offsets must be validated for the exact iOS build.",
      "Kernel memory write access must be established via tfp0 or an equivalent."
    ]
  }
}
```

The `--capabilities` flag controls which capabilities are requested:

```sh
B34ST environment-plan --version 17.6 --product iPhone12,1 --mode research-runtime \
  --capabilities kernel-patching --capabilities secure-boot-bypass
```

Simulation mode (no blockers):

```sh
B34ST environment-plan --version 17.6 --product iPhone12,1 --mode simulation
```

### Validate an environment manifest

```sh
B34ST environment-validate --plan generated-plan.json
```

Returns any validation errors or confirms validity.

## 17. Session management

### Validate a session bundle

```sh
B34ST validate-session --bundle path/to/session.zip
```

This runs FBR34KER's session validation against an existing session bundle, checking evidence integrity and profile consistency.

### Candidate report generation

```sh
B34ST physical-validation candidate-report \
  --success build-apple/physical-validation-candidate/success-session.zip \
  --failure build-apple/physical-validation-candidate/failure-session.zip \
  --recovered build-apple/physical-validation-candidate/recovered-session.zip \
  --qemu-summary build-apple/physical-validation-candidate/qemu-summary.json \
  --output report.json
```

The candidate report evaluates whether the validation candidate meets all requirements:

```
Candidate report:
  candidate_ready: true
  physical_validation_complete: false (requires physical-runtime evidence)
  success: verified (bridge-backed)
  failure: verified (bridge-backed)
  recovered: verified (bridge-backed)
  qemu: verified
```

### Hardware preparation

```sh
B34ST hardware-prepare --list-categories
```

Lists available hardware preparation categories (console, board-inventory, memory-map, timer, interrupts, watchdog, boot-evidence).

Generate detailed checklists:

```sh
B34ST hardware-prepare --save-checklists ./checklists/
```

Validate an existing hardware preparation bundle:

```sh
B34ST hardware-prepare --validate-bundle bundle.zip
```

## 18. SDK overview

The FBR34KER SDK provides a standalone, freestanding C11 library for constructing and validating handoff ABI v4 structures. It has no dependencies on monitor internals or any operating system.

### Building the SDK

```sh
make -C sdk                    # builds libfbr34ker_sdk.a
make -C sdk test               # runs conformance tests
```

### SDK contents

```
sdk/
├── include/
│   ├── fbr34ker_sdk.h
│   ├── fbr34ker_boot_image.h
│   ├── fbr34ker_handoff.h
│   ├── fbr34ker_modules.h
│   ├── fbr34ker_services.h
│   ├── fbr34ker_memory.h
│   └── fbr34ker_bridge_protocol.h
├── src/
│   ├── handoff_builder.c
│   ├── handoff_validate.c
│   └── profile_match.c
├── examples/
│   ├── minimal_loader/       ← minimal freestanding loader
│   ├── callback_console/     ← callback-based console example
│   └── framebuffer_loader/   ← framebuffer output example
├── templates/
│   ├── module/              ← FMOD module template
│   ├── driver/              ← platform driver template
│   ├── board/               ← board support template
│   └── transport/           ← transport layer template
└── tests/
    └── sdk_harness.c        ← conformance test harness
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

See `sdk/examples/` for complete working examples including callback_console and framebuffer_loader.

## 19. Release packaging

### Public operational release (recommended)

```sh
make sdk-release
```

Produces a clean public release archive in `dist/` containing everything needed to make the toolchain fully operational — B34ST research runtime, all build artifacts, scripts, tests, SDK, linker scripts, board profiles, demo modules, curated documentation, and tutorial — but **no private kernel/exploit/host source code**.

| Archive | Contents |
|---|---|
| `B34ST_0.4.4b_Beta_operational.zip` | Public release — no private code |

### Internal full-source release

```sh
make manifest       # Build all targets + generate manifest + checksums
make verify         # Run non-QEMU verification suite
make release-gate   # Full release gate (requires QEMU)
make package
```

Produces three archives in `dist/`:

| Archive | Contents |
|---|---|
| `B34ST_0.4.4b_Beta_source.zip` | All source code, docs, scripts (excludes build artifacts) |
| `B34ST_0.4.4b_Beta_operational.zip` | Source + operational artifacts — public release |
| `B34ST_0.4.4b_Beta_complete.zip` | Source + all build artifacts, SDK, boot images, simulations |

Each archive has a corresponding `.sha256` checksum file.

### Archive contents

The operational release contains:

```
B34ST_0.4.4b_Beta/
├── TUTORIAL.md
├── README.md, CHANGELOG.md, LICENSE, SECURITY.md, RELEASE_NOTES.md
├── fbr34ker, b34stctl, b34stool.py
├── b34st/                     ← full B34ST research runtime framework
│   ├── b34st.py, engine.py, build.py, control_panel.py
│   ├── research_runtime.py, environment.py, forensics.py
│   ├── device_catalog.py, api.py, version.py
│   └── .b34st-config
├── scripts/                   ← all operational scripts
│   ├── run_exploit.py, qemu_smoke.py, package_release.py
│   ├── doctor.py, release_gate.py, release_verify.py
│   ├── install.sh, uninstall.sh, establish_persistence.sh
│   └── ...
├── tests/                     ← SDK + operational test suite
├── docs/                      ← 46 curated documentation files
├── sdk/                       ← full SDK source distribution
├── linker/                    ← linker scripts
├── profiles/                  ← board/recovery profiles
├── modules/                   ← example FMOD modules
├── build/                     ← QEMU virt monitor + simulations
├── build-generic/             ← generic ARM64 monitor
├── build-loader/              ← QEMU handoff loader
├── build-hardware-probe/      ← hardware probe image
├── build-exploit/             ← operational build
├── build-apple/               ← A12/A13 boot images + simulations
└── build-sdk/                 ← compiled SDK outputs
```

## 20. Full boot chain integration

The complete end-to-end boot chain from DFU to SSH ramdisk:

```
 DFU mode
   │
   ├─ Stage 1: USBliter8 DWC3 exploit ─────────────────────── in-tree
   │    /kernel/usbliter8_exploit.c
   │    SoC-specific DWC3 firmware patch words
   │    Result: PWNDFU — vendor SET_ADDR/MEM_READ/MEM_WRITE/EXECUTE active
   │
   ├─ Stage 2: Monitor bootstrap ───────────────────────────── in-tree
   │    FBR34KER via vendor EXECUTE (physical DRAM load)
   │    Result: monitor boots, CDC ACM + DFU composite device
   │
   ├─ Stage 3: Boot policy bypass ──────────────────────────── in-tree
   │    secure-boot-bypass engine (image4-sig, cert-chain, etc.)
   │
   ├─ Stage 4: Kernel patches ──────────────────────────────── in-tree
   │    kernel-patches engine (8 patch types, per-SoC offsets)
   │
   ├─ Stage 5: iBSS/iBEC patching ──────────────────────────── external
   │    usbliter8-iboot-patchfinder (CTRR unlock, boot-args)
   │
   ├─ Stage 6: SPTM bypass ─────────────────────────────────── external
   │    usbliter8-sptm-patchfinder (iOS 27+ only)
   │
   ├─ Stage 7: TXM bypass ──────────────────────────────────── external
   │    usbliter8-txm-patchfinder (iOS 27+ only)
   │
   ├─ Stage 8: Kernel patchfinder ──────────────────────────── external
   │    usbliter8-kernel-patchfinder (~20 patch targets)
   │
   └─ Stage 9: Boot + SSH ramdisk ──────────────────────────── external
        usbliter8ra1n (kernel boot, dropbear via iProxy)
```

| Stage | Component | Source | iOS version gate |
|---|---|---|---|
| 1 | USBliter8 DWC3 exploit | In-tree | All A12+ |
| 2 | Monitor bootstrap | In-tree | All A12+ |
| 3 | Boot policy bypass | In-tree | All A12+ |
| 4 | Kernel patches | In-tree | All A12+ |
| 5 | iBSS/iBEC patching | [usbliter8-iboot-patchfinder](https://github.com/Leeksov/usbliter8ra1n) | All A12+ |
| 6 | SPTM bypass | [usbliter8-sptm-patchfinder](https://github.com/Leeksov/usbliter8ra1n) | iOS 27+ only |
| 7 | TXM bypass | [usbliter8-txm-patchfinder](https://github.com/Leeksov/usbliter8ra1n) | iOS 27+ only |
| 8 | Kernel patchfinder | [usbliter8-kernel-patchfinder](https://github.com/Leeksov/usbliter8ra1n) | All A12+ |
| 9 | Boot + ramdisk | Target-specific external adapter | Exact product/OS/build evidence required |

## 21. External dependencies setup

For the full boot chain (stages 5-9), clone the usbliter8ra1n repositories alongside FBR34KER:

```sh
git clone https://github.com/Leeksov/usbliter8ra1n.git
git clone https://github.com/Leeksov/usbliter8-iboot-patchfinder.git
git clone https://github.com/Leeksov/usbliter8-sptm-patchfinder.git
git clone https://github.com/Leeksov/usbliter8-txm-patchfinder.git
git clone https://github.com/Leeksov/usbliter8-kernel-patchfinder.git
```

These repos are git submodules expected at the project root. The `usbliter8ra1n` repository contains:

- **usbliter8-iboot-patchfinder** — iBSS/iBEC patching, CTRR unlock, boot-args injection
- **usbliter8-sptm-patchfinder** — SPTM bypass (iOS 27+)
- **usbliter8-txm-patchfinder** — TXM code signing bypass (iOS 27+)
- **usbliter8-kernel-patchfinder** — Runtime kernelcache scanner with ~20 patch targets
- **usbliter8ra1n** — Kernel boot + SSH ramdisk (dropbear via iProxy)

These external project references are conceptual building blocks, not verified
compatibility claims. Use `fbr34ker ramdisk plan`, the deterministic FBRD
maker, and the adapter contract in `docs/RAMDISK_MAKER_LOADER.md` for an exact
product/build.

## 22. Troubleshooting

### Build failures

```
error: unknown target CPU 'apple-a12'
```
Ensure your LLVM is up to date: `brew upgrade llvm` (macOS) or install a newer LLVM package (Linux). Minimum required LLVM version: 16.

```
fatal error: 'fbr34ker/sdk.h' file not found
```
The SDK uses its own include path. Use `make -C sdk` or add `-Isdk/include` to your compiler flags.

```
error: AArch64 target not found in LLVM
```
Your LLVM installation may not include the AArch64 backend. On macOS: `brew install llvm` (ensure `llvm-ar`, `ld.lld`, and `llvm-objcopy` are in PATH). On Linux: `apt install llvm` may need `apt install llvm-dev`.

```
make: *** No rule to make target 'build-operational'
```
This target requires the full source tree (kernel/arch/platform/host). If you have the public operational release, this target builds `fbr34ker-operational.bin` from the included source.

### QEMU issues

```
qemu-system-aarch64: command not found
```
Install QEMU: `brew install qemu` (macOS) or `apt install qemu-system-arm` (Linux). On macOS, ensure `/opt/homebrew/bin` or `/usr/local/bin` is in your PATH.

```
qemu-system-aarch64: Unable to read from 'build/fbr34ker.bin'
```
Run `./fbr34ker build` or `make all` first. The build must complete before QEMU can load the binary.

```
KVM not supported on this host
```
QEMU will fall back to TCG emulation. This is slower but fully functional. On macOS, KVM is not available — TCG is the default.

```
qemu-system-aarch64: -serial chardev:char0: Could not connect to chardev
```
Another QEMU instance may already be running. Kill existing instances: `pkill qemu-system-aarch64`.

### Python issues

```
ModuleNotFoundError: No module named 'usb'
```
Install pyusb: `pip install pyusb`. This is only needed for device operations (detect, pwndfu, console), not for building or QEMU.

```
ModuleNotFoundError: No module named 'b34st'
```
The B34ST module is part of the source tree. Ensure you are running from the project root (`/path/to/FBR34KER_0.x.x_Beta/`).

```
ModuleNotFoundError: No module named 'host'
```
The `host/` directory is part of the full source tree. The public operational release includes the host modules needed for B34ST and scripts.

```
ImportError: libusb-1.0.dylib: cannot open shared object file
```
Install libusb: `brew install libusb` (macOS) or `apt install libusb-1.0-0-dev` (Linux).

### Runtime issues

```
jailbreak: no kernelcache found in DRAM
```
No kernelcache is loaded. On a real device, the exploit chain loads it via vendor MEM_WRITE. Under QEMU, this is expected — the monitor starts with no kernel.

```
Console disconnected — TransportError
```
Expected when the kernel boots — the kernel takes over the USB/serial console. The exploit framework handles this gracefully. In QEMU, this may indicate a crash or fault.

```
jailbreak: security model not enabled — mutation disabled
```
You are running a release build. Rebuild with `make build-operational` or `./fbr34ker build --security-model` to enable mutation paths.

### B34ST issues

```
Error: No module named 'b34st'
```
Run from the project root or install the package: `pip install -e .` (if setup.py is available).

```
Error: usb.core.USBError: [Errno 13] Access denied (insufficient permissions)
```
On Linux, add a udev rule for the device or run with `sudo`. On macOS, this should not occur with pyusb + libusb.

```
B34ST: session directory creation failed
```
Ensure the project root is writable. B34ST creates session directories under `runtime-artifacts/b34st/`.

```
Error: CVE database not found
```
The CVE database should be at `host/cve/data/cve_database.json`. If missing, the CVE subsystem was not included in your build.

### QEMU-specific troubleshooting

```
The monitor boots but the shell prompt does not appear
```
Wait 2-3 seconds for initialization. If it still does not appear, try:
```sh
pkill qemu-system-aarch64
./fbr34ker run direct
```

```
Ctrl-A then X does not exit QEMU
```
The Ctrl-A sequence must be pressed quickly. Try `Ctrl-A` then `X` (uppercase). Alternatively, kill the process: `pkill qemu-system-aarch64`.

## 23. Further reading

| Document | Description |
|---|---|
| `docs/ARCHITECTURE.md` | System architecture, entry sequence, security-state models |
| `docs/EXPLOIT_CHAIN.md` | USBliter8 DWC3 exploit chain design, USB device model, vendor requests |
| `docs/KERNEL_PATCHING.md` | Kernel patching state machine, per-SoC offset tables |
| `docs/SECURE_BOOT_BYPASS.md` | Secure boot bypass subsystem, 6 bypass types |
| `docs/PERSISTENCE.md` | Persistence subsystem, 8 hook types, 16-hook model |
| `docs/B34ST_DESIGN.md` | B34ST unified multi-tool architecture, session instrumentation |
| `docs/B34ST_DEVICE_WORKFLOW.md` | Device dashboard, upgrade/erase/downgrade workflows |
| `docs/B34ST_TASKS.md` | Historical B34ST task list (all complete as of 0.4.4b) |
| `docs/LOADER_SDK.md` | SDK usage, handoff ABI v4 builder/validator |
| `docs/BINARY_HANDOFF.md` | Handoff ABI specification |
| `docs/HANDOFF.md` | Handoff protocol details |
| `docs/QEMU_GENERIC_LOADER.md` | QEMU generic loader design |
| `docs/BOOT_IMAGE.md` | Boot image format specification |
| `docs/PHYSICAL_VALIDATION_CANDIDATE.md` | Validation methodology, maturity states |
| `docs/PHYSICAL_HARDWARE_PROBE.md` | Hardware probe design and policy |
| `docs/PHYSICAL_DEVICE_INTEGRATION.md` | Physical device integration procedures |
| `docs/HARDWARE_BRINGUP_CHECKLIST.md` | Hardware bring-up procedures |
| `docs/A12_A13_HARDWARE_BRINGUP.md` | Authorized A12/A13 hardware bring-up |
| `docs/A12_A13_IRECOVERY.md` | iRecovery integration for A12/A13 |
| `docs/MODULE_FORMAT.md` | FMOD dynamic module format |
| `docs/BYTECODE.md` | FMBC bytecode specification |
| `docs/BRIDGE_PROTOCOL.md` | Bridge protocol specification |
| `docs/HOST_PROTOCOL.md` | Host protocol specification |
| `docs/DEPLOYMENT_PROTOCOL.md` | Deployment protocol specification |
| `docs/TRANSPORT_DEPLOYMENT.md` | Transport and deployment procedures |
| `docs/MMIO.md` | Memory-mapped I/O abstraction |
| `docs/INTERRUPTS.md` | Interrupt controller abstraction |
| `docs/FRAMEBUFFER_CONSOLE.md` | Framebuffer console design |
| `docs/CALLBACK_SAFETY.md` | Callback safety and containment |
| `docs/PLATFORM_SERVICES.md` | Platform service catalog |
| `docs/PORTING.md` | Porting guide for new platforms |
| `docs/PORT_CERTIFICATION.md` | Port certification requirements |
| `docs/BOARD_BRINGUP.md` | Board bring-up procedures |
| `docs/BRINGUP_SHELL.md` | Bring-up shell commands |
| `docs/FIRST_STAGE_ADAPTER.md` | First-stage adapter specification |
| `docs/REAL_HARDWARE_ADAPTER.md` | Real hardware adapter design |
| `docs/RUNTIME_ARCHITECTURE.md` | Runtime architecture graph |
| `docs/RUNTIME_VALIDATION.md` | Runtime validation procedures |
| `docs/THREAT_MODEL.md` | Security threat model |
| `docs/HARDWARE_DIAGNOSTICS.md` | Hardware diagnostics procedures |
| `docs/LOADER_CONFORMANCE.md` | Loader conformance test specification |
| `docs/LOADER_SIMULATOR.md` | Loader simulator design |
| `docs/PROFILE_MATURITY.md` | Profile maturity state model |
| `docs/QUICK_START.md` | Quick reference guide |
| `docs/B34ST_PLAN.md` | Original B34ST planning document |
| `docs/B34ST_REQUIREMENTS.md` | Original B34ST requirements document |
| `sdk/README.md` | SDK documentation |
| `CHANGELOG.md` | Version history |
| `RELEASE_NOTES.md` | Release notes |
| `SECURITY.md` | Security boundary and policy |
