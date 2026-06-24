# FBR34KER 0.2.3 completeness and correctness audit

## Outcome

Approved as a **Physical Validation Candidate** for deterministic bridge validation, QEMU-capable CI, evidence integrity, profile maturity enforcement, and controlled recovery testing.

It is not proof of physical A12/A13 execution, stock-iBoot compatibility, jailbreak capability, or exploit delivery.

## Implemented scope

- evidence-gated proof classes and ordered profile maturity states;
- read-only hardware preparation and operator checklists;
- exact-profile, console-entry, boot-evidence, required-stage, and checksum validation;
- deterministic success/failure/recovery candidate report;
- controlled console, memory-map, timer, and boot-evidence fault matrix;
- stage-specific failure explanations;
- public physical-validation ABI and schema;
- QEMU-capable release CI and explicit unavailable/not-run status locally;
- retained persistent bridge, bounded transfer, exact product profiles, and reset-driven reauthorization.

## Correctness findings resolved

1. **A profile maturity label could exceed its evidence.** Promotion now computes the strongest permitted maturity and rejects stronger claims.
2. **Simulator success could be described too broadly.** Candidate and completed physical validation are separate booleans, and proof class is explicit.
3. **A failed session required manual log interpretation.** Failure explanations now identify the failed stage and bounded next diagnostic action.
4. **Preparation and mutation were not clearly separated at the top-level CLI.** `hardware prepare` is explicitly read-only; mutation remains behind the existing authorization and unsigned-code acknowledgements.
5. **Only one injected stage was represented in release evidence.** The candidate matrix now covers console, memory-map, timer, and boot-evidence failures.
6. **The public ABI did not describe validation claims.** A fixed 32-byte physical-validation claim structure and schema version are now frozen and natively tested.

## Remaining limitations

- QEMU was unavailable on the local packaging host unless supplied by CI or another validation host.
- No physical device or external first-stage bridge was tested during local packaging.
- The reference bridge identity remains simulator-backed even though the persistent transport itself is exercised.
- Apple-family profiles intentionally do not invent hardware memory maps.
- FBRI is not Apple IMG4 and is not represented as accepted by unmodified iBoot.

## Security boundary

The release contains no SecureROM exploit, signature bypass, iBoot patch, DFU-entry mechanism, arbitrary memory read/write command, credential extraction, persistence mechanism, or automatic retry of target execution. The external bridge remains operator-supplied trusted code and requires independent review.
