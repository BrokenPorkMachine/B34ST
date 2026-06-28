# FBR34KER 0.3.0 release notes

Version 0.3.0 is the **Beta** release. It incorporates the results of a
full completeness/correctness audit of all exploit source code, documentation,
and the B34ST framework, with all identified discrepancies resolved.

## Audit results

- **Source-code audit** — Verified all header-declared functions have implementations
  across kernel/usbliter8_exploit.c, jailbreak.c, kernel_patches.c, command.c, and
  apple_platform.h. Confirmed 14-state jailbreak state machine, 6 secure boot bypass
  types, 8 persistence hook types, 7-SoC × 2-iOS-version kernel patch tables, and
  layered SECURITY_MODEL gating (compile-time `#ifdef` + runtime `_allowed()` checks)
- **Documentation audit** — Corrected T8027→T8028 (A12Z), added T8110 (A15) to all
  SoC tables, fixed CPID tables in A12_A13_IRECOVERY.md and KERNEL_PATCHING.md
  (expanded 3→7 SoCs), corrected iOS 18→17+ version gating
- **Profile audit** — Fixed 8 profile JSON files with wrong CPIDs (A12 had A13's 0x8020,
  A13 had A14's 0x8030, A12X had 0x8027 instead of A12Z's 0x8028)
- **Test audit** — Fixed 6 test file CPIDs to match SoC hardware values
- **B34ST audit** — Audited all 11 Python modules, 5 docs, 4 test files, entry-point
  scripts; fixed 5 discrepancies (disclaimers, subcommand listing, compatible_profiles,
  category count, duplicate version banner)
- **Build-system fix** — scripts/package_release.py verify_archive: PRIVATE_SOURCE_DIRS
  check gated on operational=True only

## Platform support

- A12 (T8015), A13 (T8020), A14 (T8030), A12Z (T8028), M1 (T8103), A15 (T8110),
  M2 (T8112) across iOS 16/17+
- SPTM bypass on iOS 27+ only; TXM bypass on iOS 27+ only
- Full boot chain: DFU → USBliter8 exploit → kernel task → jailbreak → boot-args
  injection → AMFI/CoreTrust bypass → SEP bridge → SSH ramdisk

## Changes from 0.2.3

- Source code is truth — all documentation and profiles corrected to match kernel
  implementation
- Added CHIP_ID_T8028 (0x8028U) and CHIP_ID_T8110 (0x8110U) to apple_platform.h
- B34ST compatible_profiles expanded from 4 to 8 entries
- All C harnesses (29) and non-QEMU Python tests (420+) verified passing
- Release promoted from Physical Validation Candidate to Beta
