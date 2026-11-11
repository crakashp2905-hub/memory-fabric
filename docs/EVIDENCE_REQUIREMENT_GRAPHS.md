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
| `independent_sources` | `claim_id`, `min_sources` | The named claim's certificate is strengthened to require the requested minimum number of independent source roots. |
| `temporal` | `requirement`, `max_age_ms`, `anchor` | `action_time` checks certificate issuance age at authorization. `decision_time` is parsed but currently fails closed because the API has no authenticated decision-time input. |
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

## Minimal missing-evidence explanations

`requirement_atom_keys(graph)` lists the stable IDs for atomic obligations.
The caller supplies `satisfied_requirements` only after the relevant evidence
checks pass. `minimal_missing_evidence_sets(graph, satisfied_requirements)`
returns a deterministic antichain: each row is one minimal alternative set of
obligations that would complete the policy. AND combines child sets; OR keeps
the available alternatives and removes supersets. An already satisfied graph
returns `((),)`. A typo or ID from another graph raises `ValueError` instead of
being silently ignored. `max_sets` bounds the returned alternatives (default
1024, hard maximum 4096); intermediate candidate expansion is also bounded.
Exceeding either bound raises a path-independent `RequirementGraphError` with
code `limit`; results are never silently truncated.

IDs use `claim:<claim_id>` or
`independent_sources:<claim_id>:<minimum>`. Temporal wrappers append
`@temporal:<anchor>:<max_age_ms>` to each child atom, so a caller cannot mark a
freshness-constrained requirement satisfied using an unqualified claim ID.
The returned rows explain missing policy obligations; they do not fetch,
validate, or authorize evidence.

For example, with `pressure` already satisfied and an OR between `manual`
and `sensor`, the result is two one-item alternatives. The caller may request
either source to resolve the blocked requirement.

## Static local action policies

Attach a parsed graph to a host-owned `ToolRule(requirement_graph=graph)`.
At authorization time, pass `claim_certificates={claim_id: certificate}`.
Each certificate's own `claim_id` must equal its map key and every required
leaf is independently re-verified against current store state. The static rule
also strengthens each certificate with the tool's required checks, minimum
independent-source count, provenance authority, freshness and validation
requirements. A missing or invalid mandatory leaf returns
`requirement_evidence_missing` and cannot grant the action. `and`, `or`, named
rules, and independent-source nodes are evaluated deterministically.

Every graph leaf also requires a host-owned `claim_predicates` entry. A
`ClaimPredicate(subject, predicate, operator, value, unit)` is checked against
structured assertions stored on supporting memories, for example:

```python
structured = {"claims": [{
    "subject": "pump-7", "predicate": "pressure_psi", "value": 30, "unit": "psi"
}]}
predicate = ClaimPredicate("pump-7", "pressure_psi", "<=", 40, "psi")
```

The `ToolRule` must define exactly one predicate for each distinct graph claim;
missing or extra declarations reject policy construction. Matching checks
subject, predicate, unit and typed value, then counts distinct source roots
that individually support the proposition. Thus a highly relevant 70 psi
reading cannot satisfy a static `pressure_psi <= 40 psi` action requirement.
Retrieval relevance never substitutes for this support check. Structured
assertions and provenance do not independently prove that a source is truthful;
hosts still set appropriate authority, review and corroboration thresholds.
Repeated ingestions recognized as copies resolve to one root, so adding note
records cannot satisfy a multi-source threshold. Independence follows the
recorded lineage and copy relations; unrecognized semantic paraphrases may
still appear independent and require domain-specific review.

If separately rooted evidence yields values on opposite sides of the required
predicate (for example, 30 psi and 70 psi against `pressure <= 40 psi`), the
gate refuses with `claim_evidence_disputed` and
`requirement_evidence_missing`. `ActionDecision.disputed_claims` returns every
alternative with its value, evidence IDs, source roots and whether it supports
the policy. No value is selected. The durable `ActionGated` event records the
dispute reason and evidence references/support sides, not the values themselves.
Dispute detection is limited to structured assertions included in the
certificates for that action; it does not prove that omitted or inaccessible
records do not disagree.

Human approvals use `certificate_set_digest(claim_certificates)` as their
`Approval.certificate_digest`; `binding_digest(..., claim_certificates=...)`
also binds the full claim-certificate set to target, parameters, agent, tenant
and tool. Exact-action grants and `execute` use the same binding. Audit events
record claim certificate digests, deduplicated evidence IDs and versions, and
the minimal missing-evidence alternatives and disputing evidence references,
without values or memory content. A blocked
`ActionDecision.missing_evidence_sets` exposes the same alternatives to the
caller. The tests in `tests/test_action_requirements.py` cover missing
mandatory leaves at both authorization and execution boundaries.
