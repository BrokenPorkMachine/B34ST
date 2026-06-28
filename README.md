# FBR34KER 0.3.0

FBR34KER is a freestanding ARM64 preboot monitor, USBliter8 exploit chain, and authorized loader-integration research toolkit. Version 0.3.0 is a Beta providing deterministic simulation, bridge validation, DWC3 firmware exploitation, kernel patching, boot-policy bypass, persistence modeling, and evidence collection.

The tree contains operational exploit primitives including the USBliter8 DWC3 firmware exploit chain for A12+ (T8015/T8020/T8030/T8028/T8103/T8110/T8112), kernel patch engines with per-SoC offset tables, secure boot bypass state machines, and persistence deployment models. All mutation paths are compile-time gated by the `FBR34KER_ENABLE_SECURITY_MODEL` flag. Build with `SECURITY_MODEL=1` to enable the full exploit chain. The default build (`make`) keeps mutation paths disabled for safety.

## Requirements

- Python 3.10 or newer
- GNU Make
- Clang/LLD with the `aarch64-none-elf` target
- `llvm-objcopy`
- QEMU `qemu-system-aarch64` for runtime and release-gate validation
- `irecovery` only for an already-authorized recovery session
- `pyusb` / `libusb` for USB device operations via the USBliter8 exploit chain

## Build modes

FBR34KER supports two build modes controlled by the `SECURITY_MODEL` flag:

**Default (mutation disabled):**
```sh
make
```
Builds the monitor with all mutation paths disabled for safe QEMU testing.

**Operational (full exploit chain):**
```sh
make SECURITY_MODEL=1 build-operational
```
Builds the monitor with the USBliter8 exploit chain, kernel patching, secure boot bypass, and persistence mutation paths enabled. Output in `build-exploit/fbr34ker-operational.bin`.

## Canonical workflow

The unified B34ST control panel wraps all FBR34KER operations:

```sh
./scripts/B34ST
```

After installation, run `B34ST`. Direct subcommands remain available through `fbr34ker` for automation. `./fbr34ker` and `./b34stctl` remain compatibility entry points.

B34ST provides:
- USBliter8 exploit orchestration (DWC3 firmware exploitation, PWNDFU entry, vendor memory access)
- Build management (default and operational builds)
- QEMU runtime execution and console access
- IPSW catalog, download, upgrade, and tethered-downgrade workflows
- Device dashboard (mode, model, firmware, matching profiles, available actions)
- Physical validation candidate evidence collection
- Session logging and runtime orchestration

For the evidence-gated research-runtime workflow:

```sh
B34ST research-runtime guided
# or
python3 scripts/guided_research_runtime.py guided
```

The orchestrator inventories the exact kernelcache, profile, device, boot image, bootstrap archive, first-stage evidence, safe reset, and independently produced runtime-stage evidence.

## Targeted IPSW workflows

B34ST includes targeted firmware discovery, Apple-CDN downloads, IPSW manifest inspection, signed upgrades/restores, and tethered downgrade planning:

```sh
B34ST
# Select: Targeted IPSW downloads, upgrades, and tethered downgrades
```

The lower-level interface is:

```sh
fbr34ker ipsw catalog --product iPhone12,1 --signed-only
fbr34ker ipsw download --product iPhone12,1 --version 17.6.1
fbr34ker ipsw upgrade --product iPhone12,1 --ipsw file.ipsw
fbr34ker ipsw tethered-downgrade --product iPhone12,1 --ipsw old.ipsw
```

Unsigned firmware is never passed to the stock restore path. Tethered downgrades require an external authorized adapter and must be booted again after every restart.

When B34ST starts, its first screen is a connected-device dashboard showing mode, model, reviewed launch firmware, current firmware where detectable, latest signed firmware, matching profiles, and device-specific available or blocked actions. See [docs/B34ST_DEVICE_WORKFLOW.md](docs/B34ST_DEVICE_WORKFLOW.md).

```sh
# Default build (mutation disabled — safe for QEMU testing)
make

# Operational build (full exploit chain enabled)
make SECURITY_MODEL=1 build-operational

# All non-QEMU verification
make check-native

# QEMU-backed release gate
make release-gate
```

## Monitor shell commands

Once running under QEMU (`make run`), the monitor shell provides access to the exploit subsystems:

```
kernel-patches [status|apply|revert|escalate]
secure-boot-bypass [status|activate|forgive|manifest]
persistence [status|deploy|activate|evade]
exploit-chain [status|pwndfu|load|exec|run|reset]
jailbreak [status|security-model|bypass-pac|bypass-aprr|bypass-wxn|bypass-all|detect-kernel|detect-kaslr|inject-bootargs|detect-sep|chain-all|boot-kernel]
usb-status
usb-dfu-configure
exploit-status
```

**Default build:** Mutation commands (apply, activate, deploy, pwndfu, exec, run, inject) return failure.
**Operational build (`SECURITY_MODEL=1`):** All mutation paths are active.

## Apple-family image workflow

```sh
make apple-boot-images
./fbr34ker boot-image inspect build-apple/a13/boot.img --json
```

## Public operational release

The public release includes all non-private operational content:

```sh
make sdk-release
```

Produces `dist/FBR34KER_0.3.0_Beta_operational.zip` containing:
- B34ST research runtime framework (`b34st/`, `b34stctl`, `b34stool.py`)
- All build artifacts (`build/`, `build-generic/`, `build-exploit/`, `build-apple/`, `build-loader/`, `build-hardware-probe/`, `build-sdk/`)
- SDK (headers, library, examples, templates, tests)
- Linker scripts, board profiles, demo modules
- 46 curated documentation files
- Test suite (30 C harnesses + 37 Python tests)
- CLI (`fbr34ker`, completions)
- **Excludes**: `kernel/`, `arch/`, `platform/`, `host/` (private exploit/kernel source)

## Documentation

| Path | Purpose |
|------|---------|
| docs/ARCHITECTURE.md | System architecture and trust model |
| docs/EXPLOIT_CHAIN.md | USBliter8 exploit chain for A12+ |
| docs/QUICK_START.md | Quick-start guide |
| docs/A12_A13_IRECOVERY.md | A12/A13 recovery workflow |
| docs/B34ST_DEVICE_WORKFLOW.md | Device dashboard and workflows |
| docs/B34ST_DESIGN.md | B34ST framework design |
| docs/KERNEL_PATCHING.md | Kernel patching subsystem (per-SoC offset tables) |
| docs/SECURE_BOOT_BYPASS.md | Secure boot bypass engine (6 bypass types) |
| docs/PERSISTENCE.md | Persistence deployment engine (8 hook types) |
| docs/THREAT_MODEL.md | Threat model |
| docs/PHYSICAL_VALIDATION_CANDIDATE.md | Validation methodology |
| docs/LOADER_SDK.md | Standalone loader SDK guide |
| docs/BINARY_HANDOFF.md | Handoff ABI v4 specification |
| docs/HANDOFF.md | Handoff protocol details |
| sdk/README.md | SDK documentation |
| CHANGELOG.md | Version history |
| SECURITY.md | Security boundary and policy |
| RELEASE_NOTES.md | Release notes |

## Key features in 0.3.0

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

## Full boot chain (USBliter8 → iOS kernel + SSH ramdisk)

FBR34KER provides the USBliter8 entry (DWC3 exploit → PWNDFU → vendor memory access → monitor bootstrap) and the onboard jailbreak coordinator (kernel patching, secure boot bypass, persistence). The remaining boot chain components — iBoot patcher, SPTM bypass, TXM bypass, kernel patchfinder, SSH ramdisk — are provided by the external [usbliter8ra1n](https://github.com/Leeksov/usbliter8ra1n) ecosystem:

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
- SPTM bypass is only needed on iOS 27+ (A12/A13 don't have SPTM/TXM on iOS 26.5 and earlier).
- TXM bypass is only needed on iOS 27+.
- The iBoot patcher, SPTM bypass, TXM bypass, kernel patchfinder, and SSH ramdisk are all external and maintained in the usbliter8ra1n project family.

### External dependencies

Install alongside FBR34KER to complete the boot chain:

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

The SSH ramdisk (bundled in `usbliter8ra1n/ramdisk/`) provides a dropbear SSH server exposed via iProxy on port 2222 → device port 44.
