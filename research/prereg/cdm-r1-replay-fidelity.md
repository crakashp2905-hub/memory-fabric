# CDM-R1: factual replay fidelity preregistration

Status: frozen before benchmark tuning. Version 1. Date: 2026-11-08.

## Hypothesis and estimand

For registered deterministic finite Bayesian worlds, exact enumeration and
state transitions reproduce the independently enumerated posterior and
decision proposal exactly (within absolute floating tolerance `1e-12`). The
primary metric is exact state/proposal agreement; secondary metrics are
refusal on incomplete/forged traces, event work, CPU time and memory.

## Arms and controls

- Candidate: versioned updater plus deterministic threshold proposal.
- Oracle: separately written direct likelihood/product path on the same graph,
  observations, options and budget.
- Negative controls: omitted calibration, duplicated same-origin observation,
  irrelevant evidence, impossible evidence and altered fingerprint.

## Data and seeds

World definitions are generated in-tree. Development seeds are 20261108–12;
held-out seeds are 20261113–22. The current fixed battery demonstrator is a
smoke fixture, not the held-out benchmark. Hidden truth is excluded from
candidate updater inputs.

## Stop rules and limits

Any oracle mismatch, unauthorized/erased-content output or exact certificate
accepted after tampering falsifies the gate. A zero-headroom result is reported
as such. Results support only deterministic generated worlds and do not imply
physical diagnosis validity or external generalization.
