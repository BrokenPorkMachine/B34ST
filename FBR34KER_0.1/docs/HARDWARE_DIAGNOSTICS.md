# Hardware diagnostics bundle

`fbr34kctl hardware-diagnostics` collects a bounded, privacy-preserving evidence package from a running monitor.

Collected data can include:

- monitor/platform version information
- normalized handoff summary
- owned-memory region descriptions
- platform-service availability
- memory-map validation result
- FDT metadata and compatibility strings
- bounded timer/console diagnostics and console-transport state
- platform, IRQ, and watchdog self-test output
- framebuffer metadata and FDT `/chosen` output routing
- monitor log ring
- preserved crash report

The collector does not request arbitrary memory reads and writes `sensitive_memory_included: false` into its summary. Individual unsupported commands are recorded rather than aborting the entire collection.

```bash
python3 host/fbr34kctl.py hardware-diagnostics \
  --unix build/fbr34ker.sock \
  --output hardware-diagnostics
```

The directory and deterministic ZIP can be attached to a bug report. Review logs before public sharing because loader-provided labels or device-tree strings may still identify a board or local configuration.
