# E4-05 SQLite stress — Windows AMD64, 8 CPUs, Python 3.13.5, SQLite 3.49.1

Commit `f59e2aa6c2d31eabbd79034ab9c20674d7f5ba32`; 50 concurrent processes, 3 trials, transaction event sizes (1, 5, 10); SQLite busy timeout 5000 ms; FULL synchronous mode; connections staggered 25 ms each before synchronized writes.

| trial | writes expected/observed | transactions | wall seconds | WAL mode | busy timeout | auto-checkpoint pages | chain verified | result |
|---:|---:|---:|---:|---|---:|---:|---|---|
| 0 | 1600/832 | 180 | 25.28 | wal | 5000 | 1000 | True | FAIL |
| 1 | 1600/160 | 75 | 25.60 | wal | 5000 | 1000 | True | FAIL |
| 2 | 1600/192 | 80 | 24.44 | wal | 5000 | 1000 | True | FAIL |

The experiment requires complete event identity, contiguous authoritative sequence numbers, a valid integrity chain, zero worker errors, successful checkpoint calls, and a bounded lock-timeout control followed by a successful write after lock release. Full transaction latency, checkpoint results and worker exit codes are in the JSON artifact.
