# P12b — many agents through one agent-api process

Produced by `python -m experiments.p12b_api_load` using the source committed at
`a626fdccd69842bac31d86811bd5783a6e31543c` (source SHA-256
`d7a26a682d2b53d0d0456d32b240cb2c1e5316e60c772532ef23e1a7418c0c2f`); raw numbers
in [master-checklist-http-capacity-v1.json](master-checklist-http-capacity-v1.json). Machine: Windows AMD64, 8 CPUs, Python 3.13.5. One `agent-api`
server process on a SQLite store seeded with 200 memories, rate limiting
off. N agents with their own credentials are client threads, 20 requests
each (30% remember, 50% recall, 20% fetch then verify). An operational measurement,
not pre-registered.

Latencies in ms as the client sees them, p50 / p95 / p99. Throughput is successful
operations per second of wall time (a fetch+verify counts once).

| agents | ok / ops | ops/s | all ops | remember | recall | fetch+verify | errors |
|---|---|---|---|---|---|---|---|
| 1 | 20/20 | 4 | 136.3 / 233.3 / 2782.8 | 225.2 / 2782.8 / 2782.8 | 136.3 / 216.6 / 216.6 | 27.6 / 40.8 / 40.8 | none |
| 1 | 20/20 | 6 | 145.8 / 282.0 / 338.6 | 223.6 / 282.0 / 282.0 | 143.7 / 280.6 / 338.6 | 27.7 / 33.8 / 33.8 | none |
| 1 | 20/20 | 4 | 178.3 / 497.7 / 1443.1 | 234.1 / 1443.1 / 1443.1 | 136.2 / 328.7 / 328.7 | 31.2 / 31.6 / 31.6 | none |
| 5 | 100/100 | 6 | 665.2 / 1477.7 / 2586.3 | 608.2 / 1195.7 / 2371.5 | 548.9 / 968.5 / 1126.6 | 913.5 / 2586.3 / 2693.6 | none |
| 5 | 100/100 | 4 | 863.6 / 3658.8 / 8131.4 | 863.6 / 6070.1 / 6709.1 | 768.1 / 3635.6 / 3658.8 | 1125.5 / 8131.4 / 8352.1 | none |
| 5 | 100/100 | 4 | 1004.0 / 2099.2 / 3405.6 | 1048.8 / 2500.5 / 3401.3 | 803.2 / 1381.1 / 3405.6 | 1194.7 / 2099.2 / 4472.3 | none |
| 10 | 200/200 | 6 | 1587.5 / 3298.7 / 5185.8 | 1299.0 / 2838.0 / 3095.3 | 1203.6 / 3022.1 / 3381.0 | 2064.0 / 5185.8 / 5337.4 | none |
| 10 | 200/200 | 5 | 1444.8 / 6269.2 / 10258.8 | 1402.8 / 9756.1 / 10182.7 | 1351.3 / 2746.3 / 10065.2 | 1960.3 / 2955.6 / 12473.2 | none |
| 10 | 200/200 | 4 | 1888.8 / 7003.2 / 11329.4 | 1734.8 / 11130.3 / 11272.4 | 1662.4 / 5364.1 / 11249.9 | 3185.1 / 6715.4 / 12676.3 | none |
| 25 | 500/500 | 3 | 4788.6 / 26318.5 / 39758.2 | 4631.5 / 23642.5 / 36689.1 | 3959.6 / 23255.9 / 36007.3 | 8767.6 / 29981.0 / 47585.7 | none |
| 25 | 500/500 | 5 | 4154.2 / 9657.4 / 11372.3 | 4021.4 / 6954.6 / 8133.2 | 3754.7 / 6850.5 / 8912.4 | 8864.0 / 11647.4 / 11910.9 | none |
| 25 | 500/500 | 5 | 4501.2 / 10724.3 / 14019.3 | 3481.3 / 8813.1 / 10571.5 | 3473.5 / 7829.7 / 10925.6 | 6684.9 / 14172.8 / 14621.4 | none |
| 50 | 1000/1000 | 5 | 7903.8 / 18359.6 / 21565.7 | 7020.2 / 14004.6 / 15269.9 | 6811.0 / 13551.8 / 15400.6 | 14838.1 / 21565.7 / 22273.4 | none |
| 50 | 1000/1000 | 4 | 11026.1 / 22348.8 / 25450.2 | 10337.8 / 13488.1 / 13906.0 | 10389.4 / 13258.8 / 13835.9 | 19601.4 / 25508.2 / 26206.6 | none |
| 50 | 1000/1000 | 5 | 10275.8 / 22230.7 / 25601.0 | 9338.2 / 13504.8 / 14279.9 | 8463.2 / 13509.1 / 14492.2 | 18778.9 / 25651.3 / 27654.8 | none |

## Capacity curve across trials

Intervals are 95% normal-approximation confidence intervals across independent
trials; a one-trial point has a zero-width interval and is descriptive only.

| agents | trials | successful / attempted | ops/s mean [CI] | p99 ms mean [CI] |
|---|---:|---:|---:|---:|
| 1 | 3 | 60/60 | 4.7 [3.2, 6.3] | 1521.5 [136.4, 2906.6] |
| 5 | 3 | 300/300 | 4.8 [3.1, 6.5] | 4707.7 [1320.7, 8094.8] |
| 10 | 3 | 600/600 | 4.8 [3.6, 6.0] | 8924.7 [5210.8, 12638.5] |
| 25 | 3 | 1500/1500 | 4.3 [3.1, 5.5] | 21716.6 [3972.5, 39460.7] |
| 50 | 3 | 3000/3000 | 4.6 [4.2, 5.0] | 24205.7 [21617.1, 26794.2] |

Compare [P12](p12-load.md), where each agent was its own process opening the
store: 214 → 31 → 9 → 4 ops/s at 1, 10, 50 and 100 agents on SQLite.
