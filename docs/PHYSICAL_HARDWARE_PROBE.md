# Physical hardware probe image

`build-hardware-probe/fbr34ker-hardware-probe.bin` is the immutable, read-only
bring-up image retained in FBR34KER 0.6.0_beta. It accepts the same handoff-v4
contract as the generic monitor, but it permanently enforces defensive policy.

## Permanent restrictions

The probe image cannot unlock dynamic modules, framebuffer writes, IRQ delivery
changes, watchdog configuration, power actions, or reboot/halt callbacks.
`bringup-exit unlock` is deliberately rejected. It does not provide arbitrary
physical-memory reads or writes.

Additionally, the probe image unconditionally locks all three exploit
subsystems. The gating functions
`hardware_probe_kernel_patching_allowed()`,
`hardware_probe_secure_boot_bypass_allowed()`, and
`hardware_probe_persistence_allowed()` always return false when
compiled with `FBR34KER_PHYSICAL_PROBE_IMAGE=1`. Shell commands for
all three subsystems remain visible but report the locked state.

## Read-only commands

Useful commands include `probe-status`, `compatibility`, `exception-level`,
`system-registers`, `handoff-info`, `boot-modules`, `memory-map`,
`memory-check`, `device-tree-summary`, `services`, `console-services`,
`timer-frequency`, `timer-test`, `irq-controller`, `watchdog-services`, and
`framebuffer-info`.

## Console fallback

The generic platform chooses a loader service callback first, then a valid early
console callback, then a PL011 discovered through a validated FDT and a granted
MMIO region. Every emitted character is also retained in the bounded memory
console ring. Framebuffer and semihosting mirrors are never enabled implicitly
on a physical probe boot.

## QEMU immutability test

```bash
make probe-qemu-smoke
```

The test boots the probe through the separate QEMU handoff loader and proves the
probe prompt appears, metadata commands work, and unlock/module/display/IRQ/
watchdog mutations remain blocked.
