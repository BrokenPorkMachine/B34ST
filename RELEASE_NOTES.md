# FBR34KER 0.6.1b Beta release notes

FBR34KER 0.6.1b Beta is a patch release based on the merged 0.4.0 Beta tree. It
packages the latest fixes and updates under one consistent release identity.

## Patch-release highlights

- **Correctness**: Operational builds now retain
  `FBR34KER_ENABLE_SECURITY_MODEL`; the build fails if the produced image
  contains the simulated patch path.
- **Correctness**: Canonical Apple identities are consistent across profiles,
  examples, host payload maps, and firmware tables: A12/T8020, A13/T8030,
  and A14/T8101.
- **Safety**: Kernel version scanning uses aligned word reads without
  overwriting byte-sized stack storage.
- **Safety**: Kernel patch apply and revert operations propagate MMIO failures
  and never mark failed writes successful.
- **Safety**: Persistence tracks physical base metadata separately from its
  bounded in-array allocation cursor.
- **Evidence**: checkm8, limera1n, USBliter8, and monitor execution paths now
  require positive PWNDFU, vendor-request, or re-enumeration evidence.
- **Testing**: Top-level menu tests are part of `make check`; operational
  mutation, target identity, profile consistency, and negative-evidence
  regressions were added.
- **Fix**: CLI now supplies the experimental DWC3 transfer corpus and requires
  a successful vendor-interface probe before recording USBliter8 success
- **Fix**: Unknown Apple devices no longer default to A12 in detect_device_chipset; proper error handling added
- **Fix**: Execution reporting now correctly reports failure after transfer errors in run_exploit.py
- **Fix**: Non-empty result dict no longer marks legacy chain success despite all failures
- **Feature**: Added SEP exploitation pipeline to B34ST menus (b34stool.py)
- **Audit**: Completed fuzzing code correctness and completeness audit

## Inherited 0.4 functionality

- Guided tethered-downgrade planning with exact firmware selection, local or
  downloaded IPSW validation, SHA-256 evidence, explicit execution
  acknowledgements, and a documented external-adapter contract.
- Working installed `forensics` and `cve` routing.
- Interactive QEMU sessions without a launcher timeout or leaked nonblocking
  terminal flags.
- macOS/Python TLS CA discovery for firmware-catalog access.
- Monitor formatting support for width, alignment, zero-padding, and `size_t`.
- Generic and exact-product recovery profiles for A14, A15, M1, and M2.

## Compatibility

0.6.1b does not change the public binary interfaces:

- protocol: 1
- handoff ABI: 4
- module ABI: 3
- FMOD: 1
- FMBC: 2

Loaders and modules that conform to the 0.4.0 interfaces require no migration.

## Operational boundaries

- Default builds keep physical writes disabled. `SECURITY_MODEL=1` remains a
  separate, explicit lab build mode.
- FBRI images are external-loader containers, not Apple-signed IMG4 images and
  not directly compatible with stock iBoot.
- Tethered downgrade execution requires a separately installed,
  target-specific adapter. The repository does not claim a universal A12+
  first-stage adapter.
- Public A11-and-earlier checkm8-era tools must not be assumed compatible with
  A12, A13, A14, A15, M1, or M2.
- Physical-device execution remains unverified unless exact-target session
  evidence is supplied.
- Ramdisk profile compatibility does not imply that every OS build boots.
  Exact product/build adapter evidence remains required.

## Validation

The 0.6.1b source is gated by release-version consistency checks, isolated host
tests, native harnesses, Clang analysis, deterministic build and conformance
stages, QEMU integration/smoke tests, archive verification, checksum
verification, and an extracted operational-package smoke test. Measured
results are recorded in [BUILD_VALIDATION.md](BUILD_VALIDATION.md) and
`validation-logs/non-qemu/`.
