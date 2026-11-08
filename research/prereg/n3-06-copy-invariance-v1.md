# N3-06 — Credit invariance under irrelevant copies

Status: preregistered before generating the duplication experiment result.

## Frozen worlds

For copy counts `{0, 1, 2, 4, 8}`, create one relevant memory, one irrelevant
source note, and the requested number of recognized copies of that irrelevant
note. Record every copy with the normal `COPY_RECOGNISED` event pointing to the
same root. Enumerate all permitted inclusion subsets of the relevant memory,
irrelevant root, and copies. The deterministic safe-success oracle returns one
iff the relevant memory is included; copies never enter the outcome equation.
Each subset is one verified episode and every memory's inclusion propensity is
`0.5`.

## Measures and acceptance

Compute exact Shapley allocations and fit the existing IPS estimator for every
world. Report useful-memory credit, the sum of irrelevant-root/copy credit,
maximum absolute copy credit, recognized lineage counts, and subset count.
Acceptance requires the useful-memory credit to remain `1.0` within `1e-12`,
irrelevant-group Shapley and IPS totals to remain zero within `1e-12`, and no
growth in unrelated attribution as copies are added. All subsets are enumerated,
so this measures exact finite-world invariance rather than sampling noise.

The experiment does not establish invariance for unrecognized paraphrases,
correlated but unlinked copies, observational data without overlap, or the
noncontrastive usage baseline. A system must not sum absolute usage scores as
causal credit.
