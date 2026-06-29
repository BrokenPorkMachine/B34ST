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

The complete end-to-end boot chain combines FBR34KER's USBliter8 exploit with
external patchfinder tools from the [usbliter8ra1n](https://github.com/Leeksov/usbliter8ra1n)
ecosystem. Clone those repos alongside FBR34KER first (see README.md).

### Phase 1 — Build FBR34KER operational image

```sh
make SECURITY_MODEL=1 build-operational
```

### Phase 2 — Put device in DFU mode

Connect via USB, hold Power + Volume Down for 10s, release Power, hold
Volume Down for 5s. Verify:

```sh
irecovery -q | grep CPID    # Should show 0x8015 (A12), 0x8020 (A13), etc.
```

### Phase 3 — Apply USBliter8 DWC3 exploit (FBR34KER)

```sh
python3 scripts/run_exploit.py --monitor build-operational/fbr34ker-operational.bin --auto
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

### Phase 9 — Boot kernel and launch SSH ramdisk

```sh
# Boot the patched kernel
python3 usbliter8ra1n/boot.py --kernel kernelcache.patched --rd ramdisk.dmg

# Connect via SSH through iProxy
iproxy 2222 44 &
ssh -p 2222 root@localhost
```

The device boots into a jailbroken state with SSH access via dropbear on
port 44, tunneled through iProxy on host port 2222.
