# AO-061 — selector ablation protocol (draft)

**Status: DRAFT / DEVELOPMENT ONLY.** This document does not authorize a
confirmatory run, ranking, or promotion. The implementation is available via
`python benchmarks/outcome_matched_arms.py --mode selector-ablation --seeds …`.

## Registered candidate selectors

The development harness compares random, recency, exact model dependence,
leave-one-out, exact Shapley, and budgeted replay on identical generated
three-sensor worlds. Every arm receives the same evidence IDs, answer context,
one evidence removal, and an eight-coalition posterior-update budget. The
posterior states for all coalitions are computed once from the same world and
the shared preparation cost is charged to every arm. Selector and replay CPU,
wall time, and peak allocation are measured separately and reported; no
selector is described as having identical wall-clock cost.

Exact model dependence retains every evidence item whose removal changes the
target posterior under the complete generated model, then uses a stable
earliest-evidence tie break. Leave-one-out selects the largest absolute
posterior change. Shapley selects the highest exact contribution to the target
posterior. The budgeted arm uses the fixed public priority heuristic and a
`ReplayBudget` of 3 events, 1 attempt, 4 nodes, five seconds from selection
through replay, and zero tool calls. A wall-time overrun rejects the run.

Hidden truth is evaluator-only after proposal emission. The evaluator scores
counterfactual-minus-factual utility. Reports retain every paired seed, all
terminal proposals, decision flips, resource costs, and the cost-quality
frontier. Development results are not pooled with confirmatory outcomes.

## Freeze requirements before confirmation

Confirmatory seeds and disjoint development seeds, task/world generator digest,
sample size, stopping rule, multiplicity procedure, material-effect threshold,
cost acceptance rule, resource caps, and freeze commit remain unset. The design
must additionally establish that the synthetic worlds exercise all six
selectors without a baseline ceiling or degenerate outcome. Until these fields
are frozen, reports remain `DEVELOPMENT_ONLY_PROTOCOL_DRAFT` and promotion
remains `NOT_ASSESSED`.
