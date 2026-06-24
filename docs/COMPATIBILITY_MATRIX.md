# Compatibility matrix

| Target or workflow | Status in 0.2.3 | Evidence |
|---|---|---|
| Linux/macOS-compatible host toolchains | Validated | Cross-builds, isolated host modules, native harnesses, static analysis |
| QEMU `virt` | Profiles included; local emulator unavailable | Four tests discovered and skipped |
| A12/T8020 FBRI packaging | Validated | Deterministic image and parser checks |
| A12X/A12Z/T8027 FBRI packaging | Experimental | Deterministic image and parser checks |
| A13/T8030 FBRI packaging | Validated | Deterministic image and parser checks |
| Device list/watch and exact-profile matching | Offline validated | Host fixtures and exact product-group tests |
| One-shot first-stage adapter ABI v1 | Simulator validated | Existing adapter tests and C ABI harness |
| Persistent bridge protocol v1 | Simulator validated | Chunked upload, sequencing, console, reset, recovery tests |
| Physical-integration evidence bundles | Validated | Deterministic success/failure/recovery bundles and checksum verification |
| Real `irecovery` USB session | Not tested locally | `irecovery` unavailable on validation host |
| Stock iBoot execution | Unsupported/unclaimed | No IMG4 signing or signature bypass included |
| Physical A12/A13 monitor execution | Not tested | Requires an operator-supplied authorized first stage |
