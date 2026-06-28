# Kernel patching subsystem

## Overview

The kernel patching subsystem provides per-SoC kernel patch offset tables for
Apple A12/A13/A14/A12Z/A15/M1/M2 across iOS 16 and iOS 17+. It supports
registration, application, reversion, and privilege escalation operations on
the modeled patch state. iOS 18 is detected via the iOS 17+ version string
scanner (Darwin 23.x).

## Supported SoCs and offsets

| SoC | Target | iOS versions | Offsets |
|-----|--------|-------------|---------|
| T8015 | A12 | 16, 17+ | amfi, task_for_pid, privilege, mount_root, codesign, sandbox, pe_debugger, cs_enforcement |
| T8020 | A13 | 16, 17+ | amfi, task_for_pid, privilege, mount_root, codesign, sandbox, pe_debugger, cs_enforcement |
| T8030 | A14 | 16, 17+ | amfi, task_for_pid, privilege, mount_root, codesign, sandbox, pe_debugger, cs_enforcement |
| T8028 | A12Z | 16, 17+ | amfi, task_for_pid, privilege, mount_root, codesign, sandbox, pe_debugger, cs_enforcement |
| T8103 | M1 | 16, 17+ | amfi, task_for_pid, privilege, mount_root, codesign, sandbox, pe_debugger, cs_enforcement |
| T8110 | A15 | 16, 17+ | amfi, task_for_pid, privilege, mount_root, codesign, sandbox, pe_debugger, cs_enforcement |
| T8112 | M2 | 16, 17+ | amfi, task_for_pid, privilege, mount_root, codesign, sandbox, pe_debugger, cs_enforcement |

## Build modes

**Default build (`make`):** Mutation paths disabled. `kernel-patches apply|revert|escalate` return failure.

**Operational build (`make SECURITY_MODEL=1 build-operational`):** All mutation paths active. The
`kernel-patches` commands perform full state transitions on the kernel patch model.

## Shell commands

```
kernel-patches [status|apply|revert|escalate]
```

- `status` — Show registered patches, SoC target, and current state
- `apply` — Apply all registered kernel patches to the active state model
- `revert` — Revert all applied patches
- `escalate` — Escalate privileges via the privilege_offset patch

## Event bus integration

Kernel patch operations publish `kernel-patch-*` events for each lifecycle
transition (apply, revert, escalate, failure).
