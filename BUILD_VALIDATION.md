# FBR34KER 0.6.0_beta Beta validation

Validation date: 2026-06-30

## Result

The 0.6.0_beta Beta release preparation passed the canonical non-QEMU gate, the
complete QEMU-backed release gate, deterministic package construction,
checksum verification, and an extracted operational-package smoke test.

## Canonical gates

- **Non-QEMU gate:** all 10 stages passed in **43.985 seconds**.
- **QEMU-backed release gate:** all 7 stages passed in **63.822 seconds**.
- **Host suite:** **466 tests passed**; 4 QEMU-dependent tests were skipped in
  the isolated non-QEMU run and executed by the integration stage.
- **Version consistency:** all **35 active release surfaces** matched
  `0.6.0_beta-beta`.
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
- The release manifest identifies version `0.6.0_beta`,
  channel `beta`, source ID `0.6.0_beta-beta`, and release root
  `B34ST_0.6.0_beta_Beta`.
- Deployment, bring-up, persistent-bridge, failure-matrix, reset-invalidation,
  and recovery-after-reauthorization simulations passed.

## Package validation

The following deterministic archives were built and verified:

- `B34ST_0.6.0_beta_Beta_source.zip`
- `B34ST_0.6.0_beta_Beta_complete.zip`
- `B34ST_0.6.0_beta_Beta_sdk.zip`
- `B34ST_0.6.0_beta_Beta_operational.zip`

All four SHA-256 sidecars passed `shasum -a 256 -c`. The operational archive
was extracted and successfully ran:

- `fbr34ker version`
- `fbr34ker abi-check`
- `fbr34ker forensics list-profiles`
- `fbr34ker cve stats`
- the tether-adapter contract example
- the 35-surface version-consistency check

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