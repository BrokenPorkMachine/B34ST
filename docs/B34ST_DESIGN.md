# B34ST Unified Multi-Tool Design

## Architecture

```
b34stool.py (unified entry point)
    │
    ├── Session class (inherits from control_panel.py pattern)
    │   ├── session directory creation
    │   ├── session.log for all operations
    │   └── evidence/*.json for operation results
    │
    ├── Menu System
    │   ├── main_menu() - 14 category selection
    │   ├── submenu handlers for each category
    │   └── run_and_log() - wrap subprocess calls
    │
    └── Command Router
        ├── Interactive mode (default)
        └── Non-interactive mode (--command, --args)
```

## Session Instrumentation

Every operation writes:
1. **Timestamps**: ISO format timestamps for start/end
2. **Command logging**: Full command line to session.log
3. **Evidence JSON**: Structured output in session directory
4. **Duration tracking**: Timing for each operation

Session path format: `runtime-artifacts/b34st/b34stool/YYYYMMDD-HHMMSS-microseconds/`

## Menu Categories

| Category | Options | Commands Invoked |
|----------|---------|------------------|
| System | 1-8 | fbr34ker version/doctor/build/test/clean |
| Device | 1-7 | fbr34ker device/detect/console/pwndfu/exploit |
| USBliter8 | 1-5 | scripts/run_exploit.py with chain |
| IPSW | 1-9 | fbr34ker ipsw catalog/download/etc |
| Boot Image | 1-5 | fbr34ker boot-image commands |
| Deployment | 1-5 | fbr34ker deploy/recover/inspect |
| Hardware | 1-5 | fbr34ker hardware/bringup commands |
| Session | 1-6 | fbr34ker session tools |
| Validation | 1-8 | fbr34ker physical-validation commands |
| Release | 1-4 | fbr34ker package/gate/permissions |
| Module | 1-5 | fbr34ker module commands |
| Research Runtime | 1-3 | b34st research-runtime commands |
| B34ST | 1-4 | b34st environment-plan/control-panel |

## Evidence Schema

```json
{
  "schema_version": 1,
  "operation": "category/action",
  "timestamp": "ISO-8601",
  "command": ["list", "of", "args"],
  "exit_code": 0,
  "duration_ms": 1234,
  "output_summary": "brief description or error"
}
```
