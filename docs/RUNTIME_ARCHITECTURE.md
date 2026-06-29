# Runtime architecture

FBR34KER 0.4.4b retains the explicit, allocation-free runtime architecture added
in 0.1.6 and makes its activation transactional and restartable.

## Lifecycle graph

`kernel/lifecycle.c` processes components through ordered early, core, platform,
services, extensions, and interactive phases. Each descriptor declares required
and provided capabilities plus start, stop, and health callbacks. Duplicate
names, capability collisions, failed starts, and unresolved dependencies remain
observable.

The built-in graph contains `trace`, `event-bus`, `service-registry`,
`driver-manager`, and `platform-catalog`. Successful starts receive monotonically
increasing activation sequence numbers. On failure, active components stop in
reverse sequence and enter `rolled-back`; normal shutdown enters `stopped`.

## Event and trace planes

The event bus retains 32 fixed-size records and supports up to eight synchronous
subscribers. The structured trace retains 64 records with category, action,
status, bounded source, and two numeric values. Architecture events are mirrored
into trace records. Both structures overwrite oldest entries deterministically.

## Service registry

Services have bounded names and owners, versions, feature masks, states, and
transition counts. Compatible lookup checks name, minimum version, required
features, and readiness. The platform catalog covers console output/input,
monotonic time, interrupt control, framebuffer, watchdog, power, and
semihosting. Immutable-probe mutation services remain disabled.

## Driver manager

Drivers declare priority, required platform features, a provided service, and an
optional dependency contract consisting of service name, minimum version, and
required features. Missing optional hardware is blocked rather than failed;
probe/start failures propagate to service state. Stops run in reverse activation
order.

## Validation boundaries

Fault injection is compile-time gated by `FBR34KER_ENABLE_FAULT_INJECTION`.
Mutation-capable shell commands are separately gated by
`FBR34KER_ENABLE_TEST_COMMANDS`. Release monitor images include the trace and
status paths but not the ability to arm failures or restart the graph from the
shell.

The layer does not add native dynamic drivers, threads, preemption, arbitrary
MMIO, exploit delivery, or device-specific protected-memory knowledge. All
capacities are fixed at compile time.
