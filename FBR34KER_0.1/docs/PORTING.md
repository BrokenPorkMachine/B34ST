# Porting FBR34KER to an authorized ARM64 platform

1. Reserve resident memory for the generic monitor, handoff workspace, FDT, services, and optional modules.
2. Produce a sorted, non-overlapping ownership map with explicit attributes.
3. Document the actual entry EL, MMU state, cache state, and translation granule.
4. Implement bounded console output first.
5. Validate a handoff-v4 JSON design and run the offline conformance suite.
6. Use `examples/generic_loader/loader_adapter.c` as the neutral adapter reference.
7. Transfer control to the generic entry with the handoff pointer in `x0`.
8. Remain in restricted mode while checking `handoff-info`, `memory-check`, `services`, `console-test`, and `timer-test`.
9. Add runtime input, timer, and power callbacks.
10. Add FDT, framebuffer, interrupt controller, and watchdog one service at a time.
11. Collect `hardware-diagnostics` before using `bringup-exit unlock`.

## Interrupt choices

A port may provide IRQ callbacks, describe a supported GICv2/GICv3 in the FDT, or stay polling-only. Do not enter with interrupt delivery enabled. For GICv3, the previous exception level must permit EL1 access to the ICC system-register interface.

## Framebuffer

Grant only a validated framebuffer-owned region. Ensure cache visibility and implement `framebuffer_flush` when writes are not automatically coherent with scanout.

## Address contract

The packaged generic image links at `0x80000000` and is not self-relocating. A different base requires a matching linker configuration or an external relocation design.

This repository intentionally contains no exploit-specific entry mechanism or protected-memory manipulation.
