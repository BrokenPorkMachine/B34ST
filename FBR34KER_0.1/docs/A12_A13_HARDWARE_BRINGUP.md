# Authorized A12/A13 hardware bring-up

## Read-only discovery

```sh
./fbr34ker device doctor \
  --profile profiles/apple-a13-recovery.json \
  --device-info examples/a13-device-info.json

./fbr34ker irecovery verify \
  --profile profiles/apple-a13-recovery.json \
  --device-info examples/a13-device-info.json
```

Omit `--device-info` only when `irecovery` is installed and an owned or otherwise authorized device is connected.

## Simulator evidence

`make apple-bringup-simulate` creates three deterministic bundles:

- `success-evidence.zip`
- `failure-evidence.zip`
- `recovered-evidence.zip`

The failure session injects a timer-stage failure, resets the adapter, proves authorization was invalidated, then reauthorizes and completes the next run.

## External adapter

```sh
./fbr34ker bringup run \
  --adapter-command /path/to/authorized-adapter \
  --state-dir runtime-artifacts/a13 \
  --device-info runtime-artifacts/a13-device.json \
  --profile profiles/apple-a13-recovery.json \
  --image build-apple/a13/boot.img \
  --authorized-session \
  --authorization-id your-session-id \
  --acknowledge-unsigned-code \
  --evidence runtime-artifacts/a13-evidence.zip
```

The adapter must report the actual writable/executable memory map. FBR34KER validates every explicit FBRI load and entry address against that map before upload. Metadata components with a zero load address remain adapter-assigned; the executable monitor cannot use a zero load address.

## Stages

The standard order is console, board inventory, memory map, timer, interrupts, watchdog, and boot evidence. Each stage is individually recorded. Failure can trigger a controlled reset, which always invalidates authorization.

## Evidence boundary

Evidence proves only what the selected adapter reports and what the host validates. A simulator result is not physical-device evidence. A recovery-mode query or successful file send is not proof that stock iBoot accepted or executed the monitor.
