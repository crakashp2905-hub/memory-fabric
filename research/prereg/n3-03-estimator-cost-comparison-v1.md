# N3-03 — Estimator accuracy under a common oracle budget

Status: preregistered before estimator comparison results are generated.

## Target and fixed worlds

The target is each memory's exact Shapley allocation of safe-success utility in
the four deterministic four-memory worlds registered for N3-02. This target
averages each memory's marginal effect over all insertion orders and therefore
allocates interaction utility among participating memories. It is not the
uniform-background average treatment effect from N3-02. Worlds and outcome
functions are reused unchanged; all 16 subsets per world define evaluation
truth.

## Compared methods

- **Leave-one-out (LOO):** utility with all memories minus utility with the
  selected memory removed from the full set.
- **Shapley approximation:** average marginal utility across three seeded,
  uniformly sampled memory permutations; query results are cached within a
  replicate.
- **Propensity weighting (IPS):** for each memory, sample 16 backgrounds by
  choosing predecessor-set size uniformly from `0..n-1` and a uniform subset
  of that size; randomize inclusion at propensity `0.5`; use the Horvitz-
  Thompson contrast `mean(2*A*Y - 2*(1-A)*Y)`. This identifies the Shapley
  target in expectation under the registered background design.
- **Naive recency:** on the same 16 randomized records per memory, compute an
  exponentially recency-weighted exposed-outcome mean (`0.8` per step), then
  subtract the fixed neutral score `0.5`. It is a deliberately noncausal
  heuristic and has no propensity correction.

## Budget, metrics, and reproducibility

Each method has a common cap of 64 oracle outcome evaluations per world and
replicate. The cap equals the 4 memories times 16 IPS observations; actual
oracle queries are counted and reported, including methods that use less than
the cap. No repeated oracle query is charged twice when a method caches it.
The benchmark uses seeds `0..127`, fixed world order, Python's `random.Random`,
and no learned model, prompt, or external dataset.

For every method, report pooled RMSE, signed bias, mean within-memory/world
variance across seeds, mean outcome-query count, cap, and estimate count against
exact Shapley truth. Also report per-world/per-method RMSE so interaction
failures cannot be hidden by pooling. Acceptance requires all methods to be
present, all estimates finite, query counts within budget, the exact Shapley
efficiency identity to hold, and deterministic output for a repeated run with
the same seeds. There is no post-hoc winner threshold.

These are synthetic decision functions, not real agent trajectories. The
results compare estimator mechanics and compute in this finite testbed; they
do not establish field validity, model cost, or external generalization.
