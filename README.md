# B34ST - FBR34KER 0.4.1

FBR34KER is a freestanding ARM64 preboot monitor, USBliter8 exploit chain, and authorized loader-integration research toolkit. Version 0.4.1 (Beta, codename "B34ST") provides deterministic QEMU simulation, bridge validation, DWC3 firmware exploitation, kernel patching with per-SoC offset tables, boot-policy bypass, persistence modeling, evidence collection, and the B34ST unified multi-tool control panel.

The tree contains operational exploit primitives including the USBliter8 DWC3 firmware exploit chain for A12+ (T8015/T8020/T8030/T8028/T8103/T8110/T8112), kernel patch engines with per-SoC offset tables across 7 SoCs x 2 iOS versions, secure boot bypass state machines with 6 bypass types, persistence deployment models with 8 hook types, a CVE database and exploit chain planner, forensics acquisition, and an evidence-gated 16-stage research runtime orchestrator. All mutation paths are compile-time gated by the `FBR34KER_ENABLE_SECURITY_MODEL` flag. Build with `SECURITY_MODEL=1` to enable the full exploit chain. The default build (`make`) keeps mutation paths disabled for safety.

---

## Quick start / TLDR

```sh
make                # build QEMU monitor
./fbr34ker run direct  # boot in QEMU
```

For the full B34ST menu-driven experience:

```sh
./scripts/B34ST
```

---

## Requirements

- Python 3.10 or newer
- GNU Make
- Clang/LLD with the `aarch64-none-elf` target
- `llvm-objcopy`
- QEMU `qemu-system-aarch64` for runtime and release-gate validation
- `irecovery` only for an already-authorized recovery session
- `pyusb` / `libusb` for USB device operations via the USBliter8 exploit chain

### Optional

- `libirecovery` (`brew install libirecovery`) for iRecovery queries
- `iproxy` (from `libusbmuxd`) for SSH tunnel to device

---

## Installation / setup

```sh
git clone https://github.com/BrokenPorkMachine/B34ST.git
cd B34ST
./fbr34ker doctor   # verify toolchain
./fbr34ker build     # build and validate all release targets
```

Install to system path (optional):

```sh
sudo ./scripts/install.sh
```

After installation, `B34ST` is available as a system command.

---

## Build modes

FBR34KER supports two build modes controlled by the `SECURITY_MODEL` flag:

### Default (mutation disabled)

```sh
make
```

Builds the monitor at `build/fbr34ker.bin` with all mutation paths disabled for safe QEMU testing. The `kernel-patches`, `secure-boot-bypass`, `persistence`, and `exploit-chain` mutation commands return failure.

### Operational (full exploit chain)

```sh
make SECURITY_MODEL=1 build-operational
```

Output: `build-exploit/fbr34ker-operational.bin`. Enables the USBliter8 exploit chain, kernel patching, secure boot bypass, and persistence mutation paths. Use for physical device workflows.

### Other build targets

```sh
make all              # build the direct QEMU monitor
make apple-boot-images # A12/A12X/A13/A14/A15/M1/M2 recovery bundles
make check-native     # all non-QEMU verification
make release-gate     # QEMU-backed release gate
make sdk-release      # produce dist/FBR34KER_0.4.1_Beta_operational.zip
make exploit-chain    # build + capability summary
make establish-persistence  # generate persistence concept inventory
```

---

## Directory structure

```
B34ST/
├── b34st/                    # B34ST unified multi-tool Python package
│   ├── b34st.py              # CLI entry point (b34st command)
│   ├── engine.py             # Command routing engine (cve, forensics, etc.)
│   ├── research_runtime.py   # Evidence-gated research runtime orchestrator
│   ├── environment.py        # Environment plan builder
│   └── forensics.py          # Forensics utilities
├── scripts/                  # Shell and Python orchestrators
│   ├── B34ST                 # Main menu entry point for the guided UI
│   ├── run_exploit.py        # USBliter8 exploit chain orchestrator
│   ├── guided_research_runtime.py  # Wrapper for guided orchestrator
│   ├── doctor.py             # Toolchain verification
│   └── ...                   # qemu_smoke.py, release_gate.py, etc.
├── host/                     # Host-side tooling
│   ├── usb_serial.py         # USB CDC ACM console client
│   ├── cve/                  # CVE database, chain planner, fuzzer, device DB
│   │   ├── cve_db.py         # CVE database engine
│   │   ├── exploit_chain.py  # Chain planner and exploit goals
│   │   ├── fuzzer.py         # Fuzzer framework
│   │   ├── devices.py        # Device and SoC database
│   │   └── data/             # cve_database.json
│   ├── forensics/            # Forensics acquisition, secrets, activation
│   ├── ramdisk_manager.py    # Deterministic FBRD maker/inspector/adapter loader
│   └── ...                   # hardware_bringup.py, boot_image.py, etc.
├── kernel/                   # In-tree kernel subsystem
│   ├── kernel_patches.c      # Kernel patching (per-SoC offset tables)
│   ├── secure_boot_bypass.c  # Secure boot bypass engine
│   ├── persistence.c         # Persistence deployment engine
│   ├── usbliter8_exploit.c   # USBliter8 DWC3 firmware exploit
│   └── ...                   # Shell, events, FDT, crash, allocator, modules
├── arch/                     # ARM64 architecture code
│   └── arm64/                # Entry, vectors, CPU helpers
├── platform/                 # Platform support
│   ├── qemu_virt/            # PL011, timer, PSCI, GICv3, semihosting
│   └── generic_arm64/        # Handoff callback/FDT adapter
├── loader/                   # Reference loaders
│   └── qemu_handoff/         # Executable reference loader
├── sdk/                      # Standalone loader SDK
│   ├── include/              # C11 headers for handoff ABI v4
│   ├── src/                  # SDK library source
│   ├── examples/             # SDK usage examples
│   ├── templates/            # Project templates
│   └── tests/                # SDK conformance tests
├── exploits/                 # CVE exploit catalog (20 categories)
│   ├── bootrom/              # checkm8, limera1n, blackbird, absinthe
│   ├── kernel/               # Kernel-level CVEs
│   ├── iokit/                # IOKit CVEs
│   ├── webkit/               # WebKit CVEs
│   └── ...                   # accounts, baseband, sep, sandbox, etc.
├── docs/                     # 46 documentation files
├── profiles/                 # Device recovery profiles
├── modules/                  # FMBC bytecode modules
├── linker/                   # Linker scripts
├── schemas/                  # JSON schemas (tether and ramdisk adapters, etc.)
├── tests/                    # Test suite (30 C + 37 Python)
├── fbr34ker                  # CLI entry point
├── b34stctl                  # Compatibility entry point
└── b34stool.py               # Python control panel
```

---

## B34ST unified multi-tool — the main entry point

B34ST is the unified control panel that wraps all FBR34KER operations. Launch it from the source tree:

```sh
./scripts/B34ST
```

After installation, run `B34ST` from anywhere. Direct subcommands remain available through `./fbr34ker` for automation.

### 16 menu categories

| Category | Description |
|----------|-------------|
| System | Build, doctor, test, clean, version info |
| Device | Detect, console, pwndfu, exploit orchestration |
| USBliter8 | Full USBliter8 exploit chain (A12+ DWC3) |
| IPSW | Catalog, download, upgrade, tethered downgrade |
| Boot Image | Inspect, validate, sign boot images |
| Ramdisk Maker / Loader | Target plan, deterministic FBRD bundle, external adapter load |
| Deployment | Deploy, recover, inspect deployments |
| Hardware | Bring-up, probe, diagnostics |
| Session | Session management and log inspection |
| Validation | Physical validation candidate, evidence validation |
| Release | Package, gate, permissions, release management |
| Module | FMOD/FMBC module operations |
| Research Runtime | Guided evidence-gated workflow |
| Frontier | A13+/M-series exploit research, chipset catalog, CVE planning |
| B34ST | Environment plan, control panel configuration |
| Forensics | Evidence acquisition, secrets extraction |

### Session logging system

Every B34ST operation writes:

1. **Timestamps**: ISO format timestamps for start/end of each operation
2. **Command logging**: Full command line to `session.log`
3. **Evidence JSON**: Structured output in session directory
4. **Duration tracking**: Timing for each operation

Session path format:

```
runtime-artifacts/b34st/b34stool/YYYYMMDD-HHMMSS-microseconds/
```

Evidence schema:

```json
{
  "schema_version": 1,
  "operation": "category/action",
  "timestamp": "ISO-8601",
  "command": ["list", "of", "args"],
  "exit_code": 0,
  "duration_ms": 1234,
  "output_summary": "brief description or error"
}
```

---

## Device dashboard and connected-device workflow

When B34ST starts, its first screen is a connected-device dashboard that queries normal-mode devices through `ideviceinfo` and recovery/DFU devices through `irecovery`.

### Dashboard fields

- Device name and product identifier
- Connection mode and board model
- Reviewed launch firmware for supported project devices
- Current firmware and build (when lockdownd exposes them; unavailable in DFU/recovery)
- Latest signed firmware and build from the configured IPSW catalog
- Matching exact recovery profiles
- Actions currently available and why blocked actions are unavailable

### Action workflow

Every device action opens a preparation page containing:

1. Availability and the device-specific reason
2. Required hardware, software, storage, backup, and authorization materials
3. The complete operational sequence
4. A how-to-proceed note
5. An explicit confirmation before execution

External commands inherit the terminal so their prompts and progress remain visible. B34ST records the exit status and transcript, returns to the UI, and refreshes device and firmware state.

### Upgrade

Signed upgrades require: a recent backup, a matching Apple-hosted IPSW, a catalog record reporting the firmware as signed, `idevicerestore`, owner authorization, and an execution confirmation. B34ST runs an `idevicerestore --no-action` preflight before offering execution.

### Erase restore

Erase restore adds `idevicerestore --erase`. Intentionally separate from upgrade because it destroys user data.

### Tethered downgrade

Choose **Guided tethered downgrade**. B34ST validates a local or downloaded
unsigned IPSW, preflights a separately installed external adapter, saves the
plan, and only then offers execution. It does not bundle a target-specific
adapter or use the signed stock restore path. Without an adapter, the guide
stops safely after planning. The external boot stage must run again after every
restart. The adapter is a separately installed executable or reviewed wrapper
that performs the target-specific DFU/recovery boot sequence; it is not the
IPSW, cable, or `idevicerestore`. See
[`docs/TETHERED_DOWNGRADE.md`](docs/TETHERED_DOWNGRADE.md).

### Ramdisk maker and loader

Choose **Ramdisk maker and loader → Guided maker / loader**. B34ST resolves an
exact iPhone, iPad, or Apple silicon Mac profile, records the exact
iOS/iPadOS/macOS version and build, and packages prepared ramdisk,
kernelcache, DeviceTree, and optional boot-chain components into a
deterministic `.fbrd` bundle. Every component is hash-verified before a load
request is created.

Physical loading is plan-only by default and requires a separately installed,
reviewed target/build-specific ramdisk adapter. Current product profiles are
simulation-validated and do not prove that every OS build boots. See
[`docs/RAMDISK_MAKER_LOADER.md`](docs/RAMDISK_MAKER_LOADER.md).

### Failure and return behavior

- No hidden fallback from signed restore to unsigned restore
- No target-changing operation without confirmation
- External exit status is captured
- Logs remain in the B34ST session directory
- Control always returns to B34ST after the external process exits
- Refreshing the dashboard recalculates the next valid actions

---

## Monitor shell commands

Once running under QEMU (`make run`), the monitor shell provides the following commands:

```
kernel-patches [status|apply|revert|escalate]
secure-boot-bypass [status|activate|forgive|manifest]
persistence [status|deploy|activate|evade]
exploit-chain [status|pwndfu|load|exec|run|reset]
jailbreak [status|security-model|bypass-pac|bypass-aprr|bypass-wxn|bypass-all|detect-kernel|detect-kaslr|inject-bootargs|detect-sep|chain-all|boot-kernel]
usb-status
usb-dfu-configure
exploit-status
mmio [read|write|dump|peek|poke]
```

**Default build:** Mutation commands (apply, activate, deploy, pwndfu, exec, run, inject) return failure.
**Operational build (`SECURITY_MODEL=1`):** All mutation paths are active.

### Detailed command reference

| Command | Description |
|---------|-------------|
| `kernel-patches status` | Show registered patches, SoC target, and current state |
| `kernel-patches apply` | Apply all registered kernel patches |
| `kernel-patches revert` | Revert all applied patches |
| `kernel-patches escalate` | Escalate privileges via privilege_offset patch |
| `secure-boot-bypass status` | Show enabled/disabled state for all 6 bypass types |
| `secure-boot-bypass activate <type>` | Enable a specific bypass type |
| `secure-boot-bypass forgive <type>` | Disable a specific bypass type |
| `secure-boot-bypass manifest` | Show full boot manifest state |
| `persistence status` | Show all registered hooks and their current state |
| `persistence deploy <type>` | Register and deploy a new persistence hook |
| `persistence activate` | Activate all pending persistence hooks |
| `persistence evade` | Remove all active persistence hooks |
| `exploit-chain status` | Show exploit chain state (IDLE/PWNDFU/IMAGE_LOADED/EXECUTING/COMPLETE/FAILED) |
| `exploit-chain pwndfu <cpid>` | Enter PWNDFU state for given SoC |
| `exploit-chain load <addr> [size]` | Load raw image at address |
| `exploit-chain dfu-load [addr]` | Load DFU-received image |
| `exploit-chain exec [entry]` | Execute loaded image |
| `exploit-chain run [cpid]` | Execute full exploit chain for given SoC |
| `exploit-chain reset` | Reset exploit chain state |
| `usb-status` | Show DWC3 USB device state |
| `usb-dfu-configure` | Reconfigure for Apple DFU mode |
| `jailbreak status` | Show all jailbreak subsystem states |
| `jailbreak security-model` | Show whether SECURITY_MODEL is enabled |
| `jailbreak bypass-pac` | Activate PAC bypass |
| `jailbreak bypass-aprr` | Activate APRR bypass |
| `jailbreak bypass-wxn` | Activate WXN bypass |
| `jailbreak bypass-all` | Activate all security bypasses |
| `jailbreak detect-kernel` | Detect kernel base address |
| `jailbreak detect-kaslr` | Compute KASLR slide |
| `jailbreak inject-bootargs` | Inject boot-args into kernel |
| `jailbreak detect-sep` | Check SEP readiness |
| `jailbreak chain-all` | Chain all jailbreak steps |
| `jailbreak boot-kernel` | Boot the patched kernel |
| `mmio read <addr>` | Read MMIO register |
| `mmio write <addr> <value>` | Write MMIO register |
| `mmio dump <addr> <size>` | Dump MMIO memory region |
| `mmio peek` | Read and display known MMIO locations |
| `mmio poke <addr> <value>` | Write a test pattern to MMIO |

---

## Jailbreak subsystem

The jailbreak subsystem implements a 14-state state machine that coordinates:

### Security bypasses

- **PAC bypass** — Bypass Pointer Authentication Codes
- **APRR bypass** — Bypass Application Processor Read/Write Restrictions
- **WXN bypass** — Bypass Write XOR Execute memory policy

### Kernel detection and manipulation

- **Kernel base detection** — iOS 17+ kernel base detection at `0xFFFFFFF007804000` with dual-base KASLR slide scan
- **KASLR detection** — KASLR slide computation from kernel base
- **Boot-args injection** — Boot-args magic scanning (`0xBA696F53` / `0x626F6F74`) instead of fixed offset
- **Kernel version string scanning** — Precise iOS version detection from kernel strings
- **SEP detection** — A13 SEP base probe at `0x82E000000` before A12 fallback

### Chain orchestration

- `chain-all` — Execute full jailbreak chain: all bypasses, kernel detection, KASLR, boot-args injection, SEP check, kernel boot
- `boot-kernel` — Transfer control to the patched kernel (kernel entry passes boot-args pointer in x1 for iOS 17+)

---

## USBliter8 exploit chain

### Overview

The USBliter8 exploit chain implements USB-based DWC3 firmware exploitation for A12+ Apple SoCs. Unlike A5-A11 (checkm8), A12+ has no bootrom exploit — instead, the DWC3 USB controller's internal firmware is exploited via USB control transfers from the host.

### Supported SoCs

| SoC | Target | DWC3 firmware patch words |
|-----|--------|--------------------------|
| T8015 | A12 | 6 DWC3 firmware patch words |
| T8020 | A13 | 6 DWC3 firmware patch words |
| T8030 | A14 | 7 DWC3 firmware patch words |
| T8028 | A12Z | 6 DWC3 firmware patch words |
| T8103 | M1 | 8 DWC3 firmware patch words |
| T8110 | A15 | 8 DWC3 firmware patch words |
| T8112 | M2 | 8 DWC3 firmware patch words |

### USB device model

After the DWC3 exploit, FBR34KER presents as a composite USB device (VID 0x05AC, PID 0x1227):

| Interface | Class | Description |
|-----------|-------|-------------|
| 0 | CDC ACM (0x02/0x02/0x01) | Serial console (control) |
| 1 | CDC Data (0x0A/0x00/0x00) | Serial console (data, EP0x01 OUT + EP0x82 IN) |
| 2 | DFU (0xFE/0x01/0x02) | Firmware upload (control endpoint only) |

### Vendor-specific requests

After DWC3 firmware exploitation, the device accepts vendor-specific control requests on EP0 providing physical memory access and code execution:

| bRequest | Name | Direction | Data stage |
|----------|------|-----------|------------|
| 0x01 | SET_ADDR | OUT | 8-byte target address (little-endian) |
| 0x02 | MEM_READ | IN | Returns `wLength` bytes from target address |
| 0x03 | MEM_WRITE | OUT | Writes data to physical DRAM |
| 0x04 | EXECUTE | OUT | Jumps to target address (no data stage) |

The target address auto-increments after each MEM_READ/MEM_WRITE by the transfer length, allowing sequential access without re-issuing SET_ADDR.

### PWNDFU entry

The exploit chain state machine supports: `IDLE -> PWNDFU -> IMAGE_LOADED -> EXECUTING -> COMPLETE -> FAILED`, with GSNPSID-based DWC3 firmware version detection for v1/v2 controller variants.

### Exploit chain orchestration

Full host-side orchestrator:

```sh
python3 scripts/run_exploit.py \
  --monitor build-operational/fbr34ker-operational.bin \
  --auto
```

Manual monitor shell:

```
fbr34ker> exploit-chain pwndfu <cpid>
fbr34ker> exploit-chain load <address>
fbr34ker> exploit-chain exec <entry>
```

### Full boot chain (DFU → SSH ramdisk)

```
DFU → USBliter8 DWC3 exploit → iBSS → iBEC → SPTM bypass → TXM bypass → Kernel → SSH ramdisk
 │                              │       │        │             │          │          └─ dropbear (iproxy 2222→44)
 │                              │       │        │             │          └─ kernel_patchfinder (20 targets, ~6s)
 │                              │       │        │             └─ txm_patchfinder (15 patches, iOS 27+)
 │                              │       │        └─ sptm_patchfinder (6 patches, iOS 27+)
 │                              │       └─ iboot_patchfinder (CTRR unlock, boot-args, sig bypass)
 │                              └─ FBR34KER USBliter8 (this repo)
```

| Stage | Component | Source | iOS version gate |
|-------|-----------|--------|------------------|
| 1. DFU entry | USBliter8 DWC3 exploit | In-tree (`kernel/usbliter8_exploit.c`) | All A12+ |
| 2. Monitor bootstrap | FBR34KER via vendor EXECUTE | In-tree | All A12+ |
| 3. Boot policy bypass | `secure-boot-bypass` engine | In-tree | All A12+ |
| 4. Kernel patches | `kernel-patches` engine | In-tree | All A12+ |
| 5. iBSS/iBEC patching | usbliter8-iboot-patchfinder | External | All A12+ |
| 6. SPTM bypass | usbliter8-sptm-patchfinder | External | iOS 27+ only |
| 7. TXM bypass | usbliter8-txm-patchfinder | External | iOS 27+ only |
| 8. Kernel patchfinder | usbliter8-kernel-patchfinder | External | All A12+ |
| 9. Boot + ramdisk | Target-specific external adapter | External | Exact product/OS/build evidence required |

**Important version notes:**
- SPTM bypass is only needed on iOS 27+ (A12/A13 don't have SPTM/TXM on iOS 26.5 and earlier)
- TXM bypass is only needed on iOS 27+
- The iBoot patcher, SPTM bypass, TXM bypass, kernel patchfinder, and SSH ramdisk are external (usbliter8ra1n ecosystem)
- External project names in this conceptual chain are not verified compatibility
  claims. Use `fbr34ker ramdisk plan` and the reviewed adapter contract for an
  exact target/build.

### Hardware guide and recommended hardware

For reliable DWC3 exploitation, it is important to use a capable USB host.
The **Waveshare RP2350 USB-A** (dual Cortex-M33, native USB-A host, ~$15-25)
is the recommended host board. See `docs/USBLITER8_HARDWARE_GUIDE.md` for full
details on hardware selection, cable choice, firmware preparation, and
troubleshooting.

### Hardware bring-up procedure

1. **Prepare hardware**: See `docs/USBLITER8_HARDWARE_GUIDE.md` for
   recommended Waveshare RP2350 USB-A host setup, cable selection, and power.
2. **Build operational image**: `make build-operational`
3. **Put device into DFU mode**: Power + Volume Down for 10s, release Power, hold Volume Down for 5s
4. **Verify DFU**: `irecovery -q | grep CPID` (expect 0x8015 for A12, 0x8020 for A13, etc.)
5. **Apply USBliter8 exploit**: `python3 scripts/run_exploit.py --monitor build-exploit/fbr34ker-operational.bin --auto`
6. **Connect to USB console**: via CDC ACM device or `host/usb_serial.py`
7. **Run exploit commands**: `secure-boot-bypass forgive`, `kernel-patches apply`, `kernel-patches escalate`, `persistence deploy`, `persistence activate`, `exploit-chain run`

Each step in B34ST's USBliter8 workflow can be skipped if already completed.
Use `b34st usbliter8 --skip-hardware-prep --skip-build` to skip preparation
and go straight to exploitation. After the exploit and external work is done,
B34ST returns to its main menu automatically.

---

## Kernel patching

### Overview

The kernel patching subsystem provides per-SoC kernel patch offset tables for Apple A12/A13/A14/A12Z/A15/M1/M2 across iOS 16 and iOS 17+. iOS 18 is detected via the iOS 17+ version string scanner (Darwin 23.x).

### Supported SoCs and offset tables

| SoC | Target | iOS versions | Patch types |
|-----|--------|-------------|-------------|
| T8015 | A12 | 16, 17+ | 8 |
| T8020 | A13 | 16, 17+ | 8 |
| T8030 | A14 | 16, 17+ | 8 |
| T8028 | A12Z | 16, 17+ | 8 |
| T8103 | M1 | 16, 17+ | 8 |
| T8110 | A15 | 16, 17+ | 8 |
| T8112 | M2 | 16, 17+ | 8 |

### 8 patch types

1. `amfi` — Apple Mobile File Integrity bypass
2. `task_for_pid` — task_for_pid entitlement bypass
3. `privilege` — Privilege escalation (kernel task)
4. `mount_root` — Root filesystem mount patch
5. `codesign` — Code signing enforcement bypass
6. `sandbox` — Sandbox policy bypass
7. `pe_debugger` — PE_debugger enable
8. `cs_enforcement` — Code signing enforcement disable

### Shell commands

```
kernel-patches [status|apply|revert|escalate]
```

- `status` — Show registered patches, SoC target, and current state
- `apply` — Apply all registered kernel patches to the active state model
- `revert` — Revert all applied patches
- `escalate` — Escalate privileges via the privilege_offset patch

### Event bus integration

Kernel patch operations publish `kernel-patch-*` events for each lifecycle transition (apply, revert, escalate, failure).

---

## Secure boot bypass

### Bypass types

The secure boot bypass engine provides 6 bypass types for modeling Apple secure boot policy evasion:

| Type | Description |
|------|-------------|
| `image4-sig` | Image4 signature verification bypass |
| `cert-chain` | Certificate chain validation bypass |
| `ap-ticket` | APTicket validation bypass |
| `shsh-blob` | SHSH blob verification bypass |
| `iboot-auth` | iBoot authentication bypass |
| `boot-manifest` | Boot manifest validation bypass |

### Shell commands

```
secure-boot-bypass [status|activate|forgive|manifest]
```

- `status` — Show enabled/disabled state for all 6 bypass types
- `activate <type>` — Enable a specific bypass type
- `forgive <type>` — Disable a specific bypass type
- `manifest` — Show the full boot manifest state

Each bypass type has independent activation, deactivation, and status tracking within the state machine.

---

## Persistence

### Hook types

The persistence subsystem provides 8 hook types for modeling post-exploit persistence deployment:

| Type | Description |
|------|-------------|
| `boot-hook` | Boot-time execution hook |
| `launchd-plist` | Launchd property list persistence |
| `kext` | Kernel extension loading |
| `hidden-storage` | Concealed storage allocation (up to 64KB) |
| `payload-deploy` | Payload deployment mechanism |
| `tamper-resist` | Tamper detection resistance |
| `ota-persist` | OTA update survivability |
| `evasion` | Detection evasion |

### Shell commands

```
persistence [status|deploy|activate|evade]
```

- `status` — Show all registered hooks and their current state
- `deploy <type>` — Register and deploy a new persistence hook
- `activate` — Activate all pending persistence hooks
- `evade` — Remove all active persistence hooks

Maximum capacity: 16 hooks total, 64KB hidden storage.

---

## CVE database and exploit chain planner

The B34ST CVE subsystem provides a comprehensive vulnerability database, device-aware chain planning, fuzz target integration, and exploit goal planning.

### Database

Reference database of CVEs affecting Apple iOS devices across multiple components: accounts, baseband, bluetooth, bootrom, coregraphics, dtrace, fairplay, fontparser, foundation, imageio, iokit, kernel, keybag, reminders, sandbox, security-framework, sep, wallet, weather, webkit.

### Commands

```sh
B34ST cve stats                    # database statistics
B34ST cve search CVE-2023-28204    # search by ID
B34ST cve query 17.0               # CVEs for an iOS version
B34ST cve filter --version 16.5 --min-severity high  # filter by criteria
B34ST cve chain jailbreak 17.0     # plan exploit chain for a goal
B34ST cve device-chain jailbreak 16.5 iPhone10,1  # device-specific chain
B34ST cve goals                    # list all built-in exploit goals
B34ST cve suggest 17.0             # suggest achievable goals for a version
B34ST cve device-info              # list supported devices and SoCs
B34ST cve fuzz list                # list available fuzz targets
```

### Exploit goals

Built-in exploit goals include jailbreak, kernel-read, kernel-write, bootchain-control, and more. Each goal specifies required subgoals, difficulty level, and estimated success rate. The chain planner searches the CVE database for chains that satisfy the goal constraints for a given iOS version.

### Fuzzer integration

The CVE subsystem includes a fuzzer framework with available fuzz targets for discovering new vulnerabilities.

---

## Forensics capabilities

B34ST provides a comprehensive forensics and data acquisition subsystem.

### Commands

```sh
B34ST forensics guided             # interactive guided forensics workflow
B34ST forensics acquire            # standard evidence acquisition
B34ST forensics verify             # verify a forensics evidence bundle
B34ST forensics list-profiles      # list built-in acquisition profiles
```

### Acquisition profiles

- `quick` — Fast targeted acquisition
- `full` — Complete device acquisition
- `memory-only` — Volatile memory capture
- `storage-only` — Non-volatile storage capture
- `filesystem-only` — Filesystem logical acquisition
- `network-only` — Network traffic capture

### Secrets extraction

```sh
B34ST forensics secrets            # iCloud/Keychain/Keybag extraction
```

### Activation and FMI control

```sh
B34ST forensics activation         # activation bypass, baseband, FMI control
```

### Passcode operations

```sh
B34ST forensics passcode           # passcode on/off/change/bypass
```

### Chain of custody

All forensics operations include chain-of-custody logging, acquisition reports, and structured evidence output.

---

## Research runtime orchestrator

The research runtime orchestrator is an evidence-gated 16-stage state machine for authorized first-stage validation. It automates bounded validation and external-reviewed-adapter contracts. Target-specific exploit, kernel-patch, trust-cache, and bootstrap-install implementations remain external inputs and must provide machine-readable evidence before the state machine advances.

### 16-stage state machine

```
HOST_READY → TARGET_PROFILE_VALIDATED → KERNEL_IDENTIFIED → MONITOR_IMAGE_VALIDATED → MONITOR_RUNTIME → SAFE_RESET_VERIFIED → KERNEL_PATCH_ATTEMPTED → KERNEL_PATCH_VERIFIED → CODE_SIGNING_POLICY_VERIFIED → TRUST_CACHE_ACCEPTED → WRITABLE_RESEARCH_ENVIRONMENT → BOOTSTRAP_VERIFIED → BOOTSTRAP_ACTIVE → USERSPACE_SHELL_RESPONDING → RESEARCH_RUNTIME_READY → JAILBREAK_ATTESTED
```

### Launch

```sh
B34ST research-runtime guided
# or
python3 scripts/guided_research_runtime.py guided
```

### Evidence gates

7 of the 16 stages require external evidence with strict validation:

- KERNEL_PATCH_ATTEMPTED
- KERNEL_PATCH_VERIFIED (requires rollback.available=true)
- CODE_SIGNING_POLICY_VERIFIED (requires rollback.available=true)
- TRUST_CACHE_ACCEPTED
- WRITABLE_RESEARCH_ENVIRONMENT
- BOOTSTRAP_ACTIVE
- USERSPACE_SHELL_RESPONDING

Evidence must match the exact kernelcache SHA-256 and use schema_version 1.

### Runtime session output

Output is written to `runtime-artifacts/b34st/research-runtime/YYYYMMDD-HHMMSS-microseconds/` containing:

- `runtime-state.json` — Full state machine report
- `orchestrator.log` — Timestamped operation log
- `01-host-readiness.log`, etc. — Command transcripts
- `evidence-templates/` — Evidence templates for all 7 external stages
- `legacy-component-audit.json` — Audit of why legacy in-tree models cannot satisfy evidence gates
- `kernel-identity-template.json` — Template if kernel identity requires review
- `jailbreak-attestation.json` — Final operator attestation when complete

### Audit of legacy components

The orchestrator audits why in-tree state models cannot satisfy runtime evidence gates:

| Component | Classification | Reason |
|-----------|---------------|--------|
| `kernel/kernel_patches.c` | UNVERIFIED_MUTATION_MODEL | Fixed base-relative offsets; no exact-kernel hash binding or read-back proof |
| `kernel/secure_boot_bypass.c` | UNVERIFIED_STATE_MODEL | State flags and fixed offsets do not prove Image4 or code-signing policy changes |
| `kernel/persistence.c` | IN_MEMORY_MODEL | Internal storage and hook state are not a signed userspace bootstrap |
| `kernel/usbliter8_exploit.c` | UNVERIFIED_TARGET_MODEL | Patch words lack target firmware identity, provenance, and read-back evidence |
| `scripts/run_exploit.py` | LEGACY_ORCHESTRATOR | Runs mutation-labelled commands; not accepted as stage evidence |

---

## IPSW workflows

B34ST includes targeted firmware discovery, Apple-CDN downloads, IPSW manifest inspection, signed upgrades/restores, and tethered downgrade planning.

### Commands

```sh
fbr34ker ipsw catalog --product iPhone12,1 --signed-only
fbr34ker ipsw download --product iPhone12,1 --version 17.6.1
fbr34ker ipsw upgrade --product iPhone12,1 --ipsw file.ipsw
fbr34ker ipsw tethered-downgrade-guide
```

### IPSW catalog

The catalog command queries Apple's firmware signing window. Results include build version, build ID, signing status, release date, and download URL.

### Upgrade workflow

1. Recent backup confirmed
2. Matching Apple-hosted IPSW identified
3. Catalog record reports firmware as signed
4. `idevicerestore --no-action` preflight passes
5. Owner authorization and execution confirmation obtained
6. Data-preserving update requested (firmware may force erase if lacking customer-upgrade identity)

### Erase restore

`idevicerestore --erase` — Intentionally separate from upgrade; destroys user data. Backups and Find My requirements shown before execution.

### Tethered downgrade

Use B34ST's **Guided tethered downgrade** workflow. It selects or downloads the
target IPSW, validates the exact product/manifest/SHA-256, preflights the
external adapter, saves a human-readable and JSON plan, and only then offers
execution. B34ST does not bundle the target-specific adapter; without one the
guide stops safely after planning. Tethered runtime requires the external boot
stage after every restart. The adapter is the separately installed
target-specific executable that performs the device-side boot sequence and
returns JSON to B34ST. See
[`docs/TETHERED_DOWNGRADE.md`](docs/TETHERED_DOWNGRADE.md).

Public checkm8-era projects such as Legacy iOS Kit, Semaphorin, and palera1n
target A11 or earlier hardware and are not drop-in adapters for B34ST's A12+
profiles. The full guide includes a compatibility table and a contract-only
example adapter.

---

## SDK overview

The SDK is a standalone C11 library for constructing, validating, and parsing the FBR34KER handoff ABI v4. It is independent of the main FBR34KER source and can be used by external loaders.

```sh
make build-sdk
```

### SDK components

- **Headers** (`sdk/include/`) — Public API for handoff ABI v4
- **Library** (`sdk/src/`) — Handoff builder, validator, matcher
- **Examples** (`sdk/examples/`) — Usage demonstrations
- **Templates** (`sdk/templates/`) — Project scaffolding
- **Tests** (`sdk/tests/`) — Conformance test suite

See `sdk/README.md` and `docs/LOADER_SDK.md` for full details.

---

## Full boot chain

FBR34KER models the USBliter8 entry and onboard coordinator. Remaining
boot-chain and ramdisk components must be supplied by a reviewed external
adapter. References below are conceptual and do not establish compatibility
with an exact product or OS build:

```
DFU → USBliter8 DWC3 exploit → iBSS → iBEC → SPTM bypass → TXM bypass → Kernel → SSH ramdisk
 │                              │       │        │             │          │          └─ dropbear (iproxy 2222→44)
 │                              │       │        │             │          └─ kernel_patchfinder (20 targets, ~6s)
 │                              │       │        │             └─ txm_patchfinder (15 patches, iOS 27+)
 │                              │       │        └─ sptm_patchfinder (6 patches, iOS 27+)
 │                              │       └─ iboot_patchfinder (CTRR unlock, boot-args, sig bypass)
 │                              └─ FBR34KER USBliter8 (this repo)
```

**Important version notes:**
- SPTM bypass is only needed on iOS 27+ (A12/A13 don't have SPTM/TXM on iOS 26.5 and earlier)
- TXM bypass is only needed on iOS 27+
- The iBoot patcher, SPTM bypass, TXM bypass, kernel patchfinder, and SSH ramdisk are all external

---

## External dependencies

Clone these alongside FBR34KER to complete the boot chain:

```sh
# iBoot/iBSS/iBEC patcher — CTRR unlock, boot-args injection, sig bypass
git clone https://github.com/Leeksov/usbliter8-iboot-patchfinder.git

# SPTM CTRR bypass — 6 patches, iOS 27+
git clone https://github.com/Leeksov/usbliter8-sptm-patchfinder.git

# TXM code signing bypass — 15 patches, iOS 27+
git clone https://github.com/Leeksov/usbliter8-txm-patchfinder.git

# Kernel patchfinder — 20 patch targets, runtime scanner, ~6s
git clone https://github.com/Leeksov/usbliter8-kernel-patchfinder.git

# Full chain toolkit (includes SSH ramdisk with dropbear)
git clone https://github.com/Leeksov/usbliter8ra1n.git
```

Do not assume an external project's ramdisk, SSH configuration, or advertised
device range applies to a B34ST target. Package prepared components with
`fbr34ker ramdisk build`, create a plan-only load request, and require exact
adapter evidence as documented in `docs/RAMDISK_MAKER_LOADER.md`.

---

## Apple-family image workflow

```sh
make apple-boot-images
./fbr34ker boot-image inspect build-apple/a13/boot.img --json
```

### Recovery upload commands

```sh
./fbr34ker irecovery query
./fbr34ker irecovery send --profile profiles/apple-a12-recovery.json --image build-apple/a12/boot.img --dry-run
./fbr34ker irecovery send --profile profiles/apple-a12-recovery.json --image build-apple/a12/boot.img --authorized-session --evidence runtime-artifacts/a12-upload.json
```

---

## Public operational release

```sh
make sdk-release
```

Produces `dist/FBR34KER_0.4.1_Beta_operational.zip` containing:

- B34ST research runtime framework (`b34st/`, `b34stctl`, `b34stool.py`)
- All build artifacts (`build/`, `build-generic/`, `build-exploit/`, `build-apple/`, `build-loader/`, `build-hardware-probe/`, `build-sdk/`)
- SDK (headers, library, examples, templates, tests)
- Linker scripts, board profiles, demo modules
- 47 documentation files
- Test suite (32 C sources/harnesses + 42 Python test modules)
- CLI (`fbr34ker`, completions)
- **Excludes**: `kernel/`, `arch/`, and `platform/` firmware source. Required
  public host-side runtime tools are included so the packaged CLI remains
  functional.

---

## System architecture

### Entry sequence

1. Preserve `x0`
2. Accept EL2 or EL1 entry; unsupported exception levels stop safely
3. From EL2, configure AArch64 EL1h and timer access
4. Install linked stack and vectors, mask interrupts, clear BSS preserving `.crashlog`
5. Validate boot context; initialize FDT, platform services, console transports, exceptions, allocator, stack guards, logging, protocol, watchdog, modules, and hardware-probe policy
6. Initialize the runtime architecture graph
7. Enter normal or restricted interactive monitor

FBR34KER does not install an MMU. A loader must document inherited translation and cache state.

### Runtime architecture graph

An allocation-free orchestration layer with fixed compile-time capacities. Component lifecycle spans 6 ordered phases: early, core, platform, services, extensions, interactive.

Built-in graph components:
1. `event-bus` — core phase; provides event-journal capability (32 records, 8 subscribers)
2. `service-registry` — core phase; depends on event bus (16 services max)
3. `driver-manager` — platform phase; depends on event bus and registry (16 drivers max)
4. `platform-catalog` — services phase; activates the logical platform-service catalog

### Security-state models

Version 0.4.1 includes bounded in-memory models for patch, boot-policy, and persistence concepts. They exist to validate interface shape, status output, policy gates, event wiring, and failure handling. They do not modify target memory, Apple trust policy, filesystems, or reboot state.

Release builds do not define `FBR34KER_ENABLE_SECURITY_MODEL`, so mutation operations return failure. Immutable probe images remain locked regardless of build options.

### Layers

- `arch/arm64`: entry, vectors, CPU helpers
- `kernel`: lifecycle, events, service/driver orchestration, shell, framing, FDT, crash handling, allocator, consoles, modules, kernel patching, secure boot bypass, persistence
- `platform/qemu_virt`: PL011, timer, PSCI, GICv3, semihosting
- `platform/generic_arm64`: handoff callback/FDT adapter
- `platform/gic.c`: compact GICv2/GICv3 implementation
- `loader/qemu_handoff`: executable reference loader
- `sdk`: standalone handoff-v4 builder, validator, matcher, examples, tests
- `host`: compiler, transport, handoff schema, simulator, diagnostics, release tooling
- `tests`: native, Python, direct-QEMU, generic-loader QEMU tests

### Trust model

Loader pointers/callbacks and built-in native code are privileged. External FMOD modules are validated FMBC bytecode interpreted under capability and instruction limits. Hashes and CRCs provide integrity and error detection, not signer identity.

---

## Documentation map

| Path | Purpose |
|------|---------|
| docs/ARCHITECTURE.md | System architecture and trust model |
| docs/EXPLOIT_CHAIN.md | USBliter8 exploit chain for A12+ |
| docs/QUICK_START.md | Quick-start guide |
| docs/A12_A13_IRECOVERY.md | A12/A13 recovery workflow |
| docs/A12_A13_HARDWARE_BRINGUP.md | A12/A13 hardware bring-up procedure |
| docs/B34ST_DEVICE_WORKFLOW.md | Device dashboard and connected-device workflows |
| docs/RAMDISK_MAKER_LOADER.md | Exact-profile ramdisk maker/loader and adapter contract |
| docs/TETHERED_DOWNGRADE.md | Guided tethered downgrade and adapter contract |
| docs/B34ST_DESIGN.md | B34ST framework design (16-category menu system) |
| docs/B34ST_PLAN.md | B34ST implementation plan |
| docs/B34ST_REQUIREMENTS.md | B34ST requirements specification |
| docs/B34ST_TASKS.md | B34ST task tracking |
| docs/KERNEL_PATCHING.md | Kernel patching subsystem (per-SoC offset tables) |
| docs/SECURE_BOOT_BYPASS.md | Secure boot bypass engine (6 bypass types) |
| docs/PERSISTENCE.md | Persistence deployment engine (8 hook types) |
| docs/THREAT_MODEL.md | Threat model |
| docs/PHYSICAL_VALIDATION_CANDIDATE.md | Physical validation methodology |
| docs/PHYSICAL_DEVICE_INTEGRATION.md | Physical device integration guide |
| docs/PHYSICAL_HARDWARE_PROBE.md | Physical hardware probe documentation |
| docs/LOADER_SDK.md | Standalone loader SDK guide |
| docs/LOADER_CONFORMANCE.md | Loader conformance requirements |
| docs/LOADER_SIMULATOR.md | Loader simulator documentation |
| docs/BINARY_HANDOFF.md | Handoff ABI v4 specification |
| docs/HANDOFF.md | Handoff protocol details |
| docs/CALLBACK_SAFETY.md | Callback safety and containment |
| docs/BRIDGE_PROTOCOL.md | Bridge protocol specification |
| docs/HOST_PROTOCOL.md | Host protocol specification |
| docs/DEPLOYMENT_PROTOCOL.md | Deployment protocol specification |
| docs/TRANSPORT_DEPLOYMENT.md | Transport deployment guide |
| docs/BYTESTREAM.md | BYTESTREAM operation code format |
| docs/MODULE_FORMAT.md | FMOD/FMBC module format specification |
| docs/RUNTIME_ARCHITECTURE.md | Runtime architecture detailed design |
| docs/RUNTIME_VALIDATION.md | Runtime validation methodology |
| docs/PLATFORM_SERVICES.md | Platform services specification |
| docs/INTERRUPTS.md | Interrupt handling design |
| docs/FRAMEBUFFER_CONSOLE.md | Framebuffer console specification |
| docs/MMIO.md | MMIO operation documentation |
| docs/BOOT_IMAGE.md | Boot image format specification |
| docs/BOARD_BRINGUP.md | Board bring-up guide |
| docs/BRINGUP_SHELL.md | Bring-up shell commands |
| docs/HARDWARE_BRINGUP_CHECKLIST.md | Hardware bring-up checklist |
| docs/HARDWARE_DIAGNOSTICS.md | Hardware diagnostics commands |
| docs/PORTING.md | Porting guide for new platforms |
| docs/PORT_CERTIFICATION.md | Port certification process |
| docs/REAL_HARDWARE_ADAPTER.md | Real hardware adapter specification |
| docs/PROFILE_MATURITY.md | Profile maturity and evidence policy |
| docs/FIRST_STAGE_ADAPTER.md | First-stage adapter documentation |
| docs/QEMU_GENERIC_LOADER.md | QEMU generic loader documentation |
| sdk/README.md | SDK documentation |
| CHANGELOG.md | Version history |
| SECURITY.md | Security boundary and policy |
| RELEASE_NOTES.md | Release notes |

---

## Key features in 0.4.1

- **Guided tethered downgrade** — exact firmware selection, local or downloaded
  IPSW verification, evidence-first planning, explicit adapter contract, and
  separately acknowledged execution
- **Ramdisk maker / loader** — exact-profile iPhone, iPad, and Apple silicon
  Mac planning, deterministic hash-verified FBRD bundles, and plan-first
  external adapter execution
- **Reliable installed tooling** — working `forensics`/`cve` routing,
  interactive QEMU without a launcher timeout, terminal flag restoration, and
  macOS TLS CA discovery
- **Expanded release coverage** — generic and exact-product profiles for A14,
  A15, M1, and M2, with deterministic boot images included in manifests and
  complete packages
- **USBliter8 exploit chain** for A12+ (T8015/T8020/T8030/T8028/T8103/T8110/T8112) — DWC3 firmware exploitation with real SoC-specific patch byte sequences, PWNDFU entry, vendor-specific physical memory access (SET_ADDR/MEM_READ/MEM_WRITE/EXECUTE), and image loading/execution
- **Jailbreak coordinator** — 14-state machine: PAC bypass, APRR bypass, WXN bypass, kernel detection, KASLR slide computation, boot-args injection, SEP readiness, kernel boot
- **Per-SoC kernel patch offset tables** for A12/A13/A14/A12Z/A15/M1/M2 across iOS 16/17 — amfi, task_for_pid, privilege escalation, root mount, codesign, sandbox, PE_debugger, cs_enforcement (8 patch types)
- **Secure boot bypass engine** — 6 bypass types (Image4 sig, cert chain, APTicket, SHSH blob, iBoot auth, boot manifest)
- **Persistence deployment engine** — 8 hook types (boot hook, launchd plist, kext, hidden storage, payload deploy, tamper resist, OTA persist, evasion) with 16 max hooks, 64KB hidden storage
- **DWC3 firmware-aware payloads** with GSNPSID version detection for v1/v2 controllers
- **Full USB device-mode stack** — CDC ACM serial console, DFU firmware upload, vendor-specific control requests
- **iOS 17+ kernel base detection** (0xFFFFFFF007804000) with dual-base KASLR slide scan
- **Boot-args magic scanning** (0xBA696F53 / 0x626F6F74) instead of fixed offset
- **Kernel version string scanning** for precise iOS detection
- **A13 SEP base probe** (0x82E000000) before A12 fallback
- **Kernel entry passes boot-args pointer in x1** for iOS 17+ compatibility
- **B34ST unified multi-tool** — 16-category menu system with session logging, evidence JSON, and orchestration
- **Device dashboard** — Connected-device auto-detection with mode, model, firmware, profiles, and available actions
- **CVE database and exploit chain planner** — 1155 CVEs indexed by iOS version, component, severity; device-aware chain planning and fuzz targets
- **Evidence-gated research runtime** — 16-stage state machine with strict evidence validation and chain-of-custody
- **Forensics subsystem** — Evidence acquisition, secrets extraction (iCloud/Keychain/Keybag), activation bypass, FMI control, passcode operations
- **IPSW workflows** — Catalog, download, upgrade, erase restore, tethered downgrade
- **SDK** — Standalone C11 library for handoff ABI v4

---

## License / Security / Changelog

- **License**: See [LICENSE](LICENSE)
- **Security policy**: See [SECURITY.md](SECURITY.md) for security boundary, responsible disclosure, and policy
- **Changelog**: See [CHANGELOG.md](CHANGELOG.md) for version history
- **Release notes**: See [RELEASE_NOTES.md](RELEASE_NOTES.md) for 0.4.1 Beta release notes
