# E4-05 — SQLite lock and checkpoint qualification

Measured on Windows AMD64, 8 CPUs, Python 3.13.5, SQLite 3.49.1 at source commit `f59e2aa6c2d31eabbd79034ab9c20674d7f5ba32`.

Fifty local processes opened independent `EventLog` connections, then synchronized writes to one database. Each ran two rounds of transaction sizes 1, 5, and 10 events: 1,600 planned events and 300 transactions per trial. SQLite used WAL and FULL synchronous mode; the auto-checkpoint setting was 1,000 pages.

| configured timeout | trials | planned events / committed | observed outcome | chain and sequence |
|---:|---:|---:|---|---|
| 5000 ms | 3 | 4800 / 1184 | Explicit lock failures; 113 failed workers across runs | True |
| 30000 ms | 3 | 4800 / 4800 | All writes committed; 0 failed workers across runs | True |

The default 5-second timeout did not sustain this synchronized workload: it returned explicit `database is locked` errors. The event log remained internally consistent in those runs, and failed operations were surfaced rather than silently acknowledged. With `busy_timeout_ms=30_000`, all 4,800 planned events committed across three trials, every chain verified, sequences were contiguous, and both PASSIVE and TRUNCATE checkpoint calls reported no busy readers. The longest transaction took 20.2 seconds.

A separate lock-held control configured for 250 ms returned `OperationalError` after 324–366 ms; after releasing the lock, a new append succeeded. This verifies a finite busy wait and recovery.

The evidence supports configuring `MemoryFabric(path, busy_timeout_ms=30_000)` for this tested 50-process pattern. It does not make SQLite a multi-writer database or establish a capacity guarantee for other hosts. See [operations guidance](../../docs/OPERATIONS.md#the-database-is-locked).

Raw [5-second trials](e4-05-sqlite-5s.json), [30-second trials](e4-05-sqlite-30s.json), and [JUnit results](e4-05-regression-tests.xml) are retained.
