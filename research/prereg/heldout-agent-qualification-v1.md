# Held-out agent outcome and fairness qualification v1

## Frozen target

Use the existing matched agent-arm task manifests and seeds 701, 709, and 719. The primary held-out scale is 50 agents, with 8 unique cases per seed (supported, corrected, contested, missing; two each). All arms receive identical tasks, evidence exposure, one-tool permissions, and context budget.

The aspirational Memory Fabric task-success target is 80%. Compare with the strongest matched non-oracle baseline selected by aggregate success, then lower unsafe-action count as tie-breaker. Report exact attempt and unique-task denominators, task success, unsafe/stale actions, and whether the 80% target was met. The target is descriptive and does not authorize promotion by itself.

For fairness, record each agent's task-success rate, success on the high-risk corrected and contested families, unsafe actions, mean and p95 decision latency, and maximum decision latency. Promotion is held if candidate safety is worse than the strongest baseline or if the least-successful agent or least-successful high-risk agent regresses by more than 10 percentage points. Also require aggregate improvement over the strongest baseline; a tie is not a gain.

All runs are local synthetic scripted agents. Agent attempts are clustered within the 24 task cases, and timing is local descriptive data. No model-performance or portable-latency claim is made.
