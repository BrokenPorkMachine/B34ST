# FBR34KER recovery boot image

FBR34KER 0.4.1 can produce optional `boot.img` bundles for A12, A12X/A12Z,
A13, A14, A15, M1, and M2 external-loader experiments. The file uses the
bounded **FBRI v1** container format. It is not an Apple-signed IMG4 object and
is not represented as directly compatible with stock iBoot.

## Contents

Each release image contains:

- the generic AArch64 FBR34KER monitor;
- a validated handoff-v4 container;
- the example FMBC module;
- a fixed-capacity canonical JSON manifest;
- SHA-256 hashes for the manifest, payload area, complete image, and each component.

The release monitor component is linked for load and entry at `0x80000000`. This is a packaging contract, not a claim that the address is safe on any Apple product. An authorized first-stage loader must validate and provide the actual placement contract before execution. Custom images can override the declared monitor load and entry addresses.

## Build all family images

```sh
make apple-boot-images
```

Generated files:

```text
build-apple/a12/boot.img
build-apple/a12/boot.raw
build-apple/a12x/boot.img
build-apple/a12x/boot.raw
build-apple/a13/boot.img
build-apple/a13/boot.raw
```

Each file has a JSON sidecar. `boot.img` is an FBRI bundle. `boot.raw` is the unwrapped generic AArch64 monitor for authorized adapters that explicitly require a raw payload.

## Build a custom bundle

```sh
./fbr34ker boot-image build \
  --profile profiles/apple-a13-recovery.json \
  --monitor path/to/monitor.bin \
  --monitor-load 0x80000000 \
  --monitor-entry 0x80000000 \
  --stage0 path/to/authorized-stage0.bin \
  --dtb path/to/device-tree.dtb \
  --output build-apple/custom/boot.img
```

`--stage0` is optional and accepts only a file supplied by the user. FBR34KER does not generate an exploit stage, a signature-bypass stage, or a SecureROM entry payload.

## Validate

```sh
./fbr34ker boot-image inspect build-apple/a13/boot.img --json
```

Inspection rejects malformed headers, unsupported flags, invalid sizes, manifest corruption, payload corruption, component overlaps, and mismatched component hashes.
