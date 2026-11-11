# N3-02 — Exact-oracle decision worlds

Status: preregistered before generating estimator results.

## Purpose and frozen design

This experiment tests a logged value estimator against causal effects defined
by deterministic decision worlds. It uses four binary memory-availability
variables, enumerates all `2^4 = 16` permitted subsets in each world, and
records the oracle safe-success outcome for every subset. Every memory is
included in exactly half of the subsets, with logged assignment propensity
`0.5`; all subsets have equal target-population weight.

Four worlds are frozen:

1. `complementary`: safe success requires both `a` and `b`.
2. `redundant`: safe success requires either `a` or `b`.
3. `harmful`: inclusion of `harmful` causes failure; other memories do not
   change success.
4. `irrelevant`: `useful` is required for success and `irrelevant` has no
   effect.

The estimand for memory `m` is the finite-world average paired inclusion
contrast over all backgrounds:
`2^-3 * sum_{S subset M\\{m}} [Y(S union {m}) - Y(S)]`.
This is the causal effect of randomized inclusion under the uniform background
distribution; it is not a context-free intrinsic value and is not the Shapley
value. The exact oracle contrast is computed directly from paired potential
outcomes. The IPS estimate is computed from the logged episodes and compared
against that contrast. The naive exposed-only estimate is retained as a
descriptive baseline and is not interpreted causally.

## Acceptance and limits

Acceptance requires all 16 subsets per world, both potential outcomes for
every memory/background pair, and IPS agreement with each exact oracle
contrast to numerical tolerance `1e-12`. The benchmark verifies estimator
output against oracle causal differences, not source co-occurrence. This
deterministic synthetic fixture tests implementation and estimand alignment;
it does not establish identification under real-world confounding, stochastic
outcomes, agent adaptation, or incomplete support.
