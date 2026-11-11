# CDM-R6: TAME-inspired first-party comparator

Status: frozen before implementation and held-out execution. Version 1.
Date: 2026-11-08.

This is a conceptual local baseline based only on the evaluator-score,
experience annotation, and bounded update idea summarized in the master plan.
It is not an official implementation or reproduction of TAME.

## Baseline contract

- One score annotation is stored per selected evidence item; initial score is
  0.5 and the experience counter starts at zero.
- After an observed task outcome, update the selected item's score with
  `new = clip(old + 0.1 * (reward - old), 0, 1)`.
- Clamp the update counter at 20. At the cap, retain the score and increment no
  further state. Missing/incomplete outcome means no update.
- Reward is the frozen R4 task utility mapped from `[-1, 1]` to `[0, 1]` as
  `(utility + 1) / 2`.
- The baseline may use its score annotation only as a pre-task ranking signal;
  held-out outcomes are never visible before a proposal is emitted.
- Annotation is diagnostic comparator state only; it cannot change Memory
  Fabric source truth, authorization, lifecycle, or action grants.

## Data and evaluation

- Training seeds: `20261201`–`20261210`.
- Held-out seeds: `20261211`–`20261220`.
- Each arm receives the same generated world, evidence, proposal policy, one
  evidence-removal budget, and deterministic outcome evaluator.
- Report task utility, proposal accuracy, correct-evidence withholding,
  annotation trajectory, event/replay count, and refusal count separately.
- No network, hosted model, outside data, or source downloads.
- Any hidden-state label remains evaluator-only until the arm has emitted its
  proposal. Synthetic results do not support deployment claims.

This protocol is frozen before the comparator implementation and before any
held-out seed is run. Amendments require a new version and fresh seeds.
