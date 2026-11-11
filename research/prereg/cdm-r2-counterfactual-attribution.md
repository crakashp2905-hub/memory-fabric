# CDM-R2: intervention estimands preregistration

Status: frozen before benchmark tuning. Version 1. Date: 2026-11-08.

Three outcomes remain separate:

1. **Decision flip:** whether the selected internal proposal differs under the
   declared evidence intervention and unchanged policy.
2. **Utility difference:** hidden generated-world reward difference, computed
   only by a separate evaluator after candidate outputs are frozen.
3. **Authority difference:** whether the current action gate's verdict changes;
   hypothetical replay evidence can never enter that gate.

Primary intervention family: suppress one explicit observation. Controls:
no-op, irrelevant evidence, independent corroboration, same-origin duplicate,
and policy swap labelled separately. Candidate selection comparators are
random, recency, influence graph, dependence sufficiency, leave-one-out and
exact enumeration at small N. All arms share evidence and compute budgets.

At least five disjoint seeds per generated family are required before a
registered comparison. Baselines run before proposing thresholds. The oracle
has the same candidate budget and mechanism, differing only in access to
generated truth. Any arm beating it invalidates the run. Raw paired results,
refusal counts, confidence intervals and fidelity must be retained. No result
is claimed until those runs exist.
