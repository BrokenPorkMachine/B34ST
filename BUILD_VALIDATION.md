# FBR34KER 0.2.3 Physical Validation Candidate validation

Validation date: 2026-06-24

## Validation model

The release is validated in nine isolated, bounded stages. Each stage preserves its command, duration, log, and exit status before packaging. The evidence model distinguishes simulator, persistent-bridge, QEMU, and physical-device proof and refuses to promote a profile beyond the supplied evidence.

## Canonical gate

The complete nine-stage non-QEMU release gate passed in **435.170 seconds**. It covered host readiness, staged installation and ABI checks, host tests, monitor and SDK analysis, native harnesses, all release builds, conformance simulations, manifest generation, and final layout/artifact verification.

## Host validation

- **111 Python host tests:** 107 passed and 4 QEMU-dependent tests skipped.
- Coverage includes bridge sequencing, bounded chunk upload, exact product matching, device list/watch, evidence integrity, session replay, console capture, reset invalidation, profile maturity enforcement, physical attestation checks, and persistent-bridge recovery.

## Native and analysis validation

- **28 native monitor/format/ABI harnesses** plus the SDK loader-example harness, all passed.
- **50 Clang static-analysis units:** 47 monitor/loader units and 3 SDK units, with no findings.
- The public ABI check covers FBDP v1, first-stage adapter v1, persistent bridge v1, FBRI v1, physical-session schema v1, and physical-validation claim schema v1.

## Release builds and evidence

- Direct QEMU monitor, generic ARM64 monitor, immutable probe, reference loader, SDK archive, and FMBC module builds passed.
- Deterministic A12, A12X/A12Z, and A13 FBRI images passed inspection.
- Deployment, one-shot bring-up, persistent-bridge integration, and Physical Validation Candidate conformance passed.
- Candidate evidence proves bridge-backed console and boot-evidence capture, four controlled failure classes, authorization invalidation after reset, and recovery after reauthorization.
- **56 release-manifest artifacts** have internal SHA-256 entries.
- ELF layout, FBRI parsing, release manifest, internal checksums, and artifact-content checks passed. Archive CRC, external SHA-256, source-boundary, and independent reproduction checks are performed after packaging.

## Evidence result

- `candidate_ready`: **true**
- Persistent-bridge console proof: **present**
- Controlled failure and recovery proof: **present**
- QEMU runtime proof: **not present locally**
- Physical-device execution proof: **not present**
- `physical_validation_complete`: **false**

## Environment limits

`qemu-system-aarch64` and `irecovery` were not installed on the packaging host. Four emulator tests were skipped. No physical A12/A13 device or external first-stage loader was tested, so the release is a validation candidate rather than a completed physical validation.
