# Memory Fabric × Vega-U — Next End-to-End Correctness and Agent-Effectiveness Checklist

**Version:** 2026-11-25 · **Purpose:** close the specific problems found in PR #41, then prove or reject the semantic CDM hypothesis.  
**Implementation size:** 160 atomic tasks / 16 workstreams / seven sequential gates.  
**Scope:** first-party Memory Fabric code and tests; optional locally served third-party Vega model, no hosted inference.  
**Start state:** merged `main` at `1cfb7dd3c6cdb8012ba63b9c0753a1eca3c69fc8` and open PR #41 at `1015a33447a1692457d33067b9e79066a5fbd7b0`.  
**Status:** specification, NOT a record of completed implementation or experimental success.

## 0. Executive decision

Do **not** merge a claim of Vega-assisted agent efficacy or enable Vega to influence consequential decisions from the present development results. The open PR #41 contains substantial code and local-model evidence, but its frozen **development** report shows A5-V safe success 0.893 versus A5 0.857 across 56 cases per arm, **with two unsafe Vega-influenced decisions where the A5 comparator had zero**. These mistakes came from treating readings spelled as *sixty-one degrees* and *sixty-four degrees* as not exceeding 50 °C. A5 and A5-V are otherwise not yet supported by a qualified real-agent study. A6 and A6-V did not show additional benefit in that benchmark.

**Crucial safety distinction:** The existing `ActionGate` can protect *executed tool effects* without protecting against dangerous **omission** (e.g., an incorrect `no_action` for a real overheating condition). This plan explicitly adds an independent observation/decision verification boundary while leaving governance permissions, historical truth and action grants untouched.

A second defect was observed: claim/validation identifiers can collapse `P7-A` and `P7-B` into `p7` when two separate sensors on one equipment record are parsed. The fix belongs in shared claim-identity infrastructure, not in a special Vega prompt.

## 1. Integration architecture

```text
Authorized source retrieval [unchanged] + current tenant/lifecycle checks
     |
     v
Bitemporal / source-root evidence packets with immutable version references
     |
     +--> Canonical typed observation extraction (sensor, quantity, unit, time)
     |      --> Independent hazard and omission guard
     |
     +--> Vega-U semantic hypotheses (optional; OFF/SHADOW by default)
                  --> schema/identity/numeric verification --> ranked proposal ONLY
     |
     v
Verified evidence status + bounded recovery / targeted re-retrieval
     |
     +--> Dependence-first CDM dispatch only if a material alternative exists
             --> simulator-conditional replay + independent certificate verifier
     |
     v
Agent replan with host-defined legal options --> fresh verification / ActionGate
     |
     v
Independent evaluator: safe completed task, justified abstention,
unsafe execution, unsafe omission, false denial, real cost / latency
```

**Non-negotiable invariants**

1. Vega never changes tenant permissions, evidence access, validity, source-root identity, memory deletion, correction history, grant issuance, or `ActionGate` semantics.
2. A semantic proposal cannot change an independently verified numeric fact, sensor identity, threshold comparison, or safety obligation.
3. `OFF` is default, `SHADOW` is observational, `ADVISORY` is labelled non-authorizing, and `QUALIFIED` remains refused until a new research gate passes.
4. The old failure rows and disqualified preregistration remain immutable; create a **new study**, do not retune against leaked confirmatory data.
5. Model-in-loop experiments require a real local model and pinned assets; scripted policies are useful contract tests but never count as learned-agent evidence.
6. Causal hypotheses are not causal effects; replay certificates are conditional on simulator assumptions and never claim physical causality.
7. All required experiments must report both actual task completion and safety outcomes; a high 'safe success' from correct abstention alone is insufficient.

## 2. Existing repository contracts to reuse

| Existing file / component | What it supplies | Planned extension |
|---|---|---|
| `src/memory_fabric/conflicts.py` and `validation.py` | Claim indexing and contradictions | Typed sensor/component identity, non-lossy canonicalization |
| `src/memory_fabric/causal_replay/semantic/support.py` | Candidate semantic labels and lexical guard | Independently verifiable numeric/identity constraints |
| `src/memory_fabric/causal_replay/semantic/packets.py` | Authorized, bitemporal model inputs | Structured observation references with source-span provenance |
| `src/memory_fabric/adapters/vega_u.py` | Local `/v1/decide` client and model pins | Calibration, failure handling and local performance validation |
| `src/memory_fabric/outcome_typed/semantic_advisory.py` | OFF/SHADOW/ADVISORY controls | Never allow semantic label to become hazard clearance |
| `src/memory_fabric/outcome_typed/cdm_dispatch.py` | Dependence-first replay dispatch and utility | Validate only beneficial replay under matched costs |
| `benchmarks/vega_cdm_matched_arms.py` | A3/A5/A5-V/A6/A6-V/A7 evaluator | Isolate deterministic parser gains and harmful omission |
| `benchmarks/vega_cdm_confirmatory.py` | Fail-closed preregistration validator | New v2 study, powered local-agent runs and two-sided safety accounting |
| `tools/vega_cdm_gate.py` | Separate technical/evidence/release verdicts | Source-bound regression and efficacy qualification |

**Version handling:** `src` paths under PR #41 are not necessarily in merged `main` yet. Start from the PR head, rebase carefully, and preserve all existing security tests; never silently treat PR files as shipped capabilities.

## 3. Seven acceptance gates (all must be independently reported)

| Gate | Label | Required output / stop condition |
|---|---|---|
| G0 | Baseline evidence frozen | Source and model digests pinned; reproduce the two unsafe omissions and sensor collision or record a falsifiable discrepancy. |
| G1 | Semantic correctness | Typed quantities / units / identities verified; all registered known regressions blocked from false-safe decisions. |
| G2 | Safety invariants | Existing governance unchanged; omission-hazard, cross-tenant and adverse-prompt tests pass; no new unsafe outcome on development suite. |
| G3 | Model feasibility | Pinned Vega local-model performance and calibration study complete; real-model missing → MODEL_NOT_RUN. |
| G4 | Agent efficacy | New, powered, matched local-agent study shows registered positive safe **completion** gain versus strongest fair baseline and no safety regression. |
| G5 | Causal CDM value | Incremental A6-V versus A5-V improvement net of replay cost, not merely decision flips; absent gain → optional CDM only. |
| G6 | Product rollout | Replay isolation, measured operating envelope, reproducible release evidence and independent review; otherwise deployment HOLD. |

Gate semantics: `CORE_PASS`, `MODEL_NOT_RUN`, `RESEARCH_HOLD`, `RESEARCH_NO_GO`, and `RELEASE_NO_GO` are different statements. An observed absence of unsafe events requires an uncertainty bound; it is not proof of zero risk.

## 4. Suggested metrics and claim thresholds

- **Safety:** no increase in *unsafe execution* or *unsafe omission* on development gate; on confirmatory data, satisfy **preregistered** risk noninferiority with confidence bounds and failure-family checks. A few dozen successful cases do not establish a rare-harm rate.
- **Benefit:** candidate A5-V must beat the strongest development-selected fair baseline (including A3 and A5 and the deterministic numeric-parser arm) on held-out *safe task completion*, with positive lower clustered confidence bound and a minimum practical effect fixed before holdout; 5 percentage points is a candidate planning margin only if oracle headroom and power support it.
- **CDM:** A6-V must outperform A5-V in held-out decision utility after replay expense and harm penalty; non-positive utility means keep CDM advisory.
- **Calibration:** Brier, ECE, selective risk, false-safe rate, and abstention coverage by family, including numeric paraphrases and shifted phrasing; no untuned vendor calibration claim.
- **Runtime:** p50/p95/p99 end-to-end latency, local model RSS / swap, model calls, inference tokens where measured, replay calls and cost, exact hardware/threads. The previous 0.8B host reported roughly 4.17 seconds per batched decision and 5.3 GiB RSS; those are **not** Mac M4 measurements.
- **Data integrity:** zero accidental tenant disclosure; source-root copies do not count as independent corroboration; erasure and correction invalidate model inputs and caches.

## 5. Codex execution contract

- Work one workstream at a time, in sequence for P0 items; commit with `Wxx-NN` IDs. Complete a task only with a passing, named test or measured artifact bound to an exact SHA.
- New files marked `(NEW)` are suggested paths, not already-verified source files. Existing sources are targets for modification rather than instructions to rewrite them wholesale.
- No new mandatory pip dependencies in the core. Optional Vega serving stays separate and local. Use the existing Python test stack and public agent adapters; do not invent real-model results if weights aren't present.
- Keep explicit failure results and source manifests under versioned `research/results/vega-cdm/next/` paths. Never overwrite `development/vega-0.8b.json` or edit the v1 preregistration to make it pass.
- Run unit/contract gates before local-model benchmarks, exploratory development before frozen holdout, and release qualification last.
- If results disconfirm a hypothesis, mark `NO_GO` and retain the null/negative result. Do not optimize indefinitely on holdout seeds.

## 6. Atomic implementation checklist

### W01 — Freeze evidence, reproduce failures and separate claims

**Priority:** P0  
**Primary implementation targets:** `research/results/vega-cdm/; research/results/agent-outcomes/; tools/vega_cdm_gate.py`  
**Required test suite:** `tests/test_vega_ledger_and_gate.py`
- [ ] **W01-01 — Freeze the merged main and PR #41 source SHAs as two separate baselines.**  
  **Acceptance:** Evidence manifests bind tree SHA, dirty state, python/runtime, model digest, and benchmark input hashes.
- [ ] **W01-02 — Reproduce the 56-case vega-U development run with its recorded model pins.**  
  **Acceptance:** Raw per-task rows identify both unsafe hot-battery omissions; mismatch is explicitly investigated and reported.
- [ ] **W01-03 — Preserve the original negative experiment unchanged.**  
  **Acceptance:** No development, test or research artifact is overwritten; a new candidate and result directory is created.
- [ ] **W01-04 — Validate the two failed readings from raw actor-visible evidence.**  
  **Acceptance:** Store exact input text, hidden evaluator truth separately, proposal, selected action, result, and signed-off failure classification.
- [ ] **W01-05 — Trace each unsafe result from packet to parse_semantic to decide to terminal grade.**  
  **Acceptance:** A machine-readable call graph records the precise transition where evidence meaning was lost.
- [ ] **W01-06 — Reproduce the P-7 probe A versus probe B collision through the real write validator.**  
  **Acceptance:** Before-fix regression tests fail in the expected way and cite actual written/withheld memory IDs.
- [ ] **W01-07 — Inventory existing parsing and claim-index implementations before adding new parsers.**  
  **Acceptance:** Architecture report distinguishes conflicts.claim, validation, typedclaims, semantic.support and benchmark-specific parsers.
- [ ] **W01-08 — Record previous A5, A3, A6 and Vega model result populations independently.**  
  **Acceptance:** All comparisons specify tasks, seeds, learning status, source SHA, budget, and intended inference level.
- [ ] **W01-09 — Audit the currently open PR CI at its exact head revision.**  
  **Acceptance:** CI state recorded as PASS, FAIL, or INCOMPLETE per job; queued jobs are never counted as passed.
- [ ] **W01-10 — Publish the exact baseline risk register with test owner and stop rule.**  
  **Acceptance:** Both unsafe examples and the identity collision appear as blocking P0 issues with immutable reproduction steps.

### W02 — Build canonical typed numerical observation extraction

**Priority:** P0  
**Primary implementation targets:** `src/memory_fabric/causal_replay/semantic/observations.py (NEW); semantic/support.py; benchmarks/vega_cdm_matched_arms.py`  
**Required test suite:** `tests/test_semantic_quantities.py (NEW)`
- [ ] **W02-01 — Specify a typed observation record with subject, sensor, property, value, unit, relation and timestamp.**  
  **Acceptance:** Round-trip schema rejects unscoped quantities, unknown units and malformed timestamps for consequential reasoning.
- [ ] **W02-02 — Parse digit-based integers, decimals and signed quantities using a deterministic grammar.**  
  **Acceptance:** Inputs including 61 C, -4.5 C, 50.0 C and 1,250 mA round-trip to exact normalized values.
- [ ] **W02-03 — Parse supported English number words and hyphenated forms without an LLM.**  
  **Acceptance:** Sixty-one, sixty-four, fifty, one hundred and two, and negative five map deterministically or return UNKNOWN.
- [ ] **W02-04 — Normalize Celsius, Fahrenheit, kelvin and sensor-specific unit aliases.**  
  **Acceptance:** Equivalent temperatures map correctly; unsupported or dimensionally incompatible conversions abstain.
- [ ] **W02-05 — Represent comparisons as typed interval constraints rather than boolean guesses.**  
  **Acceptance:** >50, >=50, <=50, exactly 50, around 50 and below 50 have distinct evaluator outcomes.
- [ ] **W02-06 — Handle double negation, uncertainty, ranges and hedged quantities explicitly.**  
  **Acceptance:** Ambiguous expressions remain UNKNOWN; ranges crossing a threshold cannot be classified safe.
- [ ] **W02-07 — Carry extraction provenance as exact substrings, offsets and source-version references.**  
  **Acceptance:** Every extracted value is tied to a visible span; synthetic or fabricated digits cannot pass validation.
- [ ] **W02-08 — Cross-check Vega boolean hot/cold proposals against the parsed numeric predicate.**  
  **Acceptance:** A disagreement cannot yield an actionable false-safe classification; it triggers dispute or escalation.
- [ ] **W02-09 — Prevent false-negative high-risk outcomes when extraction fails.**  
  **Acceptance:** Malformed, out-of-vocabulary or missing quantities route to RECHECK/ABSTAIN instead of no_action.
- [ ] **W02-10 — Build metamorphic and fuzz tests for numbers, punctuation, paraphrases and thresholds.**  
  **Acceptance:** Properties pass for hundreds of generated equivalent sentences; known 61/64 regressions are pinned.

### W03 — Preserve entity identity and correct claim indexing

**Priority:** P0  
**Primary implementation targets:** `src/memory_fabric/conflicts.py; validation.py; typedclaims.py; causal_replay/semantic/entities.py (NEW)`  
**Required test suite:** `tests/test_sensor_entity_claims.py (NEW)`
- [ ] **W03-01 — Define an entity hierarchy for equipment, pack, module, probe and measured property.**  
  **Acceptance:** Schema models pack P-7 / probe A separately from P-7 / probe B with stable parent-child relationships.
- [ ] **W03-02 — Retain original identifier spellings and canonical IDs without lossy splitting.**  
  **Acceptance:** P7-A and P7-B canonicalize to different IDs, while approved aliases map to the correct same sensor.
- [ ] **W03-03 — Add a typed claim identity key including sensor and property scope.**  
  **Acceptance:** Claims with different sensors do not collide, while conflicting same-sensor readings stay comparable.
- [ ] **W03-04 — Revise conflicts.claim to preserve nested sensor qualifiers and component relationships.**  
  **Acceptance:** P-7 probe A 61 C and probe B 64 C do not become one contradictory assertion.
- [ ] **W03-05 — Update validation._same_claim and _same_parameter to respect typed identity.**  
  **Acceptance:** Different sensors are independent parameters; changed values for the same probe stay reviewable.
- [ ] **W03-06 — Update _ClaimIndex to store versioned typed keys and safe backfill results.**  
  **Acceptance:** New lookups are correct; old records remain readable without rewriting or declassifying them.
- [ ] **W03-07 — Keep corroboration independent of copied source roots and renamed sensors.**  
  **Acceptance:** Aliases or federation copies from the same origin count as one root, never as extra corroboration.
- [ ] **W03-08 — Preserve existing status and access restrictions during reindex and retrieval.**  
  **Acceptance:** Tenant separation, withheld, erased, corrected, and revoked records remain inaccessible as before.
- [ ] **W03-09 — Design a migration preview and rollback strategy for existing identity indexes.**  
  **Acceptance:** Dry-run reports collision counts and affected claims; rollback restores exact old query behavior.
- [ ] **W03-10 — Test mixed-version, cross-tenant, alias, case and Unicode identifier adversaries.**  
  **Acceptance:** No two distinct sensors coalesce and no equivalent known sensor is fragmented without explicit ambiguity.

### W04 — Add a deterministic semantic-evidence verification boundary

**Priority:** P0  
**Primary implementation targets:** `src/memory_fabric/causal_replay/semantic/support.py; packets.py; advice.py; verified_observations.py (NEW)`  
**Required test suite:** `tests/test_semantic_verification.py (NEW)`
- [ ] **W04-01 — Introduce an evidence verification result distinct from a Vega support proposal.**  
  **Acceptance:** Each candidate is VERIFIED, DISPUTED, UNKNOWN or INAPPLICABLE with independent evidence references.
- [ ] **W04-02 — Reject unsupported unit, quantity, polarity and entity assertions regardless of Vega confidence.**  
  **Acceptance:** A high-confidence incompatible proposal cannot become VERIFIED in unit and metamorphic tests.
- [ ] **W04-03 — Separate semantic similarity from factual entailment and usable action evidence.**  
  **Acceptance:** High relevance alone never satisfies source identity, freshness, or typed numeric predicates.
- [ ] **W04-04 — Gate numerical conclusions on independent verified spans and exact predicates.**  
  **Acceptance:** Model can nominate evidence but final hot/cold interpretation derives from typed observations.
- [ ] **W04-05 — Handle time-scoped evidence and superseded or withdrawn versions separately.**  
  **Acceptance:** Historical inference follows known_at and valid_at; present-day authorization is always rechecked.
- [ ] **W04-06 — Detect contradictions between multiple independent sensors without selecting a winner.**  
  **Acceptance:** Conflicting verified measurements produce CONTESTED until a scoped resolution policy applies.
- [ ] **W04-07 — Make abstention a typed result with a next permitted recovery action.**  
  **Acceptance:** UNKNOWN includes RE_RETRIEVE, CHECK_SOURCE, or ASK; never translates silently to no_action.
- [ ] **W04-08 — Reject missing, duplicate, NaN, renormalized or substituted Vega answer fields.**  
  **Acceptance:** Parser returns INVALID or UNAVAILABLE and records reason; no unspecified value is inferred.
- [ ] **W04-09 — Bind all model proposals to input bundle, model version and policy digests.**  
  **Acceptance:** Changing a single evidence version or model identity invalidates the advisory receipt.
- [ ] **W04-10 — Prove deterministic OFF/SHADOW parity against pre-Vega output.**  
  **Acceptance:** OFF byte-identical; SHADOW never changes action, retrieval, authorization or stored state.

### W05 — Protect against dangerous omission and inaction decisions

**Priority:** P0  
**Primary implementation targets:** `benchmarks/vega_cdm_matched_arms.py; src/memory_fabric/outcome_typed/episode.py; outcome_typed/semantic_advisory.py`  
**Required test suite:** `tests/test_omission_safety.py (NEW)`
- [ ] **W05-01 — Define omission hazards separately from executed prohibited tool effects.**  
  **Acceptance:** Terminal evaluator labels harmful no_action, timeout, missed intervention and unsafe tool execution separately.
- [ ] **W05-02 — Implement a host-defined hazard policy for high-stakes no_action proposals.**  
  **Acceptance:** If verified high-risk evidence exists, a no_action proposal is blocked from being treated as safely completed.
- [ ] **W05-03 — Require a current verified negative finding before closing a high-risk task as safe.**  
  **Acceptance:** Absent, contradicted, or unverified sensor readings cannot justify SAFE_NO_ACTION.
- [ ] **W05-04 — Make the semantic advisor incapable of lowering previously verified hazard severity.**  
  **Acceptance:** A model answer cannot turn VERIFIED_HAZARD into SAFE without an independent updated observation.
- [ ] **W05-05 — Define a safe escalation when a hazardous interpretation is ambiguous.**  
  **Acceptance:** System returns REVIEW_REQUIRED or REQUEST_MEASUREMENT with bounded retries rather than false-safe action.
- [ ] **W05-06 — Model detection obligations and time-to-response alongside authorization.**  
  **Acceptance:** Evaluator counts correct actions and required timely interventions, not only denied or allowed calls.
- [ ] **W05-07 — Add adversarial tests for adversary-supplied reassuring text next to high readings.**  
  **Acceptance:** Prompt manipulation and high confidence do not suppress verified hot readings.
- [ ] **W05-08 — Audit every host tool and decision mode for noop/abstain semantics.**  
  **Acceptance:** No_action, abstain, do_nothing and missing_response are distinguished and audited.
- [ ] **W05-09 — Replay both known hot-temperature failures against the omission guard.**  
  **Acceptance:** The two original unsafe terminal outcomes become safe abstentions or correct interventions without relaxing ActionGate.
- [ ] **W05-10 — Document why zero observed unsafe events does not prove zero risk.**  
  **Acceptance:** Research report includes the exact confidence bound denominator and hazard-family coverage.

### W06 — Harden Vega-U local adapter, identity and calibration

**Priority:** P0  
**Primary implementation targets:** `src/memory_fabric/adapters/vega_u.py; causal_replay/semantic/calibration.py; tools/vega_cdm_profile.py`  
**Required test suite:** `tests/test_vega_u_adapter.py; tests/test_vega_calibration.py (NEW)`
- [ ] **W06-01 — Keep Vega in separate local optional environment and pin model/runtime asset digests.**  
  **Acceptance:** Core imports and wheel install without weights, torch or a serving process; exact model pins are recorded.
- [ ] **W06-02 — Validate server identity plus local model artifact digests where owned by host.**  
  **Acceptance:** Reported remote digest is not misrepresented as trusted attestation; unsupported claims cause INFERENCE_UNAVAILABLE.
- [ ] **W06-03 — Apply bounded timeouts, byte limits, retries and circuit breaker to inference.**  
  **Acceptance:** Network stalls, schema errors and overload cannot hang an episode or authorize a fallback.
- [ ] **W06-04 — Record full label distribution, prediction set, abstention and unbound status.**  
  **Acceptance:** No forced scalar conversion of distribution to decisive yes/no when labels are ambiguous.
- [ ] **W06-05 — Build task-specific calibration dataset from development worlds only.**  
  **Acceptance:** Calibrator uses no confirmatory examples; reports Brier, ECE, AUROC and per-family reliability.
- [ ] **W06-06 — Evaluate calibration and selective risk under domain shift and paraphrase shifts.**  
  **Acceptance:** Thresholds and coverage curves are measured on disjoint calibration and validation worlds.
- [ ] **W06-07 — Compare zero-shot Vega, calibrated Vega and deterministic-verifier hybrid.**  
  **Acceptance:** Same tasks/budgets; report accuracy, safety, latency and abstention without winner-picking after holdout.
- [ ] **W06-08 — Add workload-aware optional inference caching keyed by authorized evidence and pins.**  
  **Acceptance:** Cache cannot return stale, erased or cross-tenant information; mutation and TTL tests pass.
- [ ] **W06-09 — Handle unavailable local models with explicit non-model qualification labels.**  
  **Acceptance:** MODEL_NOT_RUN is preserved rather than replaced by a scripted or mocked PASS.
- [ ] **W06-10 — Measure 0.8B on the target 16 GB laptop and optional 4B only if feasible.**  
  **Acceptance:** Actual RSS, cold-start, p50/p95, inference time and energy-if-instrumented reported per host.

### W07 — Build high-fidelity causal hypotheses with epistemic labels

**Priority:** P1  
**Primary implementation targets:** `src/memory_fabric/causal_replay/semantic/graph.py; beliefs.py; taxonomy.py; decision_records.py`  
**Required test suite:** `tests/test_vega_cdm_science.py; tests/test_causal_graph_constraints.py (NEW)`
- [ ] **W07-01 — Distinguish association, dependency, causal hypothesis and simulator-verified effect in types.**  
  **Acceptance:** No API method can silently upcast one epistemic tier to another.
- [ ] **W07-02 — Capture typed evidence-to-belief and belief-to-decision edges with event-time scope.**  
  **Acceptance:** Every edge records source versions, authorization epoch, policy and confidence provenance.
- [ ] **W07-03 — Nominate multiple alternative causes from corroborated and conflicting observations.**  
  **Acceptance:** Sensor bias and true overheating coexist as separate hypotheses until tested.
- [ ] **W07-04 — Preserve temporal ordering and forbid obvious backward-causal edges.**  
  **Acceptance:** Future observations do not become known causes of earlier decisions; known-at and valid-at are distinct.
- [ ] **W07-05 — Explicitly track confounding, selection bias and missing observations.**  
  **Acceptance:** Unknown latent causes prevent unwarranted real-world causal conclusions.
- [ ] **W07-06 — Deduplicate copied explanations and repeated model proposals by origin.**  
  **Acceptance:** Twenty paraphrases from one originating tool remain one evidence root.
- [ ] **W07-07 — Require candidate causal claims to cite an authorized evidence bundle.**  
  **Acceptance:** Orphan, withheld or erased evidence cannot support a newly emitted hypothesis.
- [ ] **W07-08 — Model both intervenable and non-intervenable nodes with typed constraints.**  
  **Acceptance:** Only registered legal interventions can be compiled; irrelevant hypothetical changes are refused.
- [ ] **W07-09 — Expose human-readable rationale and uncertainty without reproducing private evidence.**  
  **Acceptance:** Logs are content-safe; stored causal edges retain internal references only.
- [ ] **W07-10 — Test copy invariance, temporal reversals and confounded worlds.**  
  **Acceptance:** False causal edges remain hypotheses; approved causal effects appear only after verifiable simulation.

### W08 — Prove that selective CDM replay adds measurable value

**Priority:** P1  
**Primary implementation targets:** `src/memory_fabric/outcome_typed/cdm_dispatch.py; causal_replay/semantic/scheduler.py; effects.py; benchmarks/vega_cdm_matched_arms.py`  
**Required test suite:** `tests/test_outcome_cdm_dispatch.py; tests/test_vega_cdm_science.py`
- [ ] **W08-01 — Keep CDM independent of Vega and advisory-only.**  
  **Acceptance:** Deterministic replay remains usable without a model; all outputs are non-authorizing.
- [ ] **W08-02 — Implement dependence-first candidate pruning before any model-ranked intervention.**  
  **Acceptance:** Independent decisions produce zero model calls and zero replays under matched budgets.
- [ ] **W08-03 — Nominate replay candidates only among legally typed interventions.**  
  **Acceptance:** Unsupported state modifications return NON_REPLAYABLE or INVALID_INTERVENTION.
- [ ] **W08-04 — Require historical capture completeness and replay-fidelity evidence.**  
  **Acceptance:** A partial external-model trace cannot be reported as an exact deterministic replay.
- [ ] **W08-05 — Verify replay certificates independently from the replay executor.**  
  **Acceptance:** Corrupted state, fabricated action flip and stale policy digests fail validation.
- [ ] **W08-06 — Measure decision flips, real terminal outcomes and replay costs separately.**  
  **Acceptance:** A policy flip without better terminal outcome yields zero completion benefit.
- [ ] **W08-07 — Run oracle-hypothesis and random/recency/dependence baselines with shared budgets.**  
  **Acceptance:** Vega intervention ranking only earns gain over a fair strongest comparator.
- [ ] **W08-08 — Create causal worlds with actual headroom for a replay benefit.**  
  **Acceptance:** For each family oracle gain over no-replay is measured and predeclared before holdout.
- [ ] **W08-09 — Implement no-benefit skip rules and cost-aware early termination.**  
  **Acceptance:** When re-retrieval already resolves a change, CDM is skipped; p95 cost is bounded and logged.
- [ ] **W08-10 — Require positive net utility with no safety regression before enabling CDM in workflows.**  
  **Acceptance:** Gated comparison A6 vs A5 and A6-V vs A5-V meets registered effect and cost thresholds.

### W09 — Integrate semantic recovery into the canonical agent runtime

**Priority:** P1  
**Primary implementation targets:** `src/memory_fabric/outcome_typed/episode.py; semantic_advisory.py; diagnosis.py; replan.py; api.py`  
**Required test suite:** `tests/test_outcome_episode.py; tests/test_vega_recovery.py`
- [ ] **W09-01 — Use outcome_typed as the canonical runtime; do not introduce another package.**  
  **Acceptance:** Previous agent_outcomes and outcome_protocol imports pass compatibility tests or are clearly deprecated.
- [ ] **W09-02 — Add typed recovery intents with host-defined legal tool catalogs.**  
  **Acceptance:** Vega can propose but cannot create permissions, arbitrary tools or evaluator-side data.
- [ ] **W09-03 — Distinguish no relevant evidence, access-denied evidence, stale evidence and contradictions.**  
  **Acceptance:** Each cause maps to a different lawful recovery procedure and stable operator reason.
- [ ] **W09-04 — Integrate deterministic verified observations before semantic decisions.**  
  **Acceptance:** Agent step receives fact status and provenance, not an unverified model truth assertion.
- [ ] **W09-05 — Implement bounded observe–diagnose–recover–replan–verify–act loops.**  
  **Acceptance:** Maximum steps, memory exposure and model calls enforced with terminal reason codes.
- [ ] **W09-06 — Trigger replan on exact corrected evidence-version reliance.**  
  **Acceptance:** Merely seeing a corrected memory without relying on it does not trigger a pointless replan.
- [ ] **W09-07 — Reauthorize any consequential action at effect time.**  
  **Acceptance:** The unchanged ActionGate verifies principal, resource, evidence and exact action parameters.
- [ ] **W09-08 — Separate safe abstention from harmful omission in terminal metrics.**  
  **Acceptance:** Actor cannot mark itself successful; independent evaluator grades final world state.
- [ ] **W09-09 — Keep agent-model prompts, observations and tools equal across comparison arms.**  
  **Acceptance:** Vega treatment is the only relevant difference between A5 and A5-V.
- [ ] **W09-10 — Run scripted and genuine local-model three-role agent episodes.**  
  **Acceptance:** Every role has distinct actor identity and bounded allowed tool scope; evidence and grades stay sealed.

### W10 — Expand semantic, safety and causal benchmark worlds

**Priority:** P0  
**Primary implementation targets:** `benchmarks/vega_cdm_worlds.py; benchmarks/outcome_worlds_extra.py; research/fixtures/vega-hard-cases/ (NEW)`  
**Required test suite:** `tests/test_vega_worlds_and_arms.py; tests/test_semantic_world_properties.py (NEW)`
- [ ] **W10-01 — Retain existing 7-family worlds solely as development/regression evidence.**  
  **Acceptance:** Original 56 per-arm rows remain accessible but never serve as new confirmatory holdout.
- [ ] **W10-02 — Add numeric paraphrases covering number words, spelled fractions, negatives and decimals.**  
  **Acceptance:** Each variant includes an independently generated typed ground truth and literal input text.
- [ ] **W10-03 — Add unit conversion, comparison-boundary and rounding worlds.**  
  **Acceptance:** Exactly 50 C and slightly above/below boundaries grade differently as specified.
- [ ] **W10-04 — Add multiple sensor, nested equipment and swapped-identifier cases.**  
  **Acceptance:** Each sensor identity is independently preserved under all allowed aliases and mixed notation.
- [ ] **W10-05 — Add stale calibration, replacement sensor and false reassurance scenarios.**  
  **Acceptance:** Ground truth distinguishes measured hazard, faulty reading and unknown state.
- [ ] **W10-06 — Add time-window cases where old and new observations are both true at their times.**  
  **Acceptance:** The evaluator tests historical answer versus present decision separately.
- [ ] **W10-07 — Add repeated copied evidence, correlated sources and two-source collusion.**  
  **Acceptance:** Source independence cannot be amplified by repetition, restatement or federation.
- [ ] **W10-08 — Add prompt-injection, provenance spoofing and mixed-trust tool-output cases.**  
  **Acceptance:** Model never sees sealed truth or unauthorized material; unsafe proposals are recorded.
- [ ] **W10-09 — Add partially observed, indistinguishable and genuinely irrecoverable cases.**  
  **Acceptance:** Correct abstention is graded independently from success; oracle headroom reported per family.
- [ ] **W10-10 — Create disjoint generator templates and verify holdout fingerprint non-overlap.**  
  **Acceptance:** No development prompt, world template or equivalent paraphrase leaks into the confirmatory set.

### W11 — Run fair matched arms and isolate each effect

**Priority:** P0  
**Primary implementation targets:** `benchmarks/vega_cdm_matched_arms.py; outcome_arms.py; outcome_ablation.py; outcome_scorecard.py`  
**Required test suite:** `tests/test_outcome_matched_arms.py; tests/test_vega_worlds_and_arms.py`
- [ ] **W11-01 — Keep established A0–A7 definitions stable and add -V suffixes without reinterpreting baselines.**  
  **Acceptance:** Arm registry checksum matches preregistration and comparator semantics across versions.
- [ ] **W11-02 — Compare A3, A5, A5-V, A6, A6-V and A7 on the same tasks.**  
  **Acceptance:** All eligible cases assigned identically; evaluator truth is not actor-visible.
- [ ] **W11-03 — Define a fair deterministic numeric-parser baseline before evaluating Vega.**  
  **Acceptance:** Any gain attributable to a cheap parser is not falsely attributed to Vega semantic intelligence.
- [ ] **W11-04 — Include hybrid verifier + Vega as separate experimental treatment.**  
  **Acceptance:** Ablation isolates verifier, model and CDM effects without conflating components.
- [ ] **W11-05 — Enforce equal available retrieval, token, inference and wall-time budgets.**  
  **Acceptance:** Parity manifest records actual consumption; over-budget attempts are failures, not omissions.
- [ ] **W11-06 — Report completion, justified refusal, false withholding, omission risk and unsafe action separately.**  
  **Acceptance:** Every numerator/denominator and eligibility rule is published per arm and task family.
- [ ] **W11-07 — Include matched no-model, shuffled-advice and wrong-confidence negative controls.**  
  **Acceptance:** A new model must outperform placebo advice and simple deterministic recovery.
- [ ] **W11-08 — Report per-task paired differences and between-world variation.**  
  **Acceptance:** No duplicate seed is treated as an independent task when policy and world are identical.
- [ ] **W11-09 — Compare semantic performance on distinct model sizes and prompt representations.**  
  **Acceptance:** Report whether model benefits survive prompt changes and model-family changes without retuning holdout.
- [ ] **W11-10 — Make every arm reproducible from frozen task and source manifests.**  
  **Acceptance:** Per-run model digest, calibration split, tokenizer options, tool schemas, and RNG status are preserved.

### W12 — Preregister and execute statistical real-agent validation

**Priority:** P0  
**Primary implementation targets:** `research/prereg/vega-cdm-v2.json (NEW); research/prereg/agent-outcome-confirmatory-v2.json; benchmarks/vega_cdm_confirmatory.py`  
**Required test suite:** `tests/test_vega_cdm_science.py; tests/test_confirmatory_freeze.py (NEW)`
- [ ] **W12-01 — Create a new v2 Vega registration instead of editing the disqualified v1 study.**  
  **Acceptance:** V1 remains DRAFT/NO_GO with its known unsafe model configuration and observed results.
- [ ] **W12-02 — Select primary safe-completion and separate severe-hazard endpoints before sampling holdout.**  
  **Acceptance:** No posthoc metric swapping; unsafe omissions and unsafe executions are independent blocking outcomes.
- [ ] **W12-03 — Estimate baseline discordance and oracle headroom using development-only data.**  
  **Acceptance:** Power report justifies sample count for predeclared effect size and cluster structure.
- [ ] **W12-04 — Freeze evaluation units, stratification, exclusions, resource caps and stopping rules.**  
  **Acceptance:** Manifest SHA covers study design, models, prompts, tools, datasets, thresholds and analysis code.
- [ ] **W12-05 — Choose strongest fair baseline using development results only.**  
  **Acceptance:** Selection rule and candidate-control list are locked before confirmatory evaluation.
- [ ] **W12-06 — Run small local-model feasibility pilots with recorded failures.**  
  **Acceptance:** Prompts and policy can be refined only on development or designated pilot splits.
- [ ] **W12-07 — Execute a new matched learned-agent study with the pinned local checkpoint.**  
  **Acceptance:** The real local model produces full actor traces on every assigned case; failures remain in the denominator.
- [ ] **W12-08 — Analyze world-cluster paired gains with multiplicity and risk controls.**  
  **Acceptance:** Correct family-wise adjustment, uncertainty intervals and noninferiority checks are applied as preregistered.
- [ ] **W12-09 — Publish safety risk upper bounds and per-hazard false-negative counts.**  
  **Acceptance:** Zero observed events is accompanied by finite-sample upper confidence bounds, never labelled zero risk.
- [ ] **W12-10 — Allow READY only when all required gates pass without retuning on confirmatory data.**  
  **Acceptance:** Otherwise gate returns HOLD/NO_GO and prescribes new prospective study, not rerun-until-pass.

### W13 — Secure governance, privacy, isolation and action parity

**Priority:** P0  
**Primary implementation targets:** `src/memory_fabric/causal_replay/semantic/packets.py; adapters/vega_u.py; outcome_typed/api.py; tools/vega_cdm_gate.py`  
**Required test suite:** `tests/test_vega_cdm_security.py; tests/test_outcome_authorization_typed.py`
- [ ] **W13-01 — Prove Vega OFF/SHADOW adds no write, deletion, grant, tool execution or policy mutation.**  
  **Acceptance:** Baseline ActionGate decisions remain byte-identical over a registered security matrix.
- [ ] **W13-02 — Verify current authorization before every inference and cache hit.**  
  **Acceptance:** Revoked, erased or foreign-tenant evidence never appears in model input or cached advisory.
- [ ] **W13-03 — Test malicious evidence instructions that impersonate model or governance metadata.**  
  **Acceptance:** Schema rejects authority claims and tool instructions even when embedded in quoted text.
- [ ] **W13-04 — Constrain optional local-server use to loopback and bypass outbound proxies.**  
  **Acceptance:** No remote egress, DNS fallback, redirect or proxy route is usable by the optional adapter.
- [ ] **W13-05 — Treat the model server as an untrusted process absent independent attestation.**  
  **Acceptance:** Pin files and validate responses without asserting cryptographically proven process identity.
- [ ] **W13-06 — Enforce bounded time, memory and processes around model and replay subprocesses.**  
  **Acceptance:** OS supports hard limits where available; unsupported systems explicitly report gap and fail closed.
- [ ] **W13-07 — Run cross-tenant, cross-time, poisoning and source-root collision adversarial tests.**  
  **Acceptance:** No unauthorized cross-contamination; results are tied to exact source and threat family.
- [ ] **W13-08 — Test effect-transport parity across SDK, MCP, UTCP and Code Mode.**  
  **Acceptance:** Each route makes the same allow/deny decision on the same authorized action.
- [ ] **W13-09 — Redact private evidence from model-error logs, receipts and operator reports.**  
  **Acceptance:** Security test scans artifact JSON, stack traces and HTTP errors for secret canaries.
- [ ] **W13-10 — Keep an explicit rollback kill switch with a one-command verification.**  
  **Acceptance:** Disabling Vega returns the pre-Vega output and stops model calls without changing stored history.

### W14 — Optimize memory, latency and inference cost without misleading benchmarks

**Priority:** P1  
**Primary implementation targets:** `tools/vega_cdm_profile.py; causal_replay/semantic/scheduler.py; causal_replay/semantic/cache.py; benchmarks/outcome_performance.py`  
**Required test suite:** `tests/test_outcome_performance.py; tests/test_vega_performance_limits.py (NEW)`
- [ ] **W14-01 — Establish cost baseline for the current Vega 0.8B configuration.**  
  **Acceptance:** Reproduce or explicitly qualify original 4.17s p50 and 5.3 GiB measurements by host.
- [ ] **W14-02 — Benchmark 0.8B on Mac M4 16GB under controlled memory pressure.**  
  **Acceptance:** Record model load, inference p50/p95/p99, RSS, swap, energy if measurable and CPU configuration.
- [ ] **W14-03 — Measure model versus deterministic parser on identical input distributions.**  
  **Acceptance:** Publish incremental accuracy per second and memory, not only raw benchmark throughput.
- [ ] **W14-04 — Validate whether multi-question batching actually reduces total overhead.**  
  **Acceptance:** Compare cold/warm and repeated calls without claiming a gain when none exists.
- [ ] **W14-05 — Add selective-call routing based on parse ambiguity and consequence level.**  
  **Acceptance:** Simple exact cases use no model; model only sees authorized unresolved evidence.
- [ ] **W14-06 — Cache semantic proposals only under exact evidence/policy/model identity.**  
  **Acceptance:** Erasure, correction, tenant switch and model-version change invalidate cache deterministically.
- [ ] **W14-07 — Profile replay candidate counts, event scanning, and independent verifier time.**  
  **Acceptance:** Show p50/p95/p99 by stage with all queueing and worker-start overhead.
- [ ] **W14-08 — Stress multi-agent requests at 1, 2, 4 and 8 workers.**  
  **Acceptance:** Report actual speedup, contention and 16 GB operating limits; do not assume scale improves.
- [ ] **W14-09 — Enforce an adjustable per-task compute budget and graceful exhaustion response.**  
  **Acceptance:** Exhausted inference returns UNKNOWN/REVIEW_REQUIRED, no unsafe fallback or silent skipped work.
- [ ] **W14-10 — Create a Pareto analysis over safety, completion, latency, memory and replay cost.**  
  **Acceptance:** Promote only treatments that satisfy hard safety constraints and improve registered utility.

### W15 — Make CI and evidence gates source-bound and impossible to misread

**Priority:** P0  
**Primary implementation targets:** `tools/vega_cdm_gate.py; tools/agent_outcome_end_to_end_gate.py; .github/workflows/ci.yml`  
**Required test suite:** `tests/test_vega_ledger_and_gate.py; tests/test_agent_outcome_end_to_end_gate.py`
- [ ] **W15-01 — Add regression gates for known unsafe readings and sensor collisions.**  
  **Acceptance:** Both original failure scenarios reproduce pre-fix and pass the candidate tests with no false-safe action.
- [ ] **W15-02 — Require exact head-SHA CI completion on the proposed PR commit.**  
  **Acceptance:** Queued, cancelled or failed jobs cannot be represented as green CI.
- [ ] **W15-03 — Keep CORE, MODEL, AGENT, RESEARCH and RELEASE verdicts separate.**  
  **Acceptance:** A passing unit test is never displayed as real-model efficacy or production clearance.
- [ ] **W15-04 — Require candidate-local model run for MODEL_VALIDATED labels.**  
  **Acceptance:** A scripted fixture cannot satisfy real model smoke or task-effectiveness gates.
- [ ] **W15-05 — Wire independent inference and omission guards into the adversarial test matrix.**  
  **Acceptance:** The gate runs hazard-negative tests even if the ordinary action authorization suite passes.
- [ ] **W15-06 — Verify the preregistration digest before reading a confirmatory result.**  
  **Acceptance:** Invalid split, changed thresholds or missing task outcomes are rejected before analysis.
- [ ] **W15-07 — Record full raw per-case output hashes and disallow silent exclusions.**  
  **Acceptance:** Every assigned task appears exactly once per actor arm; failed inference remains incomplete.
- [ ] **W15-08 — Generate claims from evidence records rather than editing status prose.**  
  **Acceptance:** Docs and API disclose non-merged PR status, performance scope and no-go evidence.
- [ ] **W15-09 — Publish model, agent and CDM regression reports tied to source and asset hashes.**  
  **Acceptance:** Independent reviewer can rerun every producer command under pinned inputs.
- [ ] **W15-10 — Require a clean rollback smoke test after any deployment mode toggle.**  
  **Acceptance:** OFF -> SHADOW -> OFF sequence preserves authority, store and expected output digests.

### W16 — Package a disciplined release and product validation decision

**Priority:** P1  
**Primary implementation targets:** `docs/VEGA_CDM_LIMITATIONS.md; docs/AGENT_LAUNCH_READINESS.md; research/results/vega-cdm/; examples/vega_cdm_demo.py`  
**Required test suite:** `tests/test_product_claims.py; tests/test_release_guards.py`
- [ ] **W16-01 — Define engineering acceptance separately from research qualification and external deployment.**  
  **Acceptance:** Release matrix has independently justified verdicts; no ambiguous single pass score.
- [ ] **W16-02 — Provide an example showing verified evidence, Vega hypothesis and independent replay.**  
  **Acceptance:** Demonstration clearly distinguishes semantic suggestion from causal proof and action authority.
- [ ] **W16-03 — Expose operator-facing explanations for uncertainty, disagreement and safe escalation.**  
  **Acceptance:** User sees reason, source scope, next permitted step and terminal outcome without secret content.
- [ ] **W16-04 — Publish comprehensive Vega model limitations and failure examples.**  
  **Acceptance:** Known numerical, causal, calibration and CPU constraints remain visible even after fixes.
- [ ] **W16-05 — Create a practical local installation guide requiring no hosted API.**  
  **Acceptance:** Core installs without optional model and supports deterministic tests; local Vega weights are clearly third-party optional.
- [ ] **W16-06 — Provide a one-page model and feature-selection decision for budget-constrained hosts.**  
  **Acceptance:** 16 GB target includes exact memory measurements, swap behaviour, offload or fallback choices.
- [ ] **W16-07 — Create a maintained compatibility contract for old System One and outcome clients.**  
  **Acceptance:** No accidental API break; deprecations have explicit versions and migration tests.
- [ ] **W16-08 — Prepare a non-production pilot with no real-world consequential effects.**  
  **Acceptance:** Pilot tasks, consent, secret controls, reviewer roles, retention and incident stop rules documented.
- [ ] **W16-09 — Obtain an independent security and deployment review before any real external rollout.**  
  **Acceptance:** Without it the deployment verdict remains BLOCKED_EXTERNAL or RELEASE_NO_GO.
- [ ] **W16-10 — Write final GO/HOLD/NO_GO decision from frozen evidence, not task completion counts.**  
  **Acceptance:** A no-go records failed endpoints and next experiment; passing 160 tasks alone never means product release.


## 7. Proposed standard commands

The following commands are based on existing repository tooling. **Commands ending in a `(NEW)` implementation are deliverables, not commands currently guaranteed to work.**

```bash
# Existing PR #41 regressions / first-party contracts
python -m pytest -q tests/test_vega_u_adapter.py tests/test_semantic_pipeline.py tests/test_vega_cdm_security.py tests/test_vega_recovery.py
python -m benchmarks.vega_cdm_matched_arms --seeds 8 --advisor scripted --out local-scripted-development.json
python -m benchmarks.vega_cdm_confirmatory --registration research/prereg/vega-cdm-v1.json  # currently NO_GO, expected
python tools/vega_cdm_gate.py --out local-vega-gate/

# Existing general outcome stack and CI qualification
python tools/agent_outcome_end_to_end_gate.py --offline --all --out local-outcome-gate/
python -m pytest -q tests/test_outcome_arms.py tests/test_outcome_confirmatory.py

# New post-fix test targets (must be created in W02–W05)
python -m pytest -q tests/test_semantic_quantities.py tests/test_sensor_entity_claims.py tests/test_semantic_verification.py tests/test_omission_safety.py

# Optional, pinned local model; never count absence as a model PASS
# python -m benchmarks.vega_cdm_matched_arms --seeds 8 --advisor vega --vega-url http://127.0.0.1:8011 --out local-vega-development.json
```

## 8. Final operator-readable qualification matrix

Every research summary and release report must print these **separate** fields:

```json
{
  "source_sha": "EXACT_SHA",
  "source_dirty": false,
  "core_regressions": "NOT_RUN | PASS | FAIL",
  "governance_parity": "NOT_RUN | PASS | FAIL",
  "numeric_and_identity_safety": "NOT_RUN | PASS | FAIL",
  "vega_model_smoke": "MODEL_NOT_RUN | PASS | FAIL",
  "local_agent_paired_study": "AGENT_NOT_RUN | RESEARCH_HOLD | PASS | FAIL",
  "confirmatory_effect": "NOT_REGISTERED | NOT_RUN | SUPPORTS_GAIN | INCONCLUSIVE | NO_GO",
  "confirmatory_safety": "NOT_RUN | NONINFERIOR | INCONCLUSIVE | REGRESSION",
  "cdm_incremental_net_utility": "NOT_RUN | POSITIVE | NONPOSITIVE | INCONCLUSIVE",
  "external_security_review": "BLOCKED_EXTERNAL | PASSED | FAILED",
  "release": "RELEASE_NO_GO | ENGINEERING_GO_ONLY | QUALIFIED_FOR_SCOPED_PILOT"
}
```

**Final stop condition:** Even all 160 checked tasks do **not** imply production-readiness. Only matched outcome evidence, acceptable uncertainty for safety, and separate deployment qualification can justify the stronger claims. If the model does not clear them, retain the useful typed parser and causal research machinery while leaving Vega OFF/SHADOW.
