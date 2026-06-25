# Quick start

## Guided execution

From the project root, launch the goal-driven menu:

```sh
./scripts/B34ST
```

After installation, run `B34ST`. The lower-level `./fbr34ker` commands below
remain suitable for scripts and repeatable automation.

For an authorized, evidence-gated physical research-runtime workflow:

```sh
./scripts/B34ST research-runtime guided
```

This workflow requires an operator-supplied first-stage adapter or bridge and
exact-kernel evidence. It does not synthesize an exploit payload or infer a
jailbreak from textual command success.

## 1. Check the host

```sh
./fbr34ker doctor
```

## 2. Build and test

```sh
./fbr34ker build
./fbr34ker test
```

## 3. Build and run the exploit chain

```sh
make exploit-chain
```

See `build-exploit/exploit-summary.txt` for the capability summary.

## 4. Build A12/A13 images

```sh
make apple-boot-images
```

## 5. Inspect the selected image

```sh
./fbr34ker boot-image inspect build-apple/a12/boot.img --json
```

## 6. Install optional iRecovery support

```sh
brew install libirecovery
```

## 7. Query the connected device

```sh
./fbr34ker irecovery query
```

## 8. Dry-run the upload plan

```sh
./fbr34ker irecovery send \
  --profile profiles/apple-a12-recovery.json \
  --image build-apple/a12/boot.img \
  --dry-run
```

## 9. Upload in an authorized session

```sh
./fbr34ker irecovery send \
  --profile profiles/apple-a12-recovery.json \
  --image build-apple/a12/boot.img \
  --authorized-session \
  --evidence runtime-artifacts/a12-upload.json
```

Execution is intentionally separate. Read `docs/A12_A13_IRECOVERY.md` before adding `--execute`.

## A12/A13 bring-up simulator

```sh
./fbr34ker bringup run \
  --state-dir build-apple/quick-state \
  --device-info examples/a13-device-info.json \
  --profile profiles/apple-a13-recovery.json \
  --image build-apple/a13/boot.img \
  --authorized-session \
  --authorization-id authorized-local-session \
  --acknowledge-unsigned-code \
  --evidence build-apple/quick-evidence.zip
```
