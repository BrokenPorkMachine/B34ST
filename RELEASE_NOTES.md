# FBR34KER 0.2.3 release notes

Version 0.2.3 is the **Physical Validation Candidate**. It freezes the
physical-integration workflow around evidence and includes disabled,
non-operational state models for security-policy testing.

## Security-model scope

- Patch, boot-policy, and persistence concepts are represented as bounded
  in-memory state models.
- Release builds keep all mutation paths disabled.
- The models do not modify target memory, Apple trust policy, filesystems, or
  reboot state.

## Evidence boundary

The bundled reference bridge uses the deterministic simulator. It proves the
persistent bridge contract, console/evidence pipeline, failure handling, and
recovery policy. It does not prove execution on an Apple device.

The security models are compile-time gated and disabled in release builds.
Immutable probe images are unconditionally locked.

## Documentation changes

- Removed 11 ephemeral documentation files
- Added docs/KERNEL_PATCHING.md, docs/SECURE_BOOT_BYPASS.md,
  docs/PERSISTENCE.md, docs/EXPLOIT_CHAIN.md
- Updated threat model, security policy, and audit report with explicit
  non-operational boundaries
