# Local System 1/System 2 routing

`memory_fabric.decision_router` provides an experimental, dependency-free router over host-supplied local features. It does not call a model and does not make an authorization decision.

`RoutingFeatures` names four inputs: risk (`low`, `medium`, `high`, `critical`), the count of evidence gaps, a tool class, and available/estimated System 2 token budgets. High or critical risk, any evidence gap, consequential tool classes (`write`, `execute`, `external`, `destructive`), and unrecognized tool classes route to System 2. If the declared System 2 budget cannot cover the estimate, the router returns `abstain`; it never silently falls back to System 1.

Only low/medium risk, complete evidence, and read/analysis tool classes route to System 1. Repeated calls with the same feature values return the same result. Invalid feature types and negative counts/budgets raise `ValueError`.

The route is advisory. A System 1 result, a System 2 result, and a selected decision option still require independent evidence and `ActionGate` authorization before a consequential tool may run. The contract suite is in `tests/test_decision_router.py`.
