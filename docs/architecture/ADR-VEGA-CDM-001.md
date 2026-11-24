# ADR-VEGA-CDM-001: Vega-U as an optional semantic advisor to CDM

Status: accepted for experimental implementation. Date: 2026-11-24.
Baseline commit: `70e34c870d387cb5de8ba0bbdda0320cf3574d6c` (the plan's reviewed commit);
implemented on top of the agent-validation work (`research/results/agent-outcomes/`).

## Decision

vega-U is reached only through a new loopback client,
`memory_fabric.adapters.vega_u`, and only produces typed proposals consumed by
`memory_fabric.causal_replay.semantic`. Governance, retrieval authorization,
`ActionGate`, erasure, retraction, certificates and the event log are unchanged.
The canonical outcome runtime stays `memory_fabric.outcome_typed`; the advisor
is an opt-in annotation there (`outcome_typed.semantic_advisory`), not a fourth
outcome package. Default mode is `OFF`.

## Protocol inventory (VEGA-CDM-003)

| | System One client (`adapters/systemone.py`) | vega-U client (`adapters/vega_u.py`) |
|---|---|---|
| Server | Kev / TypeSafe | vegaml 0.19.0 `vegaml-serve` |
| Endpoint | `POST /v1/systemone` | `POST /v1/decide`, `GET /health`, `GET /v1/model` |
| Yes/no type | `noul` | `boolean` (answer is p(true); probs keyed `"True"`/`"False"`) |
| Answer fields | `choice`, `score`, distribution | `choice`/`boolean`/`score`, `probs`, `prediction_set`, `abstain`, `unbound`, `readout` |
| Identity | model name | `audit.engine_sha256`, `audit.reader`, `audit.vegaml`, `audit.calibration_version` |

The two are not coerced into each other. The response shape was pinned from a
real recorded decision (`tests/fixtures/vega_u/decide-0.19.0.json`, Hub revision
`6aee375845724d2cca21d5fd5c043a028dbc1b48`, engine sha256
`78f96be7c6a06abb873e573fcf9e43ef467010a30c72cd6cac32538cd7078db8`).

## Integration map (VEGA-CDM-004, 005)

| CDM interface | Used for | Semantic layer touching it | Acceptance test |
|---|---|---|---|
| retrieval / `_eligible_ids` | the only evidence a model sees | `semantic.packets.from_retrieval`, `recheck` | `tests/test_semantic_pipeline.py::Packets` |
| `independence.global_ref` | source roots | packets `origin_root`, `support.corroboration` | `Support::test_paraphrased_copies_of_one_root_count_once` |
| `causal_replay.state.update`, `bayes` | exact belief | `semantic.beliefs` | `Beliefs` |
| `causal_replay.intervention.create/compose` | validated interventions | `semantic.interventions` | `Interventions` |
| `executor.execute`, `verifier.verify_execution` | factual and counterfactual replay | `semantic.effects` | `Effects` |
| `scheduler` selectors | replay budget | `semantic.scheduler` | `Scheduler` |
| `outcome_typed.api.OutcomeAPI.inspect_failure` | recovery advice | `outcome_typed.semantic_advisory` | `tests/test_vega_recovery.py` |

## Invariant and threat model (VEGA-CDM-007)

A model output can never: change what a principal may read, change a memory's
lifecycle, write evidence, grant a tool, approve an action, or label a
hypothesis as a verified effect. These are enforced structurally (closed option
sets, the closed intervention vocabulary, edge-type rules, and modules that do
not import governance writers), and tested in `tests/test_vega_cdm_security.py`.
The threat model is in [VEGA_CDM_THREAT_MODEL.md](../VEGA_CDM_THREAT_MODEL.md).

## First research question (VEGA-CDM-006)

Population: the seeded worlds in `benchmarks/vega_cdm_worlds.py`. Mechanism: the
advisor reads evidence the exact parser cannot (paraphrase). Comparator: A5
(governed, exact parser), and A3 (pooled). Primary endpoint: evaluator-confirmed
safe terminal completion over all assigned cases.

## Consequences

- Core stays dependency-free; vegaml, torch and weights live in a separate
  environment and are never downloaded by this package.
- `QUALIFIED` mode is refused in code until a registered efficacy result exists.
- The development run with the 0.8B reader increased unsafe actions (see the
  limitations page), so the advisor stays `OFF`/`SHADOW`.
