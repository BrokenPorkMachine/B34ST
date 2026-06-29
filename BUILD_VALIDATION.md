# FBR34KER 0.4.5b Beta validation

Validation date: 2026-06-28

## Result

The 0.4.5b Beta release preparation passed the canonical non-QEMU gate, the
complete QEMU-backed release gate, deterministic package construction,
checksum verification, and an extracted operational-package smoke test.

## Canonical gates

- **Non-QEMU gate:** all 9 stages passed in **43.985 seconds**.
- **QEMU-backed release gate:** all 7 stages passed in **63.822 seconds**.
- **Host suite:** **444 tests passed**; 4 QEMU-dependent tests were skipped in
  the isolated non-QEMU run and executed by the integration stage.
- **QEMU integration:** all **6 tests passed**.
- **Version consistency:** all **20 active release surfaces** matched
  `0.4.5b-beta`.
- **Source validation:** 142 Python files and 23 shell files passed syntax
  validation.

The QEMU-backed gate covered host readiness, the full non-QEMU verifier,
integration tests, runtime smoke, generic-loader smoke, immutable-probe smoke,
and diagnostics collection.

## Native and analysis validation

- 30 native C harnesses passed, including formatter, crypto, boot-image,
  handoff, lifecycle, MMIO, physical-memory, runtime-recovery, bridge, and
  security-model coverage.
- The generic-loader example compiled successfully.
- Clang static analysis passed without findings across 56 monitor/loader files
  and 3 SDK files.
- Header dependency files are now generated for monitor, SDK, and reference
  loader objects; changing release metadata correctly invalidates previously
  built objects.

## Release builds and evidence

- Direct QEMU monitor, generic ARM64 monitor, immutable hardware probe,
  reference loader, SDK library/examples, FMBC module, and the explicit
  security-model build passed.
- Deterministic FBRI bundles for A12, A12X/A12Z, A13, A14, A15, M1, and M2
  passed inspection and manifest validation.
- The release manifest contains 72 artifacts and identifies version `0.4.5b`,
  channel `beta`, source ID `0.4.5b-beta`, and release root
  `FBR34KER_0.4.5b_Beta`.
- Deployment, bring-up, persistent-bridge, failure-matrix, reset-invalidation,
  and recovery-after-reauthorization simulations passed.

## Package validation

The following deterministic archives were built and verified:

- `FBR34KER_0.4.5b_Beta_source.zip`
- `FBR34KER_0.4.5b_Beta_complete.zip`
- `FBR34KER_0.4.5b_Beta_sdk.zip`
- `FBR34KER_0.4.5b_Beta_operational.zip`

All four SHA-256 sidecars passed `shasum -a 256 -c`. The operational archive
was extracted and successfully ran:

- `fbr34ker version`
- `fbr34ker abi-check`
- `fbr34ker forensics list-profiles`
- `fbr34ker cve stats`
- the tether-adapter contract example
- the 20-surface version-consistency check

## Evidence boundary

- `candidate_ready`: **true**
- QEMU runtime proof: **present**
- Controlled failure and recovery proof: **present**
- Physical-device execution proof: **not present**
- `physical_validation_complete`: **false**

No physical Apple device or target-specific A12+ tether adapter was used.
Simulator and QEMU results do not establish physical-device compatibility.

## Validation environment

- Python 3.13.4
- Homebrew Clang/LLD 22.1.4
- QEMU 11.0.0
- GNU Make 3.81
- irecovery 1.3.1
