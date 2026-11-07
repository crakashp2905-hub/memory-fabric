# E4-10 deterministic soak result

**Status: PASS** on source SHA `e792c1f4b314dd49b99494c986f600a9ddfc164d`.

| Measure | Result | Ceiling / expectation |
|---|---:|---:|
| Hard-crash commit/restart cycles | 40 | 40 |
| Backup/restore checkpoints | 4 | 4 |
| Reconciliation deliveries | 40 | 40, no gaps |
| Restart latency p50 | 1.068 s | observed |
| Restart latency p99 | 1.733 s | observed |
| Last/first quartile p99 ratio | 1.012x | <= 3.0x |
| Peak child RSS | 44.3 MiB | <= 512 MiB |
| Parent traced Python peak | 5.5 MiB | <= 256 MiB |
| Maximum database file | 0.207 MiB | <= 128 MiB |
| Maximum temporary soak data | 4.99 MiB | <= 384 MiB |
| Maximum pending outbox rows | 10 | <= 10 |

Each checkpoint verified the chain, retained all ten pending rows through restore, replayed ten recipient corrections, and settled ten redeliveries. The crash and backup regression suite also passed 22 tests and 18 subtests.

This is local SQLite evidence, not a continuous 24-hour production soak, physical-host failure test, or PostgreSQL qualification. See [the runbook](../../docs/E4_SOAK.md).
