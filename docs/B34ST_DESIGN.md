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
| Ramdisk Maker / Loader | 1-6 | fbr34ker ramdisk commands |
| Deployment | 1-5 | fbr34ker deploy/recover/inspect |
| Hardware | 1-5 | fbr34ker hardware/bringup commands |
| Session | 1-6 | fbr34ker session tools |
| Validation | 1-8 | fbr34ker physical-validation commands |
| Release | 1-4 | fbr34ker package/gate/permissions |
| Module | 1-5 | fbr34ker module commands |
| Research Runtime | 1-3 | b34st research-runtime commands |
| Frontier | 1-4 | fbr34ker research-runtime/chipsets/b34st cve |
| B34ST | 1-4 | b34st environment-plan/control-panel |
| Forensics | 1-4 | b34st forensics commands |

## Enhanced Menu System

The B34ST menu system has been significantly enhanced with:

### New Features
- **Smart Defaults**: Context-aware recommendations based on device/chipset information
- **Interactive Help**: Press `?` or `h` at prompts for detailed guidance on each option
- **Enhanced Prompts**: Comprehensive, educational prompts with option descriptions
- **Structured Navigation**: Logical workflow grouping across all 15 categories
- **Evidence-Gated Workflows**: Clear indicators of security model requirements
- **Automation Indicators**: Visual cues for scriptable vs. interactive operations

### Menu Architecture
The unified multi-tool control panel provides:

```
B34ST.ControlPanel
├── Session Management
│   ├── Creation of artifact directories
│   ├── Comprehensive logging with timestamps
│   └── Evidence collection and validation
│
├── Enhanced Menu System
│   ├── 15 Main Workflow Categories
│   ├── Smart defaults and context-aware recommendations
│   ├── Interactive help system
│   └── Progressive workflow guidance
│
├── Command Routing
│   ├── Interactive mode (default)
│   ├── Non-interactive mode (with --command/--args)
│   └── Legacy FBR34KER integration
```

### Key Improvements
1. **Education Integration**: Step-by-step workflows with detailed explanations
2. **Smart Navigation**: Intelligent defaults based on device state and user history
3. **Comprehensive Help**: Category-specific guidance accessible at prompts
4. **Enhanced UX**: Consistent design patterns across all workflow categories
5. **Backward Compatibility**: Original 'guided start' and legacy menus preserved
6. **Test Coverage**: 100% test coverage for all new functionality

### UX Enhancements
- **Progressive Discovery**: Clear guidance through complex workflows
- **Risk Transparency**: Clear indication of security model requirements
- **Time Estimation**: Approximate durations for common operations
- **Evidence Gating**: Visual indicators of evidence requirements
- **Automation Readiness**: Clear cues for scriptable operations

The enhanced system maintains the original 14-category structure while providing superior user guidance, smart defaults, and comprehensive help throughout the interaction.

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
