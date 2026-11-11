# Agent outcome evaluation v1 — preregistration shell

**Status: DRAFT / NOT FROZEN.** This file is a protocol shell. No confirmatory
outcomes may be used to tune the protocol, and no research superiority claim is
made by creating this document.

## Source and evidence baseline

- Repository checkout at protocol creation: `fix/typed-query-certificates`,
  commit `0a4d10d` (2026-11-10). The supplied proposal cites
  `4315997d066a261aa674559fc89d73d0c407d16b`; that object is absent from
  this checkout (`git cat-file` cannot resolve it), so its status is
  **SOURCE_UNAVAILABLE**.
- The [versioned historical-reference manifest](agent-outcome-baseline.v1.json)
  pins the available checkout SHA, supplied proposal digest, exact recorded
  commands where present, parameters, source/result revisions, and SHA-256
  hashes for checked-in registrations, results, raw rows and harnesses. It
  labels missing or conflicting evidence explicitly. The manifest freezes this
  inventory, not the unfinished confirmatory protocol below.
- The proposal's 50-agent success/withholding claim and CDM negative findings
  have result artifacts on the separately fetched
  `feat/grand-50-agent-evaluation` branch, pinned to commit `8d19373` in the
  manifest. The 50-agent JSON is aggregate, its run had a dirty worktree, and
  the exact CLI was not recorded. The CDM held-out and architecture artifacts
  are separate finite synthetic studies. The proposed 17.2% withholding
  ablation still has no identified matching result or raw rows and remains
  `UNVERIFIABLE_REFERENCE`. None of these populations is pooled into a new
  baseline estimate. Phase A, PA′, Phase B, exploratory Phase C, P3b, R6 and
  X4 are pinned separately with their recorded limits and negative or
  abandoned verdicts. Only the deterministic P3b metrics were replayed here;
  its original detailed table still disagrees with its reproducible summary.
- Current existing team benchmark: `experiments/teamworld.py` and
  `experiments/p3b_teams.py`. New work must reuse it where the treatment and
  outcome definitions match; a new world requires a written reason.
- Evidence classes are `contract_tested`, `local_model_tested`, and
  `deployment_validated`. A deterministic scripted recovery pilot now exercises
  a correction and a paired immediate-abstention arm. This is contract evidence
  only; no real-model or confirmatory outcome-stage result exists, and the
  protocol remains unfrozen.

## Primary estimand and frozen design

The intended primary endpoint is the fraction of unique world/task cases ending
in a correct and authorized terminal state within the fixed budget. Case IDs,
world seed, objective, legal observations, action constraints, and evaluator
digest must be retained per arm. Agent observations must exclude truth,
expected actions, evidence eligibility/conflict labels, reward, and answer keys.
Abstention is safe behavior where justified but is not task completion when a
legal completion was available.

Candidate arms are A0–A7 from the master plan, including the strongest fair
non-oracle comparator and a budget matched oracle upper bound. All arms receive
identical cases, observation/tool budgets, prompts/model settings, and grading;
only the preregistered memory/recovery/CDM intervention may differ. CDM is
advisory and cannot authorize effects.

**Not yet frozen:** minimum meaningful effect, sample size, stopping rule,
confirmatory seeds, multiplicity correction, task template split, and resource
caps. Until those are frozen before confirmatory runs, the promotion status is
`NOT_READY`; no result can pass the research superiority gate.

## Analysis and safety

Store raw paired rows; cluster uncertainty by independent world/task case, not
agent count. Report safe completion, recovery eligibility/success, abstention
opportunity cost, attempted versus executed unsafe effects, stale commitments,
correction recovery steps/time, and resource costs separately. A zero-event
safety result must include a one-sided exact binomial upper bound. A missing or
censored evaluator result is `UNDECIDABLE` and is handled only by frozen rules.

The contract tests may establish `SCRIPTED_CONTRACT_PASS` for a specified code
SHA. They cannot establish local-model usefulness, deployment qualification,
production readiness, or causal benefit from CDM.
