# Ramdisk maker and loader

B34ST 0.6.2b provides one guided workflow for assembling, validating, planning,
and externally loading recovery/research ramdisk bundles:

```text
B34ST
  → Ramdisk maker and loader
  → Guided maker / loader
```

The non-interactive entry point is:

```sh
./fbr34ker ramdisk --help
```

## Scope and compatibility

The ramdisk workflow covers every exact iPhone, iPad, and Apple silicon Mac
product in the repository's reviewed A12, A12X/Z, A13, A14, A15, M1, and M2
recovery profiles. Obtain the authoritative list from the installed version:

```sh
./fbr34ker ramdisk list-targets
./fbr34ker ramdisk list-targets --json
```

This is *profile compatibility*, not a blanket statement that every OS build
boots. The current profiles are simulation-validated and have
`physical_execution_verified=false`. B34ST therefore requires the external
adapter to establish support for the exact product, OS version, build, and
component set. It rejects unlisted products, Intel Macs, and mismatched
profiles.

| Target class | Profiled families | OS field | Required device path |
|---|---|---|---|
| iPhone | A12, A13, A14, A15 | Exact iOS version and build | Adapter-specific DFU/recovery state |
| iPad | A12, A12X/Z, A13, A14, A15, M1, M2 | Exact iOS/iPadOS version and build | Adapter-specific DFU/recovery state |
| Mac | M1, M2 | Exact macOS version and build | Adapter-specific DFU/recovery/1TR path |

Apple silicon Mac restore and boot policy are not interchangeable with an
iPhone DFU sequence. A Mac-capable adapter must explicitly implement its
required host/target state. B34ST does not route an M1/M2 Mac request through
an iPhone adapter.

## What the maker does

The maker packages already prepared target artifacts into a deterministic
FBRD (`.fbrd`) ZIP:

- `manifest.json` records the exact target, OS/build, profile digest,
  component sizes, and SHA-256 values;
- `components/<role>/...` stores each declared component;
- ZIP timestamps and permissions are normalized for reproducible output;
- symlinks, empty files, unsafe paths, duplicate roles, undeclared files, and
  out-of-bounds sizes are rejected;
- inspection streams every component through SHA-256 before a load request is
  created.

The maker does **not** decrypt, patch, personalize, or Apple-sign
firmware. It does not claim that arbitrary files form a bootable set.

The maker **can** download an IPSW and extract its components (ramdisk,
kernelcache, devicetree) for direct bundling — see the `ipsw` subcommands below.

## Components

Every bundle requires:

| Role | Meaning |
|---|---|
| `ramdisk` | Prepared restore/research disk image for the exact OS build |
| `kernelcache` | Matching prepared kernel image |
| `devicetree` | Matching target DeviceTree |

Optional standard roles are:

- `trustcache`
- `ibss`
- `ibec`
- `iboot`
- `bootlogo`
- `restore-device-tree`

An adapter may define additional roles. Add them with
`--component ROLE=PATH`. A component being accepted into an FBRD means its
format, size, and identity are recorded; it does not mean the adapter or target
can boot it.

## What the ramdisk adapter is

The ramdisk adapter is a separately installed executable or reviewed wrapper
around target-specific lab boot tooling. It owns the physical transport and
boot sequence that B34ST deliberately does not generalize:

```text
B34ST validation
  → one JSON request on adapter stdin
  → adapter-specific DFU/recovery/1TR transport
  → target boot attempt
  → one JSON evidence response on adapter stdout
```

The adapter is not:

- the ramdisk or FBRD bundle;
- a USB cable;
- `irecovery`, `libirecovery`, or `idevicerestore` by itself;
- a universal A12+ exploit;
- bundled or silently downloaded by B34ST.

Configure it for the current shell:

```sh
export B34ST_RAMDISK_ADAPTER='/absolute/path/to/reviewed-adapter --flag'
```

Or provide it to one invocation:

```sh
./fbr34ker ramdisk load bundle.fbrd \
  --adapter '/absolute/path/to/reviewed-adapter --flag'
```

The contract is documented in
[`schemas/ramdisk-adapter-v1.json`](../schemas/ramdisk-adapter-v1.json).
Adapter commands are parsed as an argument vector and are never executed
through a shell.

## IPSW-based workflow

The ramdisk maker can download an IPSW, extract components directly from it,
and build an FBRD bundle — without requiring manually prepared files.

### 1. Catalog available firmware

```sh
./fbr34ker ramdisk ipsw catalog --product iPhone12,1
```

Filter by signing status:

```sh
./fbr34ker ramdisk ipsw catalog --product iPhone12,1 --signed-only
./fbr34ker ramdisk ipsw catalog --product iPhone12,1 --unsigned-only
```

### 2. Download an IPSW

```sh
./fbr34ker ramdisk ipsw download --product iPhone12,1 --version 18.5
```

Download by build:

```sh
./fbr34ker ramdisk ipsw download --product iPhone12,1 --build 22F76
```

Downloads are saved under `downloads/ipsw/` by default.

### 3. Extract components from a local IPSW

```sh
./fbr34ker ramdisk ipsw extract \
  downloads/ipsw/iPhone12,1_18.5_22F76_Restore.ipsw
```

The output directory defaults to the IPSW filename stem (`iPhone12,1_18.5_22F76_Restore`).
When the IPSW supports exactly one product, `--product` is optional.
The extract command reads `BuildManifest.plist` inside the IPSW to locate
the ramdisk, kernelcache, devicetree, and optional components.

Override the output directory:

```sh
./fbr34ker ramdisk ipsw extract \
  downloads/ipsw/iPhone12,1_18.5_22F76_Restore.ipsw \
  --output-dir extracted/iphone12-1-18.5
```

### 4. Full automated build (download → extract → bundle)

```sh
./fbr34ker ramdisk ipsw build \
  --product iPhone12,1 \
  --os-version 18.5 \
  --output build/ramdisk/iphone12-1-18.5.fbrd
```

This single command:
1. Looks up the firmware in the catalog
2. Downloads the matching IPSW
3. Extracts components into a directory alongside the IPSW
4. Builds a deterministic FBRD bundle

Override individual extracted components:

```sh
./fbr34ker ramdisk ipsw build \
  --product iPhone12,1 \
  --build 22F76 \
  --ramdisk prepared/custom-ramdisk.dmg \
  --output build/ramdisk/iphone12-1-22F76.fbrd
```

### 5. Extract components within the guided workflow

When running the interactive guide, choose `I` (IPSW) at the component
source prompt to extract directly from a local IPSW instead of entering
individual component paths.

## Streamlined guided workflow

Run:

```sh
./fbr34ker ramdisk guide
```

The guide:

1. asks for the exact product identifier, OS version, and preferably build;
2. resolves exactly one product profile and prints every unverified condition;
3. asks for the three core files and any optional components;
4. builds and immediately verifies a deterministic FBRD;
5. creates a plan-only adapter request and evidence file;
6. prints the separate command needed for authorized execution.

The connected-device dashboard also offers **Guided ramdisk maker / loader**
when it detects an exact-profile product in DFU/recovery mode.

## Automation

### 1. Plan

```sh
./fbr34ker ramdisk plan \
  --product iPhone12,1 \
  --os-version 18.5 \
  --build 22F76 \
  --output runtime-artifacts/ramdisk-plan.json
```

For an iPad:

```sh
./fbr34ker ramdisk plan \
  --product iPad13,8 \
  --os-version 18.5 \
  --build 22F76
```

For an Apple silicon Mac:

```sh
./fbr34ker ramdisk plan \
  --product MacBookAir10,1 \
  --os-version 15.5 \
  --build 24F74
```

### 2. Build

```sh
./fbr34ker ramdisk build \
  --product iPhone12,1 \
  --os-version 18.5 \
  --build 22F76 \
  --ramdisk prepared/ramdisk.dmg \
  --kernelcache prepared/kernelcache \
  --devicetree prepared/DeviceTree.dtb \
  --trustcache prepared/trustcache \
  --ibss prepared/iBSS \
  --ibec prepared/iBEC \
  --output build/ramdisk/iphone12-1-18.5.fbrd
```

Existing output is not replaced unless `--force` is explicit.

### 3. Inspect

```sh
./fbr34ker ramdisk inspect \
  build/ramdisk/iphone12-1-18.5.fbrd
```

Use `--json` for CI or adapter preflight.

### 4. Create a load plan

```sh
./fbr34ker ramdisk load \
  build/ramdisk/iphone12-1-18.5.fbrd \
  --ecid DEVICE_ECID \
  --evidence runtime-artifacts/ramdisk-load-plan.json
```

This is the default. It validates the bundle and emits the request but sends
nothing to a device.

### 5. Execute through the adapter

First review the plan, adapter source/version, cable/power, target mode, backup,
and rollback expectations. Then run:

```sh
./fbr34ker ramdisk load \
  build/ramdisk/iphone12-1-18.5.fbrd \
  --ecid DEVICE_ECID \
  --execute \
  --owner-authorization 'I OWN OR AM AUTHORIZED TO LOAD THIS RAMDISK' \
  --confirm 'LOAD AUTHORIZED RAMDISK' \
  --evidence runtime-artifacts/ramdisk-load-result.json
```

The adapter must exit zero and return a schema-version-1 JSON object with
`"ok": true`. B34ST treats all other output, timeouts, and exit statuses as
failure.

## Adapter request and response

The request contains:

- immutable bundle path, byte count, SHA-256, and full validated manifest;
- product, device class, family, CPID list, OS version, build, and optional
  ECID;
- explicit execution authorization state;
- constraints stating that stock iBoot compatibility and persistence are
  false.

Minimum successful response:

```json
{
  "schema_version": 1,
  "ok": true,
  "status": "ramdisk-started",
  "target": {
    "product": "iPhone12,1",
    "ecid": "123456789"
  },
  "evidence": {
    "adapter": "example-adapter",
    "adapter_version": "1.0.0",
    "bundle_sha256": "64-lowercase-hex-characters",
    "stages": ["transport-ready", "components-accepted", "ramdisk-started"]
  }
}
```

An adapter should reject a target mismatch, component hash mismatch,
unsupported OS/build, unexpected device mode, or missing authorization before
performing a write or boot transition.

## Public building blocks

Public projects such as `libirecovery` can supply recovery/iBoot USB
communication, and `idevicerestore` demonstrates signed restore orchestration.
They are useful adapter building blocks, not drop-in ramdisk adapters. Existing
checkm8-era ramdisk/jailbreak projects generally target A11 and earlier
hardware and must not be represented as A12–M2 compatibility.

Use only a project that explicitly lists the exact product and OS build,
exposes an auditable non-interactive interface, and can be wrapped to honor the
request/response contract. If no such adapter exists, B34ST's supported outcome
is a validated bundle and plan—never an inferred successful boot.

## Operational checklist

Before execution:

- verify ownership or written authorization;
- preserve required device data and recovery credentials;
- confirm the product, ECID, OS version, build, and profile;
- verify all source artifact hashes;
- review and pin the adapter version;
- use stable host power and a known-good data cable;
- start from the exact mode required by the adapter;
- keep evidence storage outside the bundle output path.

After execution:

- preserve the B34ST result and adapter-native logs;
- record actual device mode and observable boot state;
- do not infer a successful boot from USB transfer completion;
- remember that the workflow does not claim persistence across restart;
- use a documented adapter reset/recovery path after failure.

## Troubleshooting

| Message | Meaning and resolution |
|---|---|
| `no exact ramdisk profile exists` | The product is outside the current exact profile catalog. Do not substitute a family-generic profile. |
| `profile ... does not include product` | The supplied profile and product disagree. Remove `--profile` for automatic exact resolution or choose the correct exact profile. |
| `missing required component(s)` | Provide ramdisk, kernelcache, and DeviceTree from the same target/build set. |
| `SHA-256 mismatch` | The bundle was modified or damaged. Rebuild it from trusted source files. |
| `bundle contains files not declared` | The archive was modified outside the maker. Rebuild it. |
| `execution requires --adapter` | Configure a reviewed adapter or remain in plan-only mode. |
| `adapter response must be ... ok=true` | The adapter violated the contract or reported failure. Inspect its own logs; do not retry blindly. |
| `guide requires an interactive TTY` | Use `plan`, `build`, `inspect`, and `load` for automation. |

