# FBR34KER 0.6.1b Beta completeness and correctness audit

## Outcome

The 0.6.1b tree is prepared as a **Beta patch release** for deterministic QEMU
validation, external-loader integration, evidence-gated physical bring-up, and
guided tethered-downgrade planning.

The July 1 correctness remediation fixed the operational-build flag override,
Apple CPID drift, unsafe kernel-version scanning, ignored MMIO failures,
unbounded persistence offsets, false USB success reporting, stale release
metadata, and incomplete top-level test discovery.

## Audited release surfaces

- firmware, host, B34ST, module, CI, branding, manifest, and package versions;
- installed launcher routing and staged-install behavior;
- interactive QEMU timeout and terminal-flag handling;
- TLS certificate discovery for firmware catalog access;
- A12 through A15 and M1/M2 profile/build/manifest/package coverage;
- A12X/T8027 and A12Z/T8028 profile identity plus bounded Apple MMIO
  discrimination;
- A12/T8020, A13/T8030, and A14/T8101 identity consistency across every
  profile, example, host map, and firmware table;
- mutation-enabled apply/revert success and failure propagation;
- fail-closed PWNDFU, vendor-request, and monitor re-enumeration evidence;
- monitor formatting behavior and native regression coverage;
- tether-adapter discovery, execution contract, evidence, documentation, and
  public-tool compatibility guidance;
- deterministic source, complete, SDK, and operational archive validation.

## Security and evidence boundary

Default release builds leave mutation paths disabled. Security-model builds are
explicit lab artifacts and do not establish physical compatibility by
themselves. Immutable probe images remain locked.

The FBRI images require an external authorized loader and are not represented
as directly compatible with stock iBoot. Tethered-downgrade execution requires
a separately installed target-specific adapter; the included adapter example
performs no device I/O.

No profile is promoted to physical execution without exact-target identity,
image hash, memory map, stage results, adapter transcript, boot evidence, and
safe-reset evidence. Simulator and QEMU results remain labeled separately from
physical-device proof.

## Compatibility conclusion

The public protocol, handoff ABI, module ABI, FMOD, and FMBC versions are
unchanged. The release is a feature and reliability update rather than an ABI
break.
