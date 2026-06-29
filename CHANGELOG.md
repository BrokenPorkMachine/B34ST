# Changelog

## 0.4.1 -- Beta

- Consolidated the latest Apple-platform fixes into a patch release, including
  explicit A12X/T8027 and A12Z/T8028 identity handling plus M1/M2 platform
  identifiers.
- Retained bounded MMIO-footprint SoC discrimination and corrected FBRI
  inspection for families that share a numeric header identifier.
- Retained generated header dependencies so version changes cannot reuse stale
  monitor, generic, probe, SDK, or reference-loader objects.
- Retained the operational-package fix that includes the host runtime required
  by the packaged CLI while excluding firmware/platform source.
- Updated firmware, host tools, B34ST, modules, CI, manifests, packages, tests,
  manuals, release evidence, and user documentation to `0.4.1-beta`.
- Confirmed no public protocol, handoff, module ABI, FMOD, or FMBC format
  changes.

## 0.4.0 -- Beta

- Added a guided tethered-downgrade workflow with explicit planning, exact
  firmware selection, SHA-256 verification, evidence output, execution
  acknowledgements, and a documented external-adapter contract.
- Documented public adapter/tooling categories and their compatibility limits;
  added a safe executable contract example that performs no device I/O.
- Added A14, A15, M1, and M2 generic and exact-product recovery profiles and
  included their deterministic boot images in builds, manifests, layout
  verification, and complete release archives.
- Restored explicit A12X/T8027 alongside A12Z/T8028 profile matching and added
  M1/M2 platform identifiers plus MMIO-footprint SoC discrimination.
- Fixed installed `forensics` and `cve` command routing, interactive QEMU
  timeout handling, inherited nonblocking terminal flags, and macOS TLS CA
  discovery for firmware catalog access.
- Expanded the monitor formatter with width, left-alignment, zero-padding, and
  `size_t` support, with a native regression harness.
- Added release-version consistency validation across firmware, host tools,
  B34ST, modules, CI, and packaging metadata.
- Refreshed release documentation, canonical validation evidence, and package
  contents for the 0.4.0 Beta.

## 0.3.0 -- Beta

- Completed full completeness/correctness audit of all exploit source code and
  documentation (kernel/usbliter8_exploit.c, jailbreak.c, kernel_patches.c,
  command.c, apple_platform.h) — verified all header-declared functions have
  implementations, all subsystem constants are correct, and security-model gating
  is properly layered
- Fixed 4 categories of source-documentation discrepancy: corrected T8027→T8028
  (A12Z) across all docs and RELEASE_NOTES; added T8110 (A15) to all SoC tables;
  fixed 8 profile JSON files with wrong CPIDs; fixed CPID tables in
  A12_A13_IRECOVERY.md and KERNEL_PATCHING.md (expanded 3→7 SoCs)
- Completed B34ST audit covering all 11 Python modules, 5 docs, 4 test files,
  and entry-point scripts — fixed 5 discrepancies: disclaimer broadened to A12+,
  added missing research-runtime subcommand to no-args help, removed duplicate
  version banner, broadened package docstrings, expanded compatible_profiles
  from 4→8 entries, corrected category count 13→14
- Fixed 6 test file CPIDs (0x8030→0x8020, 0x8020→0x8015) to match SoC hardware
- Fixed scripts/package_release.py verify_archive — PRIVATE_SOURCE_DIRS check now
  gated on operational=True only
- Added CHIP_ID_T8028 (0x8028U) and CHIP_ID_T8110 (0x8110U) to apple_platform.h
- Updated all documentation to reflect A12+ (7 SoC) coverage with iOS version
  gating notes (SPTM/TXM only on 27+)
- All C harnesses (29) and non-QEMU Python tests (420+) passing
- Version bump to 0.3.0; release promoted from Physical Validation Candidate to Beta

## 0.2.2 -- Physical Device Integration Preview

- Added a persistent, sequence-checked JSON-lines first-stage bridge protocol.
- Added bounded chunked image transfer, console polling, and reset-driven
  reauthorization.
- Added deterministic physical-integration session bundles with checksums,
  console, trace, boot, and crash records.
- Added device list/watch diagnostics and exact-product A12/A12X/A13 profile
  groups.
- Added session inspect/replay, crash decode, trace timeline, and evidence
  integrity verification.
- Added a reference simulator bridge and success/failure/recovery release
  evidence.

## 0.2.1 -- Authorized A12/A13 Hardware Bring-Up

- Added first-stage adapter ABI v1, public C descriptor, JSON schema,
  simulator, and bounded external-command interface.
- Added runtime memory-map validation, per-session authorization, staged
  diagnostics, reset invalidation, and deterministic evidence bundles.
- Added device doctor, read-only irecovery verify, bringup run/collect/recover,
  and evidence comparison commands.
- Hardened the FBRI parser and added a deterministic malformed-image corpus.
- Added profile maturity/evidence fields and release-gated success, failure,
  and recovered A13 simulation evidence.

## 0.2.0 -- A12/A13 Developer Preview

- Froze the public protocol, handoff, module, board, service, driver,
  boot-image, and recovery-profile interface versions.
- Added deterministic FBRI v1 boot.img and raw companion bundles for A12/T8020,
  experimental A12X/A12Z/T8027, and A13/T8030 profiles.
- Added CPID-gated, send-only-by-default irecovery query/upload tooling with
  explicit authorization and unsigned-code execution acknowledgements.
- Added the unified fbr34ker subcommand CLI with stable JSON output and legacy
  flag aliases.
- Added board, driver, module, and transport-adapter SDK scaffolding plus a
  public C boot-image header.
- Added ABI compatibility checking, release signature verification, and
  reproducible archive comparison.
- Added installation helpers, Bash/Zsh completions, a manual page,
  compatibility matrix, threat model, and migration guide.
- Updated CI to install QEMU, build Apple-family boot bundles, run emulator
  profiles when available, and preserve boot-image evidence.

## 0.1.9 -- Transport, Deployment & Evidence

- Added the bounded FBDP v1 framing contract with sequence numbers, CRC-32,
  capability negotiation, and 4 KiB chunks.
- Added validated deployment profiles with non-overlapping allow-listed loader
  and payload regions.
- Added a persistent file-backed development target and a loopback socket
  receiver for end-to-end transport testing.
- Added explicit authorization, resumable transfers, idempotent retry handling,
  per-artifact SHA-256 commit, and controlled monitor start.
- Added serial, TCP, Unix-socket, and in-process simulator transport adapters.
- Added deterministic deployment evidence bundles, a release deployment
  simulation, and fault tests for dropped/corrupted responses and interrupted
  sessions.

## 0.1.8 -- Board Bring-Up

- Added bounded runtime board descriptions with built-in QEMU, loader-handoff,
  validated-DTB, and generic fallback selection.
- Added typed allow-listed MMIO with alignment, permission, width, overlap,
  immutable-policy, and backend checks.
- Added fixed-capacity physical page ownership with platform and FDT reservation
  import.
- Added staged text/JSON bring-up reports and guarded read-only active probing.
- Added persistent boot-stage evidence and a host-side raw-record decoder.
- Expanded lifecycle orchestration from five to nine managed components and
  added native board/MMIO/memory/evidence harnesses.

## 0.1.7 -- Runtime Validation

- Added transactional lifecycle startup, reverse-order rollback, shutdown, and
  restart.
- Added minimum-version and feature-aware service dependencies.
- Added a 64-record structured trace ring with bounded JSON export.
- Added compile-time-gated deterministic fault injection and recovery tests.
- Added a fixed-capacity simulated console/timer/IRQ/framebuffer/watchdog/power
  HAL.
- Added a QEMU rollback-then-recovery validation profile and smoke sequence.
- Added structured crash JSON export and integration-only validation commands.
- Expanded native and host release gates for rollback, tracing, HAL, and
  failpoints.

## 0.1.6 -- Runtime Architecture

- Added a deterministic six-phase component lifecycle.
- Added a fixed-capacity runtime event journal.
- Added a typed, versioned service registry.
- Added a dependency-aware platform driver manager.
- Added architecture, component, service, driver, and event diagnostics.
- Added native tests and bounded parallel static analysis.

## 0.1.5 -- Hardware-Port SDK

- Added a standalone freestanding C11 loader SDK with public ABI-v4 headers.
- Added compile-time ABI size and offset assertions.
- Added bounded handoff builder, structural validator, and profile matcher.
- Added minimal, callback-console, and framebuffer loader examples.
- Added deterministic FBHB binary handoff build, inspect, and round-trip tools.
- Added a formal loader conformance matrix and report generator.
- Added loader callback ownership, alignment, recursion, failure, and
  soft-budget guards.
- Added the read-only service-health monitor command.
- Added conservative probe-result import into reviewed board profiles.
- Added SDK and binary-handoff artifacts to manifests, CI, and deterministic
  packages.
- Strengthened SDK validation for callback flags, IRQ callback sets,
  framebuffer ownership, module policy, boot modules, and reserved fields.

## 0.1.4 -- Physical Hardware Bring-Up Preview

Added the immutable physical-hardware probe, board profiles, compatibility
matrices, bounded transcript recording, and defensive external-loader policy.

## 0.1.3 -- Emulated Hardware Platform Pack

Added the executable QEMU handoff loader, direct GIC drivers, console
transports, framebuffer console, expanded FDT support, and generic-loader
smoke testing.

## 0.1.2 -- Loader Bring-Up Preview

Added the offline loader simulator, conformance reports, restricted bring-up
shell, and metadata-only hardware diagnostics.
