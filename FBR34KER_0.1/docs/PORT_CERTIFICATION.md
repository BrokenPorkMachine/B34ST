# Port certification checklist

A loader/board pair is not considered compatible merely because a handoff blob
parses. Certification proceeds in layers.

## Offline conformance

```sh
python3 host/fbr34kctl.py loader-conformance \
  --handoff handoff.fbhb \
  --memory-map memory.json \
  --profile board.json \
  --report conformance.json
```

Required offline results:

- ABI layout: PASS
- container integrity: PASS
- memory ownership: PASS
- monitor executable ownership: PASS
- profile exception level: PASS
- profile required callbacks: PASS or explicitly unsupported by the profile

`NOT TESTED`, `LOCKED`, and `UNSUPPORTED` are never promoted to PASS without
runtime evidence.

## Runtime probe

1. Boot the immutable hardware-probe image.
2. Capture the first 30 seconds and export metadata-only diagnostics.
3. Confirm exception level, memory map, DTB, timer, console, IRQ, watchdog, and
   framebuffer status.
4. Confirm `service-health` has no repeated failures or disabled required
   service.
5. Import reviewed evidence into a new profile; do not overwrite the original.
6. Re-run profile and conformance checks.

## Certification outcome

- `PASS`: structurally valid and demonstrated at runtime.
- `PARTIAL`: usable subset, with documented missing/untested functions.
- `FAIL`: unsafe or incompatible; do not launch the unrestricted monitor.

Certification never covers exploit delivery, signature bypasses, protected
memory modification, or arbitrary device extraction.
