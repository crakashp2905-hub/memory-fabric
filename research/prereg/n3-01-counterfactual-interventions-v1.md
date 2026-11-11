# N3-01 — Counterfactual intervention and estimand contract

Status: preregistered before the N3-02 oracle worlds and any new estimator.
This document fixes the intervention variables, outcomes, estimands, and
identification assumptions; it does not select or implement an estimator.

## Unit and intervention variables

The unit is one eligible decision episode with a fixed initial store snapshot,
query, principal, action policy, and exogenous world seed. A treatment is the
joint assignment `A_i = (M_i, R_i, E_i)` made before the decision outcome:

- **Memory inclusion `M_i`:** a binary indicator for a named memory (or a
  declared memory group) being available in the decision context. The
  intervention removes the selected memory from the eligible context while
  retaining its identity in the experiment manifest. It does not erase the
  source or change lifecycle state.
- **Routing option `R_i`:** one option from the frozen set for that experiment,
  such as `lexical`, `vector`, `hybrid`, or `fixed-baseline`. Every option gets
  the same eligible store, query, context budget, and filter policy.
- **Escalation level `E_i`:** one ordered, explicitly configured level, such
  as `none`, `deterministic-check`, or `independent-review`. Escalation may
  add checks or review; it may not weaken authorization, source authority, or
  freshness requirements.

The assigned values, eligible alternatives, randomization probability, and
the evidence exposure/reliance/authorization records must be logged before
the outcome is observed. Exposure is not treated as reliance, and retrieval is
not treated as action authorization.

## Outcomes and estimands

For eligible episode `i`, let `Y_i(m,r,e)` be the potential outcome under the
specified treatment. Outcomes are reported separately as:

1. **Safe task success:** the exact oracle decision and task result are both
   correct.
2. **Unsafe action:** a consequential side effect occurs when the oracle
   requires abstention, refusal, or a different action.
3. **Resource cost:** decision latency, exposed evidence records, estimated
   context tokens (with tokenizer provenance), and any escalation cost.

For a target population of `N` eligible episodes, the finite-population
average effects are:

- **Include/exclude effect for memory `m`:**
  `tau_M(m; r,e) = (1/N_m) * sum_i [Y_i(M_i=1,r,e) - Y_i(M_i=0,r,e)]`,
  over episodes where both inclusion states are permitted by the registered
  context policy.
- **Routing contrast:**
  `tau_R(r1,r0; M,e) = (1/N_R) * sum_i [Y_i(M,r1,e) - Y_i(M,r0,e)]`,
  over the common-support episodes eligible for both routes.
- **Escalation contrast:**
  `tau_E(e1,e0; M,r) = (1/N_E) * sum_i [Y_i(M,r,e1) - Y_i(M,r,e0)]`,
  over episodes where both escalation levels are allowed.
- **Interaction:** estimate a memory-by-route or memory-by-escalation
  interaction only when the full paired treatment cells are supported; report
  the difference-in-differences and all four cell counts.

The primary effect is the paired change in safe task success. Unsafe actions
are a hard safety guardrail and are never traded for success or cost. Effects
on latency and evidence cost are reported alongside success; they are not
folded into an undocumented scalar reward. For deterministic oracle worlds,
enumerate every permitted treatment cell and compute exact finite-world
contrasts. For randomized worlds, report the intention-to-treat effect by
assigned treatment, with assignment and observation probabilities.

## Identification assumptions and limits

- **Consistency:** the logged treatment corresponds to the declared
  intervention; removing a memory changes availability only, not source truth,
  lifecycle, agent identity, or unrelated state.
- **Paired-world stability:** paired counterfactual runs share the same
  exogenous task, source facts, correction schedule, and random seed. Any
  stochastic components use registered independent streams or common random
  numbers as specified by the experiment.
- **No interference:** one episode's treatment does not change another
  episode's store, agent policy, source state, or outcome. Experiments with
  shared state must define clusters and estimate cluster-level effects.
- **Positivity/common support:** every compared treatment has non-zero
  assignment probability for the target episodes. Unsupported cells are
  labelled `NON_IDENTIFIABLE`; they are not extrapolated into numeric credit.
- **Randomization or exchangeability:** randomized interventions identify
  the assigned-treatment contrast. Observational estimates additionally
  require all common causes of treatment and outcome to be measured and
  correctly adjusted; retrieval relevance or success correlation alone is
  not a causal identification strategy.
- **No post-treatment adjustment:** do not condition the primary effect on
  retrieved, exposed, relied-on, or authorized memories when those variables
  are affected by the intervention. Report such strata only as descriptive
  mediation analyses.
- **Outcome validity:** oracle labels and side effects are independently
  computed from the registered world specification. Agent-reported success
  cannot certify evidence, authority, or truth.

The assumptions are not guaranteed in real deployments. In particular,
selective retrieval, shared-agent adaptation, delayed feedback, hidden
confounding, and missing overlap can make a memory-level causal effect
non-identifiable. This preregistration therefore defines the estimand and
refusal conditions; it does not claim that a particular estimator is valid.
