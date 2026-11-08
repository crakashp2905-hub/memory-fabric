# CDM-176 matched-budget inference quality

## Frozen protocol

- Compare exact enumeration with a first-party standard-library
  likelihood-weighted sampler on an eight-node binary Bayesian chain.
- Condition on `x7=true`, estimate `P(x0=true)`, and define decision agreement
  at threshold 0.5. Exact posterior from the registered full enumerator is the
  oracle for both absolute error and decision agreement.
- Use disjoint seeds 20261101–20261120 and equal joint-assignment budgets 32,
  128 and 256. Exact enumeration reports `BUDGET_EXCEEDED` unless all 256
  assignments fit; sampling consumes no more than the stated budget.
- Record every seed/budget row, exact/approximate status, posterior, absolute
  error, decision agreement, and approximate effective sample size. No
  imputation is used for a zero-weight sample; it is an explicit abstention.
- These are synthetic finite measurements. Assignment counts are not a claim
  of matched wall time or memory, and no production quality claim follows.

Run `python -m benchmarks.cdm_budgeted_inference --out
research/results/cdm/budgeted-inference/report.json` to reproduce.
