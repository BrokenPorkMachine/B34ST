# USBliter8 Hardware Guide

## Overview

USBliter8 exploits the DWC3 USB controller on A12+ Apple SoCs via USB control
transfers. You need a capable host USB controller and the right setup to
successfully deliver the DWC3 firmware patch. This guide covers recommended
hardware, preparation steps, and integration with B34ST.

## Recommended hardware

### Waveshare RP2350 USB-A (recommended)

The **Waveshare RP2350 USB-A** is an excellent choice for USBliter8 host duties:

- **RP2350 dual-core Cortex-M33/RISC-V** — More than enough USB bandwidth
- **Native USB-A host port** — No adapter needed, reliable DFU enumeration
- **USB 2.0 High Speed (480 Mbps)** — Full-speed compatible
- **264 KB SRAM + 16 MB flash** — Room for custom firmware
- **PIO (Programmable I/O)** — Can implement custom USB signalling if needed
- **Price**: ~$15-25 USD
- **Open source SDK** — Raspberry Pi Pico SDK, MicroPython, CircuitPython

### Why not Raspberry Pi?

While a Raspberry Pi 4/5 can work, the Waveshare RP2350 USB-A offers:

- Dedicated USB-A host port without hub complications
- Lower power consumption (runs off device bus power)
- Smaller form factor
- Real-time USB response characteristics
- PIO capability for exotic USB timing work

### Alternative options

| Device | Pros | Cons |
|--------|------|------|
| Raspberry Pi 4/5 | Easy setup, full Linux | USB controller behind hub; power supply considerations |
| Intel NUC / x86 mini PC | Full Linux, reliable USB | Overkill for this task |
| RP2040-based board (Pi Pico) | Cheap ($4) | No native USB host; needs bit-banging |
| FTDI FT600 | Sync FIFO, fast | Expensive, complex setup |

## Hardware preparation

### 1. Identify your USB controller

Not all USB controllers work equally well with DWC3 exploitation. Check yours:

```sh
# Linux
lsusb -t | grep -E "xhci|ehci"
dmesg | grep "USB.*controller"

# macOS
system_profiler SPUSBDataType | grep "Controller"
```

Recommended: Intel xHCI, ASMedia xHCI, or RP2350 PIO-based USB.

Avoid: VIA USB 3.0 controllers (known timing issues), early Renesas
controllers.

### 2. Cable selection

Use a **high-quality USB-A to Lightning cable** rated for data sync:

- **Apple OEM cable** — Best compatibility, reliable DFU entry
- **Anker PowerLine** — Good alternative
- Avoid charge-only cables (missing data lines D+/D-)

Maximum cable length: 2 meters for USB 2.0 High Speed.

### 3. Power considerations

- Ensure the host port provides at least 500 mA
- For RP2350: connect USB-A to device, micro-USB/USB-C to power
- For Raspberry Pi: use dedicated 5V/3A PSU, not bus power

### 4. Build or source the FBR34KER operational image

```sh
make build-operational
```

Output: `build-exploit/fbr34ker-operational.bin`

If you already have a built image, you can skip this step (see below).

## B34ST integration

The recommended way to run USBliter8 is through **B34ST**, which handles
hardware preparation, exploit execution, and returning to the main workflow.

### Using the B34ST USBliter8 menu

```sh
./scripts/B34ST
```

Then select **A12+ USBliter8** from the main menu. The integrated flow:

1. **Hardware preparation** — Guided checklist, can skip if already done
2. **Firmware preparation** — Build operational image if needed, can skip if done
3. **Device connection** — Verify DFU mode device is detected
4. **USBliter8 exploitation** — Run the full DWC3 exploit chain
5. **Post-exploitation** — Collect evidence, return to B34ST

### Hardware preparation step

The B34ST hardware preparation step walks through:

```
Hardware preparation checklist:
  [1/5] Host USB controller check
  [2/5] Cable and power check
  [3/5] Device in DFU mode
  [4/5] Operational image built
  [5/5] pyusb / libusb installed
```

Each item can be individually skipped/reported done. The full checklist is
saved to the session directory as evidence.

### Firmware preparation step

If the operational image already exists at `build-exploit/fbr34ker-operational.bin`,
B34ST detects this and offers to skip the build:

```
Firmware preparation:
  [*] Found existing image: build-exploit/fbr34ker-operational.bin
  [*] Skipping build (use --force-rebuild to override)
```

Pass `--force-rebuild` if you want to rebuild anyway.

### USBliter8 execution

After hardware prep, B34ST runs the exploit orchestrator:

```
USBliter8 execution:
  [*] Waiting for A12+ device in DFU mode...
  [+] Device found
  [*] Detecting chipset...
  [*] Sending DWC3 exploit payload...
  [+] PWNDFU achieved
  [*] Sending FBR34KER monitor...
  [*] Executing monitor...
  [*] Connecting to console...
  [*] Running exploit chain...
  [+] Complete
```

### Returning to B34ST

After the exploit and external work is done, B34ST automatically reconnects
and resumes the workflow at the appropriate next step. You can also:

- Choose **Connect to FBR34KER console** for live exploration
- Choose **Return to B34ST menu** to continue other operations
- Evidence is written to the session directory

## First-time setup

### Install host dependencies

```sh
# Linux
sudo apt install libusb-1.0-0-dev python3-pip
pip install pyusb

# macOS
brew install libusb
pip3 install pyusb
```

### Verify pyusb detects your hardware

```sh
python3 -c "
from host.usb_serial import enumerate_devices
for d in enumerate_devices():
    print(d)
"
```

If no devices show when nothing is plugged in, your libusb/pyusb is working.

### Test with the device in DFU mode

```sh
# Put device in DFU mode, then:
python3 host/usb_serial.py --check-dfu
```

## Preparing firmware on the Waveshare RP2350 USB-A

### Option A: Use as a standard USB host (recommended)

The RP2350 USB-A runs Linux via Raspberry Pi Pico SDK or CircuitPython.
Flash a standard UF2 that presents as a USB host controller:

1. Download the USBliter8 host firmware from the releases page
2. Hold BOOTSEL on the RP2350, connect to computer
3. Copy the `.uf2` file to the RPI-RP2 drive
4. The RP2350 reboots and is ready as a USB host

### Option B: Custom firmware with PIO USB

For advanced users: implement USB host signalling via PIO for precise timing
control. See the `rp2350_usb_host` example in the SDK.

## Skip options

B34ST provides skip options at each stage:

| Stage | Skip method |
|-------|-------------|
| Hardware prep | `--skip-hardware-prep` |
| Firmware build | Automatically skipped if image exists, or `--skip-build` |
| DFU wait | `--no-dfu-wait` (if device already in DFU) |
| Console connection | `--no-console` for headless operation |
| Evidence collection | `--skip-evidence` |

## Verification

After preparation, verify your setup:

```sh
./fbr34ker doctor           # Check host readiness
./fbr34ker detect           # Check device is detected
./fbr34ker exploit --dry-run  # Dry-run the exploit chain
```

## Troubleshooting

### "Device not found"

- Check cable (must be data, not charge-only)
- Verify DFU mode entry procedure
- Check pyusb/libusb installation
- Try a different USB port (avoid hubs)

### "DWC3 exploit failed"

- Ensure the exact CPID is present in the reviewed target table; numeric range checks are not sufficient
- Check DWC3 firmware version compatibility
- Some devices with patched DWC3 firmware may not be exploitable
- Try with a different host USB controller

### "Monitor didn't boot"

- Check the operational image was built correctly
- Verify the load address matches the chipset
- Some devices may need a different entry point

### "Console not connecting"

- Wait 2-3 seconds after execute for USB re-enumeration
- Check PID 0x1227 appears in `lsusb` / system_profiler
- Try re-running the exploit
