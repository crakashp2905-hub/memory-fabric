# CDM lineage and side-channel audit

## Scope and method

This local review covers historical capture refusals for missing, private,
withdrawn, and erased evidence; correction-impact lineage reports; and the
replay checkpoint cache. It combines a source-path review with the focused
regressions named below and a seeded, interleaved timing sample of 80 refusals
per hidden-evidence category. The sample is recorded in
`research/results/cdm/side-channel-audit.json`.

Reviewed paths: `src/memory_fabric/causal_replay/capture.py`,
`src/memory_fabric/causal_replay/api.py`,
`src/memory_fabric/causal_replay/checkpoints.py`,
`tests/test_cdm_capture.py`, `tests/test_cdm_api.py`, and
`tests/test_cdm_checkpoints.py`.

## Findings

| Surface | Finding | Evidence |
|---|---|---|
| Capture refusal content | Missing, cross-agent private, withdrawn, and erased IDs share one `Erased` type, message, and representation length; the refusal contains no requested ID. | `tests/test_cdm_capture.py::test_missing_private_withdrawn_and_erased_ids_share_one_refusal` |
| Correction lineage | Inaccessible private descendants and grandchildren are removed from the returned impact report. | `tests/test_cdm_api.py::test_correction_report_redacts_private_descendant_lineage` |
| Capture work | Each request replays the bounded event prefix before resolving requested IDs. The four measured refusal distributions overlap, but the sample is small and noisy; it cannot prove timing equivalence. | `research/results/cdm/side-channel-audit.json` |
| Cache use | Capture does not consult a checkpoint cache. The separate `CheckpointCache` is caller-owned, keys include tenant/principal/evidence and implementation commitments, and each hit re-verifies current authorization and checkpoint integrity. Memory and principal invalidation and tenant-collision cases are tested. | `src/memory_fabric/causal_replay/checkpoints.py`; `tests/test_cdm_checkpoints.py::test_cache_invalidation_drops_memory_and_principal`, `test_cache_tenant_collision_and_poisoning_are_misses` |

## Residual risk and operating rule

The implementation is **not constant-time**. Python dictionary lookups,
visibility checks, lifecycle branches, collection grants, and cache hit/miss
paths can take different amounts of time. The timing sample is descriptive;
overlap is not evidence that a repeated or remote observer cannot classify
states. No timing-padding, jitter, or constant-time claim is made. Treat
capture refusal as a sensitive oracle: do not expose arbitrary evidence-ID
probes to untrusted callers, and apply caller-level authorization and rate
limits at any service boundary.

The audit found no shared capture-result cache that bypasses current policy
checks. It does not establish resistance to local process timing analysis,
statistical remote timing attacks, or malicious in-process code.
