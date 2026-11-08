# Evidence requirement graph v1

`memory_fabric.parse_requirement_graph` parses a versioned static policy graph
used to describe evidence that a consequential action will require. Parsing is
structural only: it does not evaluate a claim, count source independence,
interpret timestamps, or authorize an action. The action gate remains the
deterministic authority boundary.

## Grammar

```json
{
  "schema": "memory-fabric-requirement-graph/1",
  "graph_id": "pump-restart-v1",
  "rules": {
    "pressure-check": {
      "op": "and",
      "requirements": [
        {"op": "claim", "claim_id": "pressure-within-limit"},
        {"op": "independent_sources", "claim_id": "pressure-reading", "min_sources": 2}
      ]
    },
    "electrical-check": {
      "op": "or",
      "requirements": [
        {"op": "claim", "claim_id": "power-isolated"},
        {"op": "claim", "claim_id": "lockout-tagout-verified"}
      ]
    }
  },
  "root": {
    "op": "and",
    "requirements": [
      {"op": "rule", "rule_id": "pressure-check"},
      {
        "op": "temporal",
        "max_age_ms": 60000,
        "anchor": "action_time",
        "requirement": {"op": "rule", "rule_id": "electrical-check"}
      }
    ]
  }
}
```

Supported operators:

| Operator | Required fields | Meaning represented by the policy |
|---|---|---|
| `claim` | `claim_id` | One named claim is required. |
| `and` | `requirements` | Every child requirement is required. |
| `or` | `requirements` | At least one child requirement must be satisfied. |
| `independent_sources` | `claim_id`, `min_sources` | The named claim needs the requested minimum number of independent source roots; the parser only validates the constraint shape. |
| `temporal` | `requirement`, `max_age_ms`, `anchor` | A child must meet a freshness window relative to `decision_time` or `action_time`; evaluation is a later component. |
| `rule` | `rule_id` | Reference a named rule in the graph's `rules` map. |

Rule references must resolve and the rule-reference graph must be acyclic. All
objects reject unknown keys. `and` and `or` require 2–32 children. Claim and
rule identifiers are non-empty and at most 128 characters. `min_sources` is an
integer of at least 2; `max_age_ms` is a positive integer. Booleans are not
accepted as integers.

The parser accepts at most 64 named rules, 256 total syntax nodes and 32 nested
levels. Limits apply before rule expansion; references remain explicit in the
typed graph. Python container cycles and duplicate JSON object keys are rejected
with a path-aware `RequirementGraphError`. Its `code` and `path` fields let
policy tooling report a descriptive error without treating malformed policy as
an empty requirement.

```python
from memory_fabric import RequirementGraphError, parse_requirement_graph

try:
    graph = parse_requirement_graph(policy_document)
except RequirementGraphError as exc:
    print(exc.code, exc.path, str(exc))
```

`RequirementGraph.to_dict()` returns the validated typed structure and
`to_json()` emits canonical JSON. A graph records policy intent only. It grants
no permission and cannot be used in place of current evidence verification or
per-effect authorization.
