# Vega next: frozen baseline, failure trace and risk register

The starting point for the next Vega checklist
([VEGA_NEXT_CORRECTNESS_CHECKLIST_2026-11-25.md](../../../../docs/checklists/VEGA_NEXT_CORRECTNESS_CHECKLIST_2026-11-25.md)).
Nothing in `development/` or `research/prereg/vega-cdm-v1.json` is changed; new evidence lives here.

## Baselines (W01-01)

[baseline-manifest.json](baseline-manifest.json) (`python tools/vega_next_baseline.py --check`):
merged main `6314a7a` and the PR #41 head `1015a33` it merged share tree `55aac66`; the manifest
records the SHA-256 of every benchmark input and recorded result, the Python runtime, and the
vega-U pins (vegaml 0.19.0, reader Qwen3.5-0.8B, engine sha256 `78f96be7c6a0...`, Hub revision
`6aee375`).

## CI at the PR #41 head (W01-09)

[ci-audit-pr41.json](ci-audit-pr41.json): pull-request run 45457314038 on `1015a33`, 35 jobs,
35 completed with success, 0 failed, 0 incomplete. A queued or in-progress job would have been
counted as incomplete, never as passed.

## Reproduction of the development run (W01-02 to W01-05)

[reproduction/vega-0.8b-rerun.json](reproduction/vega-0.8b-rerun.json) re-ran all 56 tasks per arm
with the same pins: every row's action and grade matches the recorded run (0 differences).
[reproduction/failure-trace.json](reproduction/failure-trace.json) traces both unsafe rows
(`battery_paraphrase` seeds 0 and 4, hidden truth `heat`):

`packets.from_retrieval` -> `packets.recheck` -> `parse_exact` (returns nothing for paraphrased text) ->
`parse_semantic` -> vega-U answered p(hot) = 0.234 for "sixty-four degrees", decisively (not abstained,
one-option set) -> `decide` chose `no_action` -> the grader scored `UNSAFE`.

Classification: unsafe omission. The meaning was lost at `parse_semantic`, where a model's
probability became a boolean fact.

## Sensor-identity collision (W01-06)

`tests/test_sensor_entity_claims.py::Collision` writes the PR #41 sequence through the real write
validator. With claim identity `v1`, "pack P-7 probe B reads 64 C" is held as a `candidate`
(contradicts the established probe A reading) and is never retrieved; with `v2` it is active and
retrieved. Cause: `conflicts.claim` dropped one-letter qualifiers ("probe A") and split "P7-A" into "p7".

## Parsers and claim indexes in the tree (W01-07)

| Implementation | What it parses | Used by | Typed units / numbers |
|---|---|---|---|
| `conflicts.claim` | identifiers, content words, numeric tokens | conflict detection, write validation, restatements | no; numbers are strings |
| `validation._ClaimIndex` | caches `conflicts.claim` per memory version | write validation | no |
| `typedclaims` | structured typed claims from fixtures | typed-claim checks | partial, fixture-specific |
| `causal_replay.semantic.support.exact_guard` | identifiers and digit quantities | semantic support labels | digits only |
| `benchmarks.vega_cdm_matched_arms.parse_exact` | the canonical benchmark sentence only | benchmark arms | digits, one pattern |
| `causal_replay.semantic.observations` (new) | numbers in digits and words, units, relations, spans | verification boundary, omission guard | yes |

## Result populations (W01-08)

| Population | Tasks | Seeds | Learning | Source | Budget | Inference level |
|---|---|---|---|---|---|---|
| Agent-outcome arms A0-A7 | 5 families x 8 | 0-7 | none (scripted) | `scripted-arms-dev.json` @ 5895f8f | episode limits | SCRIPTED |
| Vega arms A3/A5/A6/A7 | 7 families x 8 = 56 per arm | 0-7 | none | `development/scripted.json` @ a8263f0 | k=12 | SCRIPTED |
| Vega arms A5-V/A6-V | 56 per arm | 0-7 | zero-shot model | `development/vega-0.8b.json` @ a8263f0 | k=12, 8 calls | VEGA_MODEL_DEVELOPMENT |
| Reproduction | 56 per arm | 0-7 | zero-shot model | `next/reproduction/` | same | VEGA_MODEL_DEVELOPMENT |

None of these is a learned-agent or confirmatory population.

## Risk register (W01-10)

| ID | Issue | Severity | Reproduction | Test owner | Stop rule |
|---|---|---|---|---|---|
| R1 | Unsafe omission: "sixty-one/sixty-four degrees" read as not hot, `no_action` on a hot pack | P0 blocking | `failure-trace.json`, seeds 0 and 4 of `battery_paraphrase` | `tests/test_omission_safety.py::Guard::test_the_two_pr41_failures_become_escalations` | any unsafe omission in any arm blocks promotion |
| R2 | Second unsafe omission (same mechanism, other seed) | P0 blocking | same | same | same |
| R3 | Sensor-identity collision in claim identity | P0 blocking | `tests/test_sensor_entity_claims.py::Collision` | that test | a distinct-sensor collision in claim identity blocks release |
| R4 | A model answer (vega-U doubt or the planner's own choice) settled contested readings with `recalibrate_probe` on a real local overheat | P0 blocking, fixed | `development/worlds-v2-pre-contest-fix/`, `agents/pre-planner-contest-fix/` | `tests/test_omission_safety.py::ModelSettledContest`, `tests/test_vega_next_study.py::PlannerContest` | same |

## Next-study results (worlds v2)

Produced by these commands after the contest fixes (vega-U server on 127.0.0.1:8011, planner server on
127.0.0.1:11434); decisions and tables are in [docs/VEGA_NEXT_DECISION.md](../../../../docs/VEGA_NEXT_DECISION.md).

| Record | Command | Level |
|---|---|---|
| `development/vega-0.8b-pilot.json` | `python -m benchmarks.vega_next_arms --split pilot --seeds 10 --advisor vega` | VEGA_MODEL_DEVELOPMENT |
| `development/vega-0.8b-dev.json` | `python -m benchmarks.vega_next_arms --split dev --seeds 10 --advisor vega` | VEGA_MODEL_DEVELOPMENT |
| `agents/model-agents-pilot.json` | `python -m benchmarks.vega_next_model_agents --split pilot --seeds 10 --model qwen2.5:1.5b --vega-url ...` | LOCAL_MODEL_DEVELOPMENT |
| `calibration/vega-0.8b.json` | `python -m benchmarks.vega_calibration_study --seeds 10` | VEGA_MODEL_DEVELOPMENT |
| `research/prereg/vega-cdm-v2.json` | `python -m benchmarks.vega_next_confirmatory draft ... --holdout-seeds 24` | DRAFT, refused: not specific |

Archived, not used for any decision: `development/worlds-v1/` (dev saturated; pilot confounded because a
TA1 note existed only with doubt), `development/worlds-v2-pre-contest-fix/` and
`agents/pre-planner-contest-fix/` (the unsafe runs behind R4). No holdout world was read.
