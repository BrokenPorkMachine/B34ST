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
