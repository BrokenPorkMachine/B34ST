# Architecture

## Executable paths

### Direct QEMU

QEMU loads `build/fbr34ker.bin` at `0x40080000`. The platform uses PL011, the architectural timer, PSCI, GICv3, the memory console ring, and optional semihosting.

### Generic QEMU loader

QEMU loads the reference loader at `0x40080000` and the generic monitor at `0x80000000`. The loader constructs handoff ABI v4 using QEMU's DTB and transfers control with the handoff pointer in `x0`.

### External generic loader

An independently authorized loader may supply the same handoff ABI. Generic boots begin in restricted bring-up mode. The loader remains responsible for truthful memory ownership, callback containment, inherited translation/cache state, and service capability declarations.

## Entry sequence

1. Preserve `x0`.
2. Accept EL2 or EL1 entry; unsupported exception levels stop safely.
3. From EL2, configure AArch64 EL1h and timer access. QEMU-specific paths also enable the GICv3 system-register interface.
4. Install the linked stack and vectors, mask interrupts, and clear BSS while preserving `.crashlog`.
5. Validate the boot context and initialize FDT, platform services, console transports, exceptions, allocator, stack guards, logging, protocol, watchdog, modules, and hardware-probe policy.
6. Initialize the runtime architecture graph and expose its state through read-only diagnostics.
7. Enter the normal or restricted interactive monitor.

FBR34KER does not install an MMU. A loader must document inherited translation and cache state.

## Security-state models

Version 0.4.1 includes bounded in-memory models for patch, boot-policy, and
persistence concepts. They exist to validate interface shape, status output,
policy gates, event wiring, and failure handling. They do not modify target
memory, Apple trust policy, filesystems, or reboot state.

Release builds do not define `FBR34KER_ENABLE_SECURITY_MODEL`, so mutation
operations return failure. Immutable probe images remain locked regardless of
build options. A native harness verifies the release-default boundary.

## Runtime architecture graph

Version 0.4.1 retains an allocation-free orchestration layer with fixed compile-time capacities.

The lifecycle starts components across six ordered phases: early, core, platform, services, extensions, and interactive. Every component declares capability bits it requires and provides, plus bounded start and health callbacks. Duplicate component names, provided-capability collisions, failed starts, unresolved dependencies, and unhealthy components remain observable.

The built-in graph is:

1. `event-bus` — core phase; provides the event-journal capability.
2. `service-registry` — core phase; depends on the event bus.
3. `driver-manager` — platform phase; depends on the event bus and registry.
4. `platform-catalog` — services phase; registers and activates the logical platform-service catalog.

No heap allocation, dynamic native loading, scheduler, thread, or preemption dependency is introduced.

## Event journal

The event bus retains 32 fixed-size records and up to eight synchronous subscribers. Each record contains a monotonic sequence, event type, bounded source name, and two integer values. When full, the oldest record is overwritten and the overwrite count is retained. Recursive dispatch is rejected and counted rather than allowing unbounded callback recursion.

Events cover boot, component state, service state, driver state, bring-up mode,
module load/execute/unload transitions, and disabled security-model state.

## Service registry

The typed registry holds up to 16 services. Each entry records a bounded name and owner, interface version, platform-feature mask, current state, and transition count. States are absent, discovered, ready, degraded, failed, and disabled.

The initial platform catalog covers:

- console output and input
- monotonic timer
- interrupt controller
- framebuffer display
- watchdog
- power control
- semihosting console

Services are descriptions of already-authorized platform facilities; registry presence does not grant new hardware access.

## Driver manager

The logical driver manager holds up to 16 descriptors. Drivers declare priority, required platform-feature bits, an optional service dependency, a provided service, and optional probe/start/stop callbacks. Activation is deterministic and dependency-aware. Missing optional facilities become blocked, while probe/start failures become failed and propagate to the associated service. Shutdown is reverse ordered.

These are built-in logical adapters, not unrestricted loadable native drivers.

## Immutable hardware probe

When immutable-probe policy is active, mutation-capable framebuffer, interrupt, watchdog, and power facilities are removed from the effective driver feature set and their registry entries are marked disabled. The architecture diagnostics remain read-only.

## Layers

- `arch/arm64`: entry, vectors, and CPU helpers
- `kernel`: lifecycle, events, service/driver orchestration, shell, framing, FDT, crash handling, allocator, consoles, modules, kernel patching, secure boot bypass, and persistence
- `platform/qemu_virt`: PL011, timer, PSCI, GICv3, and semihosting
- `platform/generic_arm64`: handoff callback/FDT adapter
- `platform/gic.c`: compact GICv2/GICv3 implementation
- `loader/qemu_handoff`: executable reference loader
- `sdk`: standalone handoff-v4 builder, validator, matcher, examples, and tests
- `host`: compiler, transport, handoff schema, simulator, diagnostics, and release tooling
- `tests`: native, Python, direct-QEMU, and generic-loader QEMU tests

## Trust model

Loader pointers/callbacks and built-in native code are privileged. External FMOD modules are validated FMBC bytecode interpreted under capability and instruction limits. Hashes and CRCs provide integrity and error detection, not signer identity. Runtime architecture metadata improves ordering and observability; it is not a security boundary by itself.
