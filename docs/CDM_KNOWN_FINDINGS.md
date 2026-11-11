# CDM known findings and limitations

This inventory records positive, null, negative, and untested results that bound
the internal CDM claim. It is an index to the frozen protocols and raw reports;
it does not convert synthetic results into deployment evidence.

## Negative and null results

| Finding | Evidence | Interpretation |
|---|---|---|
| Corrected held-out selector comparison did not show an improvement. | [heldout-v2 README](../research/results/cdm/heldout-v2/README.md), 10 fresh seeds and 70 paired rows | Every intervention arm's paired utility interval includes zero and point estimates are non-positive. No efficacy claim is supported. |
| The R5 v3 architecture superiority result misses its preregistered bar. | [R5 v3 confirmatory report](../research/results/cdm/architecture-superiority-r5v3/confirmatory/report.md) and qualification copy | The frozen superiority margin is not established; do not claim architecture superiority. |
| R7 evidence-removal arms have negative mean utility on the registered synthetic worlds. | `docs/CDM_EXECUTION_SCHEDULE.md` R7 result; [R7 report](../research/results/cdm/attribution-benchmark-confirmatory/report.json) | Attribution magnitude or a changed proposal is not evidence that an intervention improves outcomes. |
| The TAME-inspired local comparator did not outperform random on its held-out run. | [TAME-inspired qualification report](../research/results/cdm/offline-qualification/tame-inspired/manifest.json), protocol `research/prereg/cdm-r6-tame-inspired.md` | Conceptual local comparator only; not an official TAME reproduction or efficacy result. |
| Current correction-review fixture does not justify replacing dependence routing. | `research/prereg/cdm-correction-aware-utility.md`; CDM-198/199 entries in `docs/CDM_TASK_LEDGER.md` | The frozen fixture scored dependence 3.300 and CDM review rows 2.933; no confirmatory GO has been earned. |
| A self-certifying executor accepts fabricated certificate cases. | `research/prereg/cdm-r9-verifier-ablation.md`; `research/results/cdm/verifier-ablation-r9/acceptance.json` | The separate first-party verifier rejects these finite fixtures, but this is not an attack-rate estimate or security certification. |
| The initial held-out utility scorer was invalid and must not be reused. | `research/results/cdm/heldout/INVALID_UTILITY_SCORE.md` | Superseded by heldout-v2; the invalid result is retained for audit and excluded from conclusions. |

## Operational and epistemic limits

- Evidence is generated or fixture-based. There is no independent organizational
  evaluator, deployment study, physical-world causal validation, or external
  security certification.
- Replay is a deterministic local policy re-execution over a complete explicit
  trace. It cannot reconstruct unrecorded reasoning, a hosted model's internals,
  missing tool outputs, or incomplete history.
- RNG receipt verification detects post-record substitution. A caller with
  authorized write access can still submit an initially false RNG snapshot;
  there is no independent signer or trusted runtime attestation for that claim.
- The Bayesian enumerator is finite and exponential. Memory budgets are
  estimates, not allocator-enforced caps; CPU limits are not OS-enforced.
- The temporary workspace helper confines CDM temporary paths to the checkout
  result directory and cleans scoped workspaces. It is not an OS sandbox or
  protection from another process with checkout write access.
- Dependency-frontier replay retains a conservative suffix. No replay speedup
  is claimed until selective execution is proven equivalent against the full
  suffix oracle.
- Contradictory observations remain visible but are excluded from conditioning
  when no registered dependence model can interpret them. Battery parameters
  are illustrative and not physically calibrated.
- Certificates attest only to the supplied bounded synthetic model and
  complete coalition table. They carry no current action authority.
- The full offline gate proves only the checks and seed-bound synthetic runs in
  its manifest; it does not imply a deployment GO.
- A broader `unittest discover -s tests` sweep in this managed Windows runner
  encountered environment-sensitive failures in existing store/key tests and
  the quickstart harness, then was interrupted. It is not included in the CDM
  PASS claim; the scoped in-process CDM compatibility regression and all 21
  required hermetic qualification stages pass.

See [causal replay limitations](CAUSAL_REPLAY_LIMITATIONS.md),
[security boundary](CAUSAL_REPLAY_SECURITY.md), frozen protocols under
`research/prereg/cdm-*.md`, and raw results under `research/results/cdm/`.
