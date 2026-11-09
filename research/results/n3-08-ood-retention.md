# N3-08 — Retention-policy transfer to held-out world families

The source causal policy learned the feature-level effect from randomized
source rule/action tasks, then scored new memory IDs without using target
family outcomes. The smoothed-success comparator used only target calibration
outcomes. Each policy retained 20 of the same 40 candidates and was evaluated
on paired held-out tasks across 10 seeds.

| Held-out family | Causal policy success | Smoothed-success success | Paired difference (95% bootstrap CI) | Gate |
|---|---:|---:|---:|---|
| Supply-chain dispatch | 0.7063 | 0.6166 | +0.0896 [+0.0860, +0.0925] | Pass |
| Incident response | 0.6035 | 0.5167 | +0.0868 [+0.0814, +0.0920] | Pass |

The source policy selected procedural memories in all held-out budgets. The
target smoothed-success baseline selected mostly legacy memories (178/200 in
supply-chain dispatch and 176/200 in incident response, summed across seeds).
Both paired improvements exceed the historical H2 margin of five percentage
points and have intervals excluding zero.

This does not reverse or erase H2's RuleWorld result. It demonstrates transfer
only under the registered feature-effect invariance: the two target families
change task context and base-success generation while preserving the
procedure-versus-legacy causal-effect mapping. The test is synthetic, uses
known randomized source propensities, and is not real-agent evidence.
