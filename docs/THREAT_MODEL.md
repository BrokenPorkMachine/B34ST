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

The host tools bound file sizes, validate schemas, reject unsafe paths and
integer ranges, verify hashes before use, match CPIDs, allow-list commands,
require explicit authorization acknowledgements, and use finite timeouts. The
runtime uses fixed capacities and validates handoff, board, MMIO, memory,
module, and protocol structures before use.

Security state models are compile-time gated by `FBR34KER_ENABLE_SECURITY_MODEL`.
The default build (`make`) disables mutation paths for safe testing; the
operational build (`make SECURITY_MODEL=1 build-operational`) enables the full
exploit chain including kernel patching, secure boot bypass, and persistence
deployment on the modeled state.

## In-scope capabilities

- USBliter8 DWC3 firmware exploit chain for A12+ (PWNDFU, vendor memory access, image loading);
- kernel patching with per-SoC offset tables (amfi, privilege, codesign, sandbox, etc.);
- secure boot bypass engine (6 bypass types: Image4 sig, cert chain, APTicket, SHSH, iBoot auth, manifest);
- persistence deployment engine (8 hook types, 16 max hooks, 64KB hidden storage);
- deterministic monitor and loader simulation;
- bridge, session, and evidence validation;
- read-only hardware preparation.

## Non-goals

FBR34KER does not protect a compromised host, recover user data, authenticate
remote untrusted receivers, or make an unknown physical memory map safe.
