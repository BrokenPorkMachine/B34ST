# A12/A13 iRecovery workflow

FBR34KER 0.6.0_beta adds an optional host workflow for sending a validated recovery boot image through the `irecovery` utility from libirecovery. The workflow targets devices or development boards that the operator owns or is authorized to test.

## Security boundary

The included tooling does **not**:

- place a device into a compromised DFU state;
- trigger or package a SecureROM exploit;
- patch iBoot or bypass Image4 verification;
- personalize or forge Apple signatures;
- choose undocumented physical-memory addresses;
- claim that stock recovery mode accepts unsigned FBR34KER images.

A stock A12/A13 device normally enforces its secure-boot policy. The `--execute` path is therefore gated behind two explicit acknowledgements and is intended only for a separately established authorized loader environment.

## Install the optional transport

On macOS with Homebrew:

```sh
brew install libirecovery
```

Verify and match the connected device without sending data:

```sh
./fbr34ker irecovery verify --profile profiles/apple-a13-recovery.json
```

The family profiles gate the operation by CPID:

| Family | SoC | CPID | Profile |
|---|---:|---:|---|
| A12 | T8015 | `0x8015` | `profiles/apple-a12-recovery.json` |
| A12Z | T8028 | `0x8028` | `profiles/apple-a12x-recovery.json` |
| A13 | T8020 | `0x8020` | `profiles/apple-a13-recovery.json` |

The A12Z entry is marked experimental-profile-only.

## Dry run

A dry run validates the profile, device identity, image family, image hashes, size bounds, and intended command without sending anything:

```sh
./fbr34ker irecovery send \
  --profile profiles/apple-a13-recovery.json \
  --image build-apple/a13/boot.img \
  --dry-run \
  --device-info examples/a13-device-info.json
```

`--device-info` is intended for offline validation and testing. Omit it to query the connected device.

## Send only

```sh
./fbr34ker irecovery send \
  --profile profiles/apple-a13-recovery.json \
  --image build-apple/a13/boot.img \
  --authorized-session \
  --evidence runtime-artifacts/a13-send.json
```

Send-only is the default. It invokes `irecovery -f` after all local checks pass.

## Send and request execution

```sh
./fbr34ker irecovery send \
  --profile profiles/apple-a13-recovery.json \
  --image build-apple/a13/boot.img \
  --authorized-session \
  --execute \
  --acknowledge-unsigned-code \
  --boot-command bootx \
  --evidence runtime-artifacts/a13-boot.json
```

The allowed execution commands are `bootx`, `go`, and `memboot`. The profile default is `bootx`. The command is sent only after the file upload succeeds.

## Evidence

The optional evidence record includes the matched CPID, reported product/model, image hash, image format, profile ID, send/execute state, selected boot command, and the explicit security boundary. It does not contain device memory or payload contents.
