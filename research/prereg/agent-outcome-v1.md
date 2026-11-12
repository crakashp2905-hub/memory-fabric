# Agent outcome evaluation v1 — baseline freeze and preregistration

**Baseline inventory: FROZEN for implementation planning at `10f14810e08ea28c3a336a8b7d54c6babbb40f5d`. Confirmatory protocol: DRAFT / NOT FROZEN.** No confirmatory outcomes may be used to tune the protocol, and no research superiority claim is made by creating this document.

## Source and evidence baseline

- Frozen implementation baseline: current `origin/main` commit
  `10f14810e08ea28c3a336a8b7d54c6babbb40f5d` (2026-11-13). New agent-outcome
  implementation work is based on this commit. The proposal cites source
  commit `4315997d066a261aa674559fc89d73d0c407d16b`; the Git object is present,
  but it is not the frozen implementation baseline and its benchmark suite has
  not been rerun for this plan.
- Historical 50-agent synthetic and CDM results remain separate populations;
  this preregistration does not merge, reproduce, or extrapolate them.
- Current existing team benchmark: `experiments/teamworld.py` and
  `experiments/p3b_teams.py`. New work must reuse it where the treatment and
  outcome definitions match; a new world requires a written reason.
- Evidence classes are `contract_tested`, `local_model_tested`, and
  `deployment_validated`. This checkout currently has no outcome-stage result.

## Frozen historical outcome references

These entries pin the evidence available before the new implementation. They
are not pooled, and the population labels and limitations are part of the
record. The full machine-readable parameters and artifact paths are in
`research/prereg/agent-outcome-baseline-v1.json`.

| Reference | Frozen parameters and result | Reproduction status and limitation |
|---|---|---|
| Grand 50-agent baseline v2 | Source `d4fd174ac9056865c8b73abd857fa681daa6a0d7`; deterministic TeamWorld agent; seeds 101–105; 50 agents; 60 rounds; 100 tasks per seed; k=5; Windows 11, Python 3.13.5, 8 CPUs. 500 tasks: success 0.584, valid evidence withheld 0.168, stale actions 0.000. | Existing clean-checkout reproduction is recorded as exact in `research/results/grand-50-agent-baseline-reproduction-v2.json`; raw output digest is recorded there. This is scripted simulation, not LLM or deployment evidence. |
| R2 false-withholding promotion gate | Frozen input describes 500 task attempts and 125 stale controls; deterministic scripted TeamWorld. It reports 86/500 withheld (0.172), Wilson 95% interval 0.1415–0.2075, and a 5% promotion maximum. Recorded run commit `48158b62e6727ba70178fada92165178be70fb51`; Windows 11, Python 3.13.5, 8 logical CPUs, clean tree. | `research/results/r2-withholding-promotion-gate.json` is a deterministic policy-gate result with `HOLD_EXISTING_POLICY`; it is not a real-agent result. Its recorded digest for the `r2-false-withholding-ablation.json` input differs from the artifact currently in this checkout, so exact input reproduction is **NOT VERIFIED**. |
| R2 false-withholding diagnostic ablation | Seeds 101–105; 50 agents; deterministic scripted TeamWorld; 125 diagnostic cases and 500 task denominator in its report; counterfactuals are dry-run only. The currently checked-in JSON has `valid_withholding_rate: 0.0`; it does not itself report the 0.172 full-task rate. | `research/results/r2-false-withholding-ablation.json` marks a dirty Linux/Python 3.13.16 checkout and explicitly says the local corpus is not an exact import of upstream PR #30 rows. Do not substitute its diagnostic denominator for the R2 gate result. |
| Phase A and Phase A′ model-backed studies | `qwen2.5:3b`; seeds 0–4; 18 learning and 24 evaluation episodes per seed per arm. Phase A has eight arms/960 decisions; Phase A′ has six arms/720 decisions. | Results and preregistrations are retained in the baseline manifest. The decision artifacts lack source commit, model digest/quantization, full decoding settings, and run timestamp, so they are historical model-backed results with incomplete provenance, not exact reproducible baselines for the new benchmark. |
| Historical P3b agent-team report | Five seeds, 10-agent comparison, 60 rounds; deterministic scripted agents. | Retained in `research/results/p3b-agent-teams.md` as historical evidence with its own assumptions and limits. It is not combined with the 50-agent runs or treated as learned-agent evidence. |
| CDM outcome studies | See the individual frozen protocols and result manifests indexed by `docs/CDM_KNOWN_FINDINGS.md`. | Negative, null, invalidated, and untested results remain visible. No CDM benefit is presumed; these populations are not combined with TeamWorld task success. |

The historical report files contain the run parameters that were retained for
each study. When an exact command, source checkout, raw case rows, or clean provenance is
unavailable, that gap is explicitly retained in the manifest instead of being
filled by inferred parameters. None of these historical entries is a new
confirmatory run for this protocol.

## Primary estimand and endpoint freeze

**Frozen before new confirmatory runs:** the primary endpoint is the fraction of
scheduled, answerable world/task cases whose independent evaluator reports
`COMPLETED` within the fixed task budget. The denominator is every scheduled
answerable case for that arm, including failed, unsafe, abstained, missing, or
`UNDECIDABLE` results; only `COMPLETED` contributes to the numerator. Report the
full terminal-status counts beside the endpoint so missing evaluator records
remain visible. Unanswerable cases are a separate safety/abstention population,
not mixed into the primary completion denominator.

Endpoint and threshold freeze date: **2026-11-13**, before any new confirmatory
run for this protocol.

The unit and independent cluster is one `(world_seed, task_id)` case. Repeated
agents, tool calls, or retries on the same case do not increase `N`. Retain the
case IDs, world seed, objective, legal observations, action constraints,
terminal digest, and outcome for every arm. Agent observations must exclude
truth, expected actions, evidence eligibility/conflict labels, reward, and
answer keys. A safe abstention is not completion when a legal completion was
available.

The minimum materially meaningful primary gain is **5 percentage points of
absolute safe-task completion**. Promotion analysis must compare A5 against
both fair baselines A3 and A4 on the same paired cases; A5 must meet that
threshold against each, with uncertainty and safety results reported. This
threshold is an owner-selected decision bar, not an estimate fitted to the
historical studies. It is frozen for confirmatory design and may change only in
a dated preregistration amendment made before any confirmatory outcomes are
opened.

Candidate arms are A0–A7 from the master plan, including the strongest fair
non-oracle comparator and a budget matched oracle upper bound. All arms receive
identical cases, observation/tool budgets, prompts/model settings, and grading;
only the preregistered memory/recovery/CDM intervention may differ. CDM is
advisory and cannot authorize effects.

**Still not frozen:** sample size, stopping rule, confirmatory seeds,
multiplicity correction, task template split, and resource caps. Until these
are frozen before confirmatory runs, the protocol remains `DRAFT / NOT FROZEN`,
promotion status remains `NOT_READY`, and no result can pass the research
superiority gate.

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
