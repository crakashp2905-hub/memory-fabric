# N3-08 — Held-out world-family retention transfer

Status: preregistered before held-out results are generated.

## Question and families

Test whether a causal retention policy learned from past simulated rule/action
tasks transfers to two new task families: `supply_chain_dispatch` and
`incident_response`. Neither target family shares the source task labels or
base-success distribution. Both expose the same preregistered transferable
memory feature (`procedure` versus `legacy`) but generate different task
outcomes and difficulty rates. The causal-effect mapping by feature is the
explicit transfer hypothesis, not an assumed result.

The source policy is learned on 40 memories (20 per feature) over 500 episodes
per memory in the source family. Inclusion is randomized at propensity `0.5`;
the existing `IPSEstimator` estimates each memory's effect, and the mean effect
per feature becomes the frozen score assigned to new memory IDs. No target
family outcomes are used to fit or alter that score.

For each held-out family and each of 10 paired seeds, create 40 new memories
(20 per feature). The target calibration set has 100 episodes per memory.
`procedure` exposure is randomized at `0.5`; `legacy` exposure is selected
with probability `0.9` on easy tasks and `0.1` on hard tasks. Outcomes are
verified Bernoulli draws under each family's registered generator. The
smoothed-success baseline ranks each target memory by `NaiveUsageEstimator`
on calibration episodes. Both policies keep 20 of the same 40 candidate
memories; a separate 3,000-episode test set evaluates each selected set with
paired task difficulty and common random numbers.

## Frozen outcome and gate

Primary outcome: held-out test success. Report source-learned feature effects,
selected feature composition, each family's paired success difference
(`causal_policy - smoothed_success`), and a 95% bootstrap interval over the 10
paired seeds. Keep H2's historical promotion bar: the causal policy must beat
the smoothed-success baseline by at least 5 percentage points in **each** new
family, and each paired interval must exclude zero. A miss in either family
means the policy is not promoted; report the negative or inconclusive result
without changing the threshold.

This controlled transfer study deliberately holds the feature-to-effect
relationship constant while changing task family and base-success process.
It can falsify transfer across these two families; it cannot establish
generalization to real agents, different feature semantics, or field data.
