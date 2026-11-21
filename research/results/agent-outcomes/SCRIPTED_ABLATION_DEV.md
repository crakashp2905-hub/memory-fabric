# Scripted factorial ablation and oracle headroom, development rows

Raw rows and every aggregate: [`scripted-ablation-dev.json`](scripted-ablation-dev.json),
produced at commit `05ced0e3c556360111bc5c6cfa7f7a295eb561a4` by
`python -m benchmarks.outcome_ablation --seeds 8 --out research/results/agent-outcomes/scripted-ablation-dev.json`
([harness](../../../benchmarks/outcome_ablation.py), tests in
[`tests/test_outcome_ablation.py`](../../../tests/test_outcome_ablation.py)).

**Status: `SCRIPTED_DEVELOPMENT`, promotion `NOT_ASSESSED`.** It uses the same
scripted team, worlds and seeds as [SCRIPTED_ARMS_DEV.md](SCRIPTED_ARMS_DEV.md):
5 families × 8 seeds.

## Factorial: memory × recovery (safe_success)

| memory | recovery off | recovery on |
|---|---:|---:|
| pooled + recheck | 0.2 | 0.4 (A3) |
| Memory Fabric + gate | 0.4 (A4) | 0.6 (A5) |

Overall ([rows](scripted-ablation-dev.json)), the governance main effect is
+0.2, the recovery main effect is +0.2, and the interaction is 0.0. The
per-family rows in the JSON show where each effect comes from:

- recovery accounts for all of `public_correction`;
- governance accounts for all of `restricted_source`;
- neither factor moves `remote_retraction`, `silent_change` or `delayed_correction`.

The pooled cell without recovery is a design cell only; it is not a registered
arm. Correction propagation, source independence and retrieval method are not
separable factors in this harness and are listed as not run. The CDM ablation
(A6) is not run.

## Oracle headroom

- 16 of 40 tasks have no headroom: no arm can complete them.
- On 16 tasks, A3 already reaches the oracle's best terminal.
- 8 tasks, all `restricted_source`, can be improved over A3.

The largest A5−A3 difference these tasks allow is therefore 0.2. The measured
A5−A3 contrast is also 0.2, but that equality was set by how the families were
designed, not discovered.

## What this does not show

The policy is deterministic, so there is no variance and no prevalence. No
learned agent took part. Any improvement target for a real study has to be set
against headroom measured in that study's own pilot (see
[`research/prereg/agent-outcome-confirmatory-v2.json`](../../prereg/agent-outcome-confirmatory-v2.json)).
