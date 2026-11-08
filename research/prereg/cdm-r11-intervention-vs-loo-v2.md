# CDM-R11 v2: executed intervention versus leave-one-out

Status: frozen before fixture execution. Version 2. Date: 2026-11-08.
Supersedes the single-world v1 fixture for confirmatory reporting; v1 is retained
as the original frozen protocol record.

## Question and estimand

Across five seeded deterministic synthetic worlds, does executing the altered
action and regenerating its action-dependent continuation change the final
proposal and evaluator utility relative to leave-one-out (LOO), which retains
the factual continuation? The paired estimands are proposal change and
counterfactual-minus-factual utility for each seed, plus the mean over the five
registered seeds. No population or deployment efficacy claim is made.

## Seeds, world generator and arms

- Seeds are fixed at 20261701, 20261702, 20261703, 20261704 and 20261705.
- Each seed uses a local `random.Random(seed)` to draw prior fault probability
  uniformly from [0.20, 0.40), alarm sensitivity from [0.75, 0.90), and false
  positive rate from [0.15, 0.25). The code records these values per seed.
- The policy proposes `investigate` iff the Bayes posterior from the latest
  binary alarm is at least 0.50; otherwise it proposes `monitor`. The factual
  initial alarm is positive. The data-only transition table emits
  `fault_signal=False` after `investigate` and `True` after `monitor`.
- Factual arm executes the initial proposal and replays the resulting signal.
- LOO suppresses the initial alarm and retains the factual continuation.
- Executed replay suppresses the same alarm, recomputes the initial proposal,
  then regenerates the continuation from the frozen transition table under the
  altered proposal. Each arm receives the same seed/world and one suppression.

## Evaluator, thresholds and safety

- Evaluator truth is fixed to fault-present and is introduced only after all
  arm proposals have been recorded. Utility is `investigate=0` and
  `monitor=-0.5` for this truth state.
- Every seed must yield factual initial `investigate`, factual continuation
  `False`, factual and LOO final `monitor`, executed-replay final `investigate`,
  LOO utility difference 0.0, and executed-replay utility difference +0.5
  versus both factual and LOO. Any mismatch fails the experiment. The summary
  reports all five paired rows and the arithmetic mean; no threshold is tuned
  from observed results.
- No callback, filesystem access by the simulator, network, model, API, real
  tool, or authority mutation is permitted. Proposals cannot receive evaluator
  truth.

## Interpretation

This five-seed finite synthetic check tests a continuation-dependent mechanism,
not its frequency in a broader population. It establishes neither physical
causality nor average efficacy. A no-simulator continuation remains undefined
under the existing contract. Any change to seed set, generator, policy,
transition table, arms, estimand or thresholds requires a new protocol version.
