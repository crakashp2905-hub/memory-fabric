# P12b — many agents through one agent-api process

Produced by `python -m experiments.p12b_api_load` at commit `52994e4`; raw numbers
in [e4-03-local-profile.json](e4-03-local-profile.json). Machine: Windows AMD64, 8 CPUs, Python 3.13.5. One `agent-api`
server process on a SQLite store seeded with 200 memories, rate limiting
off. N agents with their own credentials are client threads; the operation count per
agent is shown for each scenario (30% remember, 50% recall, 20% fetch then verify).
An operational measurement, not pre-registered.

Latencies in ms as the client sees them, p50 / p95 / p99. Throughput is successful
operations per second of wall time (a fetch+verify counts once).

| agents | ops / agent | ok / ops | ops/s | all ops | remember | recall | fetch+verify | errors |
|---:|---:|---:|---:|---|---|---|---|---|
| 1 | 20 | 20/20 | 7 | 91.0 / 482.6 / 517.9 | 373.0 / 517.9 / 517.9 | 93.2 / 242.1 / 242.1 | 26.6 / 41.7 / 41.7 | none |
| 1 | 20 | 20/20 | 14 | 78.0 / 100.1 / 100.3 | 90.8 / 100.3 / 100.3 | 76.8 / 95.3 / 96.9 | 29.5 / 34.9 / 34.9 | none |
| 1 | 20 | 20/20 | 11 | 103.5 / 120.9 / 121.0 | 110.4 / 121.0 / 121.0 | 103.5 / 111.3 / 111.3 | 28.7 / 39.9 / 39.9 | none |
| 10 | 20 | 200/200 | 15 | 574.7 / 1022.8 / 1175.8 | 533.7 / 788.4 / 801.7 | 522.2 / 793.9 / 808.7 | 895.1 / 1175.8 / 1399.8 | none |
| 10 | 20 | 200/200 | 4 | 2494.9 / 4906.0 / 5551.9 | 2676.6 / 3852.4 / 3878.1 | 2183.8 / 3492.2 / 3740.6 | 3685.1 / 5551.9 / 6991.5 | none |
| 10 | 20 | 200/200 | 4 | 2371.0 / 4198.2 / 5839.7 | 2238.0 / 3514.3 / 3600.3 | 2133.8 / 3073.0 / 3338.9 | 3643.9 / 5839.7 / 6865.2 | none |
| 50 | 20 | 1000/1000 | 15 | 2930.5 / 5829.2 / 6642.4 | 2837.3 / 3968.7 / 4135.0 | 2744.3 / 3945.3 / 4125.0 | 5263.0 / 6642.4 / 7694.9 | none |
| 50 | 20 | 1000/1000 | 14 | 3061.4 / 6063.6 / 6669.4 | 3000.7 / 3840.8 / 4054.0 | 2974.6 / 3736.8 / 3962.0 | 5670.0 / 6708.7 / 7437.2 | none |
| 50 | 20 | 1000/1000 | 14 | 2973.7 / 5916.3 / 6702.8 | 2885.6 / 3916.9 / 4173.6 | 2859.6 / 3998.9 / 4260.5 | 5696.1 / 6704.8 / 7338.6 | none |
| 100 | 20 | 2000/2000 | 21 | 3765.0 / 7671.3 / 11993.2 | 3578.7 / 7345.0 / 7735.3 | 3648.0 / 7374.0 / 7674.8 | 7041.0 / 12467.5 / 15070.7 | none |
| 100 | 20 | 2000/2000 | 14 | 5998.7 / 12124.7 / 13219.4 | 5898.9 / 7536.3 / 8198.9 | 5859.0 / 7519.1 / 8159.0 | 11734.8 / 13278.3 / 15153.1 | none |
| 100 | 20 | 2000/2000 | 14 | 5879.4 / 11964.1 / 13548.0 | 5696.8 / 7802.4 / 8152.5 | 5729.1 / 7844.6 / 8191.1 | 11306.5 / 13709.7 / 14586.2 | none |

## Resource profile

| agents | server CPU seconds | CPU % of one core | mean fabric lock wait µs | mean SQLite append ms | OS read / write bytes | sampled RSS peak bytes | traced Python allocation peak bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.5625 | 20.030809343710484 | 4.29 | 72.366 | 0 / 729240 | 52363264 | 148764 |
| 1 | 0.5 | 34.33565048631449 | 2.35 | 27.724 | 0 / 918760 | 52584448 | 161112 |
| 1 | 0.515625 | 28.131259460996368 | 2.40 | 29.951 | 0 / 832240 | 52326400 | 149009 |
| 10 | 5.046875 | 38.56140764016236 | 2.50 | 32.120 | 1122304 / 9551888 | 53723136 | 3101069 |
| 10 | 6.09375 | 11.281054981042493 | 2.89 | 170.495 | 1142784 / 10116208 | 57245696 | 2512483 |
| 10 | 6.171875 | 11.328938242813486 | 2.86 | 168.294 | 1130496 / 9836120 | 56762368 | 778990 |
| 50 | 29.8125 | 43.408935908673115 | 2.94 | 30.994 | 6991872 / 52225232 | 62365696 | 9201769 |
| 50 | 31.3125 | 44.49638309385873 | 3.12 | 30.998 | 11284480 / 54062056 | 62521344 | 9134680 |
| 50 | 30.140625 | 42.730196643441325 | 3.24 | 30.560 | 11300864 / 52576344 | 64581632 | 8897100 |
| 100 | 59.71875 | 62.057760293051864 | 2.63 | 15.922 | 33689600 / 105348288 | 79282176 | 15178548 |
| 100 | 64.515625 | 44.87685209570081 | 3.18 | 31.032 | 67182592 / 109620920 | 80195584 | 15765918 |
| 100 | 61.96875 | 43.81903869638985 | 3.14 | 31.162 | 65261568 / 105254128 | 78176256 | 15523198 |

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
| 1 | 3 | 60/60 | 10.6 [6.8, 14.3] | 246.4 [0.0, 512.7] |
| 10 | 3 | 600/600 | 7.6 [0.0, 15.1] | 4189.1 [1231.6, 7146.7] |
| 50 | 3 | 3000/3000 | 14.3 [14.1, 14.6] | 6671.5 [6637.3, 6705.8] |
| 100 | 3 | 6000/6000 | 16.3 [11.9, 20.7] | 12920.2 [11992.9, 13847.5] |

Compare [P12](p12-load.md), where each agent was its own process opening the
store: 214 → 31 → 9 → 4 ops/s at 1, 10, 50 and 100 agents on SQLite.
