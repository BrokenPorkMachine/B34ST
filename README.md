# FBR34KER 0.2.3

FBR34KER is a freestanding ARM64 preboot monitor and authorized loader-integration research toolkit. Version 0.2.3 is a Physical Validation Candidate for deterministic simulation, bridge validation, and evidence collection.

The tree contains non-operational state models for kernel-patch, boot-policy, and persistence concepts. They do not patch a kernel, bypass Apple secure boot, install software, or persist across reboot. Release builds keep their mutation paths disabled.

## Requirements

- Python 3.10 or newer
- GNU Make
- Clang/LLD with the `aarch64-none-elf` target
- `llvm-objcopy`
- QEMU `qemu-system-aarch64` for runtime and release-gate validation
- `irecovery` only for an already-authorized recovery session

## Canonical build and test

The canonical installed command is:

```sh
B34ST
```

From the source-tree root, use:

```sh
./scripts/B34ST
```

The B34ST control panel wraps FBR34KER build, validation, USBliter8 orchestration, session logging, and runtime-console access. Physical execution requires explicit owner authorization and a second execution confirmation. Direct subcommands remain available through `fbr34ker` for automation. `./fbr34ker` and `./b34stctl` remain compatibility entry points.

For the evidence-gated research-runtime workflow directly:

```sh
B34ST research-runtime guided
# or
python3 scripts/guided_research_runtime.py guided
```

The orchestrator inventories the exact kernelcache, profile, device, boot image, bootstrap archive, first-stage evidence, safe reset, and independently produced runtime-stage evidence. It does not generate an exploit or accept the legacy mutation-labelled state models as proof.

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
# Full monitor build
make

# All non-QEMU verification
make check-native

# QEMU-backed release gate
make release-gate
```

## Monitor shell commands

Once running under QEMU (`make run`), the monitor shell provides status-only views for the disabled security models:

```
kernel-patches [status|apply|revert|escalate]
secure-boot-bypass [status|activate|forgive|manifest]
persistence [status|deploy|activate|evade]
exploit-chain [status|run]
exploit-status
```

Mutation commands are rejected in release builds.

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

Produces `dist/FBR34KER_0.2.3_Physical_Validation_Candidate_operational.zip` containing:
- B34ST research runtime framework (`b34st/`, `b34stctl`, `b34stool.py`)
- All build artifacts (`build/`, `build-generic/`, `build-exploit/`, `build-apple/`, `build-loader/`, `build-hardware-probe/`, `build-sdk/`)
- SDK (headers, library, examples, templates, tests)
- Linker scripts, board profiles, demo modules
- 46 curated documentation files
- Test suite (31 C harnesses + 35 Python tests)
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
| docs/KERNEL_PATCHING.md | Kernel patching state model reference |
| docs/SECURE_BOOT_BYPASS.md | Secure boot bypass state model reference |
| docs/PERSISTENCE.md | Persistence state model reference |
| docs/THREAT_MODEL.md | Threat model |
| docs/PHYSICAL_VALIDATION_CANDIDATE.md | Validation methodology |
| docs/LOADER_SDK.md | Standalone loader SDK guide |
| docs/BINARY_HANDOFF.md | Handoff ABI v4 specification |
| docs/HANDOFF.md | Handoff protocol details |
| sdk/README.md | SDK documentation |
| CHANGELOG.md | Version history |
| SECURITY.md | Security boundary and policy |
| RELEASE_NOTES.md | Release notes |

## Key features in 0.2.3

- **USBliter8 exploit** for A12+ (T8015/T8020/T8030) — replaces checkm8 terminology
- **iOS 17+ kernel base detection** (0xFFFFFFF007804000) with dual-base KASLR slide scan
- **Per-iOS-version kernel patch offsets** (iOS 16 / iOS 17+ tables for A12–M2)
- **PE_debugger / cs_enforcement disable patches** added
- **DWC3 firmware-aware payloads** with GSNPSID version detection
- **Boot-args magic scanning** (0xBA696F53 / 0x626F6F74) instead of fixed offset
- **A13 SEP base probe** (0x82E000000) before A12 fallback
- **Kernel entry passes boot-args pointer in x1** for iOS 17+ compatibility
- **Kernel version string scanning** for precise iOS detection