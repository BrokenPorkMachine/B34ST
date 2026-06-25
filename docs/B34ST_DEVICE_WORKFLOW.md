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

Unsigned firmware is never sent through the signed stock restore path. B34ST
first produces a tethered downgrade plan. Execution requires a reviewed
external adapter implementing `schemas/tethered-downgrade-adapter-v1.json`.

A tethered runtime is not persistent. The external boot chain must run again
after every restart.

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
