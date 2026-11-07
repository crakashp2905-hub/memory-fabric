# P12b — many agents through one agent-api process

Produced by `python -m experiments.p12b_api_load` at commit `ec58c67`; raw numbers
in [e4-04-batched-chain-pilot.json](e4-04-batched-chain-pilot.json). Machine: Windows AMD64, 8 CPUs, Python 3.13.5. One `agent-api`
server process on a SQLite store seeded with 200 memories, rate limiting
off. N agents with their own credentials are client threads; the operation count per
agent is shown for each scenario (30% remember, 50% recall, 20% fetch then verify).
An operational measurement, not pre-registered.

Latencies in ms as the client sees them, p50 / p95 / p99. Throughput is successful
operations per second of wall time (a fetch+verify counts once).

| agents | ops / agent | ok / ops | ops/s | all ops | remember | recall | fetch+verify | errors |
|---:|---:|---:|---:|---|---|---|---|---|
| 10 | 20 | 200/200 | 16 | 547.6 / 963.4 / 1113.0 | 491.5 / 778.7 / 789.3 | 495.2 / 740.0 / 813.1 | 851.1 / 1113.0 / 1213.7 | none |
| 10 | 20 | 200/200 | 15 | 602.0 / 1057.7 / 1275.8 | 576.9 / 823.2 / 841.4 | 580.5 / 778.0 / 817.9 | 854.1 / 1275.8 / 1451.3 | none |
| 10 | 20 | 200/200 | 16 | 574.5 / 1005.3 / 1212.0 | 512.0 / 725.6 / 865.5 | 516.8 / 824.7 / 840.0 | 858.4 / 1212.0 / 1269.3 | none |
| 50 | 20 | 1000/1000 | 15 | 2788.2 / 5432.4 / 6086.7 | 2741.2 / 3510.2 / 3981.3 | 2671.0 / 3500.4 / 3912.6 | 5103.2 / 6086.7 / 6946.2 | none |
| 50 | 20 | 1000/1000 | 15 | 2891.8 / 5641.0 / 6253.0 | 2784.6 / 3806.2 / 3964.0 | 2768.1 / 3813.8 / 3896.6 | 5300.1 / 6280.6 / 6698.0 | none |
| 50 | 20 | 1000/1000 | 15 | 2861.2 / 5664.5 / 6154.2 | 2767.5 / 3932.0 / 4110.5 | 2784.0 / 3944.8 / 4159.1 | 5383.3 / 6155.9 / 6673.6 | none |

## Resource profile

| agents | server CPU seconds | CPU % of one core | mean fabric lock wait µs | mean SQLite append ms | OS read / write bytes | sampled RSS peak bytes | traced Python allocation peak bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 5.453125 | 44.949740039333605 | 407917.68 | 27.788 | 1142784 / 9531168 | 54272000 | 831479 |
| 10 | 5.984375 | 46.32994345687981 | 447751.60 | 28.126 | 1134592 / 10079176 | 54194176 | 846100 |
| 10 | 5.4375 | 42.94798168901713 | 421413.46 | 27.681 | 1126400 / 9761984 | 53796864 | 800303 |
| 50 | 30.59375 | 46.9153241283872 | 2515956.44 | 28.389 | 11051008 / 52439664 | 63016960 | 8860266 |
| 50 | 31.171875 | 46.74580303573409 | 2631810.74 | 28.285 | 11620352 / 54132288 | 63799296 | 9305583 |
| 50 | 30.390625 | 45.302686799869484 | 2633750.32 | 28.669 | 11706368 / 52683680 | 63709184 | 9111293 |

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
| 10 | 3 | 600/600 | 15.9 [15.3, 16.5] | 1200.3 [1107.4, 1293.1] |
| 50 | 3 | 3000/3000 | 15.1 [14.8, 15.3] | 6164.6 [6070.0, 6259.2] |

Compare [P12](p12-load.md), where each agent was its own process opening the
store: 214 → 31 → 9 → 4 ops/s at 1, 10, 50 and 100 agents on SQLite.
