# Agent outcome evaluation

The experimental runtime contracts live in `memory_fabric.agent_outcomes`.
They are opt-in and do not replace Memory Fabric's identity, evidence
verification, or `ActionGate`. `AgentObservation` rejects evaluator-only fields
recursively, rejects evaluator handles and callables, and deep-freezes nested
data before producing a stable canonical encoding and request digest. Actor
observations and steps carry schema v3 and support strict JSON roundtrips;
unknown fields, duplicate JSON keys, non-finite values, and unrecognized
security metadata fail closed. Recovery progress records hash state tokens
instead of retaining them in its public trace. The separate `OracleTask` schema
seals hidden truth, eligibility, and reward in an
evaluator-side canonical payload. Opening it and serializing terminal grades
require a task-bound `EvaluatorCapability`; actor contracts reject oracle,
grade, and capability objects. This is an in-process API boundary, not a Python
sandbox against reflection or hostile code with module access. Actor calls still
receive only `AgentObservation`.

In-house worlds use `DeterministicWorldSpec` and `ScheduledWorldEvent` from
`benchmarks.outcome_worlds`. Replay sorts scheduled events by tick and ID,
tracks truth and legal effects in the evaluator snapshot, and increments the
revision epoch when either changes. Its canonical state bytes and outcome
digest are stable for a fixed seed and spec. `WorldSnapshot.public_view()`
returns scheduled observations and the public epoch without hidden truth or
evaluator legal-effect data.

`run_correction_after_plan_scenario(seed)` in the same module exercises a
correction that arrives after an action was planned. It quarantines the old
evidence, confirms that the stale request is refused by `ActionGate` without a
side effect, then creates a fresh certificate and exact-action grant from the
delivered correction. The terminal grader completes only after the re-evaluated
legal action executes. This remains a local scripted simulation with no
external physical effect.

`build_battery_diagnosis_world(seed)` supplies a pack-sensor reading, an
independent thermal-probe reading, and a calibration-lab record with distinct
source roots. `diagnose_battery(public_view)` returns a set of coexisting
conditions; a drifting pack sensor and actual overheating can both be present,
and the diagnosis leaves the single root cause unresolved when both findings
are supported.

The maintenance helpers provide a mock task with three coupled prerequisites:
isolation, cooling restoration, and temperature verification. Each prerequisite
has two safe action choices, dependencies constrain their order, and the final
release action is blocked until every prerequisite is satisfied. This is a
contract simulation; it does not invoke physical equipment.

`build_incident_triage_world(seed)` adds a second alert that expands the affected
dependency set. `run_incident_triage_actions` binds the revised plan to the
current revision, requires rollback of an already-applied stale remediation,
and checks containment and verification across every current dependency before
closing the incident.

`create_coding_repair_session(seed)` exposes one source file and visible
contract tests through bounded read, patch, public-test, and submit calls. The
hidden version-pair oracle returns only pass/fail; it is evaluated by a small
AST interpreter that rejects calls and other executable constructs, so patches
never run arbitrary Python. This is a scripted tool-surface contract, not a
process sandbox against hostile Python with direct module access.

`build_federated_evidence_world(seed)` and `run_federated_evidence_scenario`
cover a wrong source claim copied through two relays, a contradictory credible
source, and a delayed correction from the original source. Claims are counted
by provenance root rather than copy ID. Effects recorded against older world
revisions receive a content-free stale log naming the invalidating events.

The irrecoverable recovery fixture covers revoked permission, erased records,
an inaccessible source, and no legal replacement. Its scripted responder
reports the blocker, records an explicit abstention, and refuses privileged
override paths without executing an effect.

The recovery episode has a closed typed catalog of read-only actions. Catalog
entries reject any non-read-only setting, and the enum cannot represent effect
operations. The episode also bounds steps, event size, and deadline, rejects
repeated public state fingerprints as no progress, and routes proposed effects
through `ActionGate.execute`, which rechecks current evidence and authorization.
Recovery limits have hard ceilings, and the canonical `recovery-audit.v1`
record includes configured limits, consumed attempts, terminal status, and a
stable failure reason such as `no_monotonic_progress` or `deadline_exceeded`.

The experimental `agent_outcomes.outcomes` grader accepts only host-supplied
`ActionExecution` records paired with canonical task/step IDs and one
authoritative terminal snapshot. A proposal or actor completion sentence cannot
count as success. Refused effects do not block a later authorized recovery;
unfenced or unauthorized executions fail, while uncertain or conflicting
terminal results stay undecidable. The host remains responsible for preserving
the authenticity of the execution and world-state receipts it supplies.

## Evidence status

The attached master plan is a proposed 96-item program, not a report of work
already completed. This implementation now includes a deterministic, scripted
correction case in `benchmarks.outcome_recovery`. It exercises an observer
write, planner retrieval and replanning, executor authorization through
`ActionGate`, stale certificate refusal, and an immediate-abstention A0 pair.
The actor runner receives only its initial `AgentObservation` and a later public
correction event; the private terminal target is used only by the evaluator
after the actor returns.
This is integration coverage only: it is not an LLM agent run or evidence of
comparative benefit. Existing seeded team experiments remain in
`experiments/teamworld.py`; no full A0–A7 matched harness, confirmatory analysis,
or independent-world result is claimed here. The preregistration shell remains
`DRAFT / NOT FROZEN`.

`benchmarks.outcome_worlds` assigns generated cases by connected components of
template families, fact families, provenance roots, exact identifiers,
surface-free transition signatures, and token-order-independent text
fingerprints. This prevents those linked cases from crossing train/dev/heldout
boundaries. Too few independent components fail closed. The text check catches
literal token shuffles, not semantic paraphrases; authored provenance and family
IDs remain necessary. The allocator does not freeze the eventual world catalog,
confirmatory seeds, or analysis rules.

Run six paired scripted cases and emit a JSON report with:

```powershell
python -m benchmarks.outcome_recovery --seeds 6
```

The report records attempted and executed unsafe effects separately. The stale
proposal in this pilot is attempted but rejected, so it is not counted as an
executed safety violation. Runtime measurements are harness diagnostics and are
not a performance benchmark. Seeds can be changed with `--seeds N`; reports
must be treated as a new scripted population, not confirmatory evidence.

The [preregistration shell](../research/prereg/agent-outcome-v1.md#outcome-labels-and-exact-denominators)
defines completion, legitimate abstention, false withholding, recovery, and
safety numerators and denominators. The task population is unique matched case
IDs, never the number of agents or steps. `paired_completion_analysis` emits
schema v2 with every estimate under `metrics`, carrying its numerator,
denominator, and named population alongside the value. The current pilot does
not record evaluator-labeled abstention or evidence-availability opportunities,
so those rates remain `NOT_MEASURED`; absence of those fields is not reported as
zero.

The negative-control contract fixes eight answerable and four unanswerable
case IDs in `tests.test_outcome_matched_arms`. Its perfect-information oracle
scores 12/12 on disposition, compared with 8/12 for always-act and 4/12 for
always-abstain. Completion remains separate: the control illustrates why a safe
abstention can be correct behavior without counting as a completed task. The
always-act arm records attempted unsafe actions, not executed effects. The
test scorer synthesizes a terminal value only for exact requests on evaluator-
authorized cases; it does not call `ActionGate` or a physical-effect executor.
This fixture is not a benchmark result.

- Scripted recovery pilot: focused contract tests pass; full repository
  qualification awaits CI and the complete check suite.
- Local model: `REAL_AGENT_NOT_RUN` unless an actual pinned local inference is
  executed and recorded.
- Independent deployment and security review: `BLOCKED_EXTERNAL`.
- Policy release: `NOT_READY`; candidate recovery/CDM behavior must remain off
  by default until frozen matched gates support promotion.

The versioned offline gate is defined by
`tools/agent_outcome_gate_manifest.v16.json`. Run it with
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

Outcome report v3 requires each incomplete task row to carry one or more
supported terminal failure codes. Mixed causes are retained as a list. The
taxonomy covers retrieval misses, missing observations, unsupported claims,
false policy denials, planning and tool errors, coordination errors, stale
data, and abstention opportunity cost. Successful episodes carry no terminal
failure code; recovered intermediate refusals remain in the separate safety
attempt counters.

`memory_fabric.agent_outcomes.eligibility` separately classifies evidence
refusals as missing, withheld, irrelevant, stale, contested, unauthorized,
erased, duplicate, insufficient, or unknown. It accepts typed access,
certificate, answerability, and relevance signals. Unknown reason codes map to
`unknown`; answerability diagnosis uses the verdict and exposed-item count, not
the question or memory text. The serialized diagnosis contains only these
closed codes and read-only recovery suggestions. `not_found` stays
`missing` even when the host intentionally conceals whether an identifier is
cross-tenant. Suggestions are advisory; the actor must still pass any effect
through `ActionGate`.

`benchmarks.outcome_report.paired_completion_analysis` computes matched
completion rates, treatment-minus-baseline effects, a seed-cluster bootstrap
interval, and an exact sign test over cluster means. It rejects unmatched task
IDs and reports whether the five-independent-seed count floor is met. This is a
count check only; passing it does not establish research eligibility. An arm
compared with itself is a zero-effect negative
control. These summaries do not freeze a confirmatory threshold or turn the
current scripted pilot into a research result.
