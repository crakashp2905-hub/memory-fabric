# Correction review strategy comparison

`tests.test_cdm_correction_comparison` creates three allowed action records in
one tenant under a two-independent-source rule: one depends on the corrected
source, one still meets the rule without it, and one is unrelated.

| Strategy | Records surfaced | Classification |
|---|---:|---|
| Blanket review | 3 | All tenant actions, including unrelated work |
| Existing dependence analysis | 2 | One `depended`; one `would_stand`; unrelated action omitted |
| CDM correction report | 2 review rows | Preserves both classifications, risk-ranks the two touched decisions, omits unrelated action, and remains review-only |

The test also found and fixed a tenant-scope mismatch: counterfactual
certificates were issued under the action's tenant but verified without it,
which incorrectly classified both touched decisions as `wrong_tenant`. The
existing dependence path now passes the same tenant to verification. These
counts are a deterministic fixture, not a reviewer-effort or real-world
accuracy estimate. CDM does not replay an agent's internal reasoning and does
not change authority or perform the correction.
