# DecisionRecord schema v1

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

This is a schema contract. It does not persist decisions or automatically
connect them to action-gate events; those remain separate decision-ledger
implementation work.
