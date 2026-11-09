# N3-04 — Confounding by task difficulty

Status: preregistered before generating the N3-04 result.

## Frozen data-generating process

Generate 4,000 independent episodes with a fixed seed. Half are easy and half
hard by alternating task type. Baseline safe-success probabilities are `0.75`
and `0.25`, respectively. A single important memory has a constant causal
effect of `+0.15` when included, so its potential outcome remains in `[0,1]`.
The retrieval policy exposes it with probability `0.9` on easy tasks and `0.1`
on hard tasks. Treatment assignment is randomized within difficulty strata;
the exact assigned-treatment propensity is logged on every episode.

## Measures and acceptance

The oracle effect is the finite-population mean of `Y(1)-Y(0)`, exactly
`+0.15`. The naive association is the observed mean outcome among exposed
episodes minus that among withheld episodes, without difficulty adjustment.
The correction is the existing self-normalized IPS estimator using logged
propensities. Report each arm's counts, naive association, IPS estimate, bias
against the oracle, and 95% interval from the estimator.

Acceptance requires the exposed group to be enriched for easy tasks, the
naive association to overstate the causal effect by at least `0.20`, and IPS
absolute error to be at most `0.04`. This demonstrates that the estimator
exposes the selection bias while retaining a real positive effect. It does
not establish that logged propensities suffice under hidden confounding or
misspecified policies.
