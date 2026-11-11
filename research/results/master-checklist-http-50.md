# P12b — many agents through one agent-api process

Produced by `python -m experiments.p12b_api_load` at commit `f46aea6`; raw numbers
in [master-checklist-http-50.json](master-checklist-http-50.json). Machine: Windows AMD64, 8 CPUs, Python 3.13.5. One `agent-api`
server process on a SQLite store seeded with 200 memories, rate limiting
off. N agents with their own credentials are client threads, 20 requests
each (30% remember, 50% recall, 20% fetch then verify). An operational measurement,
not pre-registered.

Latencies in ms as the client sees them, p50 / p95 / p99. Throughput is successful
operations per second of wall time (a fetch+verify counts once).

| agents | ok / ops | ops/s | all ops | remember | recall | fetch+verify | errors |
|---|---|---|---|---|---|---|---|
| 50 | 1000/1000 | 29 | 1485.9 / 2943.4 / 3292.2 | 1383.6 / 1880.8 / 2273.3 | 1417.6 / 1901.8 / 2367.8 | 2695.9 / 3292.2 / 3422.2 | none |

Compare [P12](p12-load.md), where each agent was its own process opening the
store: 214 → 31 → 9 → 4 ops/s at 1, 10, 50 and 100 agents on SQLite.

## Verdict

Correctness and workload validity passed: 1,000/1,000 operations succeeded and
all three required families executed. The preregistered performance gate
failed: 29.1 ops/s is below 100 ops/s and 3,292 ms p99 exceeds 1,500 ms.

The historical dirty-worktree run reported 32.6 ops/s and 3,856 ms p99. This
clean exact-SHA run is directionally consistent but does not reproduce those
machine-sensitive numbers exactly; both runs fail the same release gate.
