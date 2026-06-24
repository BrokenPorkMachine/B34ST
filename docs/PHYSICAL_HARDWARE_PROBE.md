# Physical hardware probe image

`build-hardware-probe/fbr34ker-hardware-probe.bin` is the immutable, read-only
bring-up image retained in FBR34KER 0.2.3. It accepts the same handoff-v4
contract as the generic monitor, but it permanently enforces defensive policy.

## Permanent restrictions

The probe image cannot unlock dynamic modules, framebuffer writes, IRQ delivery
changes, watchdog configuration, power actions, or reboot/halt callbacks.
`bringup-exit unlock` is deliberately rejected. It does not provide arbitrary
physical-memory reads or writes.

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
