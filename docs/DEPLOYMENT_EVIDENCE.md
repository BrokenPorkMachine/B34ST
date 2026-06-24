# Deployment evidence

A successful deployment writes:

- `deployment-report.json` — profile, artifacts, target evidence, and the
  complete host exchange transcript;
- `SHA256SUMS` — digest of the report;
- a deterministic ZIP containing both files.

The release simulation additionally writes
`build/deployment-simulation/simulation-summary.json` and
`build/deployment-simulation/evidence.zip`. The summary records whether the
monitor reached the simulated entry stage and whether a lost response was
successfully retried.

Evidence classes must remain distinct:

1. **Simulator evidence** proves framing, policy, persistence, resume, commit,
   and orchestration.
2. **QEMU evidence** proves AArch64 runtime behavior under emulation.
3. **Physical evidence** proves one named board/loader combination only.

Simulator evidence must never be presented as physical-hardware execution.
