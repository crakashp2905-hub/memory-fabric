# CDM-R5: local comparator protocol

Status: corrected comparator protocol frozen before fresh held-out seed run.
Version 2. Date: 2026-11-08.

Each seed creates one binary hidden fault, three conditionally independent
binary sensors with seeded sensitivity and false-positive rates, and one
factual observation per sensor. Every arm sees the same graph, observations,
threshold policy and one-removal budget.

- `factual`: no intervention.
- `random`: one observation selected by a seed-derived random generator.
- `recency`: greatest sequence, then observation ID.
- `influence`: highest fixed log likelihood-ratio magnitude, stable index tie.
- `dependence`: earliest proposal evidence in the current prototype.
- `leave_one_out`: greatest absolute change in target posterior after removal.
- `oracle`: evaluator-only proposal using generated hidden state; never passed
  into the candidate updater.

All arms use a common seed list and identical event count. The local evaluator
is a separate pure function in the runner, but shares the process and code
owner; this is code-path separation, not independent organizational review.
Any mismatch between candidate posterior and the independent recursive
enumerator above 1e-12 invalidates the run.

For the corrected v2 run, use disjoint seeds 20261123–20261132 because the
prior utility protocol was shown to have an invalid oracle reward ordering.

---

## CDM-R5 v3: confirmatory architecture-superiority hypothesis

Status: frozen before the v3 development and confirmatory runs. Version 3.
Date: 2026-11-09. The v1/v2 protocols and their outputs remain historical and
are not confirmatory evidence for v3.

### Question and fixed hypothesis

Does exact Shapley attribution used to select one evidence-removal
counterfactual yield greater evaluator utility than leave-one-out selection in
the same small synthetic worlds? The directional hypothesis is that exact
Shapley is superior. The comparison is allowed to fail or be null; no threshold,
arm, seed, or metric can be changed after any v3 run begins.

### Arms and ceiling

- `leave_one_out`: remove the event with the largest absolute change in the
  target option's policy probability.
- `exact_shapley`: remove the event with the highest exact Shapley contribution
  to that same target-option probability.
- `sampled_shapley`: same contribution and removal rule, estimated using 256
  seeded permutations.
- `random` and `recency`: equal one-removal-budget controls.
- `oracle_one_removal`: evaluator-only ceiling that evaluates each of the
  three legal one-event removals with the identical updater and policy, then
  chooses the proposal with greatest frozen task utility. It receives no
  additional intervention budget and is never visible to a selector.

Every scored arm receives the same seeded world, target option, deterministic
policy, and exactly one temporary evidence removal. Hidden truth is exposed to
the evaluator only after the proposal is fixed. No arm may exceed the
per-world oracle utility; any such case invalidates the run.

### Outcome, threshold and decision rule

The primary per-seed outcome is the paired utility contrast
`utility(exact_shapley) - utility(leave_one_out)`. Utility is the frozen R4
three-action simulator score. The oracle headroom is the mean paired difference
`utility(oracle_one_removal) - utility(leave_one_out)` on these same held-out
worlds. The superiority margin is fixed at **20% of positive oracle headroom**;
the threshold cannot be relaxed after observing outcomes.

Support for meaningful superiority requires the lower bound of the
normal-approximation 95% paired interval for the primary contrast to exceed
that fixed margin, a strictly positive oracle headroom, and zero oracle
exceedances. If headroom is zero/negative, report the hypothesis as
unidentifiable on this benchmark. If the interval crosses the margin or is
below it, publish the null/failure result without changing the threshold.
Report the threshold, headroom and interval even when the decision is null.

Before the confirmatory run, run all registered arms and the ceiling on the
five development seeds below to verify that the metric is non-degenerate and
that every baseline is measured on the exact primary metric and one-removal
budget. Development outcomes cannot be pooled into confirmatory analysis or
used to change the frozen protocol. If the ceiling leaves no positive
headroom, publish that diagnostic and do not substitute a different metric.

### Seeds, artifacts and safety

- Development seeds: 20261901–20261905.
- Confirmatory seeds: 20261911–20261930, disjoint from development and all
  previously registered R5/R7/R8/R11/R12 seed ranges.
- Preserve all per-seed arm rows, utility contrasts, policy-probability
  contributions, cost fields, ceiling headroom, oracle-exceedance checks and
  raw output hashes.
- Publish both positive and negative/null findings. Keep exact/sampled
  Shapley and CAR-inspired labels as conceptual local baselines, not official
  reproductions of external systems.
- No network, hosted model, external API, real tool, physical action or
  Memory Fabric authority/lifecycle mutation is permitted.

Any change to the hypothesis, arms, outcome, threshold, seeds or decision rule
requires v4 and a fresh unused confirmatory seed set. This protocol does not
support a deployment or real-world efficacy claim.
