# Agent outcome evaluation

The experimental runtime contracts live in `memory_fabric.agent_outcomes`.
They are opt-in and do not replace Memory Fabric's identity, evidence
verification, or `ActionGate`. `AgentObservation` rejects evaluator-only fields
recursively and has a stable canonical encoding and request digest. The
recovery episode is bounded and routes each proposed effect through
`ActionGate.execute`, which rechecks current evidence and authorization.

## Evidence status

The attached master plan is a proposed 96-item program, not a report of work
already completed. This implementation now includes a deterministic, scripted
correction case in `benchmarks.outcome_recovery`. It exercises an observer
write, planner retrieval and replanning, executor authorization through
`ActionGate`, stale certificate refusal, and an immediate-abstention A0 pair.
This is integration coverage only: it is not an LLM agent run or evidence of
comparative benefit. Existing seeded team experiments remain in
`experiments/teamworld.py`; no full A0–A7 matched harness, confirmatory analysis,
or independent-world result is claimed here. The preregistration shell remains
`DRAFT / NOT FROZEN`.

Run six paired scripted cases and emit a JSON report with:

```powershell
python -m benchmarks.outcome_recovery --seeds 6
```

The report records attempted and executed unsafe effects separately. The stale
proposal in this pilot is attempted but rejected, so it is not counted as an
executed safety violation. Runtime measurements are harness diagnostics and are
not a performance benchmark. Seeds can be changed with `--seeds N`; reports
must be treated as a new scripted population, not confirmatory evidence.

- Scripted recovery pilot: focused contract tests pass; full repository
  qualification awaits CI and the complete check suite.
- Local model: `REAL_AGENT_NOT_RUN` unless an actual pinned local inference is
  executed and recorded.
- Independent deployment and security review: `BLOCKED_EXTERNAL`.
- Policy release: `NOT_READY`; candidate recovery/CDM behavior must remain off
  by default until frozen matched gates support promotion.

The versioned offline gate is defined by
`tools/agent_outcome_gate_manifest.v1.json`. Run it with
`python tools/agent_outcome_gate.py`; it executes the full repository suite by
default and emits a content-safe JSON manifest with the candidate Git SHA and
whether the worktree was dirty. `--skip-full` is useful for quick iteration,
but intentionally yields `NOT_RUN`, never `SCRIPTED_QUALIFIED`. Local-model
and deployment evidence remain separate `NOT_RUN` entries until performed.

The short simulated incident is available with
`python -m examples.outcome_recovery_demo`. Its actor trace shows the observed
correction, refusal of stale evidence, refreshed evidence, and authorized
effect. The evaluator view appears only after the episode ends.

Reports must preserve exact task-case denominators, raw paired outcomes, and
attempted versus executed safety events. A zero observed unsafe-event count is
not a zero risk; use a one-sided exact upper confidence bound. Historical
synthetic results are distinct experiments and are not pooled with future runs.
