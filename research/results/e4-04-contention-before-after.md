# E4-04 — contention optimization before/after

Measured on Windows AMD64, 8 CPUs, Python 3.13.5.

The treatment batches integrity-chain row inserts with `executemany` inside the same SQLite transaction. SQLite synchronous mode remains FULL. No authorization, event ordering, chain construction, or durability setting changed. Workload seed database uses seed 0; client streams use `agent_index + trial * 100000`.

Baseline source: `6bf6132`. Treatment source: `ec58c67`. Evidence-record commit: `ec58c674c7aa4a70a46d8798c157b55e0551cb6f`.

All rows use 20 operations/client and 5 warmups. Values are mean client-observed latency and throughput across 3 trials; intervals are 95% normal-approximation CIs.

| clients | baseline p99 ms [95% CI] | treatment p99 ms [95% CI] | p99 change | baseline ops/s [95% CI] | treatment ops/s [95% CI] | successes |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 1301.7 [1223.7, 1379.7] | 1200.3 [1107.4, 1293.1] | -7.8% | 14.9 [14.5, 15.3] | 15.9 [15.3, 16.5] | 600/600, 0 errors |
| 50 | 6665.8 [6503.2, 6828.5] | 6164.6 [6070.0, 6259.2] | -7.5% | 14.9 [12.9, 16.8] | 15.1 [14.8, 15.3] | 3000/3000, 0 errors |
| 100 | 18901.7 [6178.3, 31625.1] | 12347.2 [12104.5, 12589.9] | -34.7% | 14.8 [13.9, 15.7] | 14.6 [14.3, 15.0] | 6000/6000, 0 errors |

## Regression evidence

Focused integrity, event-log, and multiprocess crash-boundary suite: 42 tests and 27 subtests passed. See [JUnit XML](e4-04-regression-tests.xml). All load scenarios returned HTTP 200 for every attempted operation.

## Interpretation

At 50 clients, mean p99 improved; the baseline and treatment 95% intervals do not overlap. At 10 clients, the intervals overlap. At 100 clients, the treatment has no observed regression, while the baseline p99 is noisy; throughput remains similar. This is local operational evidence for this workload, not a general capacity claim.

Raw trial values, commits, settings, and limitations are in [machine-readable results](e4-04-contention-before-after.json).
