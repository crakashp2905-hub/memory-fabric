# CDM-R9: self-certification versus separate verifier ablation

Status: frozen before deterministic fixture evaluation. Version 1. Date: 2026-11-08.

## Question

Do fabricated or incomplete certificate claims pass when an executor accepts its
own `EXACT` status, compared with an independently coded first-party verifier
that validates the closed certificate schema, content digest and critical
non-authority/world limitations?

## Frozen arms and cases

- Self-certifying executor baseline: accepts solely when the supplied payload
  claims `status == EXACT`; it performs no separate digest or invariant check.
- Separate first-party verifier: a distinct stdlib implementation in
  `benchmarks/cdm_report.py`; it recomputes canonical JSON SHA-256 and checks
  the closed schema, digest formats, exact status, action boundary, world
  boundary, required limitations and proposal-claim consistency. It does not
  call the production certificate verifier.
- One genuine exact certificate is the positive case. Negative cases are
  tampered capture/intervention/policy digests, forged action authority,
  unsupported physical-world semantics, missing limitations, injected unknown
  completeness metadata, and a truncated replay refused by the issuer.
- Both arms receive each identical payload. Count TP/TN/FP/FN separately and
  retain per-case outputs. No human or third-party verifier participates.

## Safety and interpretation

- Fixtures are local and deterministic; no network, model, API, real tool or
  authority mutation is permitted.
- Results are acceptance behavior on this finite fixture set, not an empirical
  attack probability or a security certification.
- The independent verifier proves local certificate consistency, not that a
  physical counterfactual is true or that source facts were correctly observed.

Any change to arms, verifier checks or fixtures requires a new protocol version.
