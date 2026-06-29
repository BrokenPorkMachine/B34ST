# FBR34KER 0.4.0 Beta release notes

FBR34KER 0.4.0 Beta focuses on reliable installed tooling, broader
Apple-family packaging, and a guided tethered-downgrade workflow with explicit
operator and adapter boundaries.

## Highlights

- Added a single guided tethered-downgrade flow for firmware selection,
  download or local-IPSW validation, SHA-256 evidence, plan review, and
  separately acknowledged execution.
- Defined the tether-adapter request/response contract and added an executable
  contract example that validates input but intentionally performs no device
  I/O.
- Documented public tooling categories such as Legacy iOS Kit, Semaphorin,
  palera1n, futurerestore, idevicerestore, and libirecovery without presenting
  any of them as a verified drop-in adapter for the current A12+ profiles.
- Added generic and exact-product recovery profiles for A14, A15, M1, and M2.
  Their generic boot images are included in builds, manifests, layout checks,
  and complete release archives.
- Restored explicit A12X/T8027 matching alongside A12Z/T8028 and expanded
  Apple-platform identification with M1/M2 constants and bounded MMIO-footprint
  probes.
- Fixed installed `forensics` and `cve` command routing.
- Fixed interactive QEMU sessions so they have no launcher timeout and do not
  inherit nonblocking terminal flags.
- Added macOS/Python TLS CA discovery for firmware-catalog access.
- Expanded the monitor formatter with field width, left alignment,
  zero-padding, and `size_t` conversion support.

## Release engineering

- Added a release-version consistency check covering firmware metadata, B34ST,
  host tools, modules, CI, branding, and packaging.
- Extended complete-package verification to require A14, A15, M1, and M2 boot
  image artifacts.
- Refreshed canonical non-QEMU validation evidence for 0.4.0.
- Updated CI artifact matching and all release roots to
  `FBR34KER_0.4.0_Beta`.

## Compatibility

The public protocol remains version 1, handoff ABI remains version 4, module
ABI remains version 3, FMOD remains version 1, and FMBC remains version 2.
Existing loaders and modules that conform to those interfaces do not require a
format migration for 0.4.0.

## Operational boundaries

- Default builds keep mutation paths disabled. `SECURITY_MODEL=1` is an
  explicit, separate lab build mode.
- FBRI images are external-loader containers, not Apple-signed IMG4 images and
  not directly compatible with stock iBoot.
- Tethered downgrade execution requires a separately installed,
  target-specific adapter. The repository does not claim a universal A12+
  first-stage adapter.
- Public A11-and-earlier checkm8-era tools must not be assumed compatible with
  A12, A13, A14, A15, M1, or M2 targets.
- Physical-device execution remains unverified unless a session contains the
  required exact-target evidence.

## Validation

The source tree is release-gated by the nine-stage non-QEMU verifier, the
QEMU-backed release gate, deterministic package verification, source syntax
validation, and release-version consistency validation. Exact results for this
candidate are recorded in [BUILD_VALIDATION.md](BUILD_VALIDATION.md) and
`validation-logs/non-qemu/`.
