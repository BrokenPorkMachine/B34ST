# B34ST connected-device workflow

Launch the source-tree UI with:

```sh
./scripts/B34ST
```

After installation, run `B34ST`.

## Dashboard fields

B34ST queries normal-mode devices through `ideviceinfo` and recovery/DFU
devices through `irecovery`. The dashboard displays:

- device name and product identifier;
- connection mode and board model;
- reviewed launch firmware for supported project devices;
- current firmware and build when lockdownd exposes them;
- latest signed firmware and build from the configured IPSW catalog;
- matching exact recovery profiles;
- actions currently available and why blocked actions are unavailable.

Current firmware is normally unavailable in DFU/recovery mode. B34ST labels it
as unavailable rather than guessing.

## Action workflow

Every device action opens a preparation page containing:

1. availability and the device-specific reason;
2. required hardware, software, storage, backup, and authorization materials;
3. the complete operational sequence;
4. a how-to-proceed note;
5. an explicit confirmation before execution.

External commands inherit the terminal so their prompts and progress remain
visible. When they exit, B34ST records the exit status and transcript, returns
to the UI, and refreshes device and firmware state.

## Upgrade

Signed upgrades require:

- a recent backup;
- a matching Apple-hosted IPSW;
- a catalog record reporting the firmware as signed;
- `idevicerestore`;
- owner authorization and an execution confirmation.

B34ST runs an `idevicerestore --no-action` preflight before offering execution.
A data-preserving update is requested by default. The firmware itself may
force an erase restore if it lacks a customer-upgrade identity.

## Erase restore

Erase restore adds `idevicerestore --erase`. This is intentionally separate
from upgrade because it destroys user data. Backups and Find My requirements
are shown before execution.

## Tethered downgrade

Select **Guided tethered downgrade**. The guide accepts a local IPSW or lists
unsigned Apple catalog targets for download, validates the exact product and
manifest, checks the external adapter executable, displays a human-readable
readiness plan, and saves JSON evidence before execution is offered.

Unsigned firmware is never sent through the signed stock restore path.
Execution requires a separately installed, reviewed external adapter
implementing `schemas/tethered-downgrade-adapter-v1.json`. If no adapter is
configured, the guide stops successfully after planning and explains how to
continue. B34ST does not bundle a target-specific adapter.

The adapter is a target-specific executable—a program, script, or reviewed
wrapper around lab boot tooling—that communicates with the device in
DFU/recovery mode and performs the external boot sequence. It is not the IPSW,
USB cable, `idevicerestore`, or a universal B34ST component. B34ST validates
and orchestrates; the adapter performs the device-side boot work and returns a
JSON result.

A tethered runtime is not persistent. The external boot chain must run again
after every restart.

See `docs/TETHERED_DOWNGRADE.md` for the complete operator and adapter
contract.

## Ramdisk maker and loader

For an exact-profile device in DFU/recovery, select **Guided ramdisk maker /
loader**. The guide records the exact iOS/iPadOS/macOS version and build,
packages prepared ramdisk, kernelcache, DeviceTree, and optional boot-chain
files into a deterministic `.fbrd`, and verifies every component hash.

Loading is plan-only by default. Execution requires a separately installed
target/build-specific adapter implementing
`schemas/ramdisk-adapter-v1.json`, exact owner authorization, and a second
execution confirmation. Current A12–A15/M1–M2 profiles are simulated and are
not blanket proof that every OS build boots.

See `docs/RAMDISK_MAKER_LOADER.md` for supported products, components,
examples, the adapter contract, and troubleshooting.

## Failure and return behavior

B34ST cannot guarantee external Apple services, cables, USB controllers,
third-party adapters, or restore tools will succeed. It guarantees the local
workflow behavior:

- no hidden fallback from signed restore to unsigned restore;
- no target-changing operation without confirmation;
- external exit status is captured;
- logs remain in the B34ST session directory;
- control always returns to B34ST after the external process exits;
- refreshing the dashboard recalculates the next valid actions.
