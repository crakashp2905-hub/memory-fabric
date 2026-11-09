# DecisionRecord schema v1

## Re-evaluation receipts

`DecisionLedger.reevaluation_receipts_from_event(event_id)` returns immutable
`DecisionReevaluationReceipt` values for exact correction/retraction impacts.
Each receipt includes the changed `EvidenceVersion`, current replayed decision
status, reliance proof edge IDs, affected effect edge IDs, and a deterministic
content-derived ID. `to_json()` emits canonical JSON for byte-identical replay.
Receipts set `reevaluation_required=true` and `action_authorized=false`; callers
must perform their ordinary authorization and execution checks independently.
Receipt generation is a read-only projection and does not add an event.

`memory_fabric.DecisionRecord` is an immutable, JSON-serializable contract for
recording a goal, candidate options, the selected option, evidence versions,
constraints, and lifecycle status. Each option can carry its own evidence
version references, so discarded alternatives retain their basis.

```python
from memory_fabric import DecisionOption, DecisionRecord, EvidenceVersion

pressure = EvidenceVersion(memory_id="mem-123", version=2)
record = DecisionRecord(
    decision_id="decision-7",
    tenant_id="tenant-1",
    agent_id="agent-9",
    decided_at="2026-11-08T10:30:00Z",
    goal="Choose a safe operating mode",
    options=(
        DecisionOption("reduced", "Use reduced load", (pressure,)),
        DecisionOption("stop", "Stop the process", (pressure,)),
    ),
    chosen_option_id="reduced",
    evidence_versions=(pressure,),
    constraints={"max_load_percent": 60},
)
payload = record.to_dict()
restored = DecisionRecord.from_dict(payload)
```

Identity (`decision_id`, `tenant_id`, `agent_id`) and timezone-aware
`decided_at` are required. The v1 statuses are `proposed`, `approved`,
`executed`, `superseded`, and `requires_reconsideration`. Status changes use
`transition_status`, which returns a new record and appends a typed transition;
the original object and its history remain immutable. Illegal transitions
raise `DecisionTransitionError`. Evidence versions use the memory ID and
positive integer version; the record does not copy evidence content.
Constraints are restricted to finite JSON scalar values.

`DecisionLedger` stores immutable `DecisionRecorded`, `DecisionSeen`, and
`DecisionEdgeRecorded` events in the hash-chained event log. `DecisionGraph`
rebuilds the decision and its typed `seen`, `relied_on`, `authorized`, and
`executed` relationships by replay. A `seen` row must point to an exposed
`ExposureDecided` event; it is deliberately separate from reliance. A
`relied_on` edge carries an exact evidence version listed by the decision.
Effect edges carry no claim evidence. Their target is the integrator-supplied
governed effect receipt ID, kept separate from claim evidence; automatic
derivation from action-gate/execution receipts and correction-driven impact
queries remain separate work.

For an impact query, pass the event ID of a `MemoryVersioned` correction or
`RetractionApplied` event to `DecisionLedger.impacts_from_event`. The result
contains the exact changed evidence version, the direct reliance edges that
form its proof path, and authorization/execution receipts attached to that
decision. For federated retractions it checks the origin version and every
locally cited version of the explicitly targeted local memory ID.
`RetractionRequested` is not treated as a completed retraction.

The ledger incrementally indexes appended decision and edge events by sequence.
After restart it rebuilds the in-memory index from the append-only log. The
`reference_impacts_for` path remains available for qualification and uses a
full scan; the 10,000-decision qualification and its seeded manifest are
recorded in `research/results/n1-04-dependency-index.json`.

`DecisionOptionAssessed` records why a non-selected option lost and the exact
evidence versions that formed its rejection basis. `reassess_alternatives`
shows each registered option, the recorded reason, and whether a corrected
version makes the option worth reconsidering. `reconsider` means the
alternative might become viable; it does not change the chosen option or grant
authority. Options without an assessment remain visible as `unassessed`.

`DecisionLedger.transition_decision` appends each status transition as a
`DecisionStatusChanged` event. It validates the current status while holding
the event-log write transaction, rejects competing stale transitions with
`DecisionTransitionError`, and rebuilds `status_history` from the log after
replay. Repeating the exact same transition is idempotent.
