# Security policy

FBR34KER is a generic ARM64 research monitor, loader-contract testbed, bounded deployment simulator, and optional authorized recovery-image sender.

## Apple recovery boundary

The A12/A13 tooling operates only after a device is already visible to libirecovery in DFU or recovery mode. It does not create a compromised session or alter the device's secure-boot policy.

The adapter enforces:

- explicit profile selection;
- CPID-family matching;
- bounded image size;
- complete FBRI header, manifest, payload, and component hash validation;
- an explicit `--authorized-session` acknowledgement before upload;
- a second `--acknowledge-unsigned-code` acknowledgement before execution;
- an execution-command allow-list;
- upload success before any boot command;
- bounded subprocess timeouts;
- optional machine-readable evidence without payload or memory contents.

FBRI is a FBR34KER container, not an Apple IMG4 signature container. Stock iBoot acceptance is not claimed.

## FBDP deployment boundary

FBDP is not an access-control or exploit protocol. It is used only after an authorized development receiver exists. Receivers exposed beyond a trusted local development environment require their own mutual authentication, authorization, rate limiting, and transport security.

## Runtime boundary

Lifecycle, service, driver, event, board, MMIO, physical-memory, trace, and subscriber capacities are compile-time bounded. Immutable-probe mutation services remain disabled. The monitor does not expose an unrestricted MMIO or arbitrary physical-memory shell.

## Out of scope

- exploit delivery or DFU-entry triggers;
- boot-chain or Image4 signature bypass;
- iBoot or SecureROM patches;
- SEP attacks or credential extraction;
- kernel patching or persistence;
- device-specific protected-memory offsets;
- unrestricted MMIO or physical-memory upload/download;
- bypassing activation, ownership, passcodes, or user-data protections.

## First-stage adapter boundary (0.2.3)

The first-stage adapter is trusted code supplied by the operator. FBR34KER validates its ABI version, output size, device identity, memory-map shape, image hash, and explicit load/entry ranges, but cannot prove that an external adapter truthfully describes the device or enforces secure transport. Use only adapters you control and review.

Authorization is scoped to one adapter session generation. Every reset increments the generation and invalidates authorization. The simulator stores only a hash of the authorization identifier. External adapters must provide equivalent or stronger handling.

The adapter interface does not define a SecureROM exploit, signature bypass, DFU-entry mechanism, or arbitrary memory operation. Reports of adapters that silently add those capabilities should be treated as separate projects and reviewed independently.

## Persistent bridge boundary (0.2.3)

The persistent bridge is a local operator-controlled integration contract. It uses bounded JSON-lines messages, strictly increasing sequence numbers, a 1 MiB message limit, 128 KiB chunks, finite timeouts, and a 4096-message ceiling. It is not authenticated transport; a bridge exposed beyond a trusted local environment must add its own mutual authentication and encryption.

External physical sessions require exact product profiles by default. Broad family profiles remain available only for simulation or an explicit controlled-development override. FBR34KER validates the bridge-reported memory map but cannot prove that a third-party bridge reports it truthfully.

Session bundles contain device identifiers, hashes, console output, and crash evidence. Review them before sharing. They intentionally do not include uploaded payload bytes or arbitrary memory dumps.
