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
