# N3-09 — Off-policy support qualification

Both IPS and doubly robust estimation now require both observed actions in every
selected context stratum and action propensities in `[0.01, 0.99]`. Unsupported
cases are explicitly labelled `NON_IDENTIFIABLE`; the public confidence interval
accessor returns `None`, and serialized estimates preserve the status.

| Check | Result |
|---|---|
| One observed arm only | Both estimators refuse |
| Near-deterministic action propensity | Both estimators refuse |
| Marginal arms present but a context stratum lacks overlap | Both estimators refuse |
| Supported confounded fixture | Existing causal estimator qualifications remain green |
| Focused estimator suite | 26 passed, 2 subtests passed |
| Serialization and event-log compatibility suite | 50 passed, 2 subtests passed; workspace-local temp directory |
| Ruff | Passed |

This is synthetic contract evidence. It does not establish correct propensity
logging or remove unmeasured confounding. The support floor is configurable and
may reject valid but weak overlap.
