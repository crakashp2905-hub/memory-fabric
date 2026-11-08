# CDM-R5 v3 confirmatory architecture comparison

Conceptual first-party baselines only; not official reproductions.

Seeds: 20261911, 20261912, 20261913, 20261914, 20261915, 20261916, 20261917, 20261918, 20261919, 20261920, 20261921, 20261922, 20261923, 20261924, 20261925, 20261926, 20261927, 20261928, 20261929, 20261930

Primary contrast mean: 0.0550; 95% interval: [-0.0528, 0.1628]

Oracle headroom: 0.2600; fixed margin: 0.0520 (20% of positive headroom).

Decision: **DOES_NOT_SUPPORT_REGISTERED_SUPERIORITY_HYPOTHESIS**

## Arm utility deltas

| Arm | Mean utility difference | 95% interval | Mean CPU ns | Mean wall ns | Max peak bytes |
|---|---:|---:|---:|---:|---:|
| leave_one_out | -0.2550 | [-0.4845, -0.0255] | 1562500 | 3747335 | 11455 |
| exact_shapley | -0.2000 | [-0.4184, 0.0184] | 19531250 | 19483275 | 35543 |
| sampled_shapley | -0.2000 | [-0.4184, 0.0184] | 848437500 | 849611225 | 272845 |
| random | -0.0750 | [-0.2220, 0.0720] | 781250 | 726510 | 3531 |
| recency | -0.1000 | [-0.2349, 0.0349] | 0 | 672895 | 3531 |
| oracle_one_removal | 0.0050 | [-0.0048, 0.0148] | 1562500 | 1992300 | 5775 |

## Scope and limitations

All arms use the same worlds, deterministic policy and one-removal budget. The oracle is evaluator-only and selects among the same legal removals.

- No official reproduction of Shapley, CAR or another external system.
- Normal-approximation intervals are imprecise at these sample sizes.
- No real-world transfer or efficacy claim is supported.
