# Handoff ABI v4

The handoff ABI is the only supported boundary between an external loader and the generic ARM64 monitor. The current structure appends v4 fields to the stable v1-v3 prefix; fields are never reordered.

## Entry contract

The loader calls:

```c
void fbr34ker_entry(const fbr34ker_handoff_t *handoff);
```

Before entry it must keep the monitor image, stack/heap backing, handoff object, region table, service table, FDT, and boot-module images resident. The loader must declare the actual exception level and translation granule. It must not reclaim described monitor memory.

## Required v4 fields

- magic, version 4, and complete structure size;
- monitor base and size;
- 1–128 sorted, non-overlapping memory regions;
- entry exception level 1–3;
- page granule 4 KiB, 16 KiB, or 64 KiB;
- optional platform service table v1 when callback services are supplied.

The monitor range must fit within a region of type `monitor` carrying read, write, and execute attributes.

## Region types

- `usable`: allocator-eligible memory intentionally offered to the monitor;
- `reserved`: resident metadata or memory unavailable for allocation;
- `mmio`: device range; must include the device attribute;
- `monitor`: image, stack, heap, and monitor-owned data;
- `framebuffer`: pixel backing memory.

Attributes are read, write, execute, device, and DMA. Regions must not overlap.

## Optional facilities

Flags activate device tree, framebuffer, runtime input, timer, power, platform services, and module policy. Each flag has corresponding pointer/callback consistency checks.

Timer and power callbacks remain in the v3 extension and are valid in a v4 object. The v4 service table adds bulk console I/O, flush, interrupt controller, framebuffer flush, and watchdog services.

## Module policy

A loader may restrict external FMBC modules with:

- capability allow mask;
- dynamic slot count, maximum 4;
- instruction budget, maximum 4096.

A module exceeding any policy value is rejected at load and rechecked before execution.

## Offline validation

```bash
python3 host/fbr34kctl.py handoff-template handoff.json
python3 host/fbr34kctl.py handoff-validate handoff.json --output normalized.json
```

This checks the logical design document. The monitor still validates the actual in-memory object at boot.

## 0.6.0_beta SDK and offline conformance workflow

Use `fbr34kctl handoff-template`, `handoff-validate`, and `loader-simulate` to produce the exact packed v4 structures before writing a physical loader. The generated callback stubs are deliberate traps and must never be used as live callbacks. A loader must reserve all monitor, metadata, DTB, module, framebuffer, stack, and heap ranges before entry.
