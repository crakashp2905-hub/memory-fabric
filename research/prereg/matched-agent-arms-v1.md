# Matched multi-agent policy arms v1

This specification freezes the comparison before the arm run. Population is scripted and synthetic.

- Seeds: 701, 709, 719; counts: 5, 10, 25, 50, 100.
- Identical task IDs and family composition per seed/count across arms: supported, corrected, contested, missing; two tasks each.
- Arms: `isolated` (agent acts on its initially exposed cached item), `pooled_shared` (fresh shared retrieval with no action certificate gate), `blanket_retraction` (withdraws all later source use after a correction and refuses contested evidence), `memory_fabric` (ActionGate and current certificate verification), `oracle` (the evaluator's task label; gold is not included in agent context).
- Equalization: every agent receives the same initial task context (one evidence item when present, zero when missing), same `publish` runtime grant, and same task order. The report binds context-content hashes and per-agent grant counts for each arm.
- Outcomes: exact safe decision accuracy, unsafe actions, false abstentions, stale actions, task-family denominators, elapsed time.
- Failure condition: any arms receive different task IDs/context hashes/budgets/permissions, Memory Fabric or oracle accepts an unsafe action, or a run omits denominators.
- Baselines are diagnostic implementations of the named policies; their results are synthetic systems evidence, not model-agent quality claims.
