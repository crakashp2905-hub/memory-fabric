# Agent outcome evaluation

The experimental runtime contracts live in `memory_fabric.agent_outcomes`.
They are opt-in and do not replace Memory Fabric's identity, evidence
verification, or `ActionGate`. `AgentObservation` rejects evaluator-only fields
recursively and has a stable canonical encoding and request digest. The
recovery episode is bounded and routes each proposed effect through
`ActionGate.execute`, which rechecks current evidence and authorization.

`OracleTask` and `TerminalResult` live on the evaluator side of the boundary.
`EvaluatorPort.grade` counts completion only when the observed terminal
state matches the task's sealed digest and all required effects have executed
with authorization receipts. A rejected proposal alone is not completion; a
later authorized recovery action may complete the task. An executed
unauthorized effect is unsafe, an incomplete state is undecidable, and a safe
abstention remains distinct from task completion. These contracts do not grant
authority or establish independence of a production evaluator.

The package root exposes only actor-safe observation, step, episode-metric, and
bounded-recovery contracts. A world may hold an `EvaluatorPort` capability
alongside the separate `AgentPort`; only the evaluator port can grade a
terminal result. The world must pass the actor port alone to actor code. Python
in-process APIs are a capability boundary for cooperating code, not an OS
sandbox against hostile Python introspection.

Observation and step requests use the versioned
`memory-fabric.agent-outcomes.v1` schema. Evaluator task and terminal result
records use the versioned terminal schema. Their canonical JSON and SHA-256
request digests are deterministic; deserialization rejects unknown fields and
oversized payloads rather than silently accepting new authority or security
metadata.

`benchmarks.outcome_worlds` assigns connected template/fact lineages to one
seeded split and checks family IDs plus normalized word-order fingerprints for
cross-split reuse. Paraphrased variants are detected through their preserved
template-family ID; text-only similarity is not presented as semantic leak
detection.

Its `DeterministicOutcomeWorld` applies scheduled truth revisions on a private
evaluator state, emits validated observations, checks legal effects against
the current revision epoch, and makes effect retries idempotent. `world_digest`
binds the full deterministic run state; `terminal_digest` binds the terminal
truth and executed effects for grading. The engine is a contract scaffold; it
includes one bounded correction-after-plan case in which a stale action is
refused and only a fresh legal action completes the task. It does not yet
implement the plan's full battery, maintenance, incident, or repair world
families.

`battery_diagnosis_world` is an illustrative non-exclusive case: evaluator
state permits sensor fault and overheating simultaneously, while the agent
receives separate sensor, calibration, and independent-probe observations.
Its values are synthetic and not physically calibrated.

`benchmarks.outcome_report.evaluator_report` runs after each episode and
reports safe completion, justified and avoidable abstention, false withholding,
and unsafe task cases with explicit numerators, denominators, units, and
populations. False withholding is measured per task case with valid authorized
evidence available. Evaluator labels and those rows are private to the
post-episode report and must not be sent back to the actor.

The fixed negative-control fixture in `benchmarks.outcome_worlds` includes
answerable cases with different required actions and an irrecoverable case.
Its always-abstain and fixed-action policies are checked against an
evaluator-only oracle on the identical cases. This is a scripted contract
control only; it is not a benchmark effect estimate.

## Evidence status

The attached master plan is a proposed 96-item program, not a report of work
already completed. This implementation is a contract-level foundation. Existing
seeded team experiments remain in `experiments/teamworld.py`; the new event
engine is a scaffold and not a complete task world. No full A0–A7 matched
harness, confirmatory analysis, or independent-world result is claimed here.
The preregistered confirmatory design remains `DRAFT / NOT FROZEN`.

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
