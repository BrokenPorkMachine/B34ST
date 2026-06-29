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

For targeted IPSW workflows, launch B34ST and select option 7. Downloads are
restricted to HTTPS Apple domains. Signed upgrades use `idevicerestore`;
for unsigned targets choose **Guided tethered downgrade**. The guide validates
the IPSW and saves a plan even when no external adapter is configured.
Execution requires a separately installed target-specific adapter: an
executable program/script that communicates with the device in DFU/recovery
mode and performs the external boot sequence. It is not the IPSW, cable, or
`idevicerestore`. See `docs/TETHERED_DOWNGRADE.md`.

The initial B34ST screen automatically inspects the connected device and shows
only actions valid for its current mode and available evidence.

For a prepared recovery/research ramdisk, use the guided maker/loader:

```sh
./fbr34ker ramdisk guide
```

It supports exact-profile A12–A15/M1–M2 iPhone, iPad, and Apple silicon Mac
products, produces a deterministic `.fbrd`, and creates a plan-only load
request. A separately installed target/build-specific adapter is required for
physical loading. See `docs/RAMDISK_MAKER_LOADER.md`.

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

## 10. Full boot chain: USBliter8 → iOS kernel + SSH ramdisk

This section shows the conceptual boundary between FBR34KER and external
patchfinder/boot tooling. External project references are not verified
compatibility claims. An exact product/OS/build plan and reviewed adapter are
required before physical use.

### Phase 0 — Hardware setup (first time only)

Review `docs/USBLITER8_HARDWARE_GUIDE.md` for recommended hardware (the
**Waveshare RP2350 USB-A** is strongly recommended). Ensure your USB host
controller is capable and you have a data-capable USB-A to Lightning cable.
B34ST can guide you through this:

```sh
./scripts/B34ST usbliter8
```

Select hardware preparation; each step can be individually skipped.

### Phase 1 — Build FBR34KER operational image

```sh
make build-operational
```

### Phase 2 — Put device in DFU mode

Connect via USB, hold Power + Volume Down for 10s, release Power, hold
Volume Down for 5s. Verify:

```sh
irecovery -q | grep CPID    # Should show 0x8015 (A12), 0x8020 (A13), etc.
```

### Phase 3 — Apply USBliter8 DWC3 exploit (FBR34KER)

```sh
python3 scripts/run_exploit.py --monitor build-exploit/fbr34ker-operational.bin
```

This loads FBR34KER into physical DRAM via DWC3 vendor requests and executes
it. The monitor boots and re-enumerates as a CDC ACM + DFU composite device.

### Phase 4 — Connect to monitor console

```sh
python3 -c "
from host.usb_serial import USBConsole
c = USBConsole(); c.open()
print(c.read_until_prompt(timeout=10.0))
c.run_command('secure-boot-bypass forgive', timeout=10.0)
c.run_command('kernel-patches apply', timeout=10.0)
c.run_command('kernel-patches escalate', timeout=10.0)
"
```

### Phase 5 — Patch iBSS/iBEC (usbliter8-iboot-patchfinder)

```sh
python3 usbliter8-iboot-patchfinder/patch.py \
  --ibss ibss.dump \
  --ibec ibec.dump \
  --ctrr-unlock \
  --boot-args "amfi=0xff cs_enforcement_disable=1"
```

### Phase 6 — Apply SPTM bypass if iOS 27+ (usbliter8-sptm-patchfinder)

```sh
python3 usbliter8-sptm-patchfinder/patch.py --sptm sptm.dump
```

### Phase 7 — Apply TXM bypass if iOS 27+ (usbliter8-txm-patchfinder)

```sh
python3 usbliter8-txm-patchfinder/patch.py --txm txm.dump
```

### Phase 8 — Run kernel patchfinder (usbliter8-kernel-patchfinder)

```sh
python3 usbliter8-kernel-patchfinder/scan.py --kernel kernelcache.dump --all
```

This scans the kernelcache and applies ~20 patch targets in ~6 seconds.

### Phase 9 — Package and plan the ramdisk load

```sh
./fbr34ker ramdisk build \
  --product iPhone12,1 \
  --os-version 18.5 \
  --build 22F76 \
  --ramdisk ramdisk.dmg \
  --kernelcache kernelcache.patched \
  --devicetree DeviceTree.dtb \
  --output build/ramdisk/target.fbrd

./fbr34ker ramdisk inspect build/ramdisk/target.fbrd
./fbr34ker ramdisk load build/ramdisk/target.fbrd \
  --evidence runtime-artifacts/ramdisk-load-plan.json
```

The final command is plan-only. It sends nothing to a device. Physical loading
requires a reviewed external adapter that explicitly supports the exact
product and OS build; follow `docs/RAMDISK_MAKER_LOADER.md`. Do not infer a
successful ramdisk boot or SSH service from component transfer alone.
