# Matched multi-agent policy arms

Run from a clean checkout with:

```powershell
python -m benchmarks.matched_agent_arms
```

The report at `research/results/r3-02-matched-agent-arms.json` evaluates isolated cached evidence, fresh pooled retrieval, blanket source retraction, Memory Fabric's `ActionGate`, and an evaluator-only oracle over the same seeds, agent counts, task IDs, initial evidence, context budgets, and tool grants. The oracle's labels are not included in agent context. This is a local scripted policy comparison, not a comparison against independently implemented external memory products or real-model agents.
