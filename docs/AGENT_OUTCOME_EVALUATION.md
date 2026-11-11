# Agent outcome evaluation

The experimental runtime contracts live in `memory_fabric.agent_outcomes`.
They are opt-in and do not replace Memory Fabric's identity, evidence
verification, or `ActionGate`. `AgentObservation` rejects evaluator-only fields
recursively and has a stable canonical encoding and request digest. The
separate `OracleTask` schema seals hidden truth, eligibility, and reward in an
evaluator-side canonical payload. Its printed form and seal check do not expose
the payload. The seal detects accidental mutation; it is not an in-process
security boundary. Actor calls still receive only `AgentObservation`.

The recovery episode has a read-only typed recovery catalog, bounded steps/event
size/deadline, rejects repeated public state fingerprints as no progress, and
routes each proposed effect through `ActionGate.execute`, which rechecks current
evidence and authorization.

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

- Scripted recovery pilot: focused contract tests pass; full repository
  qualification awaits CI and the complete check suite.
- Local model: `REAL_AGENT_NOT_RUN` unless an actual pinned local inference is
  executed and recorded.
- Independent deployment and security review: `BLOCKED_EXTERNAL`.
- Policy release: `NOT_READY`; candidate recovery/CDM behavior must remain off
  by default until frozen matched gates support promotion.

The versioned offline gate is defined by
`tools/agent_outcome_gate_manifest.v2.json`. Run it with
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
