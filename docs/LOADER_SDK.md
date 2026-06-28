# Loader SDK integration guide

FBR34KER 0.3.0 publishes a standalone loader SDK under `sdk/`. Its purpose is
to let an authorized ARM64 loader construct a versioned handoff without copying
private monitor declarations.

## Boot flow

```text
loader establishes CPU/memory state
  -> reserves monitor, metadata, stack, DTB, modules, and callback code
  -> builds a sorted non-overlapping region map
  -> fills optional services and policy
  -> validates the handoff
  -> cleans/synchronizes caches as required by the platform
  -> branches to the generic monitor entry with x0 = handoff address
  -> monitor validates everything again and enters restricted bring-up mode
```

## Minimal integration

1. Initialize `fbr34ker_handoff_builder_t` with the loaded monitor range.
2. Add regions in strictly ascending order.
3. Ensure the monitor is covered by a `MONITOR` region with read/write/execute.
4. Add optional FMOD boot modules and platform services.
5. Set the expected EL, page granule, identifiers, DTB, framebuffer, and policy.
6. Call `fbr34ker_handoff_builder_finalize`.
7. Relocate the handoff and its referenced tables into final loader-owned memory.
8. Run `fbr34ker_handoff_validate_sdk` on the final structure.
9. Transfer control only after platform cache/TLB requirements are satisfied.

The examples in `sdk/examples/` show minimal, callback-console, and framebuffer
configurations. They intentionally use harmless host callbacks and do not
perform boot-chain manipulation.

## Memory ownership example

```text
0x40000000..0x4007ffff  loader code/metadata, readable+executable
0x40080000..0x400fffff  loader data, readable+writable
0x80000000..0x807fffff  FBR34KER monitor, readable+writable+executable
0x80800000..0x80ffffff  monitor-owned heap/stack, readable+writable
0x90000000..0x900fffff  optional framebuffer, readable+writable
```

Actual addresses are platform choices. Regions must not overlap, callback code
must be in declared readable/executable memory, and every referenced metadata or
module range must be loader-owned and readable.

## ABI lifecycle

- The `magic`, `version`, and `structure_size` fields are mandatory.
- ABI v4 is the current SDK target and has a fixed 284-byte packed layout.
- Reserved fields must remain zero.
- Readers reject unknown flag/capability bits.
- New compatible fields may only be appended under a new ABI version.
- Existing field meaning, width, and offset will not be silently changed.
- A loader must reject a monitor requiring an ABI newer than it implements.

## Defensive requirements

Physical ports must boot the immutable probe or restricted generic mode first.
Modules, framebuffer writes, IRQ mutation, watchdog changes, and power actions
remain locked until the operator reviews the reported platform state. No loader
integration requires arbitrary physical-memory commands or firmware patching.
