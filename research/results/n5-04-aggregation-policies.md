# N5-04 aggregation policy benchmark

Protocol: `research/prereg/n5-04-aggregation-policies-v1.md`. The pilot used 100 tasks; held-out evaluation used 2500 tasks across seeds 201, 202, 203, 204, 205. Pilot degeneracy stop: **False**.

Evidence-quality mean headroom share: **0.726** (registered target 0.250; target met: **True**).

## Held-out seed means

| policy | utility | decisive accuracy | action errors / 2,500 | minority recovery | mean convergence wave |
|---|---:|---:|---:|---:|---:|
| majority | 0.305 | 0.656 | 838 | 0.013 | 2.09 |
| reputation | 0.300 | 0.650 | 875 | 0.031 | 2.10 |
| independent_root | 0.641 | 0.889 | 228 | 0.000 | 2.28 |
| evidence_quality | 0.812 | 0.906 | 235 | 0.462 | 1.49 |
| oracle | 1.000 | 1.000 | 0 | 1.000 | 1.00 |

## Paired bootstrap intervals

Intervals resample tasks within each seed (10,000 replicates). The first interval is evidence-quality utility minus the best of majority/reputation; the second is its per-seed share of oracle headroom.

| seed | utility contrast 95% CI | headroom share 95% CI |
|---:|---:|---:|
| 201 | 0.414 to 0.592 | 0.650 to 0.804 |
| 202 | 0.404 to 0.580 | 0.649 to 0.801 |
| 203 | 0.420 to 0.602 | 0.644 to 0.801 |
| 204 | 0.434 to 0.612 | 0.668 to 0.814 |
| 205 | 0.360 to 0.536 | 0.605 to 0.769 |

The explicit oracle is perfect by construction, as required. The full 15.8 MB input manifest is `research/results/n5-04-aggregation-manifest.json`; the JSON result binds its SHA-256 and all per-seed counts, errors, minority recovery, convergence, and test status. The generator's quality rates are synthetic assumptions, not real-world source reliability estimates. This result does not establish field efficacy or action safety.
