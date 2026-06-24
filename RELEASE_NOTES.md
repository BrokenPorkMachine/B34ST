# FBR34KER 0.2.3 release notes

Version 0.2.3 is the **Physical Validation Candidate**. It freezes the physical-integration workflow around evidence rather than adding another hardware access mechanism.

The release classifies proof as simulator, QEMU, persistent bridge, console, boot evidence, or physical runtime. Profile promotion is performed into a new output file and is rejected when the supplied evidence cannot support the requested maturity.

New operator commands provide read-only preparation, safety checklists, evidence validation, and stage-specific failure explanations. A deterministic candidate generator proves successful bridge-backed console and boot-evidence capture, observes four controlled failure classes, confirms authorization invalidation after reset, and verifies recovery after reauthorization.

QEMU-capable CI executes the existing runtime, generic-loader, and immutable-probe profiles. Local packaging remains honest when QEMU is unavailable: the candidate report records the missing proof instead of treating a skipped emulator as a pass.

## Evidence boundary

The bundled reference bridge uses the deterministic simulator. It proves the persistent bridge contract, console/evidence pipeline, failure handling, and recovery policy. It does not prove execution on an Apple device.

Physical validation is complete only when both a passing QEMU gate and a non-simulator physical-runtime evidence bundle are supplied. No exploit, secure-boot bypass, or stock-iBoot patch is included.
