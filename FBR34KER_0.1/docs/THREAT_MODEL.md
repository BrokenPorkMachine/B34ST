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

Security-concept state models are compiled for status visibility but their
mutation gates are disabled in release builds. They do not perform target
memory writes, signature-policy changes, installation, hiding, or persistence.

## In-scope capabilities

- deterministic monitor and loader simulation;
- bounded deployment-protocol validation;
- bridge, session, and evidence validation;
- read-only hardware preparation;
- non-operational security-state modeling.

## Non-goals

FBR34KER does not protect a compromised host, recover user data, authenticate
remote untrusted receivers, or make an unknown physical memory map safe.
