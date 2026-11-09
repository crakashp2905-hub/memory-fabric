# Resource budgets

The `agent-api` command exposes the store and server budgets directly:

```powershell
memory-fabric --db team.db agent-api --agents-file agents.txt `
  --max-memories 1000000 --max-retention-actions 1000 `
  --max-request-bytes 65536 --max-workers 32
```

Defaults are finite and invalid non-positive or non-integer values fail during
configuration:

| Setting | Default | Scope and behavior |
|---|---:|---|
| `Limits.max_memories` / `--max-memories` | 1,000,000 | Maximum records in the store. A new write at the cap fails as `memory_budget_exhausted` before an event is appended. |
| `Limits.max_retention_actions` / `--max-retention-actions` | 1,000 | Maximum lifecycle changes in one applied retention sweep. Deprecations are selected before terminal deletions; IDs break ties deterministically. A later sweep handles remaining candidates. Preview mode remains uncapped. |
| `RateLimit.max_request_bytes` / `--max-request-bytes` | 65,536 bytes | Maximum declared HTTP request body on the agent API; excess bodies receive 413 and bounded draining. |
| `RateLimit.max_workers` / `--max-workers` | 32 | Maximum concurrent POST request handlers doing agent API work. Excess requests receive 503 with `worker_budget_exhausted` and close; requests are not queued behind a saturated worker pool. |

Library callers can set store budgets with `MemoryFabric(limits=Limits(...))`
and API-server budgets with `AgentApi(service, limits=RateLimit(...))`.
`None` disables the memory or retention cap when explicitly configured in the
Python API. Server command defaults remain finite. HTTP worker slots bound
active request work; the standard-library server still creates a short-lived
thread for an accepted connection that is immediately refused at saturation.
These limits do not establish a production capacity guarantee; tune them using
the deployment's workload and measured host limits.
