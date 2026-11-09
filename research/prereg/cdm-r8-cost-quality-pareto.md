# CDM-R8: matched architecture cost-quality Pareto comparison

Status: frozen before confirmatory run. Version 1. Date: 2026-11-08.

## Question and comparison contract

Estimate the non-dominated cost-quality operating points for the seven first-party
attribution/replay arms: leave-one-out, exhaustive one-removal subset, exact
Shapley, 256-permutation sampled Shapley, seeded random, recency, and CAR-inspired
full-suffix replay. This is a conceptual in-house comparison, not an official
reproduction of TAME, CAR, or another published system.

Every arm receives the same generated three-event world for each seed, the same
one-removal budget, the same deterministic proposal policy, the same paired
counterfactual-minus-factual simulator utility estimand, and the same evaluator
visibility rule (hidden truth is visible only after proposal emission). No arm
may use hidden truth for selection. No arm may make network/API/model calls,
real tool calls, or authority changes.

## Cost and quality

- Quality coordinate: per-seed counterfactual utility minus factual utility;
  summarize the paired mean and normal-approximation 95% interval.
- Cost coordinate: measured local selector plus replay CPU nanoseconds and wall
  nanoseconds. Peak traced allocation is the maximum of the selector and replay
  phases. Report transition counts separately. Cost excludes process startup,
  benchmark harness overhead and output serialization.
- A point dominates another only when its mean CPU cost is no greater, its mean
  paired utility difference is no lower, and at least one is strictly better.
  The Pareto frontier is the sorted set of non-dominated arm operating points.
- This is one common intervention budget. The frontier compares architecture
  operating points under that budget; it is not a response curve over different
  budgets and must not be described as one.

## Seeds and reporting

- Confirmatory seeds: 20261401–20261420, fixed and disjoint from prior R7 sets.
- Preserve each paired raw row, arm cost/quality point, frontier, refusal and
  safety counters, plus source/configuration/output hashes.
- Retain dominated points and negative utility differences. No architecture is
  selected or deployed based on this synthetic comparison.
- Report CPU as the frontier cost axis; wall time and peak allocation remain
  secondary cost dimensions. Synthetic results do not establish real-world
  transfer or efficacy.

Any change to generator, arm set, estimand, budget, seed list, cost accounting,
or dominance rule requires a new protocol version and fresh seeds.
