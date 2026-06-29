# B34ST

B34ST is a lightweight wrapper around FBR34KER validation plus a bounded iOS
17+ research-environment planner. It does not include an exploit, secure-boot
bypass, kernel patcher, persistence mechanism, activation bypass, or protected
user-data access.

Run it from the repository root:

```sh
./scripts/B34ST
```

After installation:

```sh
B34ST
```

The control panel provides a logged, guided path through host readiness,
environment planning, safe QEMU simulation, authorized USBliter8 execution,
and the FBR34KER runtime console. A successful transport step is not presented
as proof that stock iOS is patched or jailbroken; that claim remains
evidence-gated.

## Guided research-runtime orchestration

```sh
B34ST research-runtime guided
```

The orchestrator automates:

- host readiness and exact profile/device validation;
- kernelcache SHA-256 and Mach-O UUID inventory;
- deterministic FBRI boot-image verification;
- authorized external adapter or persistent-bridge execution;
- safe-reset authorization invalidation and reauthorization;
- trusted bootstrap archive hash verification;
- runtime evidence templates and exact-kernel evidence validation;
- final `RESEARCH_RUNTIME_READY` and `JAILBREAK_ATTESTED` computation.

It prompts for target-specific inputs and external evidence. The files
`kernel/kernel_patches.c`, `kernel/secure_boot_bypass.c`,
`kernel/persistence.c`, `kernel/usbliter8_exploit.c`, and
`scripts/run_exploit.py` are automatically recorded in a legacy-component
audit and are not accepted as runtime proof.

## IPSW management

The control panel includes:

- product-targeted firmware catalogs;
- currently signed firmware filtering;
- resumable Apple-CDN IPSW downloads;
- `BuildManifest.plist` and `Restore.plist` inspection;
- signed data-preserving upgrades and explicit erase restores;
- a guided local/download → validation → plan → adapter-preflight tethered
  downgrade workflow;
- bounded external tether-adapter execution when a separately installed,
  reviewed adapter is configured.

Stock upgrades require a catalog record marked as signed and remain subject to
Apple TSS acceptance. B34ST does not make unsigned restores persistent or
bypass Apple signing.

The tether adapter is a separately installed target-specific executable or
reviewed wrapper around device boot tooling. It communicates with the device
in DFU/recovery mode and performs the external boot sequence; it is not the
IPSW, cable, `idevicerestore`, or a universal component included with B34ST.

For the exact operator flow, adapter input/output contract, plan-only behavior,
public-project compatibility table, contract-only example, and troubleshooting
messages, see `docs/TETHERED_DOWNGRADE.md`.

## Ramdisk maker and loader

The control panel includes a dedicated guided ramdisk section:

```sh
fbr34ker ramdisk guide
```

It resolves exact-profile iPhone, iPad, and Apple silicon Mac products,
records the exact OS/build, creates a deterministic hash-verified `.fbrd`
from prepared components, and generates a plan-only load request. Physical
loading requires a separately installed, reviewed target/build-specific
adapter. B34ST neither creates Apple-signed components nor represents its
simulation profiles as proof that a particular build boots.

See `docs/RAMDISK_MAKER_LOADER.md` and
`schemas/ramdisk-adapter-v1.json`.

The control panel opens with a live connected-device dashboard. Each available
action includes required materials, numbered steps, a how-to-proceed note,
external command handoff, result capture, and an automatic return to the
refreshed dashboard. See `docs/B34ST_DEVICE_WORKFLOW.md`.

## Environment manifests

Create an auditable simulation plan:

```sh
python3 -m b34st.b34st environment-plan \
  --ios 17.6.1 \
  --product iPhone12,1 \
  --mode simulation \
  --owner-authorized \
  --capability kernel-patching \
  --output runtime-artifacts/b34st/ios17-plan.json
```

Validate a saved plan:

```sh
python3 -m b34st.b34st environment-validate \
  --plan runtime-artifacts/b34st/ios17-plan.json
```

Supported requested capabilities are:

- `activation-bypass`
- `credential-extraction`
- `kernel-patching`
- `passcode-bypass`
- `persistence`
- `protected-data-access`
- `secure-boot-bypass`

Each capability maps to a corresponding `security_boundary` flag that is set
to `true` in the plan when the capability is requested.  The `validate_plan()`
function permits a boundary flag to be `true` only when the matching
capability was requested.

`research-runtime` mode records physical-session prerequisites. A reviewed
first-stage adapter and an independently authorized boot path must already
exist; `physical_execution_ready` remains false until external evidence exists.
If one or more capabilities are requested, capability-specific blockers are
added to the plan's `blockers` list.

## Validation wrappers

Validate a session bundle:

```sh
python3 -m b34st.b34st validate-session \
  --bundle runtime-artifacts/session.zip \
  --profile profiles/apple-a13-iphone-recovery.json
```

Generate a candidate report:

```sh
python3 -m b34st.b34st physical-validation \
  --success success.zip \
  --failure failure.zip \
  --recovered recovered.zip \
  --output candidate-report.json
```

Generate read-only hardware preparation checklists:

```sh
python3 -m b34st.b34st hardware-prepare \
  --save-checklists runtime-artifacts/checklists
```

## Forensics and data acquisition

B34ST provides forensic data acquisition capabilities for authorized iOS research
environments. All acquisitions require explicit operator authorization and produce
tamper-evident evidence bundles.

List built-in acquisition profiles:

```sh
python3 -m b34st.b34st forensics list-profiles
```

Run a non-interactive acquisition session:

```sh
python3 -m b34st.b34st forensics acquire \
  --profile quick \
  --device-id DEVICE_ECID \
  --operator "Operator Name" \
  --output runtime-artifacts/b34st/forensics
```

Available profiles:

- `quick` - Filesystem listing and network state only (triage) - **No user data access**
- `full` - Memory, storage, filesystem, and network (complete acquisition) - **Requires capabilities**
- `memory-only` - RAM contents with page-level hashing - **Requires capabilities**
- `storage-only` - Storage partition imaging with block hashing - **May require capabilities**
- `filesystem-only` - Recursive file listing and extraction - **Requires `protected-data-access` capability**
- `network-only` - Network interfaces, connections, routing, DNS - **No user data access**

### Protected user data access

For profiles that access protected user data (filesystem, keychain, memory), you must
acknowledge the security boundary requirements:

```sh
python3 -m b34st.b34st forensics acquire \
  --profile filesystem-only \
  --device-id DEVICE_ECID \
  --capabilities protected-data-access \
  --output runtime-artifacts/b34st/forensics
```

Requirements for protected data access:

- The user data partition must be decrypted and mounted
- File Data Protection class granularity must be accounted for
- For keychain: passcode or unlocked SEP required (use `--capabilities credential-extraction`)

Verify an evidence bundle:

```sh
python3 -m b34st.b34st forensics verify runtime-artifacts/forensics/bundle.zip
```

## Requirements and status

B34ST uses the same Python 3.10+ requirement and security boundary as
FBR34KER. Version 0.4.5b is a Beta, not proof of
physical A12+ execution or stock-iBoot compatibility.
