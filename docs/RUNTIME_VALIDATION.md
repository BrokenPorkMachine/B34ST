# Runtime validation design

## Goals

FBR34KER 0.6.2b validates failure handling without making host-only success look
like hardware proof. The design uses the same bounded runtime mechanisms in
native harnesses and the integration monitor while keeping failpoint control out
of ordinary release images.

## Transaction model

1. Components register before startup.
2. Lifecycle phases start in order after capability dependencies are satisfied.
3. Every successful start receives an activation sequence.
4. A real or injected failure marks the responsible component failed.
5. Active components are stopped in reverse activation order.
6. Provided capability bits are removed as each component rolls back.
7. A later architecture restart reconstructs the graph and may recover.

## Deterministic failpoints

Supported points are `component-start`, `driver-probe`, `driver-start`,
`service-register`, `event-publish`, and `timeout`. A failpoint can match a
bounded source name, wait for a specified number of checks, and fire a bounded
number of times. Status records checks, remaining injections, and total
injections.

## Simulated HAL

`kernel/hal_sim.c` provides a fixed-capacity model for:

- bounded console output
- monotonic millisecond advancement
- IRQ enable, raise, and acknowledgement
- framebuffer clear state
- watchdog configuration, kicking, and expiry
- shutdown/reset requests

The simulator has no allocator, threads, files, sockets, or external side
effects. It is intended for deterministic contract tests, not as a substitute
for emulator or board execution.

## QEMU validation profile

`profiles/qemu-runtime-validation.json` defines the `virt`/GICv3 machine,
integration image, required architecture capabilities, and the expected
rollback-then-recovery sequence. `scripts/qemu_smoke.py --runtime-validation`
performs these checks when `qemu-system-aarch64` is available:

1. Inspect healthy architecture and trace state.
2. Arm a one-shot component-start failure for `platform-catalog`.
3. Restart and require a failed transaction with rollback evidence.
4. Confirm the failpoint was consumed.
5. Restart again and require healthy recovery.
6. Inspect version-aware driver dependencies.

## Diagnostic export

`trace-json` emits retained structured trace records in a bounded JSON object.
`crash-json` exports the preserved crash report when one exists. The textual
commands remain available for interactive inspection.

## Evidence policy

Native simulation proves deterministic state-machine behavior. Offline loader
conformance proves structural compatibility. QEMU execution proves emulator
behavior only. Physical compatibility requires separate evidence from an
authorized target and must not be inferred from any earlier gate.
