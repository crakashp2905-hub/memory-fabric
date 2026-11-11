# N3-03 — Exact-oracle estimator comparison

The comparison covers 128 deterministic seeds, four four-memory decision
worlds, and 2,048 estimates per method. Every method is evaluated against the
exact Shapley allocation of the same oracle worlds. The common budget cap is
64 oracle outcome evaluations per world and replicate; realized query counts
are shown because methods consume different amounts of work.

| Method | RMSE | Mean signed error | Mean within-case variance | Mean oracle outcome queries |
|---|---:|---:|---:|---:|
| Leave-one-out | 0.2500 | 0.0000 | 0.0000 | 5.00 |
| Three-permutation Shapley approximation | 0.1443 | 0.0000 | 0.0207 | 9.21 |
| Propensity weighting (IPS) | 0.3471 | 0.0145 | 0.1189 | 64.00 |
| Naive recency score | 0.3409 | -0.0633 | 0.0424 | 64.00 |

LOO has no sampling variance but its context is the full memory set, so its
interaction-world error is visible in the per-world table in the JSON result.
The sampled Shapley method is unbiased over random permutations and has lower
error and variance here, at a small but higher query count. IPS targets the
Shapley allocation in expectation under the registered predecessor-set
sampling design, but 16 observations per memory have substantial variance.
The recency score is not a causal contrast; its errors are descriptive and it
must not be used as action authorization or as a causal credit estimate.

These results demonstrate behavior only on the preregistered synthetic
functions. The shared limit is a budget cap, not identical realized query
counts. No field, model-cost, or generalization claim is supported. Machine
results and per-world breakdown: `n3-03-estimator-comparison.json`.
