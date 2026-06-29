# FBR34KER 0.4.0 Beta

Version 0.4.0 is an evidence-gated beta. It does not promote an
A12/A13 profile merely because an upload or simulator run succeeded. Every claim
is classified as simulator, QEMU, persistent-bridge, console, boot-evidence, or
physical-runtime proof.

## Candidate workflow

```sh
./fbr34ker hardware prepare \
  --device-info examples/a13-device-info.json \
  --profile profiles/apple-a13-iphone-recovery.json \
  --image build-apple/a13/boot.img

./fbr34ker hardware checklist profiles/apple-a13-iphone-recovery.json
make physical-validation-candidate

./fbr34ker physical-validation candidate-report \
  --success build-apple/physical-validation-candidate/success-session.zip \
  --failure build-apple/physical-validation-candidate/failure-session.zip \
  --recovered build-apple/physical-validation-candidate/recovered-session.zip \
  --qemu-summary build-apple/physical-validation-candidate/qemu-summary.json
```

`hardware prepare` is read-only. `hardware run` delegates to the existing
explicitly authorized first-stage workflow and retains its separate unsigned-code
acknowledgement. The security-state models are compile-time gated by
`FBR34KER_ENABLE_SECURITY_MODEL`; build with `SECURITY_MODEL=1` to enable
mutation paths. Immutable probe images remain unconditionally locked regardless
of build options.

## Maturity states

Profiles may use these ordered states:

1. `simulated`
2. `qemu-verified`
3. `bridge-verified`
4. `console-verified`
5. `boot-evidence-verified`
6. `physical-runtime-verified`

Promotion is performed with `physical-validation promote-profile`. The output is
a new profile file; the source profile is never modified in place. Evidence that
does not contain the requested proof is rejected.

## Candidate versus completed validation

A package is candidate-ready when the persistent bridge reaches the FBR34KER
console, exports boot evidence, observes an injected failure, invalidates
authorization on reset, and recovers after reauthorization.

Physical validation is complete only when QEMU runtime evidence and an actual
physical-runtime evidence claim are also present. The bundled reference bridge
uses a simulator and therefore cannot satisfy the physical-runtime requirement.
