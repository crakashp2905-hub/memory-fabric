# CDM-R3: evidence-bounded certificate protocol

Status: frozen before held-out seed run. Version 1. Date: 2026-11-08.

## Allowed claim

The current certificate may attest only that a complete deterministic local
replay under named input commitments produced the supplied factual and
counterfactual fingerprints and that the declared proposal changed. It does
not establish real-world causality, correctness of the hidden world, external
reproducibility, or authority to act.

## Acceptance and stop rules

All digests must be lowercase SHA-256; schema, status, claims, entitlement,
and every required field are checked; any changed field, omitted field,
unknown field, truncated replay, unavailable current authorization, or erased
evidence causes refusal. False acceptance threshold is zero in the local
tampering fixtures. A passing fixture is not an independent security audit.
