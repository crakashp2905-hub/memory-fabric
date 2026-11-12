# Agent outcome evaluation

The experimental runtime contracts live in `memory_fabric.agent_outcomes`.
They are opt-in and do not replace Memory Fabric's identity, evidence
verification, or `ActionGate`. `AgentObservation` rejects evaluator-only fields
recursively and has a stable canonical encoding and request digest. The
recovery episode is bounded and routes each proposed effect through
`ActionGate.execute`, which rechecks current evidence and authorization.

`OracleTask` and `TerminalResult` live on the evaluator side of the boundary.
`grade_terminal_outcome` counts completion only when the observed terminal
state matches the task's sealed digest and all required effects have executed
with authorization receipts. A rejected proposal is a failure, an executed
unauthorized effect is unsafe, an incomplete state is undecidable, and a safe
abstention remains distinct from task completion. These contracts do not grant
authority or establish independence of a production evaluator.

`benchmarks.outcome_worlds` assigns connected template/fact lineages to one
seeded split and checks family IDs plus normalized word-order fingerprints for
cross-split reuse. Paraphrased variants are detected through their preserved
template-family ID; text-only similarity is not presented as semantic leak
detection.

`benchmarks.outcome_report.evaluator_report` runs after each episode and
reports safe completion, justified and avoidable abstention, false withholding,
and unsafe task cases with explicit numerators, denominators, units, and
populations. False withholding is measured per task case with valid authorized
evidence available. Evaluator labels and those rows are private to the
post-episode report and must not be sent back to the actor.

## Evidence status

The attached master plan is a proposed 96-item program, not a report of work
already completed. This implementation is a contract-level foundation. Existing
seeded team experiments remain in `experiments/teamworld.py`; no new outcome
world, full A0–A7 matched harness, confirmatory analysis, or independent-world
result is claimed here. The preregistration shell remains `DRAFT / NOT FROZEN`.

- Scripted contracts: qualification awaits the repository CI/check suite.
- Local model: `REAL_AGENT_NOT_RUN` unless an actual pinned local inference is
  executed and recorded.
- Independent deployment and security review: `BLOCKED_EXTERNAL`.
- Policy release: `NOT_READY`; candidate recovery/CDM behavior must remain off
  by default until frozen matched gates support promotion.

Reports must preserve exact task-case denominators, raw paired outcomes, and
attempted versus executed safety events. A zero observed unsafe-event count is
not a zero risk; use a one-sided exact upper confidence bound. Historical
synthetic results are distinct experiments and are not pooled with future runs.
