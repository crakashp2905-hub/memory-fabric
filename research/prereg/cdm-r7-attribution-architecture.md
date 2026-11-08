# CDM-R7: matched attribution architecture comparison

Status: frozen before the confirmatory seed run. Version 1. Date: 2026-11-08.

## Question and estimands

Compare candidate-selection and replay paths on identical generated binary
sensor worlds. The policy's probability assigned to the factual selected option
is the attribution game value. Hidden generated truth is withheld until each
counterfactual proposal is fixed; a separate evaluator then reports utility
difference and decision flips. Removing evidence is an intervention and is not
itself a recommendation to correct or delete source memory.

## Frozen arms and budgets

- Leave-one-out, exhaustive one-removal subset selector, exact Shapley,
  256-permutation sampled Shapley, seeded random, recency, and full-suffix
  deterministic replay (CAR-style path).
- Every arm receives the same three-event world and one-removal budget.
- The exact subset selector chooses the removal with the largest absolute
  change in the selected proposal's probability. The Shapley arms rank evidence
  by contribution to that same proposal score. Random and recency do not use
  generated truth. The full-suffix arm replays the exact subset selected by the
  exhaustive one-removal rule.
- Truth is evaluator-only after proposal emission. No selector is trained on
  held-out outcomes. No network, model, API, external charge, real tool or
  action is used.

## Seeds and reporting

- Exploratory development seeds: 20261301–20261320; not confirmatory evidence.
- Confirmatory seeds: 20261321–20261340, fixed and disjoint from exploratory
  seeds.
- Preserve every paired raw row, negative result, decision flip, utility
  difference, completeness flag, event transition count and local cost field.
- Report per-arm paired utility-difference means and normal-approximation 95%
  intervals, clearly labeling their small-sample limitations. Do not select an
  arm or change the policy based on these outcomes.
- This is a synthetic architecture comparison, not evidence of deployment
  efficacy or an official reproduction of any external architecture.

Any change to arms, scoring, budget or seeds requires a new protocol version
and fresh seeds.
