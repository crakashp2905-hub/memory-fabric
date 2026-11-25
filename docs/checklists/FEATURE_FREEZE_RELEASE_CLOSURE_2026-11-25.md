# Memory Fabric — Feature-Frozen Production Qualification & HOLD-Closure Plan

**Date:** 2026-11-25  
**Target repo:** `crakashp2905-hub/memory-fabric`  
**Observed `main`:** `4c3ed1ff70806f08ee1bc04ce64bac1157fce306` (PR #42 merged)  
**Strategy:** **NO NEW FEATURES.** Fix, simplify, benchmark, secure, qualify, and release existing functionality.  
**Status:** **SPECIFICATION ONLY.** This file does not demonstrate that tasks have passed and does not authorize autonomous or physical-world deployment.

## Executive release policy

The goal is one supported product with four independently qualified contracts:
1. **Core/governance:** memory lifecycle, provenance, tenant access, authenticated effect execution, correction/erasure and multi-host operations.
2. **Vega:** locally served, pinned, calibrated and evidence-bounded semantic **advisor**; no model authority over numbers, provenance, grants, evidence status or external effects. Turning its suggestions into an autonomous action-selection input additionally requires demonstrated outcome gain and the omission-safety gate.
3. **CDM:** deterministic, complete-trace, authorized, resource-bounded counterfactual replay and advisory. No reconstruction of opaque model reasoning or claim of real-world causality. Using CDM to automatically select a new action requires independent fresh verification and action authorization, plus measured incremental utility.
4. **Learned-agent workflow:** observer, planner, executor, recovery and evaluator with independently graded real-model outcomes. Disabling models cannot be misreported as qualified model execution.

**Definition of feature freeze:** allow only changes with a linked failing test, threat, measured bottleneck, release-readiness gap, operational failure or documentation mismatch. No new research modules, novel architecture, extra protocol, unapproved public API or benchmark invented to favor a candidate.

**No artificial GO:** an underpowered or negative experiment remains `HOLD`/`NO_GO`. Never tune acceptance thresholds after seeing held-out results. If Vega or CDM cannot satisfy a claim, production-grade deployment must explicitly scope it as *read-only advisory* or leave it disabled. A fully enabled release requires proving its stronger claims; the outcome cannot be guaranteed by implementing tasks.

## Evidence at planning baseline

- `docs/STATUS_AT_HEAD.md`: 3,988 collected tests, version 0.19.0; these are not equivalent to 3,988 test passes at the current SHA.
- `docs/VEGA_NEXT_DECISION.md`: **HOLD**, v2 confirmatory not run; A5-P 50%, A5-PV 56%, shuffled placebo 55% safe-success in a 100-task scripted/model-assisted pilot. This does **not** establish useful model-specific semantics.
- The 100-task-per-arm learned planner pilot: M-A5=31%, M-A5-P=32%, M-A5-PV=33% safe-success; completed tasks 21%/22%/23%; corrected guard produced zero observed unsafe omissions in those recorded cases.
- `research/results/vega-cdm/next/cdm/cdm-value.json`: positive **scripted** dependence-first utility, not learned-agent or real-world causal proof.
- `research/results/vega-cdm/next/gate/matrix.json`: core/identity safeguards PASS; CDM net utility INCONCLUSIVE; confirmatory NOT_RUN; security review BLOCKED_EXTERNAL; exact-head CI status stale.
- On 2026-11-25 latest `main` CI runs were **queued**, although earlier pre-merge CI passed. Recheck before any release decision.
- `research/checklist/vega-next-ledger.json`: 136 VALIDATED, 16 MODEL_VALIDATED, five IMPLEMENTED, three BLOCKED. `research/checklist/agent-validation-ledger.json`: 211 TESTED, 17 IMPLEMENTED, 12 BLOCKED_EXTERNAL. **Do not sum these as qualified production evidence.**

## Acceptance decision hierarchy

| Component | Candidate GO requires | Else |
|---|---|---|
| Core memory/governance | exact-SHA CI + security, correction, tenant, effect, migration, operations, staging gates | HOLD |
| Vega advisory serving | verified model identity + read-only provenance + privacy + calibration + reliability + independent review | OFF or SHADOW |
| Vega influencing autonomous choices | above **plus** preregistered true-content benefit versus strongest baseline **and placebo**, safety bounds and agent-outcome improvement | ADVISORY ONLY / HOLD |
| CDM advisory | exact verified replay on supported deterministic cases, resource isolation, privacy, certificates, operational logs, independent review | SHADOW / HOLD |
| CDM automatic decision repair | above **plus** positive held-out incremental utility over full-replan and recovery-only matched baselines, then fresh ActionGate | ADVISORY ONLY / HOLD |
| Learned agents | valid-model qualification, full outcome metrics and independent safety assessment, canary + rollback | OFF / supervised only |
| Whole-product 1.0 | **All** applicable components qualified, exact release SHA passed, independent review and supervised pilot done | NO-GO for unqualified scope |

### Hard-stop conditions

Any cross-tenant exposure, stale/forged effect authorization, irreversible data loss, unauthenticated control surface, unsafe omission in a gate requiring zero events, model override of verified truth, replay-effect leakage, or failure of a required stage **blocks promotion**. Zero events in finite tests does not prove zero risk; report exact upper confidence bounds.

### Operational metrics to keep separate

`task_completed`, `safe_task_success` (may include justified refusal), `justified_abstention`, `false_withholding`, `unsafe_executed_effect`, `unsafe_omission`, `wrong_intervention`, `recovery_time`, `model_calls`, `replay_calls`, `model_memory_RSS`, `p95/p99_latency`, `cost_per_safe_completion`, `tenant_leak`, `unreconciled_effects`. The evaluator must be independent of model-generated observations.

## Workstreams — tasks and exit gates

Every checkbox below is **to reverify at the final release candidate**. Many mechanisms already exist and are tested; do not duplicate them. Instead, close the specific qualification gap and attach a current, reproducible receipt. 

### F01 — Release freeze, exact-head inventory (G0)

**Primary paths:** `docs/STATUS_AT_HEAD.md; tools/release_bundle.py; research/results/MANIFEST.json`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F01-01 (P0)** Lock a single release-candidate SHA and classify only bug fixes, security fixes, performance fixes, test changes and documentation changes as permitted.  
  **Pass:** Tag or immutable candidate SHA, signed change log, and no feature commits.
- [ ] **F01-02 (P0)** Regenerate status, module-tier, version and results manifests on the candidate SHA.  
  **Pass:** Every derived report names that SHA; stale SHA references are identified.
- [ ] **F01-03 (P0)** Inspect every open HOLD, NO_GO, NOT_RUN, IMPLEMENTED and BLOCKED status across the two agent/vega ledgers and core release docs.  
  **Pass:** Single issue register with severity, owner, target, evidence and closure rule; no silent omissions.
- [ ] **F01-04 (P0)** Assign every outstanding risk a disposition: FIX, REPRODUCE, VERIFY, DOCUMENT_LIMIT, or OUT_OF_SCOPE_BY_CONTRACT.  
  **Pass:** Every P0 and P1 has a testable resolution; no known critical issue accepted without mitigation.
- [ ] **F01-05 (P0)** Run exact-head CI across all mandatory platforms and optional integrations in scope.  
  **Pass:** All mandatory workflows completed successfully at the exact candidate SHA; queued is not green.
- [ ] **F01-06 (P0)** Reproduce all earlier failures: unsafe Vega omissions, sensor alias collision, contested-evidence decision, planner no-action and CI decode/limits failures.  
  **Pass:** Stored pre/post reproduction with identical inputs and the final corrected outcome.
- [ ] **F01-07 (P1)** Audit the release footprint and available APIs; keep the canonical outcome_typed runtime and deprecations intact.  
  **Pass:** No new public runtime surface without signed break-fix justification; compatibility gate passes.
- [ ] **F01-08 (P0)** Freeze every evaluator, prompt, task generator, model identity, seed partition, cost and metric definition before final qualification.  
  **Pass:** Recorded digests and one-way holdout access policy; no post-hoc thresholds.

### F02 — Authorization, identity, action/effect safety (G1)

**Primary paths:** `src/memory_fabric/actions.py; src/memory_fabric/outcome_typed/; tests/test_effect_transport_parity.py`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F02-01 (P0)** Recheck tenant isolation for every SDK, CLI, API, MCP, UTCP, Code Mode, export, retrieval and historical replay read.  
  **Pass:** Cross-tenant reads and metadata side channels denied with indistinguishable responses.
- [ ] **F02-02 (P0)** Validate action-bound grants and permissions at proposal and execution time after correction or revoke.  
  **Pass:** Any revoked, stale, forged or substituted authorization yields no effect on all transports.
- [ ] **F02-03 (P0)** Close the typed action idempotency first-call ambiguity documented in KNOWN_GAPS.  
  **Pass:** An unbound first idempotency key cannot silently validate a later mismatched action; regression added.
- [ ] **F02-04 (P0)** Verify effect attempt/commit/reconcile ordering under crash, timeout and transport disconnect.  
  **Pass:** At-most-once effect where supported; unknown outcomes require explicit reconciliation, not blind retry.
- [ ] **F02-05 (P0)** Check human-approval binding to exact actor, tenant, target, params, evidence and expiry.  
  **Pass:** Stale or modified approvals are invalid at execution.
- [ ] **F02-06 (P0)** Prove semantic advisors and CDM cannot write memory, change permissions, forge receipts or execute external tools.  
  **Pass:** Boundary tests with malicious model outputs and forged certificates pass.
- [ ] **F02-07 (P0)** Test non-action hazards independently of ActionGate: no_action, abstain, missing response and wrong intervention.  
  **Pass:** The omission guard blocks unsafe closes and unsafe alternative effects in registered hazard policies.
- [ ] **F02-08 (P0)** Validate recovery, Vega and CDM feature flags default fail-safe and rollback without event-log mutation.  
  **Pass:** OFF->SHADOW->OFF byte-identical canonical outcomes, no unapproved effect.

### F03 — Memory semantics, correction, claim identity and data lifecycle (G1)

**Primary paths:** `src/memory_fabric/conflicts.py; validation.py; causal_replay/semantic/observations.py; tools/claim_identity_preview.py`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F03-01 (P0)** Prove sensor and component identities remain distinct across aliases, punctuation and nested entity references.  
  **Pass:** Independent instruments never collide or become fake corroboration in held-out identity fixtures.
- [ ] **F03-02 (P0)** Run claim_identity_preview against representative existing databases before v2 activation.  
  **Pass:** Zero unreviewed created collisions; migration plan and rollback verified from backup.
- [ ] **F03-03 (P0)** Cross-check typed quantities, units, negations, ranges and time references against manually annotated fixtures.  
  **Pass:** No unsupported text becomes VERIFIED_CLEAR; ambiguous observations stay UNKNOWN.
- [ ] **F03-04 (P0)** Trace evidence versions through corrections, erasure, federation and independent-source counting.  
  **Pass:** Every affected dependent record changes status; unrelated decisions stay intact.
- [ ] **F03-05 (P0)** Reconcile source-root deduplication against adversarial copying/paraphrasing and collusive reports.  
  **Pass:** Copies never count as independent sources; unsafe approvals remain denied.
- [ ] **F03-06 (P0)** Test historical belief reads against current permission intersection, tombstones and old certificates.  
  **Pass:** Revoked or erased evidence cannot be resurrected into current authorization.
- [ ] **F03-07 (P0)** Test encryption/backup/restore, key rotation, tenant migration and erased-record residue.  
  **Pass:** Restore drill shows no resurrected erased content or exposed keys; limitations documented.
- [ ] **F03-08 (P1)** Bound text ingestion failures and redaction including format adapters; no pretending to support OCR or visual fidelity.  
  **Pass:** All unrecognized/lossy content marked INCOMPLETE with source spans and audit trail.

### F04 — Vega decision correctness and calibration (G2)

**Primary paths:** `src/memory_fabric/adapters/vega_u.py; causal_replay/semantic/support.py; outcome_typed/semantic_advisory.py`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F04-01 (P0)** Retest the exact two 61/64-degree unsafe rows and all contested-reading planner traces.  
  **Pass:** Every former unsafe omission now escalates or selects a verified safe intervention; logs reproduce.
- [ ] **F04-02 (P0)** Restrict numeric facts, threshold comparisons, entity identity and authorization to deterministic verified parsers.  
  **Pass:** Vega output can neither override numeric evidence nor mark an unknown fact safe.
- [ ] **F04-03 (P0)** Repeat calibration on disjoint development and pilot sets for supported semantic labels.  
  **Pass:** Per-family Brier, ECE, selective accuracy, coverage and abstention published with denominators.
- [ ] **F04-04 (P0)** Qualify only question types whose calibrated error bounds meet a preregistered risk budget.  
  **Pass:** Unsupported classes remain REVIEW_ONLY; uncalibrated outputs never auto-promote.
- [ ] **F04-05 (P0)** Test model metadata pin, malicious localhost responses, timeout, proxy bypass, circuit-breaker and model absence.  
  **Pass:** Adapter fails closed; core continues without model or data egress.
- [ ] **F04-06 (P0)** Test semantic evidence packets for lifecycle recheck, erasure, source-root, tenant and sealed evaluator fields.  
  **Pass:** No secrets, cross-tenant data or hidden oracle values enter model prompts.
- [ ] **F04-07 (P1)** Validate suggestions on semantic negation, context scope, conflicting sources and unseen wordings.  
  **Pass:** False certainty triggers retrieval/review; model returns typed proposal with evidence references only.
- [ ] **F04-08 (P1)** Measure server cold/warm start, RSS, p95/p99, queueing and accuracy on exact pinned 0.8B reader.  
  **Pass:** Hardware-specific envelope with no extrapolation; model identity retained in each receipt.

### F05 — Vega causal and agent efficacy: remove research HOLD honestly (G3)

**Primary paths:** `benchmarks/vega_next_arms.py; benchmarks/vega_next_model_agents.py; research/prereg/vega-cdm-v2.json`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F05-01 (P0)** Keep the current v2 HOLD and archived negative results immutable; design a genuinely new v3 only after failure diagnosis.  
  **Pass:** Historical outcomes and thresholds are preserved; no unblinding or retroactive relabeling.
- [ ] **F05-02 (P0)** Diagnose why note relevance almost ties shuffled-note placebo; inspect answer dependence on actual note content.  
  **Pass:** Per-instance contrast and counterexample explanations stored; no model gains credited to irrelevant text.
- [ ] **F05-03 (P0)** Repair existing semantic input formulation or calibrated acceptance rule without expanding model architecture.  
  **Pass:** Improvement replicated on an untouched development subset, with all unsafe omissions separately counted.
- [ ] **F05-04 (P0)** Compare against A5-P, A3-P, placebo-shuffled, wrong-confidence, same-cost deterministic selection and Vega OFF.  
  **Pass:** Equal tasks, retrieval budget, time, system prompts and identical evaluator; call costs recorded.
- [ ] **F05-05 (P0)** Require a preregistered practically useful gain over strongest baseline AND placebo; choose effects before holdout.  
  **Pass:** All primary comparisons meet frozen effect/significance criteria or verdict remains HOLD.
- [ ] **F05-06 (P0)** Run real learned-agent arms with current pinned local model and stronger already-supported model if available.  
  **Pass:** Paired tasks show measured safe completion, real completion, refusal, unsafe omission and operator escalations.
- [ ] **F05-07 (P0)** Test safety under multiple contexts including paraphrases, prompt injection, corrupted notes and model failure.  
  **Pass:** No observed unsafe regression at the declared sample size; nonzero upper bounds reported.
- [ ] **F05-08 (P0)** Qualify Vega mode transitions only after evidence and operational gates pass.  
  **Pass:** Production switch explicitly signed; otherwise Vega remains OFF/SHADOW despite working inference.

### F06 — CDM deterministic integrity and causal claim boundaries (G4)

**Primary paths:** `src/memory_fabric/causal_replay/; docs/CAUSAL_REPLAY_LIMITATIONS.md`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F06-01 (P0)** Reproduce CDM internal offline qualification, replay certificates and verifier adversarial suite at release SHA.  
  **Pass:** Every mandatory stage passes with exact-SHA evidence; missing stages are NO_GO.
- [ ] **F06-02 (P0)** Validate complete decision traces and deterministic policy/simulator version commitment.  
  **Pass:** Unknown RNG, tool output, model internals or evidence return NON_REPLAYABLE without fabrication.
- [ ] **F06-03 (P0)** Test correction-after-decision reconstruction, temporal ordering, source version and current authorization.  
  **Pass:** Replays cannot read erased or revoked evidence and cannot claim more than captured state supports.
- [ ] **F06-04 (P0)** Run independent verifier against fabricated certificates, altered evidence, fake actions and solver mismatch.  
  **Pass:** All forged certificates refused; certificate never grants action authority.
- [ ] **F06-05 (P0)** Qualify bounded replay on supported OSes with hard process isolation and watchdog termination.  
  **Pass:** Measured CPU, memory and wall limits enforced or unsupported platforms explicitly reject unsafe mode.
- [ ] **F06-06 (P0)** Verify every data-only intervention through a whitelist and independent replay result.  
  **Pass:** No network access, host tool execution, code execution or arbitrary model call in replay worker.
- [ ] **F06-07 (P1)** Measure replay state size, checkpoint rebuild, concurrency, pruning accuracy and invalidation costs.  
  **Pass:** Exact replay preserved under all claimed optimization; limits and scaling caps published.
- [ ] **F06-08 (P0)** Require causal-language taxonomy on every API and report.  
  **Pass:** Labels distinguish hypothesis, simulator-conditional effect and unsupported real-world causality.

### F07 — CDM outcome benefit and operational promotion (G5)

**Primary paths:** `src/memory_fabric/outcome_typed/cdm_dispatch.py; benchmarks/vega_next_cdm_value.py; research/prereg/`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F07-01 (P0)** Replicate scripted CDM gain and its provenance, including negative earlier CDM research.  
  **Pass:** 240/240 deterministic pack decisions reproduced without turning synthetic metrics into real-agent proof.
- [ ] **F07-02 (P0)** Re-evaluate CDM against recovery-only, dependence-only, full replan, random and recency at identical budgets.  
  **Pass:** Best baseline fixed on development; net benefit includes inference, memory, time and replay cost.
- [ ] **F07-03 (P0)** Include tasks where replay cannot help, harms, or changes no decision to estimate wasted work.  
  **Pass:** Per-family outcomes and no-headroom cases in denominator; no cherry-picking of flips.
- [ ] **F07-04 (P0)** Prove replayed decision suggestions still pass ordinary fresh verification and ActionGate.  
  **Pass:** No trace, counterfactual or certificate path invokes effects or bypasses governance.
- [ ] **F07-05 (P0)** Compare with and without CDM using learned local agents in multi-step correction tasks.  
  **Pass:** Held-out paired task outcomes and safe completion improvement/uncertainty quantified.
- [ ] **F07-06 (P0)** Demonstrate positive incremental net utility at chosen resource budgets; enforce stop-loss.  
  **Pass:** Frozen confidence interval and safety checks pass; otherwise remain bounded advisory.
- [ ] **F07-07 (P1)** Operate CDM in shadow/canary with metrics: trigger precision, false replays, saved computations and corrections.  
  **Pass:** On-call can disable CDM instantly without changing the store; metrics reconcile with traces.
- [ ] **F07-08 (P0)** Write a narrow supported-use contract: deterministic recorded decisions only, no autonomous deletion or real-world causal proof.  
  **Pass:** The release UI and SDK cannot overstate capabilities; unsupported cases give typed refusals.

### F08 — Actual agent task performance and false withholding (G6)

**Primary paths:** `src/memory_fabric/outcome_typed/; benchmarks/vega_next_model_agents.py; docs/AGENT_PROTOTYPE.md`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F08-01 (P0)** Classify all Qwen2.5-1.5B planner errors from 100-task pilot including 77 guard blocks and frequent no_action.  
  **Pass:** Root-cause table by retrieval, parsing, planning, option selection, abstention and verification.
- [ ] **F08-02 (P0)** Improve the EXISTING planner prompt/option mapping and recoverable failure behavior without adding another agent framework.  
  **Pass:** Paired development run improves terminal completion while retaining identical safety guard.
- [ ] **F08-03 (P0)** Test already-supported model sizes locally, pin weights and decoding, and compare under full resource budgets.  
  **Pass:** Promoted planner chosen on held-out validation, not on subjective quality or token count.
- [ ] **F08-04 (P0)** Run the three-role observer/planner/executor workflow with real model calls and time-varying corrections.  
  **Pass:** All inference calls recorded; not silently replaced by scripted agents.
- [ ] **F08-05 (P0)** Compare A3/A5/A5+Vega/A5+CDM/A5+Vega+CDM and agent-local baseline with same tools and budgets.  
  **Pass:** Per-case paired outcomes, cost, safety, correct abstention and false withholding published.
- [ ] **F08-06 (P0)** Test irrecoverable tasks, hidden corrections, missing sensor, malicious instruction and contradictory provenance.  
  **Pass:** No unsafe unknown-to-clear downgrade and no critical cross-tenant information disclosure.
- [ ] **F08-07 (P0)** Freeze and run one confirmatory experiment after pilot specificity and power gates pass.  
  **Pass:** No sequential peeking; report inconclusive/negative results without manufacturing success.
- [ ] **F08-08 (P0)** Define operator-oriented thresholds for successful completion, false denial and fallback/escalation load.  
  **Pass:** Values justified by actual pilot requirements, and measured independently of safe-success metric.

### F09 — Execution boundaries, security and supply chain (G7)

**Primary paths:** `docs/SECURITY.md; tests/test_vega_next_security.py; tools/check.py; tools/release_bundle.py`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F09-01 (P0)** Threat-model every entry point and inter-process boundary including Vega local serving and CDM worker.  
  **Pass:** Documented data flows, trust boundaries, minimum privileges, SSRF, prompt injection, symlink and path risks.
- [ ] **F09-02 (P0)** Harden model-worker and replay-worker process isolation using available OS facilities.  
  **Pass:** Escaped process, fork bomb, large RAM allocation and blocked syscalls fail safely in targeted tests.
- [ ] **F09-03 (P0)** Scan dependencies and pinned model weights/runtime for known vulnerabilities, licenses and artifact integrity.  
  **Pass:** SBOM, hashes, approvals and no unbounded model downloads at production start.
- [ ] **F09-04 (P0)** Qualify tenant egress/privacy: Vega only loopback, proxies bypassed, logs redacted, model outputs bounded.  
  **Pass:** Secret canaries and cross-tenant fixtures never appear in process or receipt outputs.
- [ ] **F09-05 (P1)** Run fuzz, mutation and property tests around parsers, identity, thresholds, timestamps and advice schemas.  
  **Pass:** Specified mutation score and zero surviving critical safety mutants, with raw logs.
- [ ] **F09-06 (P0)** Independently test hostile agent/model outputs cannot execute code through MCP/UTCP/Code Mode adapters.  
  **Pass:** All effect paths enforce same contract and reject unauthorized side effects.
- [ ] **F09-07 (P0)** Qualify key management, rotation, retrieval, backup custody and emergency lockout.  
  **Pass:** Key loss and rollback drills documented; no plaintext fallback.
- [ ] **F09-08 (P0)** Obtain an independent threat assessment and remediate blocking findings.  
  **Pass:** Signed report, reproduction steps and verified fixes; internal self-review cannot close this gate.

### F10 — Persistence, federation, disaster recovery and consistency (G8)

**Primary paths:** `src/memory_fabric/_fabric/; docs/OPERATIONS.md; tests/test_multiprocess_crash.py`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F10-01 (P1)** Test SQLite and PostgreSQL under separately documented supported workloads.  
  **Pass:** p99, deadlocks, lock waits, consistency, contention and unsupported capacity disclosed.
- [ ] **F10-02 (P0)** Exercise crash and restart at every write/retract/share/effect-commit stage.  
  **Pass:** No missing tombstones, double effects, or silent acknowledgement loss.
- [ ] **F10-03 (P0)** Validate federation partitions, clock skew, duplicate events, out-of-order corrections and delayed retractions.  
  **Pass:** Eventual convergence documented within measurement window, otherwise peer remains quarantined.
- [ ] **F10-04 (P0)** Run backup, point-in-time restore, migration upgrade, downgrade and erasure precedence on disposable stores.  
  **Pass:** Operator can restore with RPO/RTO measurement, no secret or erased-content resurrection.
- [ ] **F10-05 (P1)** Check cross-version schema and protocol interoperability over supported rollout versions.  
  **Pass:** Explicit compatibility matrix or hard refusal with actionable remediation.
- [ ] **F10-06 (P0)** Exercise unresolved effect reconciliation, dead-letter queue and re-drive after outage.  
  **Pass:** Unknown outcomes surfaced, deduped, and resolved through target-system evidence.
- [ ] **F10-07 (P0)** Run repeated multi-process and physical multi-host reliability tests across realistic network conditions.  
  **Pass:** Measured loss/reordering/reconnect behavior; no synthetic-only claims about physical hosts.
- [ ] **F10-08 (P0)** Enforce global event size, queue size, retention, outbox backlog and replay buffer ceilings.  
  **Pass:** Overload becomes backpressure or typed refusal, not resource exhaustion or state corruption.

### F11 — Host and runtime performance qualification (G9)

**Primary paths:** `tools/vega_next_perf.py; docs/AGENT_OPERATING_ENVELOPE.md; research/results/vega-cdm/next/perf/`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F11-01 (P1)** Measure deterministic core, model actor, Vega and CDM separately and together.  
  **Pass:** Per-stage p50/p95/p99 and full-run CPU/RSS/latency by configuration.
- [ ] **F11-02 (P1)** Run exact supported 16GB Apple Silicon host profile and one Linux staging host profile.  
  **Pass:** Both pass memory/pressure, throughput and no-swap or bounded-swap requirements set in advance.
- [ ] **F11-03 (P1)** Load test 1/2/4/8 workers with simultaneous corrections and model inference.  
  **Pass:** Throughput, queue wait, latency tails, deadlocks and rollback behavior measured and limits fixed.
- [ ] **F11-04 (P0)** Set explicit model and replay concurrency, queue, timeout, retry and circuit-breaker caps.  
  **Pass:** Resource use bounded under adversarial tasks; no unbounded memory growth.
- [ ] **F11-05 (P0)** Bound CDM replay and model inference budgets independently, preventing contention with action-time verification.  
  **Pass:** Verification SLO remains satisfied with CDM/Vega saturated; optional workers shed load.
- [ ] **F11-06 (P1)** Measure cost per safe completion and per recovered task, not only cost per model call.  
  **Pass:** Evidence distinguishes cheap refusal from useful and safe task resolution.
- [ ] **F11-07 (P1)** Document capacity and supported configurations only at measured host classes.  
  **Pass:** Published envelope includes model size, model identity, sample counts and limitations.
- [ ] **F11-08 (P1)** Establish performance regression thresholds in CI/nightly qualification without flaky gates.  
  **Pass:** Stable controlled benchmarks, baseline trend and documented variance; release blocker for severe regression.

### F12 — Operations, alerts, incident response and operator UX (G10)

**Primary paths:** `docs/OPERATIONS.md; docs/AGENT_LAUNCH_READINESS.md; src/memory_fabric/observability/`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F12-01 (P0)** Produce one reliable release dashboard for governance, Vega, CDM, agent outcomes, model health and overall GO/HOLD.  
  **Pass:** Operator sees component-specific state, exact SHA and why any gate is blocked.
- [ ] **F12-02 (P1)** Record end-to-end trace: input evidence versions, model receipts, decision, recheck, guard, effect and evaluator.  
  **Pass:** Redacted trace links each action to a reproducible decision with no secret leakage.
- [ ] **F12-03 (P0)** Define and test alerts for unsafe omissions, cross-tenant leaks, stale evidence acted upon, replay divergence and model timeouts.  
  **Pass:** Synthetic alert drills fire; on-call runbook points to source and rollback switch.
- [ ] **F12-04 (P0)** Perform model kill switch and CDM kill switch drills during in-flight work.  
  **Pass:** Existing active writes unaffected; no already-withdrawn evidence promoted.
- [ ] **F12-05 (P0)** Exercise release rollback, store migration revert, model checkpoint rollback and corrupted snapshot restore.  
  **Pass:** Safe paths demonstrated with owner-readable steps; no irreversible migration without backup.
- [ ] **F12-06 (P1)** Test administrative role and approval UX against accidental unsafe actuation and review overload.  
  **Pass:** Operator can see and address review-required cases and all changes are audited.
- [ ] **F12-07 (P0)** Create incident runbooks for prompt injection, unsafe non-action, suspected data leak and compromised model hash.  
  **Pass:** Tabletop drill and evidence capture performed; escalation contacts assigned.
- [ ] **F12-08 (P1)** Define realistic service metrics and SLOs per deployment scenario from measured hardware and test populations.  
  **Pass:** SLOs are derived, monitored and have trigger thresholds; no invented uptime commitments.

### F13 — Build, packaging, docs, compatibility and shipping (G11)

**Primary paths:** `pyproject.toml; docs/STATUS_AT_HEAD.md; .github/workflows/; tools/release_bundle.py`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F13-01 (P0)** Build clean source/wheel twice and inspect archive contents for tests, secret keys or model weights.  
  **Pass:** Repeatability report, SBOM, hashes, provenance and clean install on supported platforms.
- [ ] **F13-02 (P0)** Verify version parity among pyproject, schema, SPEC, docs and migration notes.  
  **Pass:** Single version shown to every CLI/SDK entry point; no undocumented breaking change.
- [ ] **F13-03 (P0)** Run all mandatory CI jobs and security workflows at immutable release candidate SHA.  
  **Pass:** 100% required jobs successfully complete; no skipped model job falsely called pass.
- [ ] **F13-04 (P0)** Keep core dependency policy intact; pin optional Vega local server and model assets separately.  
  **Pass:** Core install works offline, model absence fails clearly, and no hosted API required.
- [ ] **F13-05 (P0)** Verify SDK/CLI/MCP/UTCP/Code Mode operation through installed-wheel tests.  
  **Pass:** Same authorization and typed failure behavior for supported client surfaces.
- [ ] **F13-06 (P0)** Update docs to distinguish stable core, bounded Vega advisor, bounded CDM, and separately qualified agent execution.  
  **Pass:** Every public feature has supported scope, configuration, limitation and rollback step.
- [ ] **F13-07 (P1)** Run fresh-install user journeys for corrections, safe omission, CDM audit and Vega shadow mode.  
  **Pass:** Each journey produces expected evidence, usable errors and no unapproved effects.
- [ ] **F13-08 (P0)** Sign/tag/release only after release manager, security reviewer and qualification owners approve.  
  **Pass:** Immutable artifact digest, release checklist, change log, rollback plan and explicit provenance.

### F14 — Independent evaluation, supervised pilot and final release decision (G12)

**Primary paths:** `docs/PRODUCT_READINESS.md; docs/RELEASE_READINESS.md; docs/AGENT_LAUNCH_READINESS.md`  
**Exit gate:** every P0 complete with evidence, every P1 disposition documented; no required test or independent approval missing.
- [ ] **F14-01 (P0)** Recruit at least one independent security reviewer who did not implement the change.  
  **Pass:** Independent signed review and reproducible findings; cannot be marked in-house.
- [ ] **F14-02 (P0)** Run a permissioned supervised pilot with historical/synthetic data and no live physical actuation.  
  **Pass:** Consent, scope, stop rules, owner signoff and traceable pilot outcomes.
- [ ] **F14-03 (P0)** Repeat key benchmarks on independent hardware and at least one newly authored environment.  
  **Pass:** Task and model digests, device metrics and independent reproduction report.
- [ ] **F14-04 (P0)** Measure actual operator workflow utility: completion, rework, escalations, safe refusals, recovery time.  
  **Pass:** Pilot meets preregistered user-value and safety metrics; no success extrapolation.
- [ ] **F14-05 (P0)** Close every known critical/high finding or document a supported disabled/degraded mode.  
  **Pass:** No critical/high remains enabled without mitigation; scope exclusions explicit.
- [ ] **F14-06 (P0)** Sign GO/HOLD per component: CORE, VEGA, CDM, MODEL_AGENT, FEDERATION and WHOLE_PRODUCT.  
  **Pass:** GO only when component and downstream product dependencies pass.
- [ ] **F14-07 (P0)** Perform staged deploy: shadow, supervised canary, bounded production with monitored rollback.  
  **Pass:** For each stage no stop rules breached and safety confidence intervals reported.
- [ ] **F14-08 (P0)** Publish a truthful final release manifest, known limitations and support commitment.  
  **Pass:** 1.0 claim only if G0–G12 all pass; otherwise labeled bounded beta/alpha with explicit exclusions.

## Execution order and release control

**Wave A — Immutable baseline and critical correctness:** F01, F02, F03. Before any model promotion, qualify core memory, identity, authorization, omissions and regression reproductions.

**Wave B — Vega and CDM closure:** F04–F07. Red-team and calibrate the already-implemented Vega advisor; require actual note-content specificity; requalify deterministic CDM, and demonstrate incremental real-agent decision utility. Keep all negative findings.

**Wave C — Real agents and operational security:** F08–F12. Fix the 1.5B planner's no-action failure **within existing supported model/prompt contracts**, qualify process isolation, persistence, hardware performance, alerts and rollback.

**Wave D — Release proof:** F13–F14. Immutable CI, artifacts, third-party security review, supervised pilot, signer approvals, canary and final release verdict.

## Mandatory commands to rerun on the exact candidate SHA

```bash
git rev-parse HEAD
python -m pip install -e '.[test]'
python tools/vega_next_baseline.py --check
python -m benchmarks.vega_next_confirmatory validate research/prereg/vega-cdm-v2.json
python tools/vega_next_gate.py --out ./qualification/vega-next
python tools/agent_outcome_end_to_end_gate.py --offline --all --out ./qualification/agents
python -m benchmarks.vega_next_cdm_value --seeds 40 --out ./qualification/cdm-scripted.json
python tools/claim_identity_preview.py --help
python -m pytest -q tests/test_omission_safety.py tests/test_sensor_entity_claims.py tests/test_semantic_quantities.py tests/test_vega_next_security.py
```

The v2 registration validator currently **should refuse** the existing study. Do not freeze or run the holdout just to make a gate green. Use a legitimate new preregistration only after an independently replicated, specificity-positive development pilot.

## Required evidence directory structure

```text
qualification/
  candidate.json                 # git SHA, tree digest, source build hashes, platform
  gates/core.json                # governance tests, effect parity, correction/erasure
  gates/vega.json                # model pins, calibration, placebo, safety, latency
  gates/cdm.json                 # replay fidelity, cert verifier, net utility, isolation
  gates/agents.json              # real agent task-level paired evidence and CI
  gates/security.json            # threat matrix, secret scan, review attestations
  gates/performance.json         # exact machine, memory, p99, queue and cost
  gates/operations.json          # backup/restore and kill switch drills
  gates/release.json             # exact SHA, all GO/HOLD per component, owner signoff
```

Each evidence record needs `source_sha`, command, process exit status, environment, seeds/task set, model/weights digest if used, test/evaluator digest, timestamp, raw rows, summary, limitations and reviewer. Failures are first-class artifacts, not erased.

## Independent or environment-dependent constraints

- Real external security review, user pilot, business acceptance and physical multi-host measurement cannot be produced merely by an AI-generated checklist. Arrange real access and independent reviewers; mark `BLOCKED_EXTERNAL` otherwise.
- Vega's third-party open weights and its optional server are not first-party code. Core remains installable without them; actual offline model testing requires the pinned weights already cached locally.
- Claimed Apple Silicon 16 GB support requires a real measurement there. Container estimates cannot be turned into device-specific guarantees.
- CDM cannot honestly reconstruct hidden model cognition or prove physical causality without new observation/instrumentation and appropriate experiments. Its supported production scope should remain deterministic, recorded, simulator-conditional replay.

## Final outcome

Release only when the **whole product** gates clear with reproducible records. If one capability fails, keep the overall full-functionality product on HOLD. A strictly narrower scoped release could be separately approved, but must not imply that Vega/CDM autonomous features passed. This is a **closure plan**, not a declaration of production readiness or a commitment that every research hypothesis will become true.
