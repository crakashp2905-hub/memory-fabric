# CDM-R11: executed intervention versus leave-one-out check

Status: frozen before fixture execution. Version 1. Date: 2026-11-08.

## Question and estimand

Test whether replaying an action-dependent future continuation can change the
counterfactual proposal beyond a leave-one-out (LOO) policy check that retains
the factual continuation. The estimand is the paired proposal change and
simulator utility difference on one fixed synthetic deterministic world.

## Frozen fixture and arms

- Prior fault probability is 0.30. A positive alarm observation raises the
  initial proposal to `investigate`; without it the initial proposal is
  `monitor`.
- The versioned local world emits `fault_signal=False` after `investigate` and
  `fault_signal=True` after `monitor`.
- Factual arm runs the initial proposal through the simulator and replays its
  generated observation.
- LOO arm suppresses the alarm but keeps the factual action-dependent
  observation fixed, matching the standard one-event LOO check.
- Executed-counterfactual arm suppresses the alarm, recomputes the proposal,
  then regenerates the future observation from the registered simulator using
  the altered action.
- Hidden evaluator truth is fixed to fault-present and is used only after all
  proposals are emitted. Utility is `investigate=0`, `monitor=-0.5` for this
  truth state.

## Safety and scope

All evidence is synthetic and local. The environment is a frozen data-only
transition table; no callback, filesystem, network, model, API, real tool, or
authority change is allowed. The result demonstrates a possible incremental
signal in a continuation-dependent case, not average efficacy or a physical
causal claim. A no-simulator continuation remains undefined per the existing
contract.
