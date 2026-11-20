# Memory Fabric — Agent Outcome Superiority & Production-Oriented Engineering

**Next complete end-to-end, in-house implementation checklist**  
**Audit date:** 2026-11-20  
**Target repository:** https://github.com/crakashp2905-hub/memory-fabric  
**Latest main examined:** `70e34c870d387cb5de8ba0bbdda0320cf3574d6c` (committed 2026-11-15)  
**Scope:** fully implementable in-house core; no hosted API, paid dataset, downloaded benchmark or new mandatory runtime package. Already installed local-model weights are optional for empirical learned-agent qualification.  
**Baseline status:** research/engineering alpha; **not production-qualified**.

> **Important:** This file is a DEVELOPMENT SPECIFICATION, not evidence that the proposed changes are implemented. Every checkbox begins incomplete until the repository contains implementation, tests and exact-SHA results. Production qualification is a separate evidence gate. NEVER claim agent efficacy from scripted contracts, local-model smokes or green CI alone.

## 0. Audit verdict and current evidence

### Qualitative rating: **8.7/10** (previous 8.8/10)

| Dimension | Rating | Current basis |
|---|---:|---|
| Architecture and systems design | 9.3 | Event log, provenance, action gate, CDM and agent outcome work are substantial; duplicated outcome stacks increase integration risk. |
| Engineering / CI | 9.3 | 35/35 ordinary CI jobs passed at the current head; 3,511 reported collected tests; no independent full local rerun in this review. |
| Governance and evidence control | 9.3 | Typed versioned claims, retraction, source lineage and current action authorization. |
| Security implementation | 8.3 | Strong contract gates; scheduled model-attacks workflow failed 2026-11-16; reason not verified because logs unavailable. |
| Scientific method / evidence tooling | 9.5 | `memeval`, preregistration checks, negative-result preservation, comparator parity. |
| CDM engineering | 8.3 | Deterministic replay, attribution, certificates and tests exist; demonstrated utility is inconclusive/negative. |
| Demonstrated learned-agent effectiveness | 6.2 | One Qwen smoke and one small sequential three-role smoke; no confirmatory matched learned-agent task study. |
| Demonstrated novelty | 7.0 | Decision continuity/governance candidate differentiation but no established outcome superiority. |
| Product and deployment readiness | 6.2 | Local demos, API and packaging; no independent security/pilot evidence, and experimental runtime duplication remains. |

**Verified baselines:**

1. **Code state:** 2,360 tracked files, 207 Python application sources, 446 Python test files; main SHA above unchanged since Nov 15. `docs/STATUS_AT_HEAD.md` lists 3,511 collected tests. Different counts measure different things.
2. **CI:** [`43688018330`](https://github.com/crakashp2905-hub/memory-fabric/actions/runs/43688018330) — 35 of 35 jobs successful, including an `agent-outcome-offline-gate`. That gate records **`real_agent_execution = NOT_RUN`**, making overall outcome status `NOT_RUN` despite the contract job finishing successfully.
3. **Model attacks:** [`43848470357`](https://github.com/crakashp2905-hub/memory-fabric/actions/runs/43848470357), 2026-11-16, failed. Detailed job logs could not be retrieved (GitHub returned a missing-blob error); **do not infer a security vulnerability or installation-only failure without evidence**.
4. **Agent outcomes:** `research/results/agent-outcome-a5-matched-development.json` compares **A5–A4 = +0.20** and **A5–A3 = 0.00** on 10 scripted development task cases, one seed. No model efficacy or statistical promotion follows.
5. **Scripted correction case:** A5 recovered 12/12 versus 0/12 for A0 immediate abstention. A0 is **not** the strongest fair baseline; this is a capability demonstration, not an effectiveness proof.
6. **Real model smoke:** local Qwen 2.5 1.5B `Q4_K_M` recorded one model decision and a five-call sequential three-role example. Those are interface smoke tests, not task-success populations.
7. **Confirmatory:** `research/prereg/agent-outcome-confirmatory-v1.json` is still **`DRAFT`**, with no confirmatory seeds, task IDs, sample size or frozen hashes. A6/CDM is not run in the matched comparison.
8. **Historical 50-agent study:** 58.4% scripted task success and 16.8% valid evidence withheld, 0 observed stale actions, on 500 task decisions. These are old-population baselines—not current A5 outcome results. The 17.2% separate withholding study is likewise historical.
9. **CDM novelty/utility:** R5v3 mean 0.055, 95% interval [-0.0528, 0.1628], which **does not support** the preregistered superiority hypothesis. Held-out selectors report non-positive point utility. A policy flip is not a utility gain.
10. **Release:** `docs/CDM_INTERNAL_GO_NO_GO.md` permits bounded internal research only; `docs/MEMORY_FABRIC_RELEASE_CHECKLIST.md` is NO-GO for external publication. Independent pilots/certification are not completed.

### Evidence links

- [Agent outcome evaluation](https://github.com/crakashp2905-hub/memory-fabric/blob/main/docs/AGENT_OUTCOME_EVALUATION.md)
- [Outcome protocol evaluation](https://github.com/crakashp2905-hub/memory-fabric/blob/main/docs/OUTCOME_PROTOCOL_EVALUATION.md)
- [Raw A5 development comparison](https://github.com/crakashp2905-hub/memory-fabric/blob/main/research/results/agent-outcome-a5-matched-development.json)
- [Confirmatory registration](https://github.com/crakashp2905-hub/memory-fabric/blob/main/research/prereg/agent-outcome-confirmatory-v1.json)
- [CDM limitations](https://github.com/crakashp2905-hub/memory-fabric/blob/main/docs/CDM_KNOWN_FINDINGS.md)
- [Research integrity tool](https://github.com/crakashp2905-hub/memory-fabric/tree/main/memeval)

## 1. Non-negotiable design principles

- **Outcome over architecture:** measure actual verified terminal-task completion, not number of memories, replay certificates or test cases.
- **Fair baselines:** A5 must beat equally capable A3 (pooled memory + recovery), not just A0 (immediate abstention) or A4 (governed without recovery).
- **No unsafe shortcut:** no new path may bypass `ActionGate`; recovery and CDM do not mint permission, assert source truth, or create executable plans without host policy.
- **Independent truth:** evaluation labels and legal actions belong to the evaluator, not the actor prompt, memory or tool output.
- **In-house first:** Python standard library and existing repository packages for core; no hosted services or bought datasets. Use generated deterministic task worlds for mandatory checks.
- **True learned-agent claims require genuine inference.** An existing local Ollama checkpoint can be used fully offline. If no weights/runtime are installed, produce `REAL_AGENT_NOT_RUN`; do not pretend Python heuristics or a fake local model are a learned-agent validation.
- **Product versus external certification:** in-house engineering may be completed without an outsider; independent security attestation, customer pilots and real production operating evidence may *not* be claimed from internal tests.
- **Negative findings are deliverables.** Preserve all null, negative and invalid studies and keep old frozen results intact.

## 2. Target architecture

```text
TASK REQUEST / OPERATOR
       |
       v
Agent Host / one canonical typed outcome runtime
       |
       +-- Observer (local learned agent or deterministic test double)
       |     -> governed memory retrieve + CURRENT authorization
       |     -> evidence diagnosis: relevance/answerability/freshness/source independence
       |
       +-- Planner -> task-bound version-pinned proposal and dependencies
       |
       +-- Executor -> ActionGate (current proof + exact grant + idempotency)
       |                 -> simulated world effect / host-approved real effect
       |                 -> independent terminal-state observation
       |
       +-- If blocked: bounded recovery selector
       |     -> alternate source / re-observe / targeted partial replan
       |     -> on material dependence only: optional CDM advisory worker
       |     -> NEW current certificate -> ActionGate again
       |
       +-- Independent evaluator (separate capability / hidden truth)
             -> completion, unjustified abstention, safety, latency, cost
             -> registered A0..A7 matched comparison and `memeval` audit
             -> only frozen, same-SHA evidence may qualify changes
```

**Canonical runtime choice:** provisionally prefer `src/memory_fabric/outcome_typed/` because it contains the richer typed contracts and CDM dispatch; an ADR must verify that against `outcome_protocol` and `agent_outcomes` before consolidation. A new fourth outcome package is prohibited.

**Decision mechanism:** `RETRIEVE → DIAGNOSE → PLAN → VERIFY → [ACT or RECOVER] → FRESH VERIFY → EFFECT → EVALUATE`. CDM is a conditional read-only advisory, not an always-on component.

## 3. Scientific primary outcome, baselines and promotion

### Arm registry

| Arm | Definition | Purpose |
|---|---|---|
| A0 | No memory | Negative control only |
| A1 | Agent-local memory | Minimal independent baseline |
| A2 | Pooled shared memory | Ungoverned baseline |
| A3 | **Pooled shared memory + equally capable recovery** | **Primary competitor for A5** |
| A4 | Memory Fabric governance without recovery | Isolates recovery benefit |
| A5 | Memory Fabric + bounded recovery | Primary intervention |
| A6 | A5 + conditional CDM replay | Incremental research mechanism |
| A7 | Hidden-truth oracle (evaluator only) | Headroom ceiling, never actor input |

Supplementary first-party retrieval controls: lexical, recency, fixed k, full-context within equal budget, and simple summary.

### Primary metric and definitions

`safe_completion_rate = evaluator-confirmed authorized terminal objectives reached / all scheduled eligible task cases`. Incomplete/undecidable remain in denominator unless the protocol predeclares justified exclusions.

- `false_withholding_rate = eligible task cases where current authorized usable evidence exists in the store but the agent-visible retrieval context omits all sufficient evidence / eligible task cases where such evidence exists` (report the strict eligibility rule, and exclude truth that the actor is not permitted to access). This measures **evidence delivery**, not every task failure.
- `false_abstention_rate = answerable authorized tasks where enough evidence was delivered but the agent/policy refused a permitted necessary step / answerable authorized tasks with sufficient delivered evidence` (report justified abstention separately).
- `unsafe_attempt_rate` and `unsafe_execution_rate` use separate numerators, task-case denominators, and effect-attempt denominators.
- `recovery_rate = recovered and evaluator-complete / correction-recovery-eligible tasks`.
- `net_CDM_utility = factual terminal task benefit - baseline terminal task benefit - preregistered replay resource penalty`; compare A6 versus A5 on same cases.
- `correction_to_completion_ms` measured in one monotonic time domain; never confuse total episode time with post-correction recovery latency.

**Proposed gate (freeze before runs):** A5 must beat A3 **and** A4 on independent held-out task clusters, with a lower 95% paired-cluster interval exceeding a feasible preregistered absolute material gain (candidate 0.05), plus safety non-inferiority and no major fairness regression. Use pilot effect/discordance and **oracle headroom** to power the study; never freeze an impossible bar. A6 receives a separate incremental cost-adjusted gate and cannot promote before A5. The earlier goal of ≤5% false withholding is a *development aspiration on a specific eligible population*, not a promised universal rate.

**Zero observed unsafe actions is not proof of zero risk**: report an exact one-sided binomial upper bound and test distinct adversarial families.

### Research statuses

`CONTRACT_TESTED` → `SCRIPTED_EVALUATED` → `LOCAL_MODEL_EVALUATED` → `CONFIRMATORY_SUPPORTED/NOT_SUPPORTED/INCONCLUSIVE` → `INDEPENDENT_PILOT` → `PRODUCTION_QUALIFIED`.

No automatic step: each requires its own evidence.

## 4. Implementation program and checklists

For each item, **definition of done** means code + a negative test + a positive test (where applicable), a command to reproduce, and an exact source SHA / evidence record. Each numbered checkbox is a proposed task and starts in `TODO`. Group priority is P0 (blocking) or P1 (important); **never** modify historical scientific results merely to make gates pass.


### 01. Exact revision, evidence registry, and failed-workflow triage — W01 (0 · Truthful baseline, P0)

**Existing code anchors:** `docs/STATUS_AT_HEAD.md`, `tools/status_at_head.py`, `research/results/MANIFEST.json`, `.github/workflows/model-attacks.yml`

- [ ] **W01-01 [P0]** Pin `70e34c870d387cb5de8ba0bbdda0320cf3574d6c` as the starting baseline; record clean tree, Python, SQLite, OS, installed optional packages and exact dependencies.  
  **Acceptance:** Baseline manifest round-trips deterministically and does not call remote services.

- [ ] **W01-02 [P0]** Create an immutable benchmark inventory mapping every claimed result to source commit, dataset digest, generator revision, evaluator digest, prompt digest and model digest when applicable.  
  **Acceptance:** Every promoted result resolves all required commitments; historical incomplete results retain `LEGACY_UNVERIFIED`.

- [ ] **W01-03 [P0]** Reconcile source version 0.19.0 and generated status with README, agent-outcome docs, deployment chart and release checklist without rewriting historical releases.  
  **Acceptance:** CI raises an error when current-state descriptions disagree; historical artifacts are left unchanged.

- [ ] **W01-04 [P0]** Separate main CI, optional model-attacks, synthetic gates and real-agent gates in the release-evidence matrix.  
  **Acceptance:** A 35-job green CI can never be rendered as real-agent or model-attack PASS.

- [ ] **W01-05 [P0]** Diagnose the Nov 16 model-attacks run `43848470357` using workflow metadata and reproducible local invocation; retain `CAUSE_UNVERIFIED` if logs cannot be recovered.  
  **Acceptance:** New evidence reports actual failure class, environment and failing invariant, not a guessed vulnerability.

- [ ] **W01-06 [P0]** Make the weekly model-attack stage produce local evidence and content-safe artifacts even when the model runtime is unavailable.  
  **Acceptance:** Missing runtime yields `MODEL_NOT_AVAILABLE` or `NOT_RUN`, never a fake success; actual invariant failure yields FAIL.

- [ ] **W01-07 [P0]** Build a single outcome-evidence status vocabulary: `NOT_RUN`, `BLOCKED`, `SCRIPTED_PASS`, `LOCAL_MODEL_PASS`, `CONFIRMATORY_SUPPORTED`, `FAILED`, `INCONCLUSIVE`.  
  **Acceptance:** Every gate and dashboard reflects exact status, target SHA and evidence type.

- [ ] **W01-08 [P0]** Separate past retrospective evidence from same-commit reproduction; never combine metrics from distinct populations by filename.  
  **Acceptance:** Validator refuses unpaired comparison unless task IDs, generator and outcome units match.

- [ ] **W01-09 [P0]** Add a source-to-claim scanner for `README.md`, docs and release summaries with an evidence-link allowlist.  
  **Acceptance:** Unsupported numeric claims fail local documentation qualification.

- [ ] **W01-10 [P0]** Produce `research/results/agent-outcomes/baseline-70e34c8/BASELINE.md` and machine-readable manifest.  
  **Acceptance:** Document contains known results, known failures, NOT_RUNs and non-extrapolation warnings, each with repository path.


### 02. Consolidate the three experimental outcome packages — W02 (1 · Canonical architecture, P0)

**Existing code anchors:** `src/memory_fabric/agent_outcomes/`, `src/memory_fabric/outcome_protocol/`, `src/memory_fabric/outcome_typed/`

- [ ] **W02-01 [P0]** Inventory and diff public classes, enums, schemas, evaluator boundaries, error vocabularies and recovery semantics across all three packages.  
  **Acceptance:** A generated mapping lists identical, conflicting, incompatible and missing interfaces.

- [ ] **W02-02 [P0]** Write an ADR choosing a single canonical outcome-runtime package (evaluate `outcome_typed` first; document reasons) while keeping existing stable SDK APIs intact.  
  **Acceptance:** Architecture decision identifies ownership for every runtime responsibility and no two canonical definitions.

- [ ] **W02-03 [P0]** Implement versioned translations from both legacy outcome packages to canonical observations, steps and result records.  
  **Acceptance:** Round-trip tests preserve all representable fields or return explicit incompatibility errors.

- [ ] **W02-04 [P0]** Consolidate `AgentObservation`, `AgentStep`, `RecoveryEpisode`, `RuntimeResult` and `FailureCode` into one canonical schema namespace.  
  **Acceptance:** Schema parity tests reject unknown security metadata, duplicate JSON keys and object-type confusions.

- [ ] **W02-05 [P0]** Unify canonical ID, timestamp, content digest, evidence version and actor identity semantics.  
  **Acceptance:** No mismatched identity/version may be reinterpreted silently during migration.

- [ ] **W02-06 [P0]** Keep evaluator-only objects and capabilities out of actor-facing imports and serialization by default.  
  **Acceptance:** Adversarial tests cannot pass evaluator truth through public constructor or tool-output fields.

- [ ] **W02-07 [P0]** Build a legacy call-site inventory for examples, benchmarks, CLI, adapters, documentation and tests.  
  **Acceptance:** Every import reference is either migrated or explicitly grandfathered with a sunset date.

- [ ] **W02-08 [P0]** Run differential traces through all three pre-migration packages and the canonical implementation.  
  **Acceptance:** Equivalent supported scenarios yield identical action-gate decisions and terminal truth; differences are reviewed and logged.

- [ ] **W02-09 [P0]** Deprecate redundant package facades without deleting historical research importability until evidence is migrated.  
  **Acceptance:** Historical benchmark scripts still execute or return an explicit compatibility error with migration guidance.

- [ ] **W02-10 [P0]** Add one package-surface gate preventing new outcome logic outside the canonical implementation.  
  **Acceptance:** CI detects reintroduced duplicate classes or a new third runtime copy.


### 03. One genuine end-to-end agent execution loop — W03 (1 · Canonical architecture, P0)

**Existing code anchors:** `src/memory_fabric/outcome_typed/runtime.py`, `src/memory_fabric/agent_api.py`, `benchmarks/outcome_agents.py`

- [ ] **W03-01 [P0]** Formalize the episode state machine `OBSERVE→RETRIEVE→PLAN→VERIFY→EXECUTE/RECOVER→TERMINAL` with bounded transitions.  
  **Acceptance:** A transition table and property tests exclude cycles without consumed budget.

- [ ] **W03-02 [P0]** Give every agent a task envelope with objective, public context, allowed tools, resource ceiling and stop conditions; exclude oracle labels.  
  **Acceptance:** Actor receives only the public fields under serialization tests.

- [ ] **W03-03 [P0]** Implement one typed decision invocation interface callable by scripted agents or local model adapters.  
  **Acceptance:** Both backends exercise identical host/runtime logic and emit identical step-schema versions.

- [ ] **W03-04 [P0]** Add a uniform tool registry with declarative argument schemas, permissions, idempotency and audit policy.  
  **Acceptance:** Undeclared tools and malformed requests are rejected before callback invocation.

- [ ] **W03-05 [P0]** Ensure tool outputs become a validated new observation; do not pass raw host exceptions or evaluator diagnostics into prompts.  
  **Acceptance:** Injection fixture cannot smuggle hidden truth or authority using tool output.

- [ ] **W03-06 [P0]** Bind proposal to task ID, actor ID, memory IDs, exact versions, objective ID and planned parameters.  
  **Acceptance:** Reordering/changing any field invalidates proposal commitment.

- [ ] **W03-07 [P0]** Make retries, max steps, max tool calls, max context and max wall time shared across a complete episode rather than individual subloops.  
  **Acceptance:** Budget-exhaustion test stops all roles and reports one terminal reason.

- [ ] **W03-08 [P0]** Implement explicit `COMPLETED`, `SAFE_ABSTAINED`, `FAILED`, `UNDECIDABLE`, `UNSAFE_EXECUTED` terminal states.  
  **Acceptance:** Every scheduled task produces exactly one terminal status with evaluator-only grading.

- [ ] **W03-09 [P0]** Add deterministic replayable actor-visible trace with stable event IDs, no raw secrets and reason-code taxonomy.  
  **Acceptance:** Replay digest is invariant under equivalent structured JSON and changes after event tampering.

- [ ] **W03-10 [P0]** Provide a single fully scripted 3-role executable that starts from a blank Memory Fabric store and ends with terminal evaluator receipt.  
  **Acceptance:** One local command runs observer, planner and executor without network or extra packages.


### 04. Independent outcomes and hidden-world evaluation — W04 (1 · Canonical architecture, P0)

**Existing code anchors:** `benchmarks/outcome_worlds.py`, `benchmarks/outcome_worlds_typed.py`, `src/memory_fabric/outcome_typed/outcomes.py`

- [ ] **W04-01 [P0]** Specify evaluator-owned `WorldState`, task legality, hidden ground truth and terminal objective separately from agent observations.  
  **Acceptance:** Actor object graph does not include evaluator capability, truth digest or mutable state references.

- [ ] **W04-02 [P0]** Make evaluator state reproducible via canonical serialization, seed, generator version and event sequence.  
  **Acceptance:** Independent re-instantiation yields byte-identical state digest and expected effect sequence.

- [ ] **W04-03 [P0]** Implement a separately coded terminal checker rather than trusting actor-reported success or replay certificate.  
  **Acceptance:** Mutated agent result cannot increase success without independently observed effect.

- [ ] **W04-04 [P0]** Distinguish action attempted, action authorized, action executed, state mutation observed and desired terminal state reached.  
  **Acceptance:** Fixtures with each missing stage score correctly and do not collapse into one flag.

- [ ] **W04-05 [P0]** Prevent task completion by always-abstain, always-approve or oracle-peeking negative control policies.  
  **Acceptance:** At least one task family defeats each negative control for nontrivial reasons.

- [ ] **W04-06 [P0]** Reject evaluator labels hidden in memory metadata, request kwargs, tool outputs and diagnostic exceptions.  
  **Acceptance:** Static and dynamic leakage tests fail on every deliberate injected oracle field.

- [ ] **W04-07 [P0]** Track world epoch and reconcile correction-after-plan races, including correction after verification but before execution.  
  **Acceptance:** Old proposal produces zero effects and fresh authorization is required.

- [ ] **W04-08 [P0]** Keep a transcript of independent evaluator transitions and effect receipts outside actor-visible trace.  
  **Acceptance:** Content-safe audit can verify final outcome without exposing evaluator secrets to the agent.

- [ ] **W04-09 [P0]** Model partial observability explicitly: evidence missing, delayed, duplicated, contradictory or inaccessible.  
  **Acceptance:** Task generator verifies agent observation is a projection, not direct truth object.

- [ ] **W04-10 [P0]** Build a fixture-integrity proof that generated task answer is not trivially encoded in ID, template order, seed or tool name.  
  **Acceptance:** Leakage probes and label-shuffling controls fail if the benchmark is trivially solvable.


### 05. Design broader, hard-to-game synthetic agent worlds — W05 (2 · Outcome usefulness, P0)

**Existing code anchors:** `benchmarks/outcome_worlds.py`, `benchmarks/outcome_worlds_typed.py`, `experiments/teamworld.py`

- [ ] **W05-01 [P0]** Expand correction-after-plan into independent source, missing source, delayed correction and actually irrecoverable cases.  
  **Acceptance:** Distinct world-family IDs and known legal terminals; simple retry cannot solve all families.

- [ ] **W05-02 [P0]** Construct battery-diagnosis worlds with simultaneous sensor drift and genuine overheating; never assume mutually exclusive diagnoses.  
  **Acceptance:** Oracle supports multiple coexisting causes and no unsupported physical-causality claim.

- [ ] **W05-03 [P0]** Construct maintenance workflows requiring ordered prerequisites, permission checks and final effect receipt.  
  **Acceptance:** Skipping prerequisite always fails evaluation even if the answer text looks correct.

- [ ] **W05-04 [P0]** Construct incident response worlds with stale runbook, new incident alert, rollback and recovery after partial tool failure.  
  **Acceptance:** Plan and legal-action sets change by epoch; stale requests have zero side effect.

- [ ] **W05-05 [P0]** Construct code/dependency repair worlds with allowlisted file replacement and finite deterministic checker, no arbitrary code execution.  
  **Acceptance:** Hidden test set inaccessible to actor; only supported patch grammar and outputs.

- [ ] **W05-06 [P0]** Construct multi-agent copied-rumor worlds where 20 copies of one root remain one corroborating source.  
  **Acceptance:** Provenance clusters count independence correctly and preserve minority high-quality evidence.

- [ ] **W05-07 [P0]** Construct temporal contradiction worlds where claims valid at different times must not be merged as a timeless contradiction.  
  **Acceptance:** Correct factual answer and valid action differ by valid time and known time.

- [ ] **W05-08 [P0]** Construct permission-aware worlds with legitimately inaccessible evidence to test justified abstention.  
  **Acceptance:** False-withholding denominator excludes inaccessible truth and unauthorized sources.

- [ ] **W05-09 [P0]** Construct multi-hop tasks whose answer depends on at least two legitimate records and whose available clue sequence changes over time.  
  **Acceptance:** Single-record shortcut and lexical exact-match negative controls fail.

- [ ] **W05-10 [P0]** Create seed-controlled difficulty tiers and world-family grouping to prevent split leakage through near-identical templates.  
  **Acceptance:** Group/fingerprint leakage detector enforces train/dev/heldout disjointness and emits dataset digest.


### 06. Evidence diagnosis before refusal — W06 (2 · Outcome usefulness, P0)

**Existing code anchors:** `src/memory_fabric/outcome_typed/eligibility.py`, `src/memory_fabric/answerability.py`, `src/memory_fabric/dependence.py`

- [ ] **W06-01 [P0]** Normalize failure reasons into retrieval miss, no evidence, withdrawn, superseded, contested, untrusted, no permission, stale lease and malformed assertion.  
  **Acceptance:** Each case maps to a distinct typed code without conflating relevance and authority.

- [ ] **W06-02 [P0]** Expose separately whether a needed fact exists, was retrieved, is currently authorized and actually answers the task.  
  **Acceptance:** Evaluator receives denominators; actor receives only accessible diagnostic fields.

- [ ] **W06-03 [P0]** Split absence from inaccessibility using current session authorization; never report the existence of a private source to another tenant.  
  **Acceptance:** Cross-tenant probe receives indistinguishable permitted error surfaces.

- [ ] **W06-04 [P0]** Implement targeted re-retrieval for equivalent identifiers and alternate phrasing within current tenant and scope.  
  **Acceptance:** Recall tests recover permitted known fact without wildcard exposure or widened grants.

- [ ] **W06-05 [P0]** Implement time-aware stale detection using exact evidence versions and event-log known_at/valid_at constraints.  
  **Acceptance:** Withdrawn data never revives via historical read or time-travel query.

- [ ] **W06-06 [P0]** Detect contradictory claims with independent source roots and preserve disagreement instead of naive majority vote.  
  **Acceptance:** Copy amplification never raises confidence; evaluator tracks false-corroboration.

- [ ] **W06-07 [P0]** Create a proof-carrying evidence-availability result with supporting current record IDs, versions and authorization timestamps.  
  **Acceptance:** Result is advisory and cannot be substituted for certificate or grant.

- [ ] **W06-08 [P0]** Implement structured answerability that separately reports semantic uncertainty, factual conflict and missing prerequisites.  
  **Acceptance:** Unsupported paraphrases report uncertainty instead of fabricate positive answerability.

- [ ] **W06-09 [P0]** Add evidence search budgets and fallback ordering `exact→lexical→hybrid-if-qualified→ask/abstain` with transparent costs.  
  **Acceptance:** Budgeted fallback cannot bypass filters or alter evaluation task budget.

- [ ] **W06-10 [P0]** Benchmark diagnosis accuracy against a hidden evaluator oracle using false-denial/false-allow matrices.  
  **Acceptance:** Emit per-family confusion matrices and no release if guard-sensitive false-allow increases.


### 07. Safe recovery orchestration, not blanket refusal — W07 (2 · Outcome usefulness, P0)

**Existing code anchors:** `src/memory_fabric/outcome_typed/recovery.py`, `src/memory_fabric/outcome_typed/runtime.py`, `examples/outcome_recovery_demo_typed.py`

- [ ] **W07-01 [P0]** Define typed recovery actions `RE_RETRIEVE`, `CHECK_VERSION`, `FIND_INDEPENDENT_SOURCE`, `REQUEST_OBSERVATION`, `REPLAN`, `ABSTAIN`.  
  **Acceptance:** Every action is in a closed first-party catalog and is non-authorizing.

- [ ] **W07-02 [P0]** Require an evidence diagnosis and task eligibility assessment before initiating recovery.  
  **Acceptance:** No eligible evidence or permission yields safe abstention, not endless retry.

- [ ] **W07-03 [P0]** Tie recovery state to task ID, observed state fingerprint, last failure code and evidence version set.  
  **Acceptance:** Recovery progress cannot be transferred to another task or stale state.

- [ ] **W07-04 [P0]** Enforce bounded distinct-state progress, retry ceilings, tool budgets and global recovery deadline.  
  **Acceptance:** Repeated identical observations terminate rather than loop.

- [ ] **W07-05 [P0]** Prefer exact alternate source and correction propagation before expensive counterfactual replay.  
  **Acceptance:** Scheduler has tests showing lower cost than unconditional CDM on simple recoverable cases.

- [ ] **W07-06 [P0]** Allow a recovery plan to request a new observation but not create a new authority, change permission or mark evidence valid.  
  **Acceptance:** Mutation tests reject policy bypass via recovery output.

- [ ] **W07-07 [P0]** Use evidence-version-aware replanning when relevant conditions change; preserve unaffected parts of a plan.  
  **Acceptance:** Dependency-based partial replan matches oracle and reduces unnecessary work on fixtures.

- [ ] **W07-08 [P0]** Handle missing observation, contradictory observation, and fresh observation arriving during recovery.  
  **Acceptance:** Trace ends in correct new plan or explicit reasoned abstention.

- [ ] **W07-09 [P0]** Implement operator-readable explanations: what blocked, what was retried, what changed, what remains uncertain.  
  **Acceptance:** Explanation references only authorized evidence and correct provenance.

- [ ] **W07-10 [P0]** Run all recovery worlds against current governed and pooled+recovery baselines with matched budgets.  
  **Acceptance:** Per-case benefit attributable to governance is separately reported from benefit attributable to recovery itself.


### 08. Action-time safety, idempotency and terminal effects — W08 (2 · Outcome usefulness, P0)

**Existing code anchors:** `src/memory_fabric/actions.py`, `src/memory_fabric/actions_typed.py`, `tests/test_action_fence.py`

- [ ] **W08-01 [P0]** Require fresh current evidence certificate and exact-action grant immediately before every protected effect.  
  **Acceptance:** Withdrawn or moved evidence refuses with no external callback.

- [ ] **W08-02 [P0]** Bind effect request digest to agent, task, tool, target, arguments, tenant, source versions and idempotency key.  
  **Acceptance:** Reusing key for changed payload always fails closed.

- [ ] **W08-03 [P0]** Preserve same-transaction action fence for event-log state and durable action attempt receipt.  
  **Acceptance:** Concurrent correction either occurs before authorization or after completed fenced effect, never ambiguously.

- [ ] **W08-04 [P0]** Model crash windows before effect, during effect and after effect before acknowledgment.  
  **Acceptance:** Recovery returns `UNKNOWN_EFFECT` when it cannot prove outcome, not an automatic retry.

- [ ] **W08-05 [P0]** Implement explicit `reconcile_unknown_effect` contract requiring independently observed effect status.  
  **Acceptance:** Reconciliation cannot reexecute without fresh permission and effect-specific idempotency.

- [ ] **W08-06 [P0]** Use a simulated effect executor that is deterministic, transactional over evaluator world state and never touches real devices.  
  **Acceptance:** Every benchmark effect has canonical before/after digests.

- [ ] **W08-07 [P0]** Verify state transition, not merely tool success status, before scoring completion.  
  **Acceptance:** Tool returning success with unchanged world fails terminal goal.

- [ ] **W08-08 [P0]** Add negative tests for replay-certificate passed as authorization grant.  
  **Acceptance:** CDM receipts remain non-authorizing in all SDK/MCP/UTCP paths.

- [ ] **W08-09 [P0]** Test same request through SDK, MCP, UTCP and Code Mode grant boundaries under equivalent input.  
  **Acceptance:** All paths agree on allow/deny and denial reason without loss of security fields.

- [ ] **W08-10 [P0]** Add a world-state invariant check after every effect in simulated runs.  
  **Acceptance:** Any unauthorized or out-of-order mutation stops and records unsafe attempt/execution separately.


### 09. Counterfactual Decision Memory used only where beneficial — W09 (3 · Conditional intelligence, P0)

**Existing code anchors:** `src/memory_fabric/causal_replay/`, `src/memory_fabric/outcome_typed/runtime.py`, `src/memory_fabric/dependence.py`

- [ ] **W09-01 [P0]** Build a dependence-first CDM dispatcher that skips replay for unaffected decisions and missing material alternatives.  
  **Acceptance:** Skip reasons are explicit and no model call occurs for independent decisions.

- [ ] **W09-02 [P0]** Separate factual historical reconstruction, hypothetical intervention and actual authorized replanning into different request/response types.  
  **Acceptance:** Counterfactual never mutates the production event log or executes effects.

- [ ] **W09-03 [P0]** Require complete trace, pinned policy/runtime/evidence digests and still-valid capture authorization before exact replay.  
  **Acceptance:** Missing model, nondeterminism or incomplete trace yields `NON_REPLAYABLE`.

- [ ] **W09-04 [P0]** Bound candidate interventions to authorized observed evidence and predefined finite operators.  
  **Acceptance:** Cross-tenant and erased evidence cannot be probed or restored via counterfactual request.

- [ ] **W09-05 [P0]** Use exact dependence as the no-cost baseline; compare recency, LOO, sampled Shapley and budgeted replay without claiming they are automatically beneficial.  
  **Acceptance:** Same task, budget and measured cost in all comparator arms.

- [ ] **W09-06 [P0]** Implement a replay-eligibility estimator trained/validated only on development worlds with pre-replay features.  
  **Acceptance:** The selector has an abstain option and cannot read future outcomes or hidden labels.

- [ ] **W09-07 [P0]** Run replay in named, restricted local worker with finite event/node/cpu/wall/output budgets and declared platform isolation gap.  
  **Acceptance:** Budget violation terminates worker and cannot issue action authority.

- [ ] **W09-08 [P0]** Verify counterfactual certificate through a distinct code path and bind exact observations, updates and decision fingerprints.  
  **Acceptance:** Tampered or incomplete certificate is rejected by independent verifier.

- [ ] **W09-09 [P0]** Emit a CDM utility ledger separating policy flip, observed task completion difference, safety difference and replay cost.  
  **Acceptance:** A policy flip alone never earns positive utility or promotion status.

- [ ] **W09-10 [P0]** Keep A6 optional behind A5 promotion and an incremental held-out gate; otherwise use CDM only as explanatory advisory.  
  **Acceptance:** A6 cannot promote if A5 failed/not-ready or if A6–A5 net benefit fails frozen threshold.


### 10. Multi-agent knowledge and coordination under changing truth — W10 (3 · Conditional intelligence, P1)

**Existing code anchors:** `experiments/teamworld.py`, `experiments/live_multi_agent.py`, `src/memory_fabric/federation.py`

- [ ] **W10-01 [P1]** Implement canonical observer, planner, executor and independent evaluator roles with explicit permissions.  
  **Acceptance:** No role shares evaluator capability; action execution restricted to executor grant.

- [ ] **W10-02 [P1]** Record source root for every observed, copied, summarized or federated claim.  
  **Acceptance:** N copies of one origin count as one corroborating root.

- [ ] **W10-03 [P1]** Preserve contested minority views and defer consensus until independent verification or legitimate evidence resolution.  
  **Acceptance:** False-majority world does not trigger unwarranted decisive action.

- [ ] **W10-04 [P1]** Propagate correction/retraction to every known downstream recipient with idempotent outbox and acknowledgments.  
  **Acceptance:** Delayed, reordered and duplicate notices converge on same current safe state.

- [ ] **W10-05 [P1]** Model agent disconnects and partial partitions; do not trust remote freshness without valid signed lease.  
  **Acceptance:** Protected remote-dependent effects fail closed after lease expiry.

- [ ] **W10-06 [P1]** Measure coordinator overhead separately from memory-system task effect.  
  **Acceptance:** Same coordination policy and agent work budgets across matched arms.

- [ ] **W10-07 [P1]** Add task delegation and ownership transition receipts without broadening principal permission.  
  **Acceptance:** A delegated task does not transfer credentials or grants.

- [ ] **W10-08 [P1]** Introduce coordination-repair states for missing agent observation, conflicting reports and timeout.  
  **Acceptance:** Every unresolved branch ends with explicit retry or abstention reason.

- [ ] **W10-09 [P1]** Validate alternate evidence in a second agent's store only through current federation and authorization rules.  
  **Acceptance:** No covert cross-tenant search or history leakage.

- [ ] **W10-10 [P1]** Benchmark 3-, 5-, 10-, 25- and 50-agent runs with shared task schedules and independent task-cluster uncertainty.  
  **Acceptance:** Results report unique tasks and clusters, not only inflated agent-task attempts.


### 11. Fair baselines and resource parity — W11 (3 · Conditional intelligence, P0)

**Existing code anchors:** `benchmarks/outcome_matched_arms.py`, `benchmarks/outcome_matched_arms_typed.py`, `benchmarks/matched_agent_arms.py`

- [ ] **W11-01 [P0]** Register A0 no memory; A1 private; A2 pooled; A3 pooled+recovery; A4 governed; A5 governed+recovery; A6 A5+CDM; A7 evaluator oracle.  
  **Acceptance:** A7 never executes actor code or appears in a treatment contrast.

- [ ] **W11-02 [P0]** Implement all actor arms through the same runtime, world, tools, evaluator, task order and agent weights.  
  **Acceptance:** Pairing validator compares full task IDs, world digests and agent/model identifiers.

- [ ] **W11-03 [P0]** Make A3's recovery affordances as capable as A5's, differing only in governance features.  
  **Acceptance:** A5–A3 isolates governance rather than recovery capability or prompt length.

- [ ] **W11-04 [P0]** Make A4 use the same retrieval and budgets as A5, differing only in recovery enablement.  
  **Acceptance:** A5–A4 tests recovery without changing memory supply.

- [ ] **W11-05 [P0]** Add recency, lexical, fixed-top-k, full-context-within-budget and simple summary baselines.  
  **Acceptance:** Baseline implementation is first-party and tool/cost budgets are not secretly inferior.

- [ ] **W11-06 [P0]** Measure prompt framing as a factorial negative control: neutral vs caution with pooled/governed memory.  
  **Acceptance:** Results quantify prompt-text effect separately from governance effect.

- [ ] **W11-07 [P0]** Hold model inference settings, max tokens, context, temperature, tool count and retries fixed within each paired comparison.  
  **Acceptance:** Parity report fails rather than quietly adjusting resource ceilings.

- [ ] **W11-08 [P0]** Use an evaluator-only omniscient oracle with same legal tool constraints to estimate attainable headroom.  
  **Acceptance:** No treatment scores above a legitimate task-level oracle on the same metric; otherwise fixture invalid.

- [ ] **W11-09 [P0]** Add always-abstain, fixed-action and random policy negative controls and record their failures.  
  **Acceptance:** Each strong task family has meaningful oracle headroom beyond trivial controls.

- [ ] **W11-10 [P0]** Publish matched-arm registry and machine-readable parity matrix before frozen runs.  
  **Acceptance:** Missing A6 or mismatched actor arm yields `INCOMPLETE`, not PASS.


### 12. Actual local model agents, no hosted service requirement — W12 (4 · Real-agent testing, P0)

**Existing code anchors:** `src/memory_fabric/adapters/ollama.py`, `benchmarks/outcome_agents.py`, `benchmarks/real_agent_*manifest.json`

- [ ] **W12-01 [P0]** Add preflight to enumerate already installed localhost models and their digests without downloading anything.  
  **Acceptance:** Missing model yields `REAL_AGENT_NOT_RUN` and does not silently substitute a scripted adapter.

- [ ] **W12-02 [P0]** Pin model weights digest, runtime version, quantization, prompt, decoding options, context size and tool schema.  
  **Acceptance:** Every inference record is attributable to one exact reproducible configuration.

- [ ] **W12-03 [P0]** Implement an actor-only local-model interface that receives canonical observation and emits strictly parsed AgentStep JSON.  
  **Acceptance:** Model cannot access evaluator object, grading API or hidden task output.

- [ ] **W12-04 [P0]** Run observer, planner and executor separately through existing authenticated Memory Fabric sessions.  
  **Acceptance:** Each role has least-privilege tools and one verified log of decisions.

- [ ] **W12-05 [P0]** Run a local-model multi-step correction-after-plan scenario including re-retrieval, replan and terminal gated effect.  
  **Acceptance:** Inference-backed steps and new authorized evidence are present; not only a scripted state machine.

- [ ] **W12-06 [P0]** Handle malformed JSON, hallucinated evidence IDs, invalid tool names, timeout, context overflow and OOM as distinct incomplete outcomes.  
  **Acceptance:** No hidden scripted fallback inflates completion numbers.

- [ ] **W12-07 [P0]** Record token count, wall time, cold/warm load, retry count, model failures and per-role call budgets.  
  **Acceptance:** Resource cost included in paired final report with missing costs marked unknown.

- [ ] **W12-08 [P0]** Run at least two distinct pinned local model sizes or versions when already available and feasible, otherwise explicitly scope inference transfer.  
  **Acceptance:** Robustness report never pretends one 1.5B smoke generalizes to all agents.

- [ ] **W12-09 [P0]** Compare identical learned-agent policies across A3/A4/A5/A6; only memory affordance varies.  
  **Acceptance:** Model prompts are normalized and differences enumerated in paired manifest.

- [ ] **W12-10 [P0]** Add an exact-SHA offline real-agent gate that requires newly executed inference and qualifying task outcome rows, not historical smoke JSON.  
  **Acceptance:** Gate emits `LOCAL_MODEL_EVIDENCE_AVAILABLE` only when same candidate ran substantive episodes.


### 13. Strict evaluator metrics and operator-relevant benefits — W13 (4 · Real-agent testing, P0)

**Existing code anchors:** `src/memory_fabric/outcome_typed/outcomes.py`, `benchmarks/outcome_report_typed.py`, `memeval/`

- [ ] **W13-01 [P0]** Define completion as terminal-world objective satisfied by authorized observed effects; score every scheduled eligible task.  
  **Acceptance:** Agent text assertions or accepted proposal alone cannot score a completion.

- [ ] **W13-02 [P0]** Define false withholding only when evaluator confirms current accessible authorized evidence exists and task is answerable.  
  **Acceptance:** Hidden inaccessible evidence is excluded and denominator is recorded separately.

- [ ] **W13-03 [P0]** Separate unsafe proposals, unsafe attempted actions, unsafe executed actions and stale executed effects.  
  **Acceptance:** Report all numerators/denominators and event-level provenance.

- [ ] **W13-04 [P0]** Compute recovery rate over correction-eligible cases and report irrecoverable-case abstention as a separate success dimension.  
  **Acceptance:** No denominator of zero yields fabricated 100% recovery.

- [ ] **W13-05 [P0]** Measure correction-to-verified-completion time from same monotonic domain or mark `NOT_RECORDED`.  
  **Acceptance:** End-to-end latency is never relabeled as recovery latency.

- [ ] **W13-06 [P0]** Measure unnecessary re-evaluation, false abstention, correct refusal, hallucinated evidence use and operator intervention count.  
  **Acceptance:** Each metric includes explicit eligibility criteria and independent oracle label.

- [ ] **W13-07 [P0]** Account for token counts, model calls, replay CPU, peak memory, storage bytes and worker time per arm.  
  **Acceptance:** Resource Pareto comparison only uses actually measured common dimensions.

- [ ] **W13-08 [P0]** Compute per-agent and per-world-family fairness, including minimum-performing agent and high-risk tasks.  
  **Acceptance:** Aggregate gain cannot hide a material worst-agent regression.

- [ ] **W13-09 [P0]** Make all metrics machine-readable with schema version, source SHA, task-set digest, sampling unit and uncertainty.  
  **Acceptance:** A report lacking any required basis is `INVALID` or `NOT_ASSESSABLE`.

- [ ] **W13-10 [P0]** Add plot-free JSON and Markdown scorecards with PASS/HOLD/FAIL decisions derived solely from frozen evaluator outputs.  
  **Acceptance:** Changing display formatting cannot modify inference or promotion decision.


### 14. Preregister and power the real confirmatory study — W14 (4 · Real-agent testing, P0)

**Existing code anchors:** `research/prereg/agent-outcome-confirmatory-v1.json`, `benchmarks/outcome_confirmatory.py`, `memeval/power.py`

- [ ] **W14-01 [P0]** Declare the primary task population and family mixture before seeing confirmatory results.  
  **Acceptance:** No new task family can be cherry-picked into the confirmatory denominator afterward.

- [ ] **W14-02 [P0]** Specify primary contrasts A5–A3 and A5–A4; secondary A6–A5 with registered error control.  
  **Acceptance:** Comparisons cannot be silently replaced by an easier baseline.

- [ ] **W14-03 [P0]** Freeze task IDs, generator commit/digest, prompt templates, model/runtime digest, policy hash and evaluator source digest.  
  **Acceptance:** Preregistration validator rejects any missing or later-edited commitments.

- [ ] **W14-04 [P0]** Estimate statistical power from pilot paired discordance and available oracle headroom.  
  **Acceptance:** `memeval` rejects underpowered or impossible targets; actual n selected before heldout data.

- [ ] **W14-05 [P0]** Choose world seed clusters as independent sampling units; record number of task cases and repeated agent decisions per cluster.  
  **Acceptance:** Reported sample size never treats 50 agents on same task as 50 independent worlds.

- [ ] **W14-06 [P0]** Set stopping rule, rerun handling, inference failure accounting and multiple comparison correction in advance.  
  **Acceptance:** Failed/timeout/incomplete episodes remain in denominator under frozen rule.

- [ ] **W14-07 [P0]** Freeze safety non-inferiority margin, per-family bounds and zero-event binomial upper bound rule.  
  **Acceptance:** Zero observed events cannot be translated into true risk zero.

- [ ] **W14-08 [P0]** Hold development, tune and confirmatory data in disjoint versioned artifacts with explicit hash and leakage checks.  
  **Acceptance:** No seed/template ID overlap or silent relabeling.

- [ ] **W14-09 [P0]** Generate manifest digest and state `FROZEN` only once all dependencies, exact task population and resource caps are present.  
  **Acceptance:** `benchmarks.outcome_confirmatory.validate_manifest` passes without network.

- [ ] **W14-10 [P0]** Ensure changing runtime code after freeze either invalidates candidate comparison or requires explicit documented new confirmatory campaign.  
  **Acceptance:** No threshold tuning on test outcomes, all attempts retained.


### 15. Run negative-control, ablation and confirmatory experiments — W15 (4 · Real-agent testing, P0)

**Existing code anchors:** `benchmarks/outcome_confirmatory_typed.py`, `benchmarks/outcome_selector_ablation.py`, `research/results/agent-outcomes/`

- [ ] **W15-01 [P0]** Run deterministic world generator unit and evaluator mutation tests before any development experiment.  
  **Acceptance:** Malformed truth, oracle leakage and incorrect terminal grader are all caught by tests.

- [ ] **W15-02 [P0]** Run same-case development arms A0–A7 where implemented, including task-family and per-agent breakdown.  
  **Acceptance:** No claim of promotion from development data; missing arms labeled.

- [ ] **W15-03 [P0]** Run a factorial ablation of correction propagation, source independence, retrieval method, recovery, replanning and governance.  
  **Acceptance:** Main effect and interaction are separated; no module is credited with another module's gain.

- [ ] **W15-04 [P0]** Run a CDM ablation `A5` vs `A6` with replay on/off, replay scheduling, skipped independent tasks and cost.  
  **Acceptance:** Incremental decision utility is reported after replay overhead, not raw policy flip count.

- [ ] **W15-05 [P0]** Run an oracle-headroom analysis identifying tasks where A3 is already optimal and no added governance can improve completion.  
  **Acceptance:** Such tasks do not drive unrealistic improvement targets.

- [ ] **W15-06 [P0]** Freeze canonical prompts, models and resource caps after development, then execute paired heldout cases without arm-specific retries.  
  **Acceptance:** All arm outputs, failures and per-case rows persisted content-safely with hashes.

- [ ] **W15-07 [P0]** Compute paired cluster bootstrap interval and exact paired sign test; apply registered Holm correction.  
  **Acceptance:** A5 promotion requires lower confidence bound above frozen material gain and non-inferior safety.

- [ ] **W15-08 [P0]** Evaluate A6 only if A5 passes its prerequisite gate, and use the same paired task population.  
  **Acceptance:** A6 otherwise remains advisory `HOLD` regardless of attractive exploratory score.

- [ ] **W15-09 [P0]** Perform at least one independent generator-family replication, including distribution shifts not seen at development time.  
  **Acceptance:** Report transfer gap, headroom and confidence interval separately.

- [ ] **W15-10 [P0]** Publish all attempts, negative outcomes, inconclusive results, scripts, source digests and evaluator versions.  
  **Acceptance:** No cherry-picking, no deletion of failed registered runs.


### 16. Defend learned agents against contaminated memory and unsafe prompts — W16 (5 · Reliability/security, P0)

**Existing code anchors:** `src/memory_fabric/governance/`, `tests/test_outcome_oracle_isolation_typed.py`, `.github/workflows/model-attacks.yml`

- [ ] **W16-01 [P0]** Enumerate injection points in retrieved memory, summary, federation payload, tool output, model response and recovery diagnosis.  
  **Acceptance:** Threat matrix names attacker, trust boundary, goal, mitigations and tests.

- [ ] **W16-02 [P0]** Add structured poisoning fixtures with copied source, forged independent roots, false tool results, delayed retractions and authority-shaped text.  
  **Acceptance:** At least one failing control exists for each attack family.

- [ ] **W16-03 [P0]** Verify untrusted content never modifies system instructions, evaluator grading, host grants or tool schema.  
  **Acceptance:** Tool invocation traces enforce typed roles; injections produce no unauthorized effect.

- [ ] **W16-04 [P0]** Stress false corroboration across agents and copies, including colluding agents and stale imported versions.  
  **Acceptance:** Independent-root policy resists count amplification on registered fixtures.

- [ ] **W16-05 [P0]** Test model hallucination of certificates, memory IDs, tool names and evidence versions.  
  **Acceptance:** Hallucinated objects cannot become authorized facts or protected actions.

- [ ] **W16-06 [P0]** Test error-channel and timing metadata leakage for cross-tenant evidence probes.  
  **Acceptance:** Visible refusal payloads avoid existence disclosure; residual timing differences documented and throttled.

- [ ] **W16-07 [P0]** Test prompt-injection resistance in actual local models with registered canaries and measured attempted effects.  
  **Acceptance:** No `PASS` without observed model decision and concrete allowed/forbidden effect.

- [ ] **W16-08 [P0]** Make the model-attacks scheduled job reliably package stderr, model digest, workflow failure reason and content-safe output.  
  **Acceptance:** A failure can be classified without recovering ephemeral remote logs.

- [ ] **W16-09 [P0]** Add a regression gate across agent-api, MCP and UTCP for inconsistent authorization results.  
  **Acceptance:** No alternate transport allows an effect refused by canonical host gate.

- [ ] **W16-10 [P0]** Retain every failed attack run and adversarial case; never silently weaken checks or allowlist security-sensitive results to get green CI.  
  **Acceptance:** Changes to allowlists require a reviewed negative test and dated rationale.


### 17. Persistence, recovery, and transactional consistency — W17 (5 · Reliability/security, P1)

**Existing code anchors:** `src/memory_fabric/eventlog.py`, `src/memory_fabric/pgcompat.py`, `src/memory_fabric/outbox.py`, `src/memory_fabric/causal_replay/checkpoints.py`

- [ ] **W17-01 [P1]** Specify durable episode state transitions, event sequence references and canonical task IDs with unique constraints.  
  **Acceptance:** Restart reconstructs last verified state without inventing completed side effects.

- [ ] **W17-02 [P1]** Persist pending action and unknown effect receipts before invoking an external callback in production integration.  
  **Acceptance:** Crash-injection proves every uncertain effect is reconciled, not blindly retried.

- [ ] **W17-03 [P1]** Add versioned migrations for outcome checkpoints, audit metadata and evaluator attachments.  
  **Acceptance:** Upgrade, rollback and replay across supported prior schema versions preserve exact status.

- [ ] **W17-04 [P1]** Create a bounded local job spool with lease, heartbeats, retry budget and dead-letter state using existing storage abstraction.  
  **Acceptance:** Concurrent workers cannot both own a task lease and stale lease cannot authorize effects.

- [ ] **W17-05 [P1]** Separate evaluator artifacts and actor traces at storage and API level, with tenant-bound keys and permissions.  
  **Acceptance:** Cross-session and cross-tenant reads are denied across filesystem and API.

- [ ] **W17-06 [P1]** Test event-log append atomicity and content integrity under disk-full, interrupted flush and reordered process shutdown.  
  **Acceptance:** State replay rejects partial commit and restores integrity chain.

- [ ] **W17-07 [P1]** Benchmark SQLite and optional existing PostgreSQL backend on identical transaction scenarios, without new backend requirement.  
  **Acceptance:** Report throughput, lock waits, retries and data consistency; no unsupported cross-machine claims.

- [ ] **W17-08 [P1]** Implement checkpoint invalidation after correction, key erasure, tenant revocation and policy version change.  
  **Acceptance:** Obsolete checkpoint never restores private content or authorizes stale action.

- [ ] **W17-09 [P1]** Add deterministic reconciliation workflow for offline peers with pending retractions and conflicting revisions.  
  **Acceptance:** Reordered messages converge or emit explicit unresolved conflict, not a stale allow.

- [ ] **W17-10 [P1]** Provide restore drill that compares event-log digest, content-key availability, outcome receipts and task state.  
  **Acceptance:** Recovery fails closed when encrypted key custody cannot be restored.


### 18. Performance and cost efficiency with honest measurements — W18 (5 · Reliability/security, P1)

**Existing code anchors:** `benchmarks/outcome_parallel.py`, `benchmarks/outcome_matched_arms.py`, `research/results/agent-outcome-contention-2026-11-13.json`

- [ ] **W18-01 [P1]** Build latency breakdown for observation, retrieval, verification, model inference, replanning, CDM replay, commit and effect acknowledgment.  
  **Acceptance:** Per-episode timings sum within clock-error tolerance and no substage is mislabeled as total.

- [ ] **W18-02 [P1]** Repeat 1/2/4/8-worker contention experiments with explicit host metadata, warmup and enough trials for intervals.  
  **Acceptance:** Report the already observed slowdown if it replicates; do not claim more workers automatically help.

- [ ] **W18-03 [P1]** Separate process start time from queue wait, CPU service time, database lock time and network/model time.  
  **Acceptance:** Bottleneck report identifies the top two components per scenario with reproducible samples.

- [ ] **W18-04 [P1]** Implement reuse of safe read-only retrieval results keyed by current policy and exact source version.  
  **Acceptance:** Cache invalidates on revision, revocation, source retraction and tenant identity change.

- [ ] **W18-05 [P1]** Measure cost of always-on vs dependence-triggered CDM, including wasted replays and successful decision flips.  
  **Acceptance:** Budgeted CDM Pareto table includes actual compute costs and net terminal utility.

- [ ] **W18-06 [P1]** Profile event replay at 10k, 100k and 1M synthetic events with bounded memory, snapshots and projection rebuild.  
  **Acceptance:** Time/memory limits stated by machine; no unmeasured scale guarantee.

- [ ] **W18-07 [P1]** Stress 1, 5, 10, 25 and 50 simultaneous agents with real contention and skewed traffic.  
  **Acceptance:** Tail latency, starvation, fairness and task completion measured per tenant/agent.

- [ ] **W18-08 [P1]** Implement bounded backpressure, queue-depth caps and graceful overload abstention for model and replay workers.  
  **Acceptance:** Overload does not degrade action-gate correctness or leak requests.

- [ ] **W18-09 [P1]** Study batching of read-only retrieval and proof verification without coalescing different principals' permissions.  
  **Acceptance:** Same-tenant and cross-tenant concurrency tests preserve authorization.

- [ ] **W18-10 [P1]** Publish a measured resource operating envelope for a 16GB laptop and a modest server; distinguish scripted from local-model figures.  
  **Acceptance:** Commands are reproducible and never infer model capability from CPU-only tests.


### 19. Governance privacy, consent, erasure, operator trust — W19 (5 · Reliability/security, P1)

**Existing code anchors:** `src/memory_fabric/governance/erasure.py`, `src/memory_fabric/identity.py`, `src/memory_fabric/observability/`

- [ ] **W19-01 [P1]** Document security principals for actor, evaluator, operator, integration service and auditor.  
  **Acceptance:** Every endpoint has a least-privilege permission matrix and separate secret custody.

- [ ] **W19-02 [P1]** Enforce current authorization on historical capture, correction impact and all CDM access, not merely time-of-record permission.  
  **Acceptance:** Revoked principal cannot replay or inspect an old authorized capture.

- [ ] **W19-03 [P1]** Define deletion semantics across event-log ciphertext, keys, checkpoint cache, derived summaries, replay certificates and benchmark artifacts.  
  **Acceptance:** Erasure regression removes readable content everywhere in scope and retains only allowed audit metadata.

- [ ] **W19-04 [P1]** Scrub raw prompt content, credentials, PII and unrestricted model output from public logs and operator reports.  
  **Acceptance:** Redaction scanner and negative fixtures pass across every new module.

- [ ] **W19-05 [P1]** Bind all actionable evidence and receipts to canonical tenant and agent session, with no cross-tenant cache coalescing.  
  **Acceptance:** Cross-tenant collision/invalidation tests refuse leak and unauthorized replay.

- [ ] **W19-06 [P1]** Make audit event digests tamper-evident, but label unsigned local reports as such.  
  **Acceptance:** Tamper test fails and UI never calls hashes cryptographic attestation or independent certification.

- [ ] **W19-07 [P1]** Provide a safe escalation for human review of contested or ambiguous evidence without automatically elevating sources.  
  **Acceptance:** Approval requires separate privilege and produces new signed/audited decision evidence.

- [ ] **W19-08 [P1]** Track root-cause labels as simulator-level or agent-policy-level only; disallow unverified physical causality claims.  
  **Acceptance:** Report schema has explicit `physical_causality: NOT_ESTABLISHED` unless separately supported.

- [ ] **W19-09 [P1]** Audit credentials, encryption profiles, key rotation and missing-key behavior in new outcome storage.  
  **Acceptance:** Production profile fails closed when required supported encryption is unavailable.

- [ ] **W19-10 [P1]** Test operator controls against malicious actor trying to self-grade, reclassify failure or edit outcomes.  
  **Acceptance:** Operator interventions are separately authenticated and cannot falsify historic evaluator receipt.


### 20. Developer-facing APIs, SDK and usability — W20 (6 · Productization, P1)

**Existing code anchors:** `src/memory_fabric/sdk.py`, `src/memory_fabric/agent_api.py`, `examples/outcome_recovery_demo.py`

- [ ] **W20-01 [P1]** Define one public opt-in high-level API `run_task`, `inspect_failure`, `resume_recovery`, `get_evidence`, `get_outcome` using existing service sessions.  
  **Acceptance:** API has complete typed schemas and end-to-end contract tests.

- [ ] **W20-02 [P1]** Provide an easy local `Observer→Planner→Executor` example with no hosted services or downloaded data.  
  **Acceptance:** Fresh install runs deterministic end-to-end demo from README commands.

- [ ] **W20-03 [P1]** Keep actual protected actions behind a host-supplied ActionGate integration, never a generated callback from model text.  
  **Acceptance:** Attempt to pass arbitrary Python executable through request schema is refused.

- [ ] **W20-04 [P1]** Expose structured reason codes and recommended next permitted steps for false abstention and missing evidence.  
  **Acceptance:** A developer can distinguish retrieval, permissions, stale data and tool failures.

- [ ] **W20-05 [P1]** Provide clear API errors for `NOT_RUN`, `NON_REPLAYABLE`, `BLOCKED`, `UNDECIDABLE` and `BUDGET_EXCEEDED`.  
  **Acceptance:** No generic success response for incomplete tasks.

- [ ] **W20-06 [P1]** Implement compatibility adapters for direct SDK, MCP and UTCP with identical canonical task/result semantics.  
  **Acceptance:** Contract parity harness compares observable decisions and safe effects.

- [ ] **W20-07 [P1]** Document tenant and authorization setup without hard-coded production credentials or permissive defaults.  
  **Acceptance:** Fresh-machine examples use ephemeral local credentials and deny unauthorized action.

- [ ] **W20-08 [P1]** Provide deterministic offline fixtures and a fake local-model server for integration tests; distinguish fake from real inference.  
  **Acceptance:** Tests cannot accidentally count mock responses as a model benchmark.

- [ ] **W20-09 [P1]** Add versioned OpenAPI-style schema files or stdlib JSON schema plus error tables, without new runtime package requirement.  
  **Acceptance:** Schema validation rejects unknown authority-bearing fields and exposes examples.

- [ ] **W20-10 [P1]** Build a developer-oriented troubleshooting command showing current runtime, agent visibility, recovery feature flag, model availability and gate evidence.  
  **Acceptance:** Status output is content-safe, accurate and takes no network dependency.


### 21. Control Center and operator outcome observability — W21 (6 · Productization, P1)

**Existing code anchors:** `src/memory_fabric/observability/`, `src/memory_fabric/observability/static/`, `docs/AGENT_OUTCOME_EVALUATION.md`

- [ ] **W21-01 [P1]** Add a task-level outcome summary for completion, failures, false withholding, unsafe attempts and resource use.  
  **Acceptance:** UI fetches only authorized aggregates from read-only observability surface.

- [ ] **W21-02 [P1]** Add a decision timeline from observation through retrieval, plan, correction, replan, certificate and effect.  
  **Acceptance:** Every step references permitted audit record and time; no hidden truth leak.

- [ ] **W21-03 [P1]** Add evidence lineage view marking source root, copies, exact version, trust state and retraction status.  
  **Acceptance:** Copies cannot be mistaken for independent endorsements.

- [ ] **W21-04 [P1]** Add blocked-task diagnosis panel with specific current allowed next step and reasoned abstention.  
  **Acceptance:** Operators can distinguish safe abstain from incomplete work and policy denial.

- [ ] **W21-05 [P1]** Add comparison view of A3/A4/A5/A6 with uncertainty intervals, task-family splits and cost, showing NOT_RUN distinctly.  
  **Acceptance:** Missing metrics render `NOT_MEASURED`, never zero.

- [ ] **W21-06 [P1]** Add replay explanation view for CDM policy flip vs actual observed benefit and explain non-replayability.  
  **Acceptance:** UI refuses to label hypothetical replay as real-world verified cause.

- [ ] **W21-07 [P1]** Add source-SHA, model/runtime digest, exact benchmark population and seed disclosure per graph.  
  **Acceptance:** No model-free result can be rendered with a `real-agent` badge.

- [ ] **W21-08 [P1]** Add budget/exhaustion dashboards for queue depth, replay cost and retry storms without storing raw sensitive prompts.  
  **Acceptance:** Public endpoint includes no credential, plaintext memory or oracle metadata.

- [ ] **W21-09 [P1]** Add red-team/operator scenario walkthrough including contaminated evidence, revoked principal and erased memory.  
  **Acceptance:** Negative UI tests verify no leakage or unsafe `retry` control.

- [ ] **W21-10 [P1]** Ensure operator controls are view-only unless routed through explicit authenticated governance endpoint.  
  **Acceptance:** Observability server cannot mutate evidence, policy or action authorization.


### 22. Research novelty, precise scientific claims and negative results — W22 (6 · Productization, P1)

**Existing code anchors:** `RESEARCH.md`, `research/SCORECARD.md`, `research/prereg/`, `memeval/`

- [ ] **W22-01 [P1]** Define testable thesis `governed correction+recovery improves safe terminal utility over pooled+recovery at equal budget`.  
  **Acceptance:** Primary hypothesis names source of added utility and measurable rejection condition.

- [ ] **W22-02 [P1]** Treat exact dependence, versioned correction and replay certificates as existing baselines, not novel by declaration.  
  **Acceptance:** Related-work matrix records feature overlap and which mechanism is actually different.

- [ ] **W22-03 [P1]** Propose selective counterfactual recovery as a candidate mechanism only when it saves cost and improves terminal decisions.  
  **Acceptance:** Preregister A6–A5 net-utility test before evaluation.

- [ ] **W22-04 [P1]** Quantify where governance hurts, where it helps and where recovery is enough without governance.  
  **Acceptance:** Error taxonomy includes false withholding and no-headroom categories.

- [ ] **W22-05 [P1]** Report null or negative effects prominently, including old R5 CDM interval and historical Phase A result.  
  **Acceptance:** Executive summary cannot cherry-pick only positive synthetic demonstrations.

- [ ] **W22-06 [P1]** Run orthogonal ablations for evidence quality, source independence, correction timing, model accuracy and world difficulty.  
  **Acceptance:** Mechanism effect not confounded with prompt changes or task-generator hints.

- [ ] **W22-07 [P1]** Build first-party baseline implementations from public algorithm descriptions, labeled conceptual and not official reproductions.  
  **Acceptance:** Comparative claim names provenance and fidelity limits honestly.

- [ ] **W22-08 [P1]** Calculate uncertainty using `memeval` and source-cluster pairing; refuse invalid ceilings, wrong baseline metric or implausible detectable effects.  
  **Acceptance:** `INVALID`/`UNDERPOWERED` is treated as unresolved research, never a loss or win.

- [ ] **W22-09 [P1]** Create a reproducibility capsule with exact source commit, deterministic fixture code, local model digest if applicable, environment and all per-case results.  
  **Acceptance:** Another offline checkout with assets can verify stored output digests.

- [ ] **W22-10 [P1]** Write a publishable-style technical report only after primary gates, with claim tier `CONTRACT`, `SCRIPTED`, `LOCAL_MODEL`, `CONFIRMATORY` or `INDEPENDENT`.  
  **Acceptance:** Each headline finding links to measured evidence of at least the same tier.


### 23. CI, local qualification and no-regression release gates — W23 (7 · Qualification, P0)

**Existing code anchors:** `tools/agent_outcome_gate.py`, `tools/cdm_offline_gate.py`, `.github/workflows/ci.yml`, `tests/`

- [ ] **W23-01 [P0]** Build one local `tools/agent_outcome_end_to_end_gate.py --offline --all --out DIR` command coordinating contracts, security, demo, matched scripted arms and provenance checks.  
  **Acceptance:** Exit code nonzero on required failed check, output report complete even if later stage fails.

- [ ] **W23-02 [P0]** Make real-local-model gate an explicitly optional stage with `--local-model` and no model download.  
  **Acceptance:** No installed checkpoint → `REAL_AGENT_NOT_RUN`, never auto substitutes scripted.

- [ ] **W23-03 [P0]** Run all CI matrix core tests on Python 3.11–3.13 and Linux/macOS/Windows as available, with exact unavailable-platform disclosure locally.  
  **Acceptance:** All required preexisting CI jobs remain green at target SHA.

- [ ] **W23-04 [P0]** Add source-bound tests for canonical package migration, cross-transport auth, oracle leakage, recovery budget and case-pair parity.  
  **Acceptance:** Test fails when code changes without updating required schema/fixtures.

- [ ] **W23-05 [P0]** Include separate security/model-attacks gate with a deterministic scripted tier and a truly executed model tier.  
  **Acceptance:** Model-based attack failure/no-run is visible and cannot be overridden by standard CI success.

- [ ] **W23-06 [P0]** Introduce benchmark contract mutation testing: flip a hidden outcome, remove a source root, inject a stale version and change a model digest.  
  **Acceptance:** Evaluator/gate rejects all manipulated evidence.

- [ ] **W23-07 [P0]** Guard generated result artifacts: no accidental mutation of frozen runs, stale commit fields, missing input digests or hidden raw prompts.  
  **Acceptance:** New commit cannot replace a frozen report silently.

- [ ] **W23-08 [P0]** Audit dependency closure to keep core zero mandatory runtime dependencies while allowing existing optional modules.  
  **Acceptance:** Fresh wheel imports and scripted demo run with standard-library-only runtime.

- [ ] **W23-09 [P0]** Version task ledger and automated acceptance evidence with statuses `TODO`, `IMPLEMENTED`, `TESTED`, `SCRIPTED_QUALIFIED`, `LOCAL_MODEL_QUALIFIED`, `BLOCKED_EXTERNAL`.  
  **Acceptance:** Marking a task complete requires linked test and source SHA.

- [ ] **W23-10 [P0]** Run release candidate with exact-SHA CI + offline qualification + model evidence + research promotion; publish distinct internal engineering and deployment decisions.  
  **Acceptance:** No production claim while any required independent review or real pilot gate remains blocked.


### 24. Business value and launch decision without premature deployment — W24 (7 · Qualification, P1)

**Existing code anchors:** `docs/MEMORY_FABRIC_RELEASE_CHECKLIST.md`, `DEPLOYMENT.md`, `README.md`, `docs/AGENT_OUTCOME_EVALUATION.md`

- [ ] **W24-01 [P1]** Define three practical problem statements for product differentiation: correction-aware support, safe multi-agent operations and audited decision repair.  
  **Acceptance:** Each maps to reproducible task templates and operator-visible outcome.

- [ ] **W24-02 [P1]** Calculate measurable benefit as cost of safe task completion, time to recover and unnecessary operator escalations, not stored memory count.  
  **Acceptance:** Report per-scenario units, denominators and evidence source.

- [ ] **W24-03 [P1]** Define no-go if baseline with equally capable recovery wins, no material headroom remains or model effect is underpowered.  
  **Acceptance:** Product documents explicitly describe a negative conclusion instead of inventing positive ROI.

- [ ] **W24-04 [P1]** Define one local showcase requiring no customer data, external API or external services.  
  **Acceptance:** Fresh install demo shows correction, refusal, recovery, verified action and failure explanations end-to-end.

- [ ] **W24-05 [P1]** Document maximum credible inference from deterministic simulator, local model study and independent pilot separately.  
  **Acceptance:** Labels distinguish engineering readiness from commercial readiness.

- [ ] **W24-06 [P1]** Create production deployment threat model for secret custody, effect reconciliation, remote service ingress, restart, backups and process isolation.  
  **Acceptance:** Every threat has a control, test and documented residual risk.

- [ ] **W24-07 [P1]** Document operational thresholds per deployed scenario rather than universal SLO guesses.  
  **Acceptance:** On-call runbook names metrics, stop-switch, rollback and stale-effect reconciliation.

- [ ] **W24-08 [P1]** Provide explicit feature flags and staged rollout policy, with CDM advisory by default until it passes incremental benefit gate.  
  **Acceptance:** Rollback restores last qualified behavior and leaves event log consistent.

- [ ] **W24-09 [P1]** Prepare independent-pilot protocol and security-review evidence packet as an optional external phase, not a prerequisite for building in house.  
  **Acceptance:** External state remains `BLOCKED_EXTERNAL` until evidence actually exists.

- [ ] **W24-10 [P1]** Make launch committee receive an auditable GO/HOLD/NO_GO decision based on frozen metrics, security and operational evidence.  
  **Acceptance:** Software cannot self-certify production readiness from a green internal script.


## 5. Sequential milestone gates

| Gate | Required workstreams | Exit requirement | If unmet |
|---|---|---|---|
| **G0 — Evidence truth** | W01 | Exact clean source baseline, failure disclosure and claim registry | Hold all comparative claims |
| **G1 — One runtime** | W02–W04 | Canonical schema, one working actor loop, isolated evaluator and terminal effect oracle | Stop adding new frameworks |
| **G2 — Safe recovery** | W05–W08 | Diverse tasks, diagnosis, bounded recovery, current action fence and no bypass | Recovery feature off |
| **G3 — Fair local comparisons** | W09–W11 | A0–A7 registry with full parity; CDM advisory; adversarial scripted tests | Comparisons incomplete |
| **G4 — Actual agents** | W12–W13 | Pinned real local model inference on same tasks plus accurate terminal grader; if model missing, record NOT_RUN | No learned-agent efficacy claim |
| **G5 — Confirmatory science** | W14–W15 and W22 | Frozen preregistered protocol, powered and completed heldout study, strongest-baseline gain and safety margins | Hold A5 / A6 |
| **G6 — Engineering qualification** | W16–W21, W23 | Attack gate, transactional recovery, data privacy, tail latency, integrations, CI | No production-adjacent rollout |
| **G7 — Product qualification** | W24 | Clear measured value, operator review, deployment threat controls; independent security/pilot *still distinct* | External publication/deployment NO-GO |

## 6. Local command contracts Codex must implement or verify

Commands below distinguish **existing entry points** and **new, to-be-created commands**. Never claim unimplemented scripts already work.

```bash
# Existing in repository (verify help and exact checkout before running):
python -m pytest tests -q
python tools/agent_outcome_gate.py --help
python tools/cdm_offline_gate.py --help
python -m benchmarks.outcome_recovery --seeds 12

# TO IMPLEMENT in W01/W15/W23 (not present at this review):
python tools/agent_outcome_end_to_end_gate.py --offline --all   --out research/results/agent-outcomes/candidate-offline
python -m benchmarks.outcome_run --arm A3,A4,A5,A6   --split dev --model-mode scripted   --out research/results/agent-outcomes/development
python -m benchmarks.outcome_run --arm A3,A4,A5,A6   --split confirmatory --model-mode local-only   --registration research/prereg/agent-outcome-confirmatory-v1.json   --out research/results/agent-outcomes/confirmatory
python -m benchmarks.outcome_qualification   --registration research/prereg/agent-outcome-confirmatory-v1.json   --runs research/results/agent-outcomes/confirmatory   --out research/results/agent-outcomes/final-verdict.json
```

For local-only real-agent mode, the runner must refuse if the model bytes/runtime are unavailable and **must not download**, use a hosted API, or silently replace inference with a scripted agent. The commands' flags are contract targets; implementation may provide aliases while preserving meaning and tests.

## 7. Recommended first five code-review batches

1. **Batch 1 (W01)** — freeze head and trustworthy evidence ledger; investigate the failed separate model-attack run without guessing its cause; fix current-state documentation. Exit: source-bound baseline pack.
2. **Batch 2 (W02–W04)** — decide canonical runtime through an ADR, merge schema responsibilities behind compatibility adapters, implement one real end-to-end actor→evaluator path. Exit: exact equivalent action-gate decisions and an isolated terminal grader.
3. **Batch 3 (W05–W08, W11)** — strengthen changing-truth task worlds, correct evidence availability vs false abstention metrics, and run A3/A4/A5 under fully matched recovery capabilities. Exit: a resource-parity report with per-case results; no claim of superiority yet.
4. **Batch 4 (W12–W15)** — if an offline checkpoint exists, run real local agents; power and freeze confirmatory design, then evaluate on disjoint worlds. Exit: reproducible GO/HOLD/INVALID result against the **strongest** fair baseline.
5. **Batch 5 (W09, W16–W24)** — only if A5 holds up, evaluate A6/CDM incremental utility and finish security, performance, product, ops and release-boundary work. Exit: scoped, auditable internal engineering qualification, not an invented production certificate.

## 8. Failure cases that must be visibly recorded

1. A5 beats A4 but ties A3: **governed recovery superiority NOT SUPPORTED** on that population.
2. A5 beats A3 but unsafe effect attempts/executions regress: **NO PROMOTION**.
3. A5 is supported but A6 adds no statistically supported cost-adjusted benefit: keep CDM **advisory/opt-in**.
4. Local real-agent runtime unavailable: **REAL_AGENT_NOT_RUN**; scripted completion must not be promoted as learned-agent completion.
5. Evaluator can see oracle but actor can introspect it: **INVALID EVALUATION BOUNDARY**; quarantine result until fixed.
6. Source/prereg/model/prompt digests mismatch: **INVALID EXPERIMENT**, never auto-correct metadata after results.
7. A baseline equals oracle within measured precision: mark no headroom rather than claiming high quality for needless complexity.
8. Agent finishes by unapproved side effect: **UNSAFE**, even if final world looks correct.
9. A model-attack workflow fails with unavailable logs: preserve **CAUSE_UNVERIFIED**, rerun with local detailed failure artifact before classifying.
10. No independent pilot/security review: **NOT PRODUCTION QUALIFIED**, regardless of all in-house engineering PASSes.

## 9. Suggested Codex execution instruction

> Read `AGENTS.md`, `SECURITY.md`, `STABILITY.md`, `docs/AGENT_OUTCOME_EVALUATION.md`, the frozen preregistrations, and this file. Pin current SHA and make a clean baseline before modification. Work **in order**, one workstream per atomic PR/commit or reviewable group. **Do not build another parallel outcome package.** Preserve Memory Fabric's existing authorization, erasure and event semantics. Keep zero new mandatory runtime dependencies. Every task requires implementation, regression and adversarial tests, deterministic local reproducibility and a machine-readable evidence record. Make no positive efficacy claims until powered, frozen, matched local-agent experiments qualify them. In the absence of a local model, report model evidence as NOT_RUN and complete all non-model tasks. Never falsify or rewrite negative scientific findings. Return an evidence-indexed summary of files changed, tests run, metrics, unresolved failures and GO/HOLD decision at the end of each milestone.

## 10. How to mark completion

`TODO` → `IMPLEMENTED` → `TESTED` → `SCRIPTED_QUALIFIED` → `LOCAL_MODEL_QUALIFIED` → `RESEARCH_QUALIFIED` as appropriate. These are **not** interchangeable; `BLOCKED_EXTERNAL` is permitted for third-party certification/pilot. No task may be marked passed simply because code exists or a unit test passes.

**Final desired product:** a trustworthy, correction-aware, agent-facing memory system that **actually finishes more legitimate tasks safely** than equally capable ordinary shared memory; has auditable cause-specific recovery, optional beneficial counterfactual replay, stable APIs, rigorous offline evidence, and a defensible production qualification boundary.

---

**Checkpoints: 240 atomic tasks across 24 workstreams. All are unchecked and proposed.**
