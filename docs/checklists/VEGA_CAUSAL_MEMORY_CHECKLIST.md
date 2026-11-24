# Memory Fabric × Vega-U — Semantic Causal Memory Engineering Master Plan

**End-to-end, in-house-first implementation and evaluation checklist**  
**Prepared:** 2026-11-21  
**Memory Fabric reviewed commit:** `70e34c870d387cb5de8ba0bbdda0320cf3574d6c`  
**Repo:** https://github.com/crakashp2905-hub/memory-fabric  
**Scope:** use an optional, locally hosted vega-U System One decision model to improve **evidence understanding, causal-hypothesis nomination, intervention selection, and agent recovery** without changing any existing governance or action authorization.  
**Tasks:** 180 atomic checkboxes across 18 workstreams. **All are initially NOT_STARTED**; this checklist is a specification, not executed work.

> **Core claim discipline:** Vega is a semantic classifier and candidate selector. Its probabilities are *not a causal identification method*. Historical provenance supports observed dependency; deterministic replay under registered assumptions supports *simulator-conditional causal effects*; an actual task outcome needs an independently graded terminal effect. No system should infer physical causality, agent inner reasoning, or production safety from Vega scores, textual associations, or a passing scripted demo.

## Executive verdict

**Yes, conditionally:** vega-U is a promising way to make Memory Fabric's Counterfactual Decision Memory (CDM) more semantically selective and task-oriented. The project's existing CDM engine already has exact historical capture, typed intervention candidates, deterministic replay, attribution, separate verifier, and cost-aware scheduler. Vega can provide better input *to* these capabilities. Whether it increases legitimate safe task completion is **an open experimental hypothesis**, not an established result.

### Verified starting point

- `src/memory_fabric/adapters/systemone.py` currently targets **Kev/TypeSafe** `POST /v1/systemone` with `noul`, `choice`, `score`; it is **not protocol-compatible as written** with vegaml's `POST /v1/decide` using `boolean`, `choice`, `score` and `{state, questions, mode?, alpha?, views?}`. Write a separate Vega-U protocol adapter rather than silent format coercion.
- `src/memory_fabric/decision_models.py` provides typed proposal validation and optional escalation; keep it authoritative for proposal structure, **not tool permission**.
- `src/memory_fabric/causal_replay/`: `capture.py`, `intervention.py`, `replay.py`, `attribution.py`, `verifier.py`, `scheduler.py`, `api.py`, `bayes.py` provide existing first-party mechanisms.
- `src/memory_fabric/decision_records.py` and `src/memory_fabric/outcome_typed/` contain version-bound dependency records and experimental agent-outcome runtime hooks. **Do not create another outcome package.**
- Previous CDM confirmatory architecture-superiority result: mean +0.055 with interval [-0.0528, +0.1628], **no registered superiority**. Existing A5-versus-A3 scripted development result is 0.00 on 10 cases; A5-versus-A4 is +0.20. No registered real-agent outcome result establishes a benefit of Vega.
- Core Memory Fabric is zero mandatory runtime dependencies. Vega runtime and checkpoint remain **optional external model assets** run locally. This meets "no hosted dependencies" but **not** "all code and model weights authored from scratch".

### Vega model selection

Start with **[nandakishorm/vega-U](https://huggingface.co/nandakishorm/vega-U)** using the 0.8B reader. The same vega-U engine can use a 4B reader through a reader-specific port and recalibration. A separate, unrelated **[vLLM Decision-2.0-Vega-27B](https://vllm-sr.com/docs/model-runtime/supported-models/decision-2/vega-27b/)** also exists; it is a materially larger GPU-oriented model and is **out of scope for the first local qualification**. Record exact checkpoint/reader/runtime/calibration hashes. Do not assume publisher-reported calibration transfers to Memory Fabric tasks. The 0.8B Mac MPS path is experimental and must be measured, not assumed.

## 1. Why semantic decision models can improve causal memory

| Existing causal-memory gap | Vega proposal | Independent, required validation |
|---|---|---|
| Paraphrases or semantically distant equivalent claims are missed | Typed semantic support and relevance questions | Source- and time-aware labels, identifier/quantity hard negatives |
| Apparent agreement from copied sources | Suggest support/contradiction edges | Deterministic source-root deduplication; Vega never asserts independence |
| Conflicting memories lead to reflexive refusal | Rank legal recovery steps and evidence requests | Agent completes more eligible terminal tasks under fresh ActionGate checks |
| Too many counterfactuals are expensive | Rank likely material interventions | Matched replay runs with same candidate sets, CPU/time budgets and outcome oracle |
| Attribution score treated as actual improvement | Suggest and rank hypotheses only | Exact/verified replay, paired terminal task outcomes and uncertainty estimates |
| Sensor failure and real overheating both present | Multi-label candidate hypotheses | Independent simulator representing both states; no false exclusivity |
| Model confidence mistaken for truth | Conformal-set/abstain/unbound advisory routing | Per-domain calibration, selective risk, negative controls and safe failure |

### The non-negotiable safety boundary

```
CURRENT AUTHORIZATION -> CURRENT-VERSION EVIDENCE CAPTURE -> SOURCE-ROOT PROVENANCE
                                  |
                                  v
                   Vega-U typed SEMANTIC proposals
               (relevance / support / candidate causes /
              intervention priority / recovery next-step)
                                  |
                       STRICT HOST VALIDATION
                                  |
          EXISTING CDM INTERVENTION + DETERMINISTIC REPLAY
                                  |
             INDEPENDENT VERIFIER + OUTCOME EVALUATOR
                                  |
                      READ-ONLY CAUSAL ADVISORY
                                  |
         OPTIONAL AGENT REPLAN -> FRESH CERTIFICATE + ActionGate
                                  |
             AUTHORIZED EFFECT -> INDEPENDENT TERMINAL GRADE
```

**Never modify** existing identity, memory access authorization, ActionGate, source versioning, erasure, retraction, audit or certificate authority as a side effect of a model suggestion. Vega cannot dequarantine a record, write hidden evaluator truth, declare an alternate outcome to be factual, grant a tool permission, or execute an action.

## 2. Proposed first-party module layout (no fourth outcome runtime)

```text
src/memory_fabric/
  adapters/vega_u.py                    # New optional loopback client / v1/decide
  causal_replay/semantic/
    __init__.py
    packets.py                          # Authorized bitemporal evidence packets
    support.py                          # Typed relevance and semantic support
    graph.py                            # Candidate edges, not confirmed effects
    beliefs.py                          # Bounded belief proposal adapter
    interventions.py                    # Candidate -> typed compiler
    effects.py                          # Strict effect-evidence separation
    scheduler.py                        # Expected-value replay priority
    calibration.py                      # Optional fitted local thresholds
    cache.py                            # Tenant/version/digest-aware ephemeral cache
benchmarks/
  vega_cdm_worlds.py                     # Independently evaluated synthetic worlds
  vega_cdm_matched_arms.py              # A5/A5-V/A6/A6-V + fair A3
  vega_cdm_confirmatory.py              # Frozen inferential analysis
  vega_cdm_model_report.py              # Real model metadata and costs
experiments/vega_cdm_real_agents.py      # Local 3-agent matched episodes
examples/vega_cdm_demo.py              # Operator demo, not a benchmark
research/prereg/vega-cdm-v1.json        # Freeze before confirmatory split
research/results/vega-cdm/              # Source-bound raw reports
 tools/vega_cdm_gate.py                 # Separate contracts/model/efficacy/release statuses
```

Paths above are proposed new files, not a claim that they already exist.

## 3. Canonical typed questions: implemented as proposals, not facts

The example below uses **Vega-U's documented question structure** (including `boolean`, not the legacy `noul`). It deliberately limits choices to safe, host-defined options. No source IDs, verdicts or effects are invented by the model.

```python
questions = {
  "claim_support": {
    "type": "choice",
    "instructions": "How does this CURRENT authorized evidence relate to the specified claim?",
    "criteria": {
      "supports": "This evidence directly supports the claim at its scoped time.",
      "contradicts": "This evidence directly conflicts with the claim.",
      "unclear": "The link cannot be determined from this evidence."
    }
  },
  "causal_candidate": {
    "type": "boolean",
    "instructions": "Is the stated candidate mechanism consistent with the evidence?",
    "criteria": {"true": "Consistent, not proven causal", "false": "Not supported"}
  },
  "next_step": {
    "type": "choice",
    "instructions": "Which ALLOWED investigation should be considered next?",
    "criteria": {
      "retrieve_other_source": "Find a current authorized independent observation",
      "request_new_observation": "Ask the host for an observation through an approved tool",
      "replay_candidate": "Recommend one bounded hypothetical replay for independent validation",
      "abstain": "Stop or escalate when evidence is not sufficient"
    }
  }
}
# vega-U local Python: v = vegaml.load('/path/to/pinned/checkpoint'); v.decide(state, questions)
# or optional local server: POST /v1/decide with {"state": ..., "questions": questions}
# Return only typed suggestions; ActionGate and CDM validation remain mandatory.
```

Do not assume every published model report includes the same fields. Inspect and pin an actual response fixture from the chosen runtime. For `choice`, validate exact criteria keys, `probs`, `prediction_set`, `abstain` and `unbound`; missing or invalid fields should not silently become high confidence. Log summaries and hashes, not sensitive evidence text.

## 4. Measurement design and promotion gates

**Arms**: A3 = pooled memory + recovery; A5 = governed memory + deterministic recovery; A5-V = A5 + Vega semantic advisor; A6 = A5 + CDM; A6-V = A5-V + CDM selective advisory. Preserve old frozen arm IDs and preregister the two new suffix arms. A7 remains evaluator-only oracle. Include lexical and full-context-within-budget controls, prompt framing controls, and random/recency/exact-dependence intervention selectors.

**Primary endpoint:** evaluator-confirmed **safe terminal-task completion / all registered eligible task cases**, with every failed or undecidable assigned case retained in denominator unless an exclusion was frozen in advance.

**Primary tests:** (1) A5-V vs A5, (2) A5-V vs strongest fair A3, and (3) A6-V vs A5-V and A6 for incremental net-CDM utility. Use held-out task/world clusters with matched model and resource budgets; development-only baseline selection; frozen primary contrast and multiplicity control. Predefine minimum material gain (illustrative 5 percentage points, subject to power study) and reject if confidence interval or registered safety gate fails.

**Secondary:** bitemporal correctness, semantic edge classification, candidate-replay precision@budget, posterior fidelity, ECE/Brier, conformal coverage and selective risk, counterfactual-effect error, false withholding, recovery latency, privacy breaches, unsafe attempts, unsafe executed effects, p95/p99 latency, model memory/CPU/GPU resource costs and token usage. Zero observed unsafe effects is *not* a zero-risk certificate: publish exact one-sided bounds.

**Outcome levels:** `CONTRACT_PASS` (offline deterministic tests), `VEGA_MODEL_SMOKE_PASS` (actual local inference), `REAL_AGENT_STUDY_PASS` (pinned learned-agent matched evidence), `EFFECT_SUPPORTED` (preregistered causal-advisory effect tests), `INTERNAL_QUALIFIED` (all specified in-house gates) and `EXTERNAL_DEPLOYMENT_UNQUALIFIED` until independent pilot/security evidence exists. Failed or missing model gate must remain `MODEL_NOT_RUN`, never converted to scripted pass.

### Research hypotheses (pre-register before held-out data)

- **H1 relevance:** Vega-assisted support detection improves F1/recall at a predeclared false-positive budget over deterministic answerability and lexical selectors in unseen paraphrase families.
- **H2 hypothesis utility:** Vega-generated candidate causal edges prioritize truly decision-relevant simulator interventions more efficiently than exact-dependence-only ranking at identical replay cost.
- **H3 safe completion:** A5-V improves actual safe task completion relative to A5 and A3 with matched recovery and model budgets.
- **H4 CDM net value:** A6-V improves net utility over A5-V, including replay/model overhead; if it loses, CDM stays optional.
- **H5 governance invariance:** unauthorized content exposure and executed unauthorized effects do not regress under Vega modes.
- **H6 calibration:** domain-fitted conformal abstention reduces harmful overconfidence without increasing false withholding beyond registered tolerance.

### Internal qualification procedure (after implementation)

```bash
# Do not run these non-existent proposed commands before implementing the files.
python -m pytest -q tests/test_vega_u_adapter.py tests/test_semantic_packets.py \
    tests/test_semantic_support.py tests/test_semantic_graph.py \
    tests/test_semantic_interventions.py tests/test_vega_cdm_science.py
python tools/vega_cdm_gate.py --mode offline --out research/results/vega-cdm/offline/
python -m benchmarks.vega_cdm_matched_arms --split development \
    --out research/results/vega-cdm/development/
python -m benchmarks.vega_cdm_confirmatory --registration research/prereg/vega-cdm-v1.json \
    --out research/results/vega-cdm/confirmatory/
# Enable real-model trials only when an actual pinned local Vega checkpoint exists.
```

**No-go triggers:** semantic model proposes unauthorized access; bitemporal leakage; unsupported intervention treated as verified; confounded association labeled causal; replay self-certification; downstream completion non-improvement; unsafe-execution increase; leakage or overfitting between splits; missing model proof; inaccurate release status; violating no-new-mandatory-dependency contract.

## 5. Atomic implementation checklist

### S00. Baseline, scientific contract and scope

**Implementation targets:** `docs/architecture/ADR-VEGA-CDM-001.md`, `docs/CDM_KNOWN_FINDINGS.md`, `research/prereg/vega-cdm-v1.json`

- [ ] **VEGA-CDM-001 — Record the exact Memory Fabric SHA, Python versions, module inventory, current CI and known negative CDM studies**  
  **Done when:** Baseline manifest stores SHA, dates, source hashes and non-promotable prior findings.
- [ ] **VEGA-CDM-002 — Freeze a written epistemic taxonomy: textual relevance, observed dependence, hypothetical effect, validated counterfactual, real-world causal claim**  
  **Done when:** Schemas and docs enforce distinct tags; no model score may assert causal truth.
- [ ] **VEGA-CDM-003 — Inventory the existing System One/Kev client and identify Vega-U protocol mismatches**  
  **Done when:** ADR explicitly documents /v1/systemone versus /v1/decide and noul versus boolean.
- [ ] **VEGA-CDM-004 — Inventory CDM capture, intervention, replay, attribution, evaluator, verifier and budget interfaces**  
  **Done when:** Architecture map names every integration point and acceptance test.
- [ ] **VEGA-CDM-005 — Inventory decision and outcome runtimes; choose one canonical integration and avoid creating a fourth outcome package**  
  **Done when:** ADR selects canonical runtime with compatibility plan.
- [ ] **VEGA-CDM-006 — Define the first answerable research question: Vega-assisted evidence selection reduces decision repair failures**  
  **Done when:** Protocol identifies population, intended mechanism, comparator and primary endpoint.
- [ ] **VEGA-CDM-007 — Write an explicit no-governance-change invariant and threat model**  
  **Done when:** ActionGate, identity, scopes, erasure, correction, certificates and audit semantics remain unchanged.
- [ ] **VEGA-CDM-008 — Define modes OFF, SHADOW, ADVISORY and QUALIFIED; default OFF**  
  **Done when:** Config and tests assert opt-in behavior and no automatic promotions.
- [ ] **VEGA-CDM-009 — Create a task-to-evidence ledger with statuses NOT_STARTED, IMPLEMENTED, VALIDATED, BLOCKED**  
  **Done when:** Every checklist task maps to a code/test/report artifact and exact SHA.
- [ ] **VEGA-CDM-010 — Require an honest evidence hierarchy contract for scripted, local-model, independently replicated and deployed results**  
  **Done when:** Research reports fail validation if evidence level is overstated.

### S01. Vega-U adapter and versioned inference contract

**Implementation targets:** `src/memory_fabric/adapters/vega_u.py`, `src/memory_fabric/decision_models.py`, `tests/test_vega_u_adapter.py`

- [ ] **VEGA-CDM-011 — Define VegaDecisionProvider protocol in the existing adapters layer, returning only typed, advisory decisions**  
  **Done when:** Frozen request/response contracts expose no ability to mutate store, invoke tools or approve evidence.
- [ ] **VEGA-CDM-012 — Implement an HTTP client for POST /v1/decide, not the legacy Kev /v1/systemone endpoint**  
  **Done when:** Recorded Vega-U golden fixture round-trips, including state and questions.
- [ ] **VEGA-CDM-013 — Support choice, boolean and score questions with Vega-U criteria/instructions schema**  
  **Done when:** Golden fixtures assert accurate request shape and known response fields.
- [ ] **VEGA-CDM-014 — Parse probs, selected label, conformal prediction_set, abstain, unbound and readout without silently filling missing values**  
  **Done when:** Malformed/missing/NaN probabilities produce explicit UNAVAILABLE or INVALID statuses.
- [ ] **VEGA-CDM-015 — Pin vegaml runtime version, model checkpoint digest, reader/port and calibration revision**  
  **Done when:** Every real inference receipt contains all hashes and provenance.
- [ ] **VEGA-CDM-016 — Allow the 0.8B reader initially, optional 4B, and document their actual resource requirements**  
  **Done when:** Tests reject unregistered reader IDs and silently substituted checkpoints.
- [ ] **VEGA-CDM-017 — Read local service readiness through GET /health and metadata through GET /v1/model**  
  **Done when:** Handshake fails closed if expected metadata is absent or incompatible.
- [ ] **VEGA-CDM-018 — Add local-only egress restrictions and explicit trusted-loopback/UDS connection configuration**  
  **Done when:** No default public endpoint or out-of-policy network call is permitted.
- [ ] **VEGA-CDM-019 — Implement finite deadline, bounded retries, batch limits and circuit breaker**  
  **Done when:** Timeout, malformed response, unavailable model and resource exhaustion fall back safely.
- [ ] **VEGA-CDM-020 — Keep core dependency-free; run Vega runtime in an optional separate environment and never implicitly download weights**  
  **Done when:** Core wheel installs and all default tests pass without vegaml, torch, network or checkpoint.

### S02. Evidence packet, provenance and temporal boundaries

**Implementation targets:** `src/memory_fabric/causal_replay/semantic/packets.py`, `src/memory_fabric/causal_replay/capture.py`, `tests/test_semantic_packets.py`

- [ ] **VEGA-CDM-021 — Define SemanticEvidencePacket with tenant, principal scope, evidence ID/version, content hash, origin root, known_at, valid_at, status and visible text**  
  **Done when:** Schema validation rejects missing or inconsistent provenance.
- [ ] **VEGA-CDM-022 — Construct packets only from authorized existing retrieval/capture results, never directly from the event log for model use**  
  **Done when:** Test prevents unauthorized historical content from entering Vega state.
- [ ] **VEGA-CDM-023 — Enforce current authorization even when reconstructing previously visible beliefs**  
  **Done when:** Revoked or erased evidence remains unavailable to inference at later times.
- [ ] **VEGA-CDM-024 — Preserve source-root correlation groups through copying, federation, summaries and quotations**  
  **Done when:** Duplicate source copies count once for independent corroboration.
- [ ] **VEGA-CDM-025 — Separate observation, author assertion, derived memory, tool response and hypothetical output**  
  **Done when:** Packet source kinds survive all serialization roundtrips.
- [ ] **VEGA-CDM-026 — Add canonical bounded JSON for packet assembly with stable ordering, UTF-8 and numerical checks**  
  **Done when:** Same inputs produce identical hash; malformed inputs rejected.
- [ ] **VEGA-CDM-027 — Make memory/event exposure limits configurable and enforce before model invocation**  
  **Done when:** Over-budget packets report TRUNCATED_NOT_VALIDATED, never an implied full trace.
- [ ] **VEGA-CDM-028 — Include correction lineage and version timestamps without exposing evaluator hidden truth**  
  **Done when:** Actor packet omits oracle values and sealed scoring fields.
- [ ] **VEGA-CDM-029 — Apply redaction to secrets and erased content before prompt formation and logging**  
  **Done when:** Canary and leak tests prove sensitive values never reach captured requests.
- [ ] **VEGA-CDM-030 — Build 10:00/10:15/10:30 battery evidence fixture with both sensor bias and genuine overheating possible**  
  **Done when:** Tests prevent mutually exclusive diagnosis assumption and verify source chronology.

### S03. Semantic relevance and support detection

**Implementation targets:** `src/memory_fabric/causal_replay/semantic/support.py`, `src/memory_fabric/answerability.py`, `tests/test_semantic_support.py`

- [ ] **VEGA-CDM-031 — Define a typed relevance question over a bounded, authorized candidate set**  
  **Done when:** Model may choose relevant/partial/irrelevant but cannot activate memories.
- [ ] **VEGA-CDM-032 — Define exact claim-support relation with SUPPORTED, CONTRADICTED, UNKNOWN, INCOMPARABLE options**  
  **Done when:** Unknown or ambiguous sets remain explicit and inspectable.
- [ ] **VEGA-CDM-033 — Score semantic equivalence of paraphrases while preserving identifier and numeric exact-match guardrails**  
  **Done when:** Near-miss unit IDs and quantity changes are never silently merged.
- [ ] **VEGA-CDM-034 — Implement pairwise evidence-to-claim support with version-specific evidence references**  
  **Done when:** Every proposed support edge names precise evidence versions and model receipt.
- [ ] **VEGA-CDM-035 — Keep structural answerability as comparator and required deterministic safety backstop**  
  **Done when:** No semantic score can overturn missing permission or revoked support.
- [ ] **VEGA-CDM-036 — Treat source independence as metadata-derived, never language-model estimated truth**  
  **Done when:** Copied sources cannot become independent by paraphrasing.
- [ ] **VEGA-CDM-037 — Add cheap lexical prefilter followed by Vega rerank on top-k ambiguous cases**  
  **Done when:** Measured recall/latency frontier reported against lexical and full-context.
- [ ] **VEGA-CDM-038 — Use multi-label support vectors for overlapping hypotheses instead of forced single-label classification**  
  **Done when:** Fixtures permit sensor fault and overheating jointly.
- [ ] **VEGA-CDM-039 — Record inconclusive conformal sets, abstentions and unbound scores as abstain/retrieve-more candidates**  
  **Done when:** No forced winner when output is ambiguous or off-distribution.
- [ ] **VEGA-CDM-040 — Create deterministic edge-case tests for negation, scope, quantities, chronology, aliases and same-name entities**  
  **Done when:** Expected labels established by separate fixture oracle, not by Vega.

### S04. Causal-semantic candidate graph

**Implementation targets:** `src/memory_fabric/causal_replay/semantic/graph.py`, `src/memory_fabric/influence.py`, `src/memory_fabric/lineage.py`, `tests/test_semantic_graph.py`

- [ ] **VEGA-CDM-041 — Represent a typed property graph of observation, claim, belief, decision, action and outcome nodes**  
  **Done when:** Node IDs preserve source, version and time identity.
- [ ] **VEGA-CDM-042 — Use separate edge types REPORTS, SUPPORTS, CONTRADICTS, EXPOSED_TO, RELIED_ON, PRECEDES, HYPOTHESIZED_CAUSE and VERIFIED_COUNTERFACTUAL_EFFECT**  
  **Done when:** Schema disallows conflating evidence dependency and causal effect.
- [ ] **VEGA-CDM-043 — Generate HYPOTHESIZED_CAUSE candidates from Vega typed questions only as unverified hypotheses**  
  **Done when:** No candidate may be serialized as verified without replay evidence.
- [ ] **VEGA-CDM-044 — Ground candidate edges in visible span IDs and allowed records rather than free-floating model explanations**  
  **Done when:** All edges have evidence references and provenance hashes.
- [ ] **VEGA-CDM-045 — Reject cycles for edges requiring directed acyclic causal semantics while allowing cycles in generic associations**  
  **Done when:** DAG checker and cycle regression tests pass.
- [ ] **VEGA-CDM-046 — Preserve event recording order separately from source valid time; reject post-outcome evidence leakage**  
  **Done when:** Bitemporal fixtures prove correct ordering and observation cutoffs.
- [ ] **VEGA-CDM-047 — Represent latent confounder and unobserved variable placeholders explicitly**  
  **Done when:** Unknown confounding forces CAUSAL_UNIDENTIFIABLE where necessary.
- [ ] **VEGA-CDM-048 — Maintain deterministic structural lineage from existing influence/dependence modules alongside semantic suggestions**  
  **Done when:** Existing exact lineage remains authoritative for impact reach.
- [ ] **VEGA-CDM-049 — Implement revision-aware graph invalidation on retraction, correction and erase**  
  **Done when:** Recomputed graph excludes obsolete content and retains authorized audit metadata only.
- [ ] **VEGA-CDM-050 — Verify no cross-tenant or history unauthorized edges are revealed by result counts or errors**  
  **Done when:** Cross-tenant metadata-probing regression suite passes.

### S05. Belief reconstruction and semantic state

**Implementation targets:** `src/memory_fabric/causal_replay/semantic/beliefs.py`, `src/memory_fabric/causal_replay/bayes.py`, `tests/test_semantic_beliefs.py`

- [ ] **VEGA-CDM-051 — Define a belief snapshot as observed evidence plus model proposal plus deterministic update status**  
  **Done when:** Belief evidence and generated semantic output are separate data types.
- [ ] **VEGA-CDM-052 — Keep exact Bayesian enumerator as independent oracle on small registered worlds**  
  **Done when:** Semantic-assisted results compared to exact deterministic posterior baseline.
- [ ] **VEGA-CDM-053 — Generate semantic likelihood proposals only for explicitly modeled observational variables**  
  **Done when:** Unspecified likelihoods cannot be invented and replayed as facts.
- [ ] **VEGA-CDM-054 — Calibrate Vega-derived classification probabilities separately per question family and reader**  
  **Done when:** Held-out ECE, Brier, coverage and selective risk published.
- [ ] **VEGA-CDM-055 — Test evidence duplication invariance by adding paraphrased copies from one source root**  
  **Done when:** Posterior and decision policy do not gain artificial independent support.
- [ ] **VEGA-CDM-056 — Test correction time-travel with known_at and valid_at, including late-arriving earlier-valid evidence**  
  **Done when:** Belief reconstruction matches registered historical snapshot.
- [ ] **VEGA-CDM-057 — Provide exact, approximate and non-replayable status labels with required digests**  
  **Done when:** No approximated semantic belief called an exact historical state.
- [ ] **VEGA-CDM-058 — Reject hypothetical action-observation continuation without registered simulator support**  
  **Done when:** UNDEFINED_CONTINUATION recorded instead of invented observations.
- [ ] **VEGA-CDM-059 — Test conditional hypotheses for overheating plus biased temperature sensor simultaneously**  
  **Done when:** Belief output supports coexisting states and independent calibration evidence.
- [ ] **VEGA-CDM-060 — Prevent training-label or evaluator outcome contamination of belief state**  
  **Done when:** Sealed outcome fields never appear in actor state hash or prompt.

### S06. Typed intervention generation and safety

**Implementation targets:** `src/memory_fabric/causal_replay/semantic/interventions.py`, `src/memory_fabric/causal_replay/intervention.py`, `tests/test_semantic_interventions.py`

- [ ] **VEGA-CDM-061 — Define a closed intervention proposal vocabulary: WITHHOLD, REPLACE, DELAY, DUPLICATE, REORDER_ALLOWED, SWAP_POLICY and NO_OP**  
  **Done when:** Every proposal compiles to existing validated Intervention types or explicit UNSUPPORTED.
- [ ] **VEGA-CDM-062 — Have Vega rank WHICH allowed intervention to investigate, never execute it directly**  
  **Done when:** All proposed interventions are checked by deterministic compiler and budget gate.
- [ ] **VEGA-CDM-063 — Attach exact target evidence/version, reason code, model digest and optional expected decision-change category**  
  **Done when:** Proposal provenance is complete without asserting actual effect.
- [ ] **VEGA-CDM-064 — Reject interventions on inaccessible, erased, non-exposed or out-of-scope evidence**  
  **Done when:** Tests prove no unauthorized alternate timeline disclosure.
- [ ] **VEGA-CDM-065 — Require replacement evidence from prevalidated local fixtures or authorized alternate sources**  
  **Done when:** Generated text is not treated as factual replacement evidence.
- [ ] **VEGA-CDM-066 — Add no-op controls and semantically irrelevant evidence removal controls**  
  **Done when:** Negative control invariance measured for every benchmark world family.
- [ ] **VEGA-CDM-067 — Add correlated-source duplicate control and counterfactual delayed-federation control**  
  **Done when:** Model does not infer false independence from multiple copies.
- [ ] **VEGA-CDM-068 — Bound candidate count, intervention depth, event count, bytes, time and replay work**  
  **Done when:** Test forces exhaustion and observes safe stop with accounting.
- [ ] **VEGA-CDM-069 — Prevent simultaneous mutually inconsistent interventions in one batch**  
  **Done when:** Compiler rejects contradictory targets or ambiguous ordering.
- [ ] **VEGA-CDM-070 — Record proposal≠executed replay≠validated effect in distinct ledger states**  
  **Done when:** Auditor can trace every rejected or untested intervention.

### S07. Independent replay and causal-effect estimation

**Implementation targets:** `src/memory_fabric/causal_replay/replay.py`, `src/memory_fabric/causal_replay/verifier.py`, `src/memory_fabric/causal_replay/semantic/effects.py`, `tests/test_semantic_effects.py`

- [ ] **VEGA-CDM-071 — Replay matched factual and intervention worlds under identical pinned policy, seed and environmental assumptions**  
  **Done when:** Paired runs differ only in registered intervention and causal descendants.
- [ ] **VEGA-CDM-072 — Reuse existing independent-code-path replay verifier and acceptance certificates**  
  **Done when:** No Vega-generated certificate can self-verify its own factual fidelity.
- [ ] **VEGA-CDM-073 — Separate internal policy flip, belief divergence, action proposal change, and independently graded terminal improvement**  
  **Done when:** Reports never equate proposal change with utility gain.
- [ ] **VEGA-CDM-074 — Use source-root grouped leave-one-out and interaction ablations before optional Shapley**  
  **Done when:** Attribution respects copied evidence and documented budget.
- [ ] **VEGA-CDM-075 — Report partial identifiability, confounding and nonreplayable continuations as UNKNOWN**  
  **Done when:** No fabricated causal estimate for unsupported or incomplete worlds.
- [ ] **VEGA-CDM-076 — Record paired effect estimates with confidence intervals clustered by independent world seed**  
  **Done when:** Effect CI calculation uses common task IDs and proper cluster units.
- [ ] **VEGA-CDM-077 — Use causal DAG consistency checks for intervention targets and downstream exposure**  
  **Done when:** Invalid directions or descendants are rejected with reasons.
- [ ] **VEGA-CDM-078 — Verify exact factual replay before accepting any counterfactual certificate**  
  **Done when:** Failed fidelity yields NO_EFFECT_CERTIFIED, not zero impact.
- [ ] **VEGA-CDM-079 — Compare with no-model, deterministic priority, random, recency and oracle upper bound**  
  **Done when:** Every claimed gain is measured against legitimate alternatives.
- [ ] **VEGA-CDM-080 — Preserve raw negative, null and invalid findings without rewriting protocols**  
  **Done when:** Source-bound results always carry status and registration digest.

### S08. Budgeted causal replay selector

**Implementation targets:** `src/memory_fabric/causal_replay/semantic/scheduler.py`, `src/memory_fabric/causal_replay/scheduler.py`, `tests/test_vega_scheduler.py`

- [ ] **VEGA-CDM-081 — Define replay-value decision as expected improvement under a bounded cost, not only high semantic confidence**  
  **Done when:** Ranking function is documented with measurable inputs and a no-replay option.
- [ ] **VEGA-CDM-082 — Use existing exact dependence frontier to filter cases unrelated to changed evidence**  
  **Done when:** Independent decisions skip Vega and CDM with a receipt.
- [ ] **VEGA-CDM-083 — Compare pure dependence, random, recency, cost-only and Vega-assisted selectors under equal replay budgets**  
  **Done when:** Matched ablation has identical candidate sets and compute caps.
- [ ] **VEGA-CDM-084 — Use Vega only after cheap deterministic rules cannot settle an ambiguous candidate**  
  **Done when:** No unnecessary model calls on exact-evidence simple paths.
- [ ] **VEGA-CDM-085 — Require a minimum expected value of information and measured overhead before triggering replay**  
  **Done when:** Low-value cases short-circuit to deterministic policy.
- [ ] **VEGA-CDM-086 — Apply confidence/abstain/large-conformal-set routing to independent review or targeted new observation**  
  **Done when:** No automatic intervention from uncertain answer.
- [ ] **VEGA-CDM-087 — Cache only version-bound, authorized model outputs with tenant-safe keys**  
  **Done when:** Invalidation on correction, erasure, model revision and policy revision tested.
- [ ] **VEGA-CDM-088 — Enforce total actor decision budget separately from replay worker budget**  
  **Done when:** Separate accounting prevents replay work hiding in model cost.
- [ ] **VEGA-CDM-089 — Report replay selection precision, recall at budget, regret and terminal net utility**  
  **Done when:** Scheduler gains measured on outcome oracle, not only proposal agreement.
- [ ] **VEGA-CDM-090 — Test negative value scenarios where replay increases latency without changing decision**  
  **Done when:** Selector learns to skip and reporting does not hide wasted calls.

### S09. Correction-driven agent recovery and multi-agent memory

**Implementation targets:** `src/memory_fabric/outcome_typed/runtime.py`, `src/memory_fabric/outcome_typed/eligibility.py`, `tests/test_vega_recovery.py`

- [ ] **VEGA-CDM-091 — Add optional semantic advisory to the existing canonical outcome runtime only; no fourth outcome stack**  
  **Done when:** OFF mode matches old behavior byte-for-byte for registered public records.
- [ ] **VEGA-CDM-092 — Emit typed failure cause MISSING, STALE, WITHHELD, CONTESTED, IRRELEVANT or NON_REPLAYABLE using authoritative signals**  
  **Done when:** Vega can add proposal but not rewrite existing failure codes.
- [ ] **VEGA-CDM-093 — Rank allowed recovery actions REFRESH, RE_RETRIEVE, INSPECT_PROVENANCE, ASK, REPLAN, ABSTAIN**  
  **Done when:** Suggested actions are selected from a host-defined read-only catalog.
- [ ] **VEGA-CDM-094 — Respect recovering agent identity, memory scope and per-agent rate limits through all follow-up queries**  
  **Done when:** Privilege and tenancy regression tests pass under multi-agent handoffs.
- [ ] **VEGA-CDM-095 — Handle post-plan correction using fresh evidence certificate and exact-action grant**  
  **Done when:** Old action is refused, new authorized action may complete independent terminal objective.
- [ ] **VEGA-CDM-096 — Pass conflicting evidence from independent observers without majority collapse**  
  **Done when:** False consensus fixtures retain distinct roots and uncertainty.
- [ ] **VEGA-CDM-097 — Record deliberation proposals without creating synthetic evidence or granting permissions**  
  **Done when:** Agent transcript labels model suggestion distinctly from tool observation.
- [ ] **VEGA-CDM-098 — Bound recovery steps, attempts, token budget and task wall time**  
  **Done when:** Exhaustion remains a safe terminal state with usable explanation.
- [ ] **VEGA-CDM-099 — Include deterministic peer disagreement and unavailable-source scenarios**  
  **Done when:** System can choose justified abstention and no action for irrecoverable worlds.
- [ ] **VEGA-CDM-100 — Keep CDM optional under dependence+value gate and use verified outcomes to assess usefulness**  
  **Done when:** A5-V compared fairly with A5; A6-V compared with A5-V and A6.

### S10. Model calibration and optional supervised learning

**Implementation targets:** `src/memory_fabric/causal_replay/semantic/calibration.py`, `tests/test_vega_calibration.py`, `research/results/vega-cdm/`

- [ ] **VEGA-CDM-101 — Define independent calibration splits by world family, time, source root and template**  
  **Done when:** No paraphrase of calibration task appears in confirmatory set.
- [ ] **VEGA-CDM-102 — Collect per-question probabilities, observed correctness and conformal sets from controlled fixtures**  
  **Done when:** Raw probability and correct option are separate evaluator-owned fields.
- [ ] **VEGA-CDM-103 — Measure Brier, ECE, NLL, top-1, set coverage, selective accuracy and abstention rate**  
  **Done when:** Every metric specifies population and denominator.
- [ ] **VEGA-CDM-104 — Recalibrate the chosen reader only with verified local labels under a frozen fitted artifact**  
  **Done when:** Calibration manifest pins fit/validation sample IDs and digest.
- [ ] **VEGA-CDM-105 — Retain original uncalibrated checkpoint as a comparator with no write-back**  
  **Done when:** Ablations isolate gains from calibration versus Vega architecture.
- [ ] **VEGA-CDM-106 — Evaluate threshold transfer across domains, model versions and unseen source roots**  
  **Done when:** Out-of-distribution threshold failure triggers review-only mode.
- [ ] **VEGA-CDM-107 — Keep optional online Learner disabled by default; permit only evaluator-confirmed feedback**  
  **Done when:** Never train directly on agent self-ratings, unverified rewards or generated rationales.
- [ ] **VEGA-CDM-108 — Implement shadow prequential feedback evaluation with outcome delay, no future label leakage**  
  **Done when:** Every training step is timestamped after its observed outcome.
- [ ] **VEGA-CDM-109 — Version and atomically roll back any fitted head, policy or calibration artifact**  
  **Done when:** Restore baseline decision behavior without touching memory governance.
- [ ] **VEGA-CDM-110 — Require positive matched downstream effect before activating continual learning**  
  **Done when:** No promotion from calibration improvements alone.

### S11. Synthetic worlds and independent task oracle

**Implementation targets:** `benchmarks/vega_cdm_worlds.py`, `benchmarks/outcome_worlds.py`, `tests/test_vega_worlds.py`

- [ ] **VEGA-CDM-111 — Build a deterministic seeded battery-fault world with pack sensor drift, genuine heat, probe failure and mixed diagnoses**  
  **Done when:** Separate evaluator computes ground truth without running Vega.
- [ ] **VEGA-CDM-112 — Build delayed correction after plan but before execution with immutable prior proposal**  
  **Done when:** Stale action denied; only reauthorized corrected action can change terminal state.
- [ ] **VEGA-CDM-113 — Build copied-news false corroboration and a truly independent observer comparison**  
  **Done when:** Source-root ground truth distinguishes correlation from independence.
- [ ] **VEGA-CDM-114 — Build maintenance procedure world with multi-step prerequisites and incompatible actions**  
  **Done when:** Terminal grader requires all authorized effects in correct order.
- [ ] **VEGA-CDM-115 — Build repository dependency repair world where wrong change causes hidden failure**  
  **Done when:** Evaluator checks actual constrained patch result; agent sees only permitted readouts.
- [ ] **VEGA-CDM-116 — Build late federation, partition and clock-skew worlds with known_at/valid_at**  
  **Done when:** No future or unauthorized evidence exposed in actor observation.
- [ ] **VEGA-CDM-117 — Build confounded causation controls where semantic correlation has no causal effect**  
  **Done when:** Vega hypothesis cannot be certified by intervention oracle.
- [ ] **VEGA-CDM-118 — Build invariant negative controls (no-op, irrelevant event, swapped identifiers, permuted option order)**  
  **Done when:** No material causal effect reported for controls.
- [ ] **VEGA-CDM-119 — Generate adversarial paraphrase and negation families plus multilingual/format perturbations only when supported**  
  **Done when:** Separate family fingerprints and labels prevent leakage.
- [ ] **VEGA-CDM-120 — Implement independent world test harness checking no actor/evaluator module access paths**  
  **Done when:** Mutation tests attempt to leak hidden truth and must fail.

### S12. Fair baselines and agent outcome arms

**Implementation targets:** `benchmarks/vega_cdm_matched_arms.py`, `benchmarks/outcome_matched_arms_typed.py`, `tests/test_vega_matched_arms.py`

- [ ] **VEGA-CDM-121 — Preserve existing frozen A0–A7 meaning and add new registered A5-V and A6-V arms**  
  **Done when:** No historical baseline gets retroactively relabeled.
- [ ] **VEGA-CDM-122 — Compare A5-V against A5 and strongest fair A3, holding recovery features equal**  
  **Done when:** Run manifest records same world, agent and budget for comparisons.
- [ ] **VEGA-CDM-123 — Compare A6-V with A5-V and A6 to isolate semantic assistance to CDM**  
  **Done when:** Net measured incremental gain includes model and replay work.
- [ ] **VEGA-CDM-124 — Add retrieval-only lexical, full-context within budget, semantic rerank and simple heuristic controls**  
  **Done when:** No comparison against artificially weak retrieval alone.
- [ ] **VEGA-CDM-125 — Add Vega-versus-existing Kev/System-One and deterministic model alternatives when installed**  
  **Done when:** Adapters share typed decision contract and calibration protocol.
- [ ] **VEGA-CDM-126 — Compare zero-shot, recalibrated, shadow-trained and ablated Vega policies as distinct arms**  
  **Done when:** Report each arm's inference footprint and training data provenance.
- [ ] **VEGA-CDM-127 — Randomize model-call and world-order independently of treatment label while pairing task IDs**  
  **Done when:** Allocation and scheduling are reproducible from registered seeds.
- [ ] **VEGA-CDM-128 — Require equal model weights, quantization, context, prompt information, tool grants and number of attempts across causal arms**  
  **Done when:** Parity validator rejects mismatched configurations rather than reporting superiority.
- [ ] **VEGA-CDM-129 — Measure agent and world task completion, legitimate abstention, unsafe attempt, unsafe execution, false withholding and correction recovery**  
  **Done when:** All denominators and failure codes are explicit.
- [ ] **VEGA-CDM-130 — Calculate total model tokens, inference latency, CPU time, peak RSS, replay events and normalized compute cost**  
  **Done when:** Pareto report includes measured dimensions only; never fills missing cost with zero.

### S13. Real local-model teams and evidence

**Implementation targets:** `experiments/vega_cdm_real_agents.py`, `benchmarks/vega_cdm_model_report.py`, `tests/test_vega_local_agent.py`

- [ ] **VEGA-CDM-131 — Run model-free scripted contracts first and retain separate SCRIPTED status**  
  **Done when:** No simulated actor output is labeled as model inference.
- [ ] **VEGA-CDM-132 — Create a genuinely local Vega-U 0.8B smoke using actual checkpoint bytes and version hashes**  
  **Done when:** Model receipt reports actual decision result, latency, digest and hardware.
- [ ] **VEGA-CDM-133 — Add optional 4B model comparison only if within measured system memory budget**  
  **Done when:** Memory errors recorded as NOT_RUN/RESOURCE_LIMIT, not success.
- [ ] **VEGA-CDM-134 — Use existing local Ollama agent as observer/planner/executor and Vega as their typed advisor**  
  **Done when:** Separate session identities and exact-action grants verified on a real-model episode.
- [ ] **VEGA-CDM-135 — Record model and runtime digests, quantization, temperature, context budget, seed, prompt hashes and token accounting**  
  **Done when:** Every real-agent trial is reproducible up to documented nondeterminism.
- [ ] **VEGA-CDM-136 — Run three-agent correction-after-plan episode with actual model decisions in all compared arms**  
  **Done when:** Post-correction safe completion graded by independent evaluator.
- [ ] **VEGA-CDM-137 — Test Vega model outage, malformed response, cold load and missing checkpoint**  
  **Done when:** Fallback stays deterministic and reports INFERENCE_UNAVAILABLE without invented decisions.
- [ ] **VEGA-CDM-138 — Run at least two distinct local model sizes/families when available; otherwise report coverage gap**  
  **Done when:** No cross-model robustness claim from single checkpoint.
- [ ] **VEGA-CDM-139 — Keep all weights, prompts and state offline during evaluation; audit outbound connections**  
  **Done when:** Network allowlist and logging prove no hosted inference was invoked.
- [ ] **VEGA-CDM-140 — Separate completed real-agent matched experiments from one-call smoke tests and operator demos**  
  **Done when:** Research summary never treats smoke PASS as efficacy evidence.

### S14. Security, prompt injection and privacy

**Implementation targets:** `tests/test_vega_cdm_security.py`, `tools/vega_cdm_adversarial_gate.py`, `docs/VEGA_CDM_THREAT_MODEL.md`

- [ ] **VEGA-CDM-141 — Treat retrieved evidence as data, never instructions to the decision adapter**  
  **Done when:** Injected tool commands in state are not executed or surfaced as permissions.
- [ ] **VEGA-CDM-142 — Test model suggests unauthorized memory, erased content or inaccessible source**  
  **Done when:** Result suppressed and no semantic cache entry created.
- [ ] **VEGA-CDM-143 — Test malicious option text attempts to redefine authorization, evaluator labels or score direction**  
  **Done when:** Closed options and host validation reject unauthorized semantics.
- [ ] **VEGA-CDM-144 — Test evidence poisoning across summaries and cross-agent forwarded observations**  
  **Done when:** Copied origin remains linked; independent evidence requirement unaffected.
- [ ] **VEGA-CDM-145 — Test cross-tenant inference request and cache-key reuse by other principals**  
  **Done when:** No result, error metadata, timing or cache collision reveals restricted content.
- [ ] **VEGA-CDM-146 — Test model-output overflow, NaN/Infinity, invalid normalization and malformed conformal sets**  
  **Done when:** All invalid outputs become explicit safe failure.
- [ ] **VEGA-CDM-147 — Test malicious local HTTP server response and model ID substitution**  
  **Done when:** Pinned digest and URL constraints reject replay and spoofing.
- [ ] **VEGA-CDM-148 — Ensure actor cannot submit arbitrary Python callbacks, files or shell tools to CDM through Vega proposals**  
  **Done when:** Typed compiler and replay worker allowlist accept only declared operations.
- [ ] **VEGA-CDM-149 — Block hidden evaluator truth, rewards, future labels and valid-at future data from every Vega request**  
  **Done when:** Static and dynamic oracle-leak tests pass.
- [ ] **VEGA-CDM-150 — Retain separate governance and safety regression suites without reducing prior coverage**  
  **Done when:** ActionGate/erasure/federation regression results equal unmodified baseline.

### S15. Performance, runtime isolation and deployment

**Implementation targets:** `tools/vega_cdm_profile.py`, `src/memory_fabric/causal_replay/semantic/cache.py`, `docs/VEGA_CDM_OPERATIONS.md`

- [ ] **VEGA-CDM-151 — Measure cold and warm model startup plus batch decision latency for 0.8B on CPU/MPS where supported**  
  **Done when:** p50, p95, p99 with hardware/memory and model version pinned.
- [ ] **VEGA-CDM-152 — Measure Vega scoring once per state with multiple typed questions versus repeated single-question calls**  
  **Done when:** Batch amortization ratio and payload size recorded.
- [ ] **VEGA-CDM-153 — Measure peak resident memory, model size, CPU/GPU utilization, per-task work units and energy only if instrumented**  
  **Done when:** No fabricated hardware or power metrics.
- [ ] **VEGA-CDM-154 — Enforce limits on input context, candidate count, evidence count and output bytes before local inference**  
  **Done when:** Excess input returns bounded explicit status, no silent truncation.
- [ ] **VEGA-CDM-155 — Put inference behind separate optional process, with secure local transport and restart boundaries**  
  **Done when:** Inference crash cannot corrupt event log or action transaction.
- [ ] **VEGA-CDM-156 — Enforce OS time/process limits where available and explicitly mark absence on unsupported platforms**  
  **Done when:** Isolation report distinguishes sandbox, process and advisory limits.
- [ ] **VEGA-CDM-157 — Rate-limit tenants and isolate model cache by tenant/source hash, policy version and authorization scope**  
  **Done when:** Cross-tenant collision and erasure invalidation tests pass.
- [ ] **VEGA-CDM-158 — Compare end-to-end agent completion per unit cost with and without Vega; include cold start amortization**  
  **Done when:** Matched throughput and cost curves on 1/2/4 workers.
- [ ] **VEGA-CDM-159 — Establish fallback to deterministic recovery if Vega is slower than registered deadline or unavailable**  
  **Done when:** No actor hangs and baseline decision path remains usable.
- [ ] **VEGA-CDM-160 — Write hardware profiles for 16 GB Apple Silicon laptop and optional larger GPU host**  
  **Done when:** Only measured profiles make feasibility or throughput claims.

### S16. Preregistration, evaluation science and research reproducibility

**Implementation targets:** `research/prereg/vega-cdm-v1.json`, `benchmarks/vega_cdm_confirmatory.py`, `memeval/`, `tests/test_vega_cdm_science.py`

- [ ] **VEGA-CDM-161 — Define primary endpoint as evaluator-confirmed safely completed task cases across all eligible assigned cases**  
  **Done when:** Registration freezes denominator and no arbitrary exclusion of failures.
- [ ] **VEGA-CDM-162 — Choose strongest fair baseline using development data only and freeze selection before confirmatory evaluation**  
  **Done when:** No peeking at confirmatory outcomes or changing comparator afterward.
- [ ] **VEGA-CDM-163 — Register minimum practical gain, familywise alpha, Holm adjustment, cluster unit and confidence interval type**  
  **Done when:** Frozen manifest validates all fields and analysis code hashes.
- [ ] **VEGA-CDM-164 — Determine study power and minimum detectable effect from pilot discordance and effective independent world clusters**  
  **Done when:** memeval refuses underpowered confirmatory study.
- [ ] **VEGA-CDM-165 — Freeze world-family holdouts, seeds, task IDs, template fingerprints, model digests and all resource caps**  
  **Done when:** Manifest SHA-256 and source commit stamped before experiment.
- [ ] **VEGA-CDM-166 — Run positive controls, negative controls, oracle upper-bound checks and prompt-framing factorial controls**  
  **Done when:** Invalid ceiling, contamination or arm imbalance causes INVALID verdict.
- [ ] **VEGA-CDM-167 — Require A5-V outperform A5 and strongest fair A3 on primary terminal completion criterion**  
  **Done when:** If gain absent or interval includes no meaningful effect, status HOLD.
- [ ] **VEGA-CDM-168 — Require A6-V show additional net utility versus A5-V after replay+model cost and no safety regression**  
  **Done when:** Do not force promotion if counterfactual model is neutral or harmful.
- [ ] **VEGA-CDM-169 — Report safety uncertainty using exact one-sided upper bounds and registered attack-family effects**  
  **Done when:** Zero observed unsafe effects cannot be described as zero risk.
- [ ] **VEGA-CDM-170 — Archive all raw paired task rows, attempt history, model traces as content-safe hashes, manifests and failed/null runs**  
  **Done when:** Fresh checkout reproduces registered report or clearly states missing model.

### S17. Operator product integration, rollout and release

**Implementation targets:** `docs/VEGA_CDM_GUIDE.md`, `docs/VEGA_CDM_LIMITATIONS.md`, `tools/vega_cdm_gate.py`, `examples/vega_cdm_demo.py`

- [ ] **VEGA-CDM-171 — Implement one interactive local demo of correction, semantic hypothesis, candidate intervention, verified replay and decision repair**  
  **Done when:** Operator can distinguish model proposal from tested evidence and terminal outcome.
- [ ] **VEGA-CDM-172 — Display what the model suggested, independent verification result, source versions and reason to abstain**  
  **Done when:** UI never labels hypotheses as verified causal facts.
- [ ] **VEGA-CDM-173 — Expose read-only advisory output through existing authenticated agent client, without a new mutation endpoint**  
  **Done when:** No bypass of ActionGate or tenant credentials.
- [ ] **VEGA-CDM-174 — Provide opt-in feature flag for shadow/advisory use and per-workload ability to disable instantly**  
  **Done when:** Kill switch leaves baseline outputs and stored events unchanged.
- [ ] **VEGA-CDM-175 — Create a migration/compatibility guide for vega adapter and canonical outcome runtime**  
  **Done when:** No new default dependency or breaking API change.
- [ ] **VEGA-CDM-176 — Provide offline-first install instructions with predownloaded weight locations, hashes and model absence behavior**  
  **Done when:** Core install works without internet or external model.
- [ ] **VEGA-CDM-177 — Build exact-SHA qualification gate reporting CORE_PASS, MODEL_NOT_RUN, AGENT_NOT_RUN, RESEARCH_HOLD and RELEASE_NO_GO separately**  
  **Done when:** Green CI cannot be mistaken for model efficacy qualification.
- [ ] **VEGA-CDM-178 — Add automated docs consistency checks for model version, endpoint, report SHA and research claim labels**  
  **Done when:** Stale manifest or inaccurate claims block release evidence generation.
- [ ] **VEGA-CDM-179 — Keep outside-user pilot and third-party security certification explicitly separate from in-house checks**  
  **Done when:** External claims remain NO-GO absent real evidence.
- [ ] **VEGA-CDM-180 — Publish a final evidence matrix mapping every Vega-backed feature to implementation, test, model run, effect estimate and deployment qualification**  
  **Done when:** No task marked completed on documentation or a mock-only test alone.

## 6. Integration milestones and explicit stop conditions

| Gate | Required evidence | On failure |
|---|---|---|
| G0 baseline | Exact SHA, matched baselines, documented old negative CDM results | Do not develop on ambiguous baseline |
| G1 adapter | Real vega-U 0.8B local smoke or truthful MODEL_NOT_RUN; deterministic fixtures | Disable Vega; deterministic CDM unaffected |
| G2 causal hygiene | Provenance, time boundaries, source dedupe, independent replay verifier | No proposed edges labeled verified |
| G3 scripted usefulness | Paired agent recovery, correction, replay and negative control results | Keep OFF/SHADOW |
| G4 real-agent efficacy | Frozen paired A5-V vs A5/A3; measured safety and resource costs | No improvement claims; maintain OFF |
| G5 CDM increment | A6-V vs A5-V and A6, net utility with cost, exact-source receipts | Keep CDM conditional/explanation only |
| G6 operational | Process failure handling, runtime metadata, tenant leakage, CPU/memory limits, restore | No production rollout |
| G7 external deployment | Independent review, real pilot and approved scope | NO-GO; cannot be manufactured in-house |

**Launch policy:** implement in stages: OFF -> SHADOW (observe only) -> ADVISORY (non-authorizing) -> QUALIFIED_ADVISORY (internal use under measured conditions) -> a separate externally approved deployment. Under no stage does Vega become the action authorizer or an automatic memory-deletion authority.

## 7. Codex execution contract

1. Read `AGENTS.md`, `ARCHITECTURE.md`, the current repository files, existing contract tests and this plan. Confirm SHA before any edit. Do not assume proposed paths exist.
2. Work through task IDs in dependency order; prefer small, coherent commits with unit tests and one independent evaluator test per feature.
3. Preserve current API, ActionGate authorization, all prior negative results and the zero-mandatory-dependencies core; introduce third-party Vega code **only in the opt-in inference environment**.
4. Add no extra outcome protocol fork. Reuse `outcome_typed` provisionally unless a documented ADR and compat tests demonstrate another safer canonical home.
5. Stub-based tests are useful for contracts but cannot establish real-model performance. No installed checkpoint -> `MODEL_NOT_RUN`, not a fake passing result.
6. No network calls in default test suite. Never auto-download weights. The dedicated real-model job may run only with explicitly provisioned, checksum-verified local assets and loopback-only service.
7. Every experiment must bind source SHA, model digest, source packet digest, world/task split, versioned oracle, resources, raw per-task outcome and evaluation script hash.
8. Retain null/negative results; do not retune after confirmatory evaluation or move failed seeds to development. Escalate to `NOT_READY` rather than retroactively altering gates.
9. Emit a final evidence matrix with task IDs, changed files, exact tests and artifacts, effects, missing prerequisites, and an explicit GO/HOLD/NO-GO decision.
10. **Never claim production-ready** from this specification or a synthetic test suite. The external pilot and independent security review remain separate gates.

## 8. Source references checked when authoring

- Vega-U API and runtime: https://github.com/NandhaKishorM/vegaml/blob/main/README.md ; https://github.com/NandhaKishorM/vegaml/blob/main/docs/http-api.md ; https://github.com/NandhaKishorM/vegaml/blob/main/docs/vega-u.md
- Alternate, much larger Vega (different model family): https://vllm-sr.com/docs/model-runtime/supported-models/decision-2/vega-27b/
- Memory Fabric adapter, proposed decision model, replay and evidence boundary: https://github.com/crakashp2905-hub/memory-fabric/tree/main/src/memory_fabric
- Current CDM limitations: https://github.com/crakashp2905-hub/memory-fabric/blob/main/docs/CDM_KNOWN_FINDINGS.md
- Current outcome study register: https://github.com/crakashp2905-hub/memory-fabric/blob/main/research/prereg/agent-outcome-confirmatory-v1.json
- The existing broader agent-superiority plan can be used for shared non-Vega tasks: `MEMORY_FABRIC_NEXT_END_TO_END_AGENT_VALIDATION_CHECKLIST_2026-11-20.md`.

**Deliverables of this specification:** 180 tasks, matching CSV, first-party bounded architecture, fail-closed local Vega-U adapter, scientific baselines, in-house reproducibility and evidence-level limits. **No source edits or empirical claims are implied by this document.**
