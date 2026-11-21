# Agent-outcome operating envelope

What this stack has been measured to do, and on what. Every number lives in a
committed JSON file produced by a command on this page. Nothing is extrapolated
to other hardware, and no figure describes model inference: every measured row
used scripted agents.

| Host class | Status |
|---|---|
| The CI and development container that produced the committed rows | Measured: [`performance-dev.json`](../research/results/agent-outcomes/performance-dev.json) records its Python version, platform and CPU count |
| 16 GB laptop | NOT_MEASURED |
| Modest server | NOT_MEASURED |
| Any host running a local model | NOT_MEASURED: no model checkpoint has been available (`REAL_AGENT_NOT_RUN`) |

## Reproduce

```bash
python -m benchmarks.outcome_performance --quick --out perf.json   # minutes
python -m benchmarks.outcome_performance --out perf.json           # adds 100k-event replay, more trials
python -m benchmarks.outcome_performance --full --out perf.json    # adds 1M-event replay
python -m benchmarks.outcome_storage_bench --threads 4 --per-thread 50
python tools/measure_local_footprint.py --help                     # installed-wheel footprint
```

## What the measurements cover

- **Per-stage latency of one governed episode.** Observe, retrieve, plan,
  verify, commit, effect acknowledgment and the counterfactual review are each
  timed in wall and CPU time. The runner's own overhead is shown as
  `unattributed`. Model inference is `NOT_MEASURED`.
- **Process contention at 1, 2, 4 and 8 workers.** Each count gets a warm-up,
  repeated trials, and process start, queue wait and service time reported
  separately. Speedup is reported, not assumed; on the measured host it stays
  near one (see the JSON).
- **Counterfactual review cost.** Dependence-first and always-on replay
  counts and seconds are compared.
- **Event replay.** Projection rebuild time and peak Python memory are
  measured at the listed sizes. A size that is not in the JSON was not run.
- **Many agents on one store.** Up to 50 agents with skewed traffic: tail
  latency, worst-agent tail, starvation and fairness.
- **Storage.** SQLite throughput, retries and consistency. PostgreSQL is
  measured only where a database is configured.

## Limits that hold everywhere

- **Bounded queues.** The job spool has a depth cap. When it is full, new
  work is refused (the caller abstains), and the action gate's decisions do
  not change under load.
- **No coalesced principals.** Verification is never batched across
  principals.
