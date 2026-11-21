# Scripted matched arms, development rows

Raw rows and every aggregate: [`scripted-arms-dev.json`](scripted-arms-dev.json),
produced by `python -m benchmarks.outcome_arms --seeds 8 --out research/results/agent-outcomes/scripted-arms-dev.json`
([harness](../../../benchmarks/outcome_arms.py), contract tests in
[`tests/test_outcome_arms.py`](../../../tests/test_outcome_arms.py)).

**Status: `SCRIPTED_DEVELOPMENT`, parity `INCOMPLETE` (A6 not run), promotion `NOT_ASSESSED`.**

## What this is

One deterministic scripted team (observer, planner, executor) runs through the
canonical episode runtime on 5 world families × 8 seeds = 40 tasks. Every actor
arm uses the same team, tools, budget, worlds and seeds. Arms differ only in the
memory port and in whether recovery is enabled, and A3's recovery is as capable
as A5's. A7 is the evaluator's own ceiling and is never an actor.

## Results

Rates come from the JSON above. `safe_success` counts a completed task, or a
justified abstention where nothing authorized acting.

| arm | memory | recovery | safe_success | unsafe |
|---|---|---|---:|---:|
| A0 | none | yes | 0.4 | 0.0 |
| A1 | agent-local | yes | 0.4 | 0.0 |
| A2 | pooled | no | 0.0 | 0.8 |
| A3 | pooled + recheck | yes | 0.4 | 0.4 |
| A4 | Memory Fabric + gate | no | 0.4 | 0.2 |
| A5 | Memory Fabric + gate | yes | 0.6 | 0.2 |
| A7 | evaluator ceiling | — | 0.6 | — |

These are paired, per-family contrasts on safe_success, from the same JSON:

- **A5−A3 = +0.2** overall ([rows](scripted-arms-dev.json)). All of it comes from `restricted_source`, the only
  family where tenant access control matters. A3 ties A5 on `public_correction`
  and `remote_retraction`, so when the team can see a correction or a retraction
  note, recovery alone is enough.
- **A5−A4 = +0.2** overall. All of it comes from `public_correction`, where only
  recovery completes the task.
- **A3−A2 = +0.4**, from recovery on `public_correction` and `remote_retraction`.
- **No arm exceeds the A7 ceiling.** 16 of the 40 tasks (`silent_change` and
  `delayed_correction`) have no headroom: no arm can complete them. On
  `silent_change`, every acting arm is graded unsafe.

## What this does not show

- **No variance.** The policy is deterministic, so each family's outcome is
  identical across seeds. The 8 seeds add no statistical evidence; no interval
  or test is meaningful here.
- **No prevalence.** The families were written to exercise known mechanisms.
  Which family favours which arm was set by that design, not measured in
  realistic task populations, so the overall rates mean nothing outside this
  mixture.
- **No learned-agent evidence.** Every row is scripted. Model behaviour is
  `REAL_AGENT_NOT_RUN` in this environment.
- **A6 (CDM) is not run.** The comparison is `INCOMPLETE` by its own registry.
- **The A0/A1 negative-control arms score 0.4 safe_success.** That is because
  never acting is the correct outcome in two families. Completion separates them
  from the governed arms.
