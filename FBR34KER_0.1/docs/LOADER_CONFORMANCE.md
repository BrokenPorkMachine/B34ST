# Loader conformance

The loader conformance report uses five explicit states:

- `supported` — valid and represented in the generated handoff plan
- `unsupported` — safely absent or intentionally unavailable
- `invalid` — malformed, contradictory, out of range, or uncovered
- `unsafe` — structurally valid but violates a safety policy
- `not-tested` — requires real execution or hardware observation

A report passes only when no required item is `invalid` or `unsafe`. Offline-only checks never promote runtime-only behavior to `supported`; callback execution, interrupt delivery, watchdog expiry, framebuffer visibility, and actual timer monotonicity remain `not-tested` until collected from a running monitor.

```bash
python3 host/fbr34kctl.py loader-check \
  build/loader-simulation/loader-conformance.json

python3 host/fbr34kctl.py loader-report \
  build/loader-simulation/loader-conformance.json
```

The JSON report is intended for CI, loader SDKs, and release evidence. Consumers should key on stable item identifiers and states rather than human-readable detail strings.
