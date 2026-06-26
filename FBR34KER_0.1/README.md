# FBR34KER 0.2.3

FBR34KER is a freestanding ARM64 preboot monitor and authorized
loader-integration research toolkit. Version 0.2.3 is a Physical Validation
Candidate for deterministic simulation, bridge validation, and evidence
collection.

The tree contains non-operational state models for kernel-patch, boot-policy,
and persistence concepts. They do not patch a kernel, bypass Apple secure
boot, install software, or persist across reboot. Release builds keep their
mutation paths disabled.

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

The B34ST control panel wraps FBR34KER build, validation, USBliter8 orchestration,
session logging, and runtime-console access. Physical execution requires explicit
owner authorization and a second execution confirmation. Direct subcommands
remain available through `fbr34ker` for automation. `./fbr34ker` and
`./b34stctl` remain compatibility entry points.

For the evidence-gated research-runtime workflow directly:

```sh
B34ST research-runtime guided
# or
python3 scripts/guided_research_runtime.py guided
```

The orchestrator inventories the exact kernelcache, profile, device, boot image,
bootstrap archive, first-stage evidence, safe reset, and independently produced
runtime-stage evidence. It does not generate an exploit or accept the legacy
mutation-labelled state models as proof.

## Targeted IPSW workflows

B34ST includes targeted firmware discovery, Apple-CDN downloads, IPSW manifest
inspection, signed upgrades/restores, and tethered downgrade planning:

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

Unsigned firmware is never passed to the stock restore path. Tethered
downgrades require an external authorized adapter and must be booted again
after every restart.

When B34ST starts, its first screen is a connected-device dashboard showing
mode, model, reviewed launch firmware, current firmware where detectable,
latest signed firmware, matching profiles, and device-specific available or
blocked actions. See [docs/B34ST_DEVICE_WORKFLOW.md](docs/B34ST_DEVICE_WORKFLOW.md).

```sh
# Full monitor build
make

# All non-QEMU verification
make check-native

# QEMU-backed release gate
make release-gate
```

## Monitor shell commands

Once running under QEMU (`make run`), the monitor shell provides status-only
views for the disabled security models:

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

## Documentation

| Path | Purpose |
|------|---------|
| docs/ARCHITECTURE.md | System architecture and trust model |
| docs/KERNEL_PATCHING.md | Kernel patching subsystem reference |
| docs/SECURE_BOOT_BYPASS.md | Secure boot bypass subsystem reference |
| docs/PERSISTENCE.md | Persistence subsystem reference |
| docs/EXPLOIT_CHAIN.md | Exploit chain orchestration |
| docs/QUICK_START.md | Quick-start guide |
| docs/A12_A13_IRECOVERY.md | A12/A13 recovery workflow |
| SECURITY.md | Security boundary and policy |
| docs/THREAT_MODEL.md | Threat model |
