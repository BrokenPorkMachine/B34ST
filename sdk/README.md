# FBR34KER loader SDK 0.4.1

This directory is a standalone, freestanding C11 SDK for constructing and
validating FBR34KER handoff ABI v4 structures. It does not depend on monitor
internal headers, an operating system, or an exploit/boot-chain implementation.

## Contents

- `include/`: stable public ABI declarations and compile-time layout checks.
- `src/`: bounded handoff builder, structural validator, and profile matcher.
- `examples/`: minimal, callback-console, and framebuffer loader examples.
- `tests/`: host-executable SDK contract tests.

## Build

```sh
make -C sdk
make -C sdk test
```

The default library target is `aarch64-none-elf`. Override `CC`, `AR`, or
`TARGET` for another freestanding AArch64 toolchain.

## Required final-loader work

The builder owns its temporary tables. Before transferring control, a loader
must place the finalized handoff, region table, service table, device tree, and
boot-module records in loader-owned memory described by the final memory map.
All callback addresses must point into declared readable/executable loader code.
Run the binary conformance tooling and the monitor's restricted probe before
considering a port compatible.

See `../docs/LOADER_SDK.md`, `../docs/BINARY_HANDOFF.md`, and
`../docs/PORT_CERTIFICATION.md`.
