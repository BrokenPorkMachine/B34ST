# FBR34KER 0.4.4b Beta release notes

FBR34KER 0.4.4b Beta is a patch release based on the merged 0.4.0 Beta tree. It
packages the latest Apple-platform, boot-image, build-dependency, and
operational-archive fixes under one consistent release identity.

## Patch-release highlights

- Adds a guided exact-profile ramdisk maker/loader for A12–A15/M1–M2 iPhone,
  iPad, and Apple silicon Mac products. It creates deterministic
  hash-verified FBRD bundles and remains plan-only until a reviewed
  target/build-specific external adapter is explicitly authorized.
- Preserves explicit A12X/T8027 matching alongside A12Z/T8028.
- Preserves M1/T8103 and M2/T8112 platform identifiers and bounded
  MMIO-footprint SoC discrimination.
- Correctly validates A12X and A12Z FBRI manifests even though those families
  share a numeric header identifier.
- Tracks generated C header dependencies so metadata changes rebuild direct,
  generic, probe, SDK, and reference-loader objects instead of reusing stale
  binaries.
- Includes required public host runtime modules in the operational archive so
  extracted `fbr34ker`, forensics, CVE, IPSW, TLS, and adapter workflows remain
  functional.
- Requires the complete archive to contain A14, A15, M1, and M2 recovery
  artifacts in addition to A12, A12X/A12Z, and A13.

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

0.4.4b does not change the public binary interfaces:

- protocol: 1
- handoff ABI: 4
- module ABI: 3
- FMOD: 1
- FMBC: 2

Loaders and modules that conform to the 0.4.0 interfaces require no migration.

## Operational boundaries

- Default builds keep mutation paths disabled. `SECURITY_MODEL=1` remains a
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

The 0.4.4b source is gated by release-version consistency checks, isolated host
tests, native harnesses, Clang analysis, deterministic build and conformance
stages, QEMU integration/smoke tests, archive verification, checksum
verification, and an extracted operational-package smoke test. Measured
results are recorded in [BUILD_VALIDATION.md](BUILD_VALIDATION.md) and
`validation-logs/non-qemu/`.
