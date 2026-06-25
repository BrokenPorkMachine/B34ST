# B34ST

B34ST is a lightweight wrapper around FBR34KER validation plus a bounded iOS
17+ research-environment planner. It does not include an exploit, secure-boot
bypass, kernel patcher, persistence mechanism, activation bypass, or protected
user-data access.

Run it from the repository root:

```sh
python3 -m b34st.b34st --help
```

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

## Requirements and status

B34ST uses the same Python 3.10+ requirement and security boundary as
FBR34KER. Version 0.2.3 is a Physical Validation Candidate, not proof of
physical A12/A13 execution or stock-iBoot compatibility.
