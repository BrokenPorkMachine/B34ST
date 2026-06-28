# Persistence subsystem

## Overview

The persistence subsystem provides eight hook types for modeling post-exploit
persistence deployment. Each hook type has independent state tracking within a
fixed-capacity 16-hook model. Maximum hidden storage: 64KB.

## Hook types

| Type | Description |
|------|-------------|
| `boot-hook` | Boot-time execution hook |
| `launchd-plist` | Launchd property list persistence |
| `kext` | Kernel extension loading |
| `hidden-storage` | Concealed storage allocation |
| `payload-deploy` | Payload deployment mechanism |
| `tamper-resist` | Tamper detection resistance |
| `ota-persist` | OTA update survivability |
| `evasion` | Detection evasion |

## Build modes

**Default build (`make`):** All mutation paths disabled. `deploy|activate|evade` return failure.
`make establish-persistence` generates a text inventory of the modeled concepts.

**Operational build (`make SECURITY_MODEL=1 build-operational`):** All persistence mutations active.

## Shell commands

```
persistence [status|deploy|activate|evade]
```

- `status` — Show all registered hooks and their current state
- `deploy <type>` — Register and deploy a new persistence hook
- `activate` — Activate all pending persistence hooks
- `evade` — Remove all active persistence hooks
