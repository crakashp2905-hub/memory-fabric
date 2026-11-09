# Matched multi-agent policy arms v1

This specification freezes the comparison before the arm run. Population is scripted and synthetic.

- Seeds: 701, 709, 719; counts: 5, 10, 25, 50, 100.
- Identical task IDs and family composition per seed/count across arms: supported, corrected, contested, missing; two tasks each.
- Arms: `isolated` (agent acts on its initially exposed cached item), `pooled_shared` (fresh shared retrieval with no action certificate gate), `blanket_retraction` (withdraws all later source use after a correction and refuses contested evidence), `memory_fabric` (ActionGate and current certificate verification), `oracle` (the evaluator's task label; gold is not included in agent context).
- Equalization: every agent receives the same initial task context (one evidence item when present, zero when missing), same `publish` runtime grant, and same task order. The report binds context-content hashes and per-agent grant counts for each arm.
- Outcomes: exact safe decision accuracy, unsafe actions, false abstentions, stale actions, task-family denominators, elapsed time.
- Outcome hierarchy amendment for future independent replications: one primary outcome, overall task success across the complete registered 24-case v1 split, compared separately against each of the three non-oracle baselines. Report mean paired task-case difference and 95% task-cluster bootstrap interval; adjust the three directional exact sign tests with Holm. Secondary outcomes are unsafe actions, stale actions, false abstentions and descriptive success rates for all four task families. Family-specific comparative tests, latency, cost and individual-agent extrema are exploratory and must not drive promotion.
- This hierarchy was written after the existing v1 outcomes had already been generated and inspected. Therefore the current v1 report is explicitly exploratory for inferential p-values and does not constitute a confirmatory test. The hierarchy is confirmatory only for a future independently seeded dataset frozen before execution.
- Failure condition: any arms receive different task IDs/context hashes/budgets/permissions, Memory Fabric or oracle accepts an unsafe action, or a run omits denominators.
- Baselines are diagnostic implementations of the named policies; their results are synthetic systems evidence, not model-agent quality claims.
