# Guarded MMIO

`kernel/mmio.c` provides typed 8, 16, 32, and 64-bit reads and writes. An access
is accepted only when:

- the subsystem is initialized;
- the address range is contained in one registered window;
- the address is naturally aligned for the requested width;
- the window permits the width and requested read/write operation;
- a write is not attempted under immutable-probe policy; and
- the backend reports success.

Registered windows cannot overlap. Each carries read, write, and optional
probe-safe permissions. The default backend uses volatile AArch64 accesses and
memory barriers. Native tests replace it with a deterministic memory backend.

`mmio_update32` performs a guarded read-modify-write. The shell exposes only
inventory and statistics; it does not expose arbitrary address reads or writes.

## Explicit probe fault containment

`mmio_probe_read32` is the only MMIO path permitted to recover from a register
read fault. It first verifies that the window is read-enabled and marked
probe-safe, then arms a single-use recovery record immediately around one
32-bit AArch64 load. If that load raises a synchronous data abort, the exception
handler records the ESR/FAR, advances the saved ELR by one fixed-width AArch64
instruction, and resumes with a failed probe result.

This mechanism does not contain SError, instruction aborts, unrelated data
aborts, writes, or normal MMIO accesses. Those remain fail-stop and enter the
ordinary crash path. The recovery sequence is cross-built and statically
analyzed in this release; QEMU and physical execution evidence is still pending.
