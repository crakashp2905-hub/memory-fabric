# R4-08 matched resource-budget qualification v1

For the registered 50-agent, three-seed matched-arm comparison, each arm gets
the same task order and context; no more than one evidence item is exposed per
agent-task. Every arm performs exactly two store retrieval attempts and one
simulated decision attempt per agent-task. No external tool effects execute.
All arms share a 10,000 ms wall-time ceiling per complete seed/arm run. Actual
latency and SQLite page allocation are measured as outcomes, not forced to be
equal. Any mismatch in task/context/grant identity, retrieval count, simulated
decision count, external tool calls, or wall-time budget invalidates the run.

The comparison is local, deterministic scripted-agent evidence. The shared
wall-time ceiling is a bounded budget, not a claim of equal observed runtime.
Storage is SQLite in-memory page allocation, not production memory or cost.
