# Executable QEMU generic loader

The 0.6.2b reference path tests handoff ABI v4 with actual AArch64 execution.

## Images

- `build-loader/fbr34ker-qemu-loader.bin` links at `0x40080000`.
- `build-generic/fbr34ker-generic.bin` links at `0x80000000`.
- QEMU supplies its DTB to the loader in `x0`.

The loader creates a sorted nine-region ownership map, a 1024x768 XRGB8888 framebuffer, callback console/timer/power/watchdog services, module policy, and validated FDT metadata. It prints `LDR` and calls the generic image with the handoff pointer in `x0`.

## Running

```bash
make generic-qemu-run
make generic-qemu-smoke
```

The smoke runner captures raw/decoded serial evidence and machine-readable step results.

## EL and GIC handling

QEMU enters the loader at EL2. The loader enables the GICv3 system-register interface at EL2 before transferring control. The generic monitor then performs its normal EL2-to-EL1 transition and discovers the distributor/redistributor from QEMU's DTB.

## Deliberate limitations

The virtual watchdog records configure/kick operations; it does not reset QEMU. The framebuffer is bounded RAM used to validate rendering, not a QEMU display device. These services verify ABI behavior without pretending to model hardware side effects.
