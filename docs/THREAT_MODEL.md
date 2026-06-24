# Threat model

## Trusted inputs

- project source and reviewed release artifacts;
- user-selected family profile;
- an operator-owned or explicitly authorized target;
- an already established recovery/DFU communication session;
- optional stage-0, DTB, and board data supplied by the authorized port owner.

## Untrusted inputs

- device query text;
- boot images from outside the release;
- profile JSON;
- DTBs and modules;
- serial/socket traffic;
- persisted deployment state and evidence files.

## Controls

The host tools bound file sizes, validate schemas, reject unsafe paths and integer ranges, verify hashes before use, match CPIDs, allow-list commands, require explicit authorization acknowledgements, and use finite timeouts. The runtime uses fixed capacities and validates handoff, board, MMIO, memory, module, and protocol structures before use.

## Non-goals

FBR34KER does not attempt to defeat Apple's secure boot, authenticate remote untrusted receivers, protect a compromised host, recover user data, or make an unknown physical memory map safe.
