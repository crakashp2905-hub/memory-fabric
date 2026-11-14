# Agent outcome evaluation

The experimental runtime contracts live in `memory_fabric.agent_outcomes`.
They are opt-in and do not replace Memory Fabric's identity, evidence
verification, or `ActionGate`. `AgentObservation` rejects evaluator-only fields
recursively and has a stable canonical encoding and request digest. The
recovery episode is bounded and routes each proposed effect through
`ActionGate.execute`, which rechecks current evidence and authorization.

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
