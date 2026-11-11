# N3-09 — Off-policy support and identification

Status: acceptance criteria recorded before assembling the qualification result.

## Claim under test

IPS and doubly robust estimates must abstain when logged actions do not support
both potential actions. Support is checked within every observed context stratum,
not only by marginal arm counts. The recorded propensity is the probability of
the action actually taken; its complement is counterfactual-action probability.
Both must be at least 0.01. Weight clipping and large sample size must never turn
unsupported data into a finite confidence interval.

## Acceptance

For missing-arm, near-deterministic propensity, and context-stratum support
failures, both estimators return `identification_status=NON_IDENTIFIABLE` and
`confidence_interval=None`. Supported data continues to return a finite interval.
Older serialized values with estimator `none` are interpreted as
`NON_IDENTIFIABLE`; status is persisted in new estimate JSON.

## Scope and limits

This is a deterministic contract qualification over synthetic event logs. It
proves the implementation's support gate for the enumerated conditions, not
that arbitrary observational propensities are correctly specified or that
unmeasured confounding is absent. The 0.01 floor is configurable and remains a
policy choice; it can conservatively reject sparse but mathematically positive
overlap.
