# Kernel-patch state model

This module is a bounded, in-memory state model for validating status
reporting, policy gates, event wiring, and failure handling.

It does not write target memory, modify page tables, replace syscall or
interrupt handlers, change privilege level, or hook a secure monitor.

Release builds do not define `FBR34KER_ENABLE_SECURITY_MODEL`; therefore
registration, apply, revert, and escalation operations return failure. The
native `security_model_harness` verifies that boundary.

The `kernel-patches status` shell command may be used to inspect the inactive
model. Other subcommands are rejected by the release policy gate.
