# Profile maturity and evidence policy

FBR34KER profile maturity is evidence-derived, not a manual marketing label.

| Maturity | Minimum evidence |
|---|---|
| `simulated` | Deterministic host or adapter simulation |
| `qemu-verified` | Passing QEMU runtime gate |
| `bridge-verified` | Valid persistent-bridge session and exact profile |
| `console-verified` | Bridge evidence containing a FBR34KER entry banner |
| `boot-evidence-verified` | Valid console proof plus boot-evidence export |
| `physical-runtime-verified` | Explicit physical-execution claim in a valid non-simulator session |

The profile promotion tool refuses to exceed the strongest proof in the supplied
bundle. Reset evidence must show that authorization was invalidated before the
next mutation-capable session.

`physical-runtime-verified` additionally requires a separate operator attestation
matching `schemas/physical-runtime-attestation-v1.json`. The attestation must
contain the SHA-256 of the evidence bundle and explicit ownership/authorization,
console, boot-evidence, and safe-reset observations. A self-reported session flag
alone cannot promote a profile to physical-runtime status.
