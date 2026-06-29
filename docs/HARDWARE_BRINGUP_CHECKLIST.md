# Hardware bring-up checklist

## Before entry

- [ ] Monitor image hash verified by the loader
- [ ] Entry address matches the linked generic image
- [ ] Entry EL and page granule are accurate
- [ ] Stack and monitor memory are resident and non-overlapping
- [ ] Memory regions are sorted, non-overlapping, and attributed
- [ ] All metadata pointers lie inside described readable memory
- [ ] Console callback and context remain resident
- [ ] Interrupts are masked
- [ ] Watchdog will not reset the target during first boot

## First boot

- [ ] Banner and prompt appear
- [ ] `version` reports 0.5.0b
- [ ] `handoff` reports ABI v4
- [ ] `regions` matches the loader map
- [ ] `health` reports no stack, heap, module, or crash errors
- [ ] `platform-features` reports only implemented services

## Optional services

- [ ] Runtime input works without blocking forever
- [ ] Uptime advances at the expected rate
- [ ] Reboot and halt callbacks behave as documented
- [ ] FDT passes `dt-info` and resolves stdout/aliases
- [ ] Every decoded `reg` entry matches loader expectations
- [ ] Framebuffer geometry and format are correct before clearing
- [ ] IRQ handler installed before source enable
- [ ] Spurious and unhandled IRQ behavior tested
- [ ] Watchdog configure and kick tested with a conservative timeout
- [ ] Module policy rejects disallowed capabilities and over-budget images

## Evidence

- [ ] Serial transcript captured
- [ ] Handoff JSON and normalized copy retained
- [ ] Monitor, loader, FDT, and module hashes recorded
- [ ] Crash report captured for a deliberate test fault in a test-only image
- [ ] No target-specific secrets or personal data included in published diagnostics
