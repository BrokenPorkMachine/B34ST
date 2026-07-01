# Secure boot bypass subsystem

## Overview

The secure boot bypass subsystem provides six bypass types for modeling Apple
secure boot policy evasion. Each bypass type has independent activation, deactivation,
and status tracking within the state machine.

## Bypass types

| Type | Description |
|------|-------------|
| `image4-sig` | Image4 signature verification bypass |
| `cert-chain` | Certificate chain validation bypass |
| `ap-ticket` | APTicket validation bypass |
| `shsh-blob` | SHSH blob verification bypass |
| `iboot-auth` | iBoot authentication bypass |
| `boot-manifest` | Boot manifest validation bypass |

## Build modes

**Default build (`make`):** Physical writes are disabled; operations update the bounded state model.

**Operational build (`make SECURITY_MODEL=1 build-operational`):** All bypass operations active.
Each bypass type can be individually activated, forgiven (deactivated), or inspected.

## Shell commands

```
secure-boot-bypass [status|activate|forgive|manifest]
```

- `status` — Show enabled/disabled state for all 6 bypass types
- `activate <type>` — Enable a specific bypass type
- `forgive <type>` — Disable a specific bypass type
- `manifest` — Show the full boot manifest state
