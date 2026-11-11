# CDM-R10: governance-aware capture ablation

Status: frozen before fixture execution. Version 1. Date: 2026-11-08.

## Question

Measure how reusing a historical capture without rechecking current access and
erasure rules changes stale-evidence acceptance, false blocking, and privacy
metadata exposure compared with a fresh governance-aware capture.

## Frozen arms and fixtures

- Governance-aware arm: perform a new local `capture()` for every attempt using
the current session and current source state; only a successful capture is an
acceptance.
- Weaker ablation arm: reuse a previously authorized `CaptureResult` without
rechecking current session, tenant or erasure state. It deliberately exposes the
cached evidence-reference count to represent metadata returned by this weak
path; no plaintext content is included.
- Fixtures: one currently authorized valid request, one revoked session, one
post-capture erased source, and one cross-tenant request using a cached artifact.
- Expected acceptance: only the currently authorized valid fixture. Revoked,
erased and cross-tenant fixtures must refuse.

## Metrics and safety

Report valid-case false blocks; stale evidence accepts on revoked/erased cases;
unauthorized metadata exposures on denied cases; and raw per-fixture outcomes.
The comparison is deterministic, uses in-memory Memory Fabric stores, no network,
no model, no real tool, and no persistent external artifact beyond sanitized
counts and booleans. No memory ID, digest or content is written to the report.

This finite fixture suite is a control demonstration, not a population rate or
privacy certification. Any change to cases, acceptance labels or metrics requires
a new protocol version.
