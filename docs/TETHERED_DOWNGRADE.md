# Guided tethered downgrade

## The short version

In B34ST, select:

```text
Targeted IPSW downloads, upgrades, and tethered downgrades
  → Guided tethered downgrade (recommended)
```

The guide validates the target and IPSW, creates an evidence-backed plan,
checks the external adapter, and optionally starts it. You can safely stop
after planning.

A tethered downgrade is not a stock restore and is not persistent:

- Apple does not sign the target firmware.
- B34ST does not send it through the stock restore path.
- B34ST does not bundle a target-specific boot adapter.
- A reviewed external adapter must perform the authorized boot workflow.
- The external tethered boot must run again after every device restart.

If no adapter is configured, the guide finishes successfully in plan-only
mode and prints the exact blocker. This is expected behavior.

## What is the tether adapter?

The tether adapter is a separately installed, target-specific executable. It
can be a program, a script, or a reviewed wrapper around your lab's existing
device boot tooling. Its job is to communicate with the exact device in the
required DFU/recovery state and perform the external boot sequence for that
device and firmware.

It is the boundary between two responsibilities:

- **B34ST** validates the IPSW and target, calculates the SHA-256, creates the
  plan/evidence, sends a bounded JSON request, and checks the result.
- **The tether adapter** performs the target-specific device communication and
  boot work, then returns structured success or failure JSON.

The tether adapter is **not**:

- the IPSW file;
- the USB cable or USB controller by itself;
- Apple `idevicerestore`;
- a universal downgrade component included with B34ST.

The word *tethered* describes the result: the adapter's boot sequence must run
again after a restart or loss of power. Merely having an IPSW and cable does
not provide that boot sequence.

## Public projects and compatibility

The following guidance was checked against the projects' own documentation on
2026-06-28. None of these projects natively implements B34ST's JSON adapter
contract; a reviewed wrapper would still be required.

| Public project | What it provides | Can it be used as a B34ST tether adapter? |
|---|---|---|
| [Legacy iOS Kit](https://github.com/LukeZGD/Legacy-iOS-Kit) | A complete restore/downgrade toolkit for legacy, bootrom-exploitable devices, including some A7–A11 workflows. | Use it directly for devices it explicitly supports. It is not compatible with B34ST's current A12+ profiles and is usually more appropriate as a standalone tool than as a wrapper backend. |
| [Semaphorin](https://github.com/LukeZGD/Semaphorin) | The closest conceptual example: a tethered downgrade/boot workflow for A7–A11 and older iOS versions. | Not for A12+. The maintained fork is archived, states that it has no support, and warns that it may erase device data. Treat it as historical/reference tooling, not a default recommendation. |
| [palera1n](https://github.com/palera1n/palera1n) | A checkm8-based jailbreak for A8–A11 devices on newer firmware. | No. It is not a downgrade adapter and does not support A12+. It is useful only as an example of a public tethered boot/jailbreak workflow. |
| [futurerestore](https://github.com/futurerestore/futurerestore) | An unsigned restore workflow that depends on valid SHSH tickets and compatible SEP/baseband components. | Not directly. It is a different restore model, not a repeat-on-every-boot tether adapter. Use its native workflow when its blob and compatibility requirements are satisfied. |
| [idevicerestore](https://github.com/libimobiledevice/idevicerestore) and [libirecovery](https://github.com/libimobiledevice/libirecovery) | Restore orchestration and low-level recovery/iBoot USB communication. | Components only. They do not provide an unsigned A12+ boot chain by themselves, but a target-specific adapter may use them internally. |

### Current A12+ status

B34ST's current Apple profiles start at A12. None of the public projects above
is a verified drop-in tether adapter for those profiles. Do not configure an
A7–A11/checkm8 command for an A12+ device: a matching product identifier and
IPSW do not make the underlying exploit or boot chain compatible.

For an A12+ target, the honest outcomes are:

1. Use plan-only mode until you have a separately reviewed adapter for the
   exact target.
2. Use a signed restore path when the desired firmware is still signed.
3. Use a distinct blob-based workflow such as futurerestore only when its own
   device, ticket, nonce, SEP, and baseband requirements are satisfied.
4. Develop and independently review an adapter around authorized,
   target-specific lab tooling.

## Contract-only example adapter

The repository includes
[`examples/tether_adapter_contract_example.py`](../examples/tether_adapter_contract_example.py).
It demonstrates request validation and response formatting, but deliberately
performs no device I/O and always rejects execution.

Inspect it with:

```sh
python3 examples/tether_adapter_contract_example.py --describe
```

This example is a starting point for adapter developers, not something an
operator should configure as a working downgrade backend. A real adapter must
replace the rejection path with reviewed, exact-target device operations and
must still return the JSON result described below.

## Before starting

Have the following ready:

1. A device you own or are explicitly authorized to restore.
2. The exact Apple product identifier, such as `iPhone12,1`.
3. A stable USB data cable and host power.
4. Either a matching local unsigned IPSW or enough disk space to download it.
5. For execution, a reviewed adapter compatible with the exact device,
   firmware, and required DFU/recovery state.

Back up any data that matters before beginning. The adapter determines the
device-side effects; B34ST cannot guarantee data preservation.

## Guided workflow

Launch B34ST:

```sh
B34ST
```

Choose option 7, then `Guided tethered downgrade`.

The guide performs these steps in order:

1. Confirms the Apple product identifier.
2. Uses a local IPSW or lists unsigned catalog targets for download.
3. Verifies the ZIP, `BuildManifest.plist`, product, version, build, and
   SHA-256.
4. Confirms the catalog reports that exact firmware as unsigned.
5. Discovers and validates the external adapter executable.
6. Displays a human-readable readiness plan and saves JSON evidence.
7. Stops safely unless you explicitly authorize execution.
8. Passes one bounded JSON request to the adapter and records its result.

The guide never silently changes from planning to execution.

## Configure the external adapter

Provide the adapter when prompted, pass it explicitly, or set:

```sh
export B34ST_TETHER_ADAPTER='/absolute/path/to/adapter [arguments]'
```

The executable must exist and be executable. B34ST does not invoke the
command through a shell, so shell pipelines and redirections are not
supported. Put any such orchestration in a reviewed wrapper executable.

### Adapter input

B34ST writes one JSON object to the adapter's standard input:

```json
{
  "schema_version": 1,
  "operation": "tethered-downgrade",
  "arguments": {
    "product": "iPhone12,1",
    "ipsw_path": "/absolute/path/to/target.ipsw",
    "ipsw_sha256": "64-lowercase-hex-characters",
    "version": "17.6.1",
    "build": "21G93",
    "ecid": "optional-device-ecid",
    "tethered": true
  }
}
```

The complete request contract is
[`schemas/tethered-downgrade-adapter-v1.json`](../schemas/tethered-downgrade-adapter-v1.json).

### Adapter output

The adapter must write exactly one JSON object to standard output.

Success:

```json
{"ok": true, "detail": "authorized tethered stage started"}
```

Failure:

```json
{"ok": false, "error": "actionable failure description"}
```

Diagnostic logging should go to standard error so standard output remains
valid JSON.

## Direct CLI use

Recommended interactive guide:

```sh
fbr34ker ipsw tethered-downgrade-guide
```

Plan a known local IPSW without offering execution:

```sh
fbr34ker ipsw tethered-downgrade-guide \
  --product iPhone12,1 \
  --ipsw /path/to/target.ipsw \
  --plan-only
```

Advanced non-interactive plan:

```sh
fbr34ker ipsw tethered-downgrade \
  --product iPhone12,1 \
  --ipsw /path/to/target.ipsw \
  --human \
  --evidence tethered-downgrade.json
```

The advanced command only executes when `--execute`, the external adapter,
and both exact authorization acknowledgements are supplied. Run
`fbr34ker ipsw tethered-downgrade --help` for those automation options.

## Common outcomes

| Message | Meaning | Next action |
|---|---|---|
| `Execution: PLAN ONLY` | The IPSW is valid, but no usable adapter is configured. | Set `B34ST_TETHER_ADAPTER` or rerun and enter the adapter command. |
| `target firmware is signed` | The selected firmware belongs in the signed restore workflow. | Use B34ST's signed update/restore option. |
| `IPSW does not support target product` | The archive is for different hardware. | Select an IPSW matching the exact product identifier. |
| `adapter executable was not found` | The command path/name cannot be executed. | Use an absolute executable path or fix `PATH` and permissions. |
| `adapter returned invalid JSON` | Adapter stdout violated the response contract. | Send logs to stderr and emit only one JSON object on stdout. |
| `adapter rejected the operation` | The adapter returned an error or nonzero exit. | Read the reported adapter error and the B34ST session transcript. |

## After a successful run

Keep the saved plan, adapter response, and B34ST session transcript together.
After any restart or loss of power, rerun the adapter through the guide to
boot the tethered runtime again.
