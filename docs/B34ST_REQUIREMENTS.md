# B34ST Unified Multi-Tool Requirements

## Overview
B34ST (B34KER/STAR) Runtime Authentication Tool for FBR34KER workflows. A unified interactive multi-tool providing access to all FBR34KER capabilities with full instrumentation.

## Functional Requirements

### 16 Category Menus
1. **System** - Version, doctor, build, test, clean
2. **Device** - Device info, detect, console, pwndfu
3. **USBliter8** - Pwn & Inspect, jailbreak, chain commands
4. **IPSW** - Catalog, download, inspect, upgrade, tethered downgrade
5. **Boot Image** - Build, inspect, verify, send to device
6. **Ramdisk Maker / Loader** - Target plan, deterministic FBRD, inspection, adapter load
7. **Deployment** - Deploy, recover, inspect, modules
8. **Hardware** - Prepare, bringup, profile management
9. **Session** - Session tools, console, log management
10. **Validation** - Physical validation, candidate reports, evidence validation
11. **Release** - Package, gate, permissions, abi-check
12. **Module** - Compile, inspect, upload, execute
13. **Research Runtime** - Guided workflow, evidence validation
14. **Frontier** - Guided research, chipsets, CVE planning
15. **B34ST** - Environment plan, toolkit info
16. **Forensics** - Guided acquisition and evidence verification

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
