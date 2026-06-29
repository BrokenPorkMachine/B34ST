# Reference loader simulator

The 0.4.5b loader simulator is an **offline conformance and placement tool**. It does not exploit a device, execute the monitor, emulate peripherals, or call loader callbacks.

## Inputs

- an ELF64 little-endian AArch64 generic monitor image
- a validated handoff-v4 JSON design
- zero or more FMOD boot modules
- an output directory

## Validation

The simulator checks the ELF class, byte order, machine, loadable segments, entry point, segment alignment and permissions, granted-memory coverage, metadata placement, module placement, DTB header, callback declarations, and monitor/handoff ABI compatibility.

Executable general-purpose data/MMIO regions are classified as `unsafe`. Overlap, truncation, integer overflow, uncovered objects, invalid callbacks, or malformed structures are classified as `invalid`.

## Outputs

- `handoff-v4.bin` — packed handoff structure
- `memory-regions.bin` — packed region table
- `platform-services.bin` — packed platform-service table
- `callback-stubs.bin` — synthetic trap callbacks for placement only
- `boot-modules.bin` — packed boot-module table
- `normalized-handoff.json` — normalized input design
- `sparse-memory.json` — address, size, and source placement map
- `loader-conformance.json` — machine-readable report

Synthetic callbacks contain a deliberate trap followed by a return. A real loader must replace every advertised callback with a valid implementation before transferring control.

## Commands

```bash
make loader-simulate
make loader-check
```

Or invoke the host utility directly:

```bash
python3 host/fbr34kctl.py loader-simulate \
  --image build-generic/fbr34ker-generic.elf \
  --handoff examples/handoff-v4.json \
  --module build/modules/hello-dynamic.fmod \
  --output build/loader-simulation
```
