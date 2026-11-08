# Research evidence boundaries

This table separates the kind of evidence a result provides. A passing local
test does not move a claim into an external or real-world evidence class.

| Evidence class | What current evidence can establish | What it cannot establish | Examples |
|---|---|---|---|
| Mathematical/contract checks | For the tested input domain, formulas, parsers, invariants and acceptance predicates match their stated contracts. | That assumptions fit a deployment, the implementation is defect-free, or a model behaves as expected. | Statistical interval and estimator known-answer tests; benchmark predicate mutation tests (`tests/test_statistical_intervals.py`, `tests/test_benchmarks.py`). |
| Model-free implementation tests | Deterministic code paths preserve tested authorization, correction, replay and persistence behavior on the exercised local platform. | Behavior on untested operating systems, remote databases, physical hosts, external identity systems or real users. | Unit/property/integration suite and local SQLite/process fault tests (`docs/VALIDATION.md`, `research/results/e4-10-deterministic-soak.json`). |
| Scripted or synthetic experiments | A mechanism changes measured outcomes in the declared generator, fixture, seed split and budget; negative controls can identify fixture-specific failures. | Live agent behavior, human usefulness, population effects, market demand, universal generalization or independent replication. | Grand 50-agent synthetic baseline and correction/provenance demos (`research/results/grand-50-agent-baseline-reproduction-v2.json`, `research/results/p4-04-correction-strategy-comparison.json`). |
| Real model or external validation | Nothing in the local deterministic suite is classified here unless a result records the actual model/service, immutable inputs, run identity and external provenance. | The absence of external evidence cannot be repaired by relabeling a local simulation. | Live-model trials, representative user pilots, commissioned human security review, physical three-host tests and independent research reproduction remain OPEN. |

## Negative and inconclusive outcomes

Retain failures and abandoned hypotheses with their original denominators and
conditions. In particular, an oracle ceiling with no headroom, a failed
performance threshold, or a baseline that already reaches the primary metric
is a design or deployment finding, not a successful Memory Fabric result.
Historical H2, PA and PB1 outcomes remain part of the research record; do not
replace them with a later favorable result or imply that one workload repairs
their generalization limits.

## Claiming rule

Every result statement must identify its evidence class, workload, tested
environment and limits. “Passed tests” means only the named tests passed.
“Synthetic 50-agent” means scripted agents in a synthetic workload. Neither
phrase means live-model, customer, independent, certified or production
validation. Those require separate artifacts from the corresponding external
source.
