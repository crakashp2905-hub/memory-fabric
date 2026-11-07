# P12b — many agents through one agent-api process

Produced by `python -m experiments.p12b_api_load` at commit `6bf6132`; raw numbers
in [e4-03-local-profile.json](e4-03-local-profile.json). Machine: Windows AMD64, 8 CPUs, Python 3.13.5. One `agent-api`
server process on a SQLite store seeded with 200 memories, rate limiting
off. N agents with their own credentials are client threads; the operation count per
agent is shown for each scenario (30% remember, 50% recall, 20% fetch then verify).
An operational measurement, not pre-registered.

Latencies in ms as the client sees them, p50 / p95 / p99. Throughput is successful
operations per second of wall time (a fetch+verify counts once).

| agents | ops / agent | ok / ops | ops/s | all ops | remember | recall | fetch+verify | errors |
|---:|---:|---:|---:|---|---|---|---|---|
| 1 | 20 | 20/20 | 14 | 82.7 / 112.4 / 148.6 | 89.8 / 148.6 / 148.6 | 82.7 / 112.4 / 112.4 | 27.6 / 38.9 / 38.9 | none |
| 1 | 20 | 20/20 | 13 | 87.8 / 104.4 / 114.9 | 89.0 / 114.9 / 114.9 | 87.8 / 100.5 / 101.2 | 30.8 / 35.5 / 35.5 | none |
| 1 | 20 | 20/20 | 12 | 89.1 / 116.8 / 126.1 | 99.4 / 126.1 / 126.1 | 98.1 / 106.9 / 106.9 | 38.3 / 40.4 / 40.4 | none |
| 10 | 20 | 200/200 | 15 | 588.5 / 1101.6 / 1222.3 | 553.0 / 866.3 / 906.5 | 515.0 / 850.9 / 906.9 | 894.7 / 1222.3 / 1404.5 | none |
| 10 | 20 | 200/200 | 15 | 645.8 / 1064.9 / 1337.0 | 584.3 / 864.7 / 987.2 | 571.1 / 867.0 / 969.8 | 832.7 / 1337.0 / 1453.9 | none |
| 10 | 20 | 200/200 | 15 | 645.2 / 1022.1 / 1345.8 | 559.9 / 788.4 / 793.2 | 559.6 / 835.8 / 842.7 | 845.6 / 1345.8 / 1415.7 | none |
| 50 | 20 | 1000/1000 | 14 | 3010.7 / 5863.5 / 6525.5 | 2879.5 / 3986.4 / 4305.8 | 2818.4 / 3623.1 / 4287.2 | 5419.8 / 6525.5 / 7335.1 | none |
| 50 | 20 | 1000/1000 | 13 | 3229.5 / 6371.5 / 6812.7 | 3156.1 / 4402.6 / 4766.7 | 3137.5 / 4191.7 / 4756.9 | 6027.5 / 6853.5 / 7553.6 | none |
| 50 | 20 | 1000/1000 | 17 | 2880.4 / 5926.6 / 6659.2 | 2472.7 / 3945.2 / 4138.3 | 2600.8 / 3965.1 / 4144.1 | 4722.6 / 6690.1 / 7336.2 | none |
| 100 | 20 | 2000/2000 | 15 | 5223.7 / 10538.3 / 12949.1 | 5090.6 / 7643.8 / 8445.3 | 5112.2 / 7558.0 / 8427.9 | 10019.7 / 12960.6 / 15485.1 | none |
| 100 | 20 | 2000/2000 | 15 | 5502.9 / 10930.2 / 11885.8 | 5405.6 / 6719.1 / 7476.3 | 5384.3 / 6723.1 / 7457.1 | 10668.4 / 11947.5 / 13708.0 | none |
| 100 | 20 | 2000/2000 | 14 | 3649.1 / 26451.0 / 31870.2 | 3550.4 / 25409.8 / 27489.4 | 3570.7 / 26417.1 / 27339.5 | 6950.6 / 32532.1 / 47799.7 | none |

## Resource profile

| agents | server CPU seconds | CPU % of one core | mean fabric lock wait µs | mean SQLite append ms | OS read / write bytes | sampled RSS peak bytes | traced Python allocation peak bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.375 | 26.170624235192186 | 4.14 | 27.125 | 0 / 729240 | 52346880 | 148927 |
| 1 | 0.515625 | 32.941409618809466 | 2.80 | 27.769 | 0 / 918760 | 52158464 | 161331 |
| 1 | 0.421875 | 24.315257844076513 | 3.57 | 28.399 | 0 / 832240 | 52219904 | 147850 |
| 10 | 5.625 | 43.01697722927388 | 437036.35 | 30.747 | 1126400 / 9597184 | 54013952 | 785814 |
| 10 | 6.125 | 44.809545057865726 | 474790.44 | 30.883 | 1146880 / 10062624 | 54190080 | 819569 |
| 10 | 5.78125 | 42.83896585056346 | 453511.36 | 30.895 | 1122304 / 9840288 | 53723136 | 776380 |
| 50 | 30.9375 | 44.56322150852872 | 2684322.32 | 31.231 | 11026432 / 52266288 | 64143360 | 9133611 |
| 50 | 35.015625 | 46.88135182698557 | 2960763.60 | 31.426 | 10698752 / 54074728 | 62902272 | 9220044 |
| 50 | 29.609375 | 49.742816816810034 | 2366413.33 | 23.218 | 11157504 / 52535360 | 64290816 | 8870946 |
| 100 | 61.890625 | 47.43268462226495 | 5123184.83 | 27.525 | 69029888 / 105817968 | 79392768 | 15183865 |
| 100 | 64.375 | 48.90261238794975 | 5227899.91 | 26.793 | 72278016 / 109257976 | 80764928 | 15782457 |
| 100 | 60.453125 | 41.954730979824426 | 5806316.42 | 34.300 | 49971200 / 105451816 | 86245376 | 15213390 |

Latency, CPU, I/O and RSS come from the untraced pass. Allocation peaks come
from a separate `tracemalloc` pass with the same clients and workload size.
Lock wait measures the process-local Memory Fabric lock. OS I/O counters can
omit writes served from the OS cache; RSS is sampled every 10 ms and may miss
shorter peaks.

## Capacity curve across trials

Intervals are 95% normal-approximation confidence intervals across independent
trials; a one-trial point has a zero-width interval and is descriptive only.

| agents | trials | successful / attempted | ops/s mean [CI] | p99 ms mean [CI] |
|---|---:|---:|---:|---:|
| 1 | 3 | 60/60 | 12.8 [11.4, 14.1] | 129.9 [110.4, 149.3] |
| 10 | 3 | 600/600 | 14.9 [14.5, 15.3] | 1301.7 [1223.7, 1379.7] |
| 50 | 3 | 3000/3000 | 14.9 [12.9, 16.8] | 6665.8 [6503.2, 6828.5] |
| 100 | 3 | 6000/6000 | 14.8 [13.9, 15.7] | 18901.7 [6178.3, 31625.1] |

Compare [P12](p12-load.md), where each agent was its own process opening the
store: 214 → 31 → 9 → 4 ops/s at 1, 10, 50 and 100 agents on SQLite.
