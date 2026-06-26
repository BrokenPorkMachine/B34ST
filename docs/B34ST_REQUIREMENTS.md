# B34ST Unified Multi-Tool Requirements

## Overview
B34ST (B34KER/STAR) Runtime Authentication Tool for FBR34KER workflows. A unified interactive multi-tool providing access to all FBR34KER capabilities with full instrumentation.

## Functional Requirements

### 13 Category Menus
1. **System** - Version, doctor, build, test, clean
2. **Device** - Device info, detect, console, pwndfu
3. **USBliter8** - Pwn & Inspect, jailbreak, chain commands
4. **IPSW** - Catalog, download, inspect, upgrade, tethered downgrade
5. **Boot Image** - Build, inspect, verify, send to device
6. **Deployment** - Deploy, recover, inspect, modules
7. **Hardware** - Prepare, bringup, profile management
8. **Session** - Session tools, console, log management
9. **Validation** - Physical validation, candidate reports, evidence validation
10. **Release** - Package, gate, permissions, abi-check
11. **Module** - Compile, inspect, upload, execute
12. **Research Runtime** - Guided workflow, evidence validation
13. **B34ST** - Environment plan, toolkit info

### Core Features
- **Interactive Mode**: Full menu-driven interface with colored output
- **Non-interactive Mode**: Direct command execution for scripting
- **Session Instrumentation**: Every operation logged with timestamps
- **Evidence JSON**: Machine-readable output for each operation
- **Subprocess Integration**: Wraps existing tools (fbr34ker, scripts/*, host/*)

## Non-functional Requirements
- Python 3.11+ compatible
- No external dependencies beyond existing codebase
- TTY-aware output (colors only on terminal)
- Session artifacts in runtime-artifacts/b34st/b34stool/
- Exit code propagation from wrapped commands
