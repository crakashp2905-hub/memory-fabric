# CDM replay re-evaluation classification

For a synthetic trace with one target, two transitive dependents, and two
independent events, replay cost is classified against an explicit complete
dependency graph:

| Strategy | Recomputed retained events | True affected retained events | Collateral re-evaluations | Classification |
|---|---:|---:|---:|---|
| Complete dependency frontier | 2 | 2 | 0 | Precise for the declared complete graph |
| Incomplete-graph full fallback | 4 | 2 | 2 | Conservative extra work; intentional because missing edges could hide real dependents |

"Collateral" here means extra recomputation compared with the supplied
complete graph's semantic affected set. It does not mean a false causal claim.
If graph completeness is unknown, full replay is an intentional correctness
fallback, not a selector defect. A graph marked complete is a caller
precondition; an omitted real dependency can instead cause a false negative
and stale reuse. The regression asserts both the zero-collateral complete
case and the measured two-event conservative fallback case.
