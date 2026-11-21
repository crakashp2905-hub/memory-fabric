# ADR 0004 — One canonical outcome runtime: `memory_fabric.outcome_typed`

**Status:** accepted 2026-11-21 (agent-validation checklist W02-02).

**Context.** Three experimental packages implement agent-outcome contracts:
`memory_fabric.agent_outcomes`, `memory_fabric.outcome_protocol` and
`memory_fabric.outcome_typed`. They grew in parallel branches and were merged
side by side (PR #34, PR #37) rather than reconciled. Two definitions of the same
contract can disagree silently, and a fix applied to one copy leaves the others
behind. The checklist forbids a fourth package and asks for one canonical runtime.

**Findings.** These come from `tools/outcome_package_inventory.py`, which
compares the three public surfaces from source. The committed snapshot is
[`docs/architecture/OUTCOME_PACKAGE_INVENTORY.json`](../architecture/OUTCOME_PACKAGE_INVENTORY.json).
- `agent_outcomes` defines 8 public names. None is unique to it: it is a strict
  subset of the others.
- `outcome_protocol` defines 50 public names, 35 of them unique. The unique
  ones are the episode boundary ports (`AgentPort`, `EvaluatorPort`),
  `AgentRuntime`, `TerminalResult`, `EffectReceipt`, the operator trace and the
  read-only recovery catalog.
- `outcome_typed` defines 103 public names, 88 of them unique. These include
  `FailureCode`, `EvaluatorCapability`, `OracleTask`, terminal grading
  (`grade_terminal`, `TerminalGrade`), CDM replay dispatch, typed evidence
  diagnosis, and the evidence-status vocabulary.
- Fifteen names are shared. Only three are identical: `AgentObservation`,
  `AgentStep` and `MAX_JSON_BYTES`. Twelve conflict, including `SCHEMA_ID`
  (v1 in both legacy packages, v3 here), `RecoveryStatus` (`DISABLED` exists
  only in `outcome_protocol`, `ESCALATED` only in `outcome_typed`) and
  `EpisodeOutcome` (v3 adds attempted and executed unsafe-effect counts,
  terminal failure codes and agent identity).
- The differential check found one real regression: the canonical oracle-field
  guard accepted fields that `outcome_protocol` refused (`is_correct`,
  `task_success`, `completion`, `safety_violations` and others, plus the
  `expected*` and `groundtruth*` prefixes). The canonical guard now refuses
  their union.

**Decision.**
1. `memory_fabric.outcome_typed` is the canonical outcome runtime. It writes
   schema `memory-fabric.agent-outcomes.v3`. No new outcome logic is added
   anywhere else, and no fourth package is created.
   `tests/test_outcome_canonical_package.py` enforces this.
2. Ownership of every runtime responsibility:

   | Responsibility | Canonical owner |
   |---|---|
   | Actor contracts: observation, step, failure codes | `outcome_typed.observations` |
   | Evaluator contracts: oracle task, evaluator capability | `outcome_typed.observations` |
   | Episode state machine, task envelope, tool registry, shared budget, proposals, actor trace | `outcome_typed.episode` |
   | Single-actor bounded tool loop, CDM replay dispatch and worker | `outcome_typed.runtime`, `outcome_typed.replay_worker` |
   | Recovery actions, limits, guidance and checkpoints | `outcome_typed.recovery` |
   | Evidence diagnosis and alternate sources | `outcome_typed.eligibility` |
   | Terminal grading, effect records, outcome audit, counterfactual labels | `outcome_typed.outcomes` |
   | Outcome-evidence status vocabulary and pairing rules | `outcome_typed.evidence` |
   | Translation from legacy schema v1 | `outcome_typed.compat` |
   | Episode boundary ports and operator trace (only in `outcome_protocol` at this commit) | `outcome_typed.episode`: the host/evaluator split is its `MemoryPort`, the world feed and effect callables, and the separate evaluator in `benchmarks/outcome_episode.py`. Operator explanations move in a later batch (W07-09). |
3. `agent_outcomes` and `outcome_protocol` are deprecated, not deleted. Each
   emits a `DeprecationWarning` and carries `__deprecated__` with the sunset
   date (2027-03-31). Historical benchmarks, tests and recorded results that
   import them keep working. Their 30 call sites are listed, each grandfathered
   with that sunset, in
   [`docs/architecture/OUTCOME_LEGACY_CALLSITES.json`](../architecture/OUTCOME_LEGACY_CALLSITES.json).
   A new import of a legacy package fails the canonical-package test.
4. `outcome_typed.compat` translates legacy records to schema v3 and back. Every
   representable field is preserved. A field one side cannot represent raises
   `IncompatibleRecord`; it is never defaulted. For example, a v1 outcome never
   recorded attempted or executed unsafe effects, so the caller must supply them.
5. The stable SDK surface (`STABILITY.md`) is unchanged. All three packages are
   experimental and opt-in.

**Consequences.** New outcome work has one home and one schema. A divergent
copy cannot reappear unnoticed: the package-surface test fails on new public
names in a legacy package, on outcome contract classes defined anywhere else,
and on a new outcome package. Removing the legacy packages after the sunset
still requires migrating or retiring their 30 grandfathered call sites, and it
must leave historical recorded results reproducible or explicitly retired.
