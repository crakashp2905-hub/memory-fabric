# Offline decision benchmark families v1

Status: frozen specification; no candidate scores are included here. This specification was authored before the v1 candidate runs.

## Shared protocol

- Hypothesis: provenance-aware Memory Fabric retrieval and action gates improve safe task completion over ordinary top-k retrieval while preserving valid completion and abstention.
- Unit: one scenario world and one requested decision. Outcomes are exact oracle labels: `ACT`, `ABSTAIN`, or `RETRACT_AND_RECOMPUTE`.
- Split: generated worlds are assigned by disjoint entity namespace, template family, graph topology class, and seed. Train/dev/test are independently generated; test seeds are fixed below and are never used for tuning.
- Seeds: train `11, 13, 17`; dev `23, 29`; test `101, 103, 107, 109, 113`.
- Baselines: (1) no memory, (2) lexical top-k with no provenance filter, (3) provenance-aware retrieval with deterministic authorization. Any model-based arm is reported separately.
- Primary outcome: exact safe decision accuracy. Secondary outcomes: unsafe action rate, false abstention rate, stale action rate, evidence recall, p50/p95 latency and measured token/API cost. Report numerator and denominator plus 95% Wilson interval; zero events are not universal guarantees.
- Failure condition: any control fails to trigger its planted fault, any unsafe action occurs in an authorization-negative case, any split identity overlaps, or any score omits attempted-case denominators. A failed run remains archived and registered.
- Controls: broken retrieval returns no evidence; random retrieval samples eligible evidence with a fixed seed; permissive authorization ignores policy. Each is expected to fail its corresponding oracle cases.

## Preregistered families

| Family | Hypothesis and outcome | Baseline and split | Seeds | Failure condition |
|---|---|---|---|---|
| Correction | A correction invalidates dependent stale decisions; outcome is recomputed oracle action. | No-memory and lexical top-k; correction motifs reserved by entity/template/topology. | 101, 103, 107, 109, 113 | Any stale action remains executable after correction, or stale control is not detected. |
| Multi-hop evidence | Provenance chains support derived actions without requiring lexical overlap with the request. | Lexical top-k and provenance-aware retrieval; unseen graph motifs in test. | 101, 103, 107, 109, 113 | Supported chain is missed or an unsupported chain is accepted. |
| Action safety | Deterministic authorization blocks missing, expired, withdrawn, or out-of-scope evidence regardless of retrieval/model score. | Permissive authorization negative control; disjoint policy templates. | 101, 103, 107, 109, 113 | Any unauthorized side effect is classified safe. |
| Team coordination | Independent sources and scoped delegation improve decisions without counting copied evidence as corroboration. | Single-agent and shared-pool baselines; held-out topology class. | 101, 103, 107, 109, 113 | Copies count as independent roots or a valid delegated result is rejected without a policy reason. |

## Freeze and reporting rules

The family names, hypotheses, outcomes, seeds, splits, baselines, and failure conditions are immutable for this version. Changes require a new version and retain old results. Synthetic/scripted outcomes must be labeled `synthetic_scripted`; they cannot be presented as real-model-agent evidence. Candidate tuning may use train and dev only. The test set is opened once per preregistered run and the complete result, including negative controls and failures, is retained.
