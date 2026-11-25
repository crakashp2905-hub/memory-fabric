# Supported scope per component (feature-freeze release)

What each part of Memory Fabric is supported to do in this release, how it is configured, what
it does **not** do, and how to turn it back off. Nothing is removed: a component that has not
qualified for a stronger use stays available in its safe mode. The per-component verdicts and
their evidence are in [FREEZE_RELEASE_DECISION.md](FREEZE_RELEASE_DECISION.md).

| Component | Supported use | Not supported | Rollback |
|---|---|---|---|
| **Core memory and governance** | memory lifecycle, provenance, tenant isolation, correction and erasure, the action gate with exact-action grants and approvals, multi-host operation on the measured configurations | physical multi-host claims beyond the recorded tests; a staging-host SLO | previous release (OPERATIONS.md §5); the store is never mutated by a rollback |
| **Vega (semantic advisor)** | `OFF` (default) or `SHADOW`: a locally served, pinned reader whose answers are recorded and never change an output | numbers, thresholds, entity identity, provenance, grants or evidence status (all deterministic); influencing an action selection (HOLD); `QUALIFIED` (refused by code) | set the mode to `OFF`; `python tools/vega_killswitch.py --verify` |
| **CDM (counterfactual replay)** | deterministic replay of recorded, complete decision traces; certificates checked by the independent verifier; `ADVISORY_ONLY` reports | reconstructing model reasoning; real-world causal claims; automatic decision repair (HOLD until a held-out learned-agent utility passes) | stop calling `cdm_dispatch.dispatch`; nothing it returns carries authority |
| **Learned-agent workflow** | supervised use only; every model call is recorded and every effect passes the action gate and the omission guard | unsupervised operation; a planner choice that the guard has not checked | run the scripted policy or no agent; the store is unaffected |
| **Federation** | signed exchange between configured peers with quarantine of unverified imports | eventual-convergence guarantees under real network partitions (not measured on physical hosts) | stop the peer; imported memories stay quarantined until reviewed |

## Typed refusals instead of overstated capability

* An action on unverified, contested or missing evidence is refused or escalated
  (`REVIEW_REQUIRED`, `REQUEST_MEASUREMENT`); inaction is never accepted as "safe" without a
  verified clear.
* A quantity the deterministic reader cannot read is `UNKNOWN` (hedged, negated as a whole,
  wrong unit, garbled), never a guess.
* A replay whose trace is incomplete is `NON_REPLAYABLE`; a factual replay that does not
  verify is `NO_EFFECT_CERTIFIED`, never "no effect".
* A command that needs OS resource limits the platform will not enforce is not run
  (`UNSUPPORTED_PLATFORM`).

## Causal language

Every CDM result carries a tier from `causal_replay.semantic.taxonomy`: an observed
dependence, a hypothetical effect, or a validated counterfactual under the registered
simulator. None of them is a claim about the physical world.
