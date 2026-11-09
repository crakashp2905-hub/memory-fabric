# Preregistration — N5-10: incremental diversity value after false consensus

- **Written:** 2026-11-09, before implementing or running this experiment.
- **Prior evidence:** [H4b topology/diversity preregistration](h4-topology-and-diversity.md) and [H4b result](../results/h4-topology-and-diversity.md).
- **Question:** After the same population has reached a false consensus, does H4b's contested-minority retesting improve recovery beyond continuing collapse and beyond changing to a sparser existing H4 topology?
- **Scope:** Deterministic synthetic bandit simulation. This tests a causal mechanism in the existing simulator, not live agent behavior or production memory.

## 1. Confirmatory hypotheses

**H1 (incremental recovery):** Starting from identical false-consensus checkpoint states, enabling the existing H4b policy (`preserve=True`, which spends the registered 20% pull budget on the minority while the two credible intervals overlap) improves the probability of ending with every agent favoring the better action compared with continuing greedy collapse on the same complete topology.

**H2 (incremental beyond topology):** The same H4b intervention on the complete topology improves that recovery probability compared with changing only the post-checkpoint network to the pre-existing `ring` topology while leaving agents on greedy collapse.

The ring is preselected as the intermediate connected topology from H4: it had the best unpreserved endpoint accuracy jointly with `small_world` (0.985), while `ring` is simpler and had 0.985 in the original registered run. The post-checkpoint topology contrast is a diagnostic comparator, not an estimate of the original whole-run topology effect.

## 2. Design and arms

- Use the existing H4 bandit parameters and implementation: 10 agents, `p_good=0.55`, `p_bad=0.50`, 150 rounds, 10 pulls per agent per round, 20 prior observations of BAD, 4 uniformly-rate-seeded observations of GOOD, 90% normal-approximation credible intervals, and 20% preserve budget.
- Generate each path identically under `complete + collapse` through the end of round index 20. Include only seeds where **all** agents believe BAD at that checkpoint. This eligibility is determined before the interventions and is shared by every arm.
- For every eligible seed, fork the exact posterior counts and continue four counterfactual arms through round 149: `complete + collapse`, `complete + preserve`, `ring + collapse`, `ring + preserve`.
- Give all four continuations the same seed-derived random stream. Use seeds `10000..10999`; do not replace failed or ineligible seeds. Require at least 200 eligible seeds; otherwise report underpowered/inconclusive without changing the sampling plan.
- Apply preservation only after the false-consensus checkpoint. This estimates its incremental post-event contribution, separate from preventing the checkpoint event.

## 3. Outcomes and analysis

- **Primary outcome:** paired per-seed recovery difference in endpoint all-agent correctness for `complete + preserve` minus each comparator: `complete + collapse` (H1) and `ring + collapse` (H2). This is the probability of recovering from the same pre-treatment false consensus by the fixed horizon.
- **Primary inference:** paired percentile bootstrap with 10,000 resamples over eligible seeds, deterministic bootstrap seed `10510`, two-sided 97.5% intervals for the two registered contrasts. No multiplicity adjustment or threshold changes after results.
- **Secondary:** arm recovery rates; rounds to first all-agent-GOOD profile after the checkpoint (among recovered seeds); BAD-arm pull fraction; and the factorial interaction `(complete preserve − complete collapse) − (ring preserve − ring collapse)` with 95% interval. These explain mechanisms and do not replace a failed primary result.
- Report eligibility rate, all arm denominators, paired raw binary outcomes, seeds, exact software/protocol hashes, compute time, all intervals, and negative or inconclusive outcomes.

## 4. Decision rules

- **Incremental H4b supported:** for both primary contrasts, the mean recovery uplift is at least 0.10 (10 percentage points) and the 97.5% interval's lower bound is above zero. The result must also show no data-integrity or seed-pairing failures.
- **Incremental H4b not supported at the registered resolution:** either primary contrast has a 97.5% interval whose upper bound is at or below zero.
- **Otherwise:** inconclusive. A smaller positive effect, fewer than 200 eligible seeds, intervals crossing zero, or runtime/data-integrity failure cannot be described as supported.
- Faster conditional recovery is reported but is not required to claim this narrowly preregistered recovery-probability result; do not say the intervention shortens recovery unless that secondary outcome supports it.

## 5. Relationship to prior H4b evidence

H4b previously compared collapse and contested-minority retesting from the start of a run and reported 24% versus 100% conditional recovery under `complete`. It did not fork identical post-false-consensus states, did not isolate post-event intervention, and did not compare recovery to a topology-only intervention on the same checkpoint population. This design addresses those missing causal comparisons. It does not independently validate the simulator's realism, establish performance in language-model agents, or establish production value.

## 6. Deviations

None permitted without a dated amendment made before inspecting confirmatory outcomes. If an implementation defect is found after outcomes are inspected, retain and report the original run, record the defect and amendment, then rerun the entire preregistered seed range under a new version; do not silently replace results.
