# Changelog

## 0.2.3 -- Physical Validation Candidate

- Added bounded, non-operational state models for patch, boot-policy, and
  persistence concepts.
- Added status commands for the disabled security models.
- Added a release-default compile gate and native regression harness proving
  mutation paths remain unavailable.
- Added Makefile targets (kernel-patches, secure-boot-bypass, persistence,
  exploit-chain, start-exploit, establish-persistence)
- Added shell scripts (scripts/start_exploit.sh, scripts/establish_persistence.sh)
- Added gating functions in hardware_probe for security-model access control
- Added documentation for the security models and their non-operational scope
- Removed ephemeral documentation (11 stale files consolidated)
- Updated the threat model to exclude target mutation and persistence

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
