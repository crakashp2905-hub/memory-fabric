# Feature-freeze release: decision

Per-component verdicts for the feature-frozen release, written from the records under
[qualification/](../qualification/) and [research/results/vega-cdm/freeze/](../research/results/vega-cdm/freeze/).
Plan: [FEATURE_FREEZE_RELEASE_CLOSURE_2026-11-25.md](checklists/FEATURE_FREEZE_RELEASE_CLOSURE_2026-11-25.md);
supported use, limits and rollback: [SUPPORTED_SCOPE.md](SUPPORTED_SCOPE.md).

**Release label: bounded beta.** Whole-product 1.0 is **NO_GO**: no independent security review,
staging host, supervised pilot or signed approvals exist, and those cannot be produced inside
this repository. Every feature is kept; what has not qualified runs in its safe mode.

| Component | Verdict | Why |
|---|---|---|
| CORE | **HOLD** (engineering gates pass) | tenant, effect, correction, erasure, identity and migration suites pass; staging host and independent review missing |
| VEGA | **SHADOW** advisory; autonomous influence **HOLD** | margin over the shuffled placebo +0.035 on fresh data, below the strict 0.10 bar |
| CDM | **ADVISORY_ONLY**; automatic replay selection is a **candidate** | all three ladder stages pass for dependence-first replay; the learned planner made no pack errors, so the study tests selective replay, not error recovery |
| MODEL_AGENT | **supervised only**; Qwen2.5-3B promoted as the pinned planner | pre-registered validation passes (+0.375 completion, lower bound +0.23, 0 unsafe); the three-role team completes nothing on the test server |
| FEDERATION | **HOLD** | partition, clock-skew and physical multi-host measurements have not run |
| WHOLE_PRODUCT | **NO_GO for 1.0** | depends on every component above and on external review |

## Thresholds: strict first, gentler only on fresh data

The plan asked for thresholds that start strict and relax over time. They are pre-registered in
[freeze-threshold-ladder.json](../research/prereg/freeze-threshold-ladder.json) (digest `0c4bdf2b6857`),
sealed before any stage's data existed and enforced by `benchmarks.freeze_ladder`: a gentler stage
is reachable only after the stricter one passed, only on rows no earlier stage used, and safety bounds
never relax. An efficacy stage also needs its paired one-sided 95% lower bound above zero. One sealed
amendment moved the CDM S1 population to fresh seeds because the original seeds could not reach the
stage's own minimum size; no threshold changed. Results: [qualification/ladder-results.json](../qualification/ladder-results.json).

| Metric | S1 (strict) | S2 | S3 (gentlest) |
|---|---|---|---|
| Vega margin over shuffled placebo | FAIL: +0.035 vs 0.10 (lower bound +0.005) | not eligible | not eligible |
| Vega margin over the parser | FAIL: +0.075 vs 0.10 (lower bound +0.02) | not eligible | not eligible |
| Vega unsafe-omission bound | PASS: 0/200, bound 0.0149 <= 0.02 | not run | not run |
| Planner completion gain (prompt v2) | FAIL: +0.16 vs 0.10 but lower bound -0.02 | not eligible | not eligible |
| Planner unsafe-omission bound | PASS: 0/100, bound 0.0295 <= 0.03 | not run | not run |
| CDM relative net utility | PASS: 0.15 vs 0.10 (scripted) | PASS: 0.15 vs 0.05 (learned) | PASS: 0.15 vs 0.02 (learned, 300 decisions, lower bound +0.75/task) |

No threshold was lowered after a failure: a failed stage ends that ladder and the result stays HOLD.

## What the freeze fixed (each with a regression test and a mutant)

Mutation check: 27/27 mutants killed, six of them for the guards below (`tools/mutation_check.py`).

* **Idempotency** (F02-03): a key first used without a request now binds to its tool and actor.
* **Approvals** (F02-05): an approval may expire, and an action with a request needs a bound approval.
* **Quantities** (F03-03): "no more/less than" kept its direction (it was inverted) and a statement
  negated as a whole is UNKNOWN (it was read as asserted). Found by a 43-sentence hand-annotated fixture.
* **Identity** (F03-01): "Probe-A", "probe_A", "probe(A)", "sensor TA-1", "P7/A", "cell 3-4" and
  "probe Alpha" each dropped out of the claim identity, so two instruments were one claim. No recorded
  world text changes identity; v1 is unchanged for rollback.
* **Planner contest** (W05, found by the earlier pilots): a planner model's own choice cannot settle
  contested readings without cooling.
* **Isolation** (F09-02): `RLIMIT_NPROC` did not bind under root; the child now drops to `nobody`, and a
  fork bomb is refused at 16 processes. On macOS a refused limit now means "not run" instead of an exception.

Every earlier failure re-runs on identical inputs and is corrected: 2 PR #41 unsafe omissions and 22
contested-evidence cases ([qualification/reproductions.json](../qualification/reproductions.json)).

## Vega

* Calibration: see the calibration stage in the ladder results; numbers never come from the model.
* Diagnosis ([diagnosis.json](../research/results/vega-cdm/freeze/specificity/diagnosis.json)): vega-U answered
  yes to both "in doubt?" and "verified accurate?" on half the notes, and the original rule discarded those
  answers. A margin rule fitted on dev notes only, frozen before the pilot, turned the near-tie with the
  placebo (+0.01) into a specific but small gain (+0.035, lower bound +0.005).
* Next experiment: a reader whose "verified accurate" answers carry more of the gain, measured against the
  same ladder on fresh seeds; until then Vega stays SHADOW.

## CDM

Dependence-first replay beats no replay and full replan in net utility at all three stages, re-asking one
decision per corrected decision against six for a full replan
([qualification/cost.json](../qualification/cost.json)). The learned planner (Qwen2.5-1.5B) made no pack
errors on digit readings, so dependence-first equals the oracle; the result is about choosing what to
replay, not recovering from model errors, and it is not a claim about physical causality. CDM stays
`ADVISORY_ONLY` in this release; automatic replay selection needs the operational gates (canary, on-call)
that require a deployment.

## Learned agents

* Root causes of the 1.5B planner's failures: mostly planning (no_action with a verified hot sensor),
  then selection ([error-taxonomy.json](../research/results/vega-cdm/freeze/planner/error-taxonomy.json)).
* A revised prompt raised completion but collapsed onto one action (`cool_and_recalibrate` on 74/100);
  the lower-bound rule did not credit it.
* Qwen2.5-3B (baseline prompt) was pre-registered and validated on fresh seeds 40-59: completion 0.595 vs
  0.22, 0 unsafe omissions; about twice the model time per task, less per completion.
* The three-role team with real 3B calls completed 0/5 episodes: the observer omitted `arguments.tool`. The
  loopback test server does not enforce JSON schemas, so the actor's constrained decoding was not in effect;
  a schema-enforcing runtime is the next step. Every call was recorded; no scripted substitute ran.

## Blocked outside this repository

Independent security review (F09-08, F14-01), supervised pilot and operator utility (F14-02, F14-04),
staged deployment (F14-07), independent hardware and a 16 GB Apple Silicon host (F11-02, F14-03),
physical multi-host network tests (F10-07), release signatures (F13-08).
