# E4-05 SQLite stress — Windows AMD64, 8 CPUs, Python 3.13.5, SQLite 3.49.1

Commit `f59e2aa6c2d31eabbd79034ab9c20674d7f5ba32`; 50 concurrent processes, 3 trials, transaction event sizes (1, 5, 10); SQLite busy timeout 30000 ms; FULL synchronous mode; connections staggered 25 ms each before synchronized writes.

| trial | writes expected/observed | transactions | wall seconds | WAL mode | busy timeout | auto-checkpoint pages | chain verified | result |
|---:|---:|---:|---:|---|---:|---:|---|---|
| 0 | 1600/1600 | 300 | 33.03 | wal | 30000 | 1000 | True | PASS |
| 1 | 1600/1600 | 300 | 21.42 | wal | 30000 | 1000 | True | PASS |
| 2 | 1600/1600 | 300 | 22.73 | wal | 30000 | 1000 | True | PASS |

The experiment requires complete event identity, contiguous authoritative sequence numbers, a valid integrity chain, zero worker errors, successful checkpoint calls, and a bounded lock-timeout control followed by a successful write after lock release. Full transaction latency, checkpoint results and worker exit codes are in the JSON artifact.
