# FBR34KER 0.2.3 Physical Validation Candidate validation

Validation date: 2026-06-24

## Validation model

The release is validated in nine isolated, bounded stages. Each stage preserves
its command, duration, log, and exit status before packaging. The evidence
model distinguishes simulator, persistent-bridge, QEMU, and physical-device
proof and refuses to promote a profile beyond the supplied evidence.

## Canonical gate

The complete nine-stage non-QEMU release gate passed in **40.572 seconds**.
It covered host readiness, staged installation and ABI checks, host tests,
monitor and SDK analysis, native harnesses, all release builds, conformance
simulations, manifest generation, and final layout/artifact verification.

The complete QEMU-backed release gate passed in **41.550 seconds**. It covered
host readiness, the full non-QEMU verifier, integration tests, runtime smoke,
generic-loader smoke, immutable-probe smoke, and diagnostics collection.

## Host validation

- **119 Python host tests:** 115 passed and 4 QEMU-dependent tests skipped.
- Coverage includes bridge sequencing, bounded chunk upload, exact product
  matching, device list/watch, evidence integrity, session replay, console
  capture, reset invalidation, profile maturity enforcement, physical
  attestation checks, and persistent-bridge recovery.
- **4 QEMU integration tests:** all passed in the dedicated integration stage.

## Native and analysis validation

- **29 native monitor/format/ABI/policy harnesses** plus the SDK loader-example
  harness, all passed.
- **50 Clang static-analysis units:** 47 monitor/loader units and 3 SDK units,
  with no findings.
- Additional compilation verification:
  - `kernel/kernel_patches.c` compiled without warnings
  - `kernel/secure_boot_bypass.c` compiled without warnings
  - `kernel/persistence.c` compiled without warnings
  - `kernel/command.c` with new exploit commands compiled without warnings
  - `kernel/main.c` with new init calls compiled without warnings
  - Full monitor link with 50 object files succeeded

## Release builds and evidence

- Direct QEMU monitor, generic ARM64 monitor, immutable probe, reference
  loader, SDK archive, and FMBC module builds passed.
- Deterministic A12, A12X/A12Z, and A13 FBRI images passed inspection.
- Deployment, one-shot bring-up, persistent-bridge integration, and Physical
  Validation Candidate conformance passed.
- Candidate evidence proves bridge-backed console and boot-evidence capture,
  four controlled failure classes, authorization invalidation after reset,
  and recovery after reauthorization.
- Security-model packaging (`make exploit-chain`, retained as a compatibility
  target) produces explicitly non-operational artifacts in `build-exploit/`.

## Evidence result

- `candidate_ready`: **true**
- Persistent-bridge console proof: **present**
- Controlled failure and recovery proof: **present**
- QEMU runtime proof: **present**
- Disabled security-model build proof: **present**
- Physical-device execution proof: **not present**
- `physical_validation_complete`: **false**

## Environment limits

`qemu-system-aarch64` 11.0.0 and `irecovery` 1.3.1 were available on the
packaging host. No physical A12/A13 device or external first-stage loader was
tested, so the release remains a validation candidate rather than a completed
physical validation.
