# CDM-R5 v3 development architecture comparison

Conceptual first-party baselines only; not official reproductions.

Seeds: 20261901, 20261902, 20261903, 20261904, 20261905

Primary contrast mean: 0.0000; 95% interval: [0.0000, 0.0000]

Oracle headroom: 0.1200; fixed margin: 0.0240 (20% of positive headroom).

Decision: **DOES_NOT_SUPPORT_REGISTERED_SUPERIORITY_HYPOTHESIS**

## Arm utility deltas

| Arm | Mean utility difference | 95% interval | Mean CPU ns | Mean wall ns | Max peak bytes |
|---|---:|---:|---:|---:|---:|
| leave_one_out | -0.1200 | [-0.3100, 0.0700] | 12500000 | 3784720 | 10845 |
| exact_shapley | -0.1200 | [-0.3100, 0.0700] | 18750000 | 21663160 | 40437 |
| sampled_shapley | -0.1200 | [-0.3100, 0.0700] | 884375000 | 895028840 | 270671 |
| random | 0.0000 | [0.0000, 0.0000] | 0 | 842040 | 3525 |
| recency | -0.1000 | [-0.2960, 0.0960] | 0 | 779500 | 3531 |
| oracle_one_removal | 0.0000 | [0.0000, 0.0000] | 0 | 2105120 | 5779 |

## Scope and limitations

All arms use the same worlds, deterministic policy and one-removal budget. The oracle is evaluator-only and selects among the same legal removals.

- No official reproduction of Shapley, CAR or another external system.
- Normal-approximation intervals are imprecise at these sample sizes.
- No real-world transfer or efficacy claim is supported.
