# Board bring-up workflow

The default architecture startup runs metadata-only diagnostics and records one
bounded result for each major subsystem. Inspect them with:

```text
board-info
mmio-map
physical-memory
bringup-report
boot-evidence
```

Machine-readable forms are available through `board-json`, `bringup-json`, and
`boot-evidence-json`.

`hardware-inventory probe acknowledge` requests an active read-only probe. It
reads only registered windows carrying the probe-safe flag. The immutable probe
image rejects the request, and FDT-discovered windows are not probe-safe unless
a trusted profile explicitly says otherwise. A fault during the single armed
32-bit probe read is returned as a failed diagnostic; normal MMIO faults remain
fail-stop. This recovery path still requires emulator or physical execution
evidence.

A bring-up result distinguishes pass, fail, skipped, and blocked. Skipped means
the service is optional or absent; blocked means policy prevented the operation.
A successful host or emulator report must not be represented as physical-device
evidence.
