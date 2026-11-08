# CDM task ledger

This file tracks all 240 task IDs from the attached fully in-house master plan.
The attached plan remains unchanged. Status is based on checked-in local artifacts and verified evidence.

## Complete at this checkpoint (237)

| Task | Evidence |
|---|---|
| CDM-001 | Offline manifest records local tree digest/count, HEAD/ref, uncommitted paths, runtime and test status; remote remains unknown |
| CDM-002 | `docs/COUNTERFACTUAL_DECISION_MEMORY.md` API inventory and test references |
| CDM-003 | Scope and non-goals in `docs/COUNTERFACTUAL_DECISION_MEMORY.md` |
| CDM-004 | Trust-boundary diagrams in `docs/COUNTERFACTUAL_DECISION_MEMORY.md` and `docs/CAUSAL_REPLAY_SECURITY.md`; security doc separates evaluator, independent verifier and non-authorizing certificate. |
| CDM-005 | Security threat matrix maps poisoning, injection, exfiltration, forged authority and tool-execution paths to concrete controls and offline negative tests; targeted security/replay suites passed |
| CDM-006 | Experimental contract in `docs/CAUSAL_REPLAY_API.md` (proposal scope only) |
| CDM-007 | Inert package import; socket-construction check in qualification manifest |
| CDM-008 | Empty-fabric no-mutation regression in `tests/test_cdm_api.py`; `tests/test_cdm_in_process_compatibility.py` verifies ordinary store read/write behavior around read-only CDM capture; gate covers import and API return contracts. |
| CDM-010 | `docs/architecture/ADR-CDM-001.md` |
| CDM-011 | `research/prereg/cdm-r1-replay-fidelity.md` |
| CDM-012 | `research/prereg/cdm-r2-counterfactual-attribution.md` |
| CDM-013 | Stable CDM error classes in `src/memory_fabric/causal_replay/types.py` |
| CDM-014 | `tests/test_cdm_api.py::test_dispatch_malformed_and_authorization_refusal_matrix` covers unknown operations, wrong shapes/types, unknown fields, invalid capture limits, correction request schema and revoked-session refusal for both facade operations. |
| CDM-015 | `docs/CAUSAL_REPLAY_LIMITATIONS.md` |
| CDM-016 | Provenance definitions in `docs/COUNTERFACTUAL_DECISION_MEMORY.md` |
| CDM-017 | Required `tools.cdm_offline_gate --all` qualification runs locally with network/model counts zero; replay tests prohibit socket/process/shell construction, and the inert-import gate fails if a socket is constructed. |
| CDM-018 | All required local benchmark/gate stages pass in the standard-library-only 22-stage offline qualification on Python 3.13.5; the synthetic demo passes. The local Python launcher confirms Python 3.11/3.12 are not installed, so no compatibility result is claimed for those unavailable runtimes. |
| CDM-019 | Experimental stability metadata and explicit schema major/minor parsing added: v1/v1.0 compatible, future minor/major refused; record parser normalization and refusal tests pass |
| CDM-021 | Immutable event and belief references in `types.py` |
| CDM-022 | Typed `DecisionRecord` in `types.py` |
| CDM-023 | Typed `ReplayContext` in `types.py` |
| CDM-024 | Typed `ToolObservation` commitments in `types.py` |
| CDM-025 | `MemoryService.Session` capture rechecks credentials before and after snapshot; revoked-session refusal tested |
| CDM-026 | Explicit-ID, 100-ID and bounded-event snapshot semantics in `capture.py` |
| CDM-027 | `CaptureResult.trace` binds authorized selected evidence to digest-only availability, exposure (including withheld), citation, and verified decision receipt events; query text and unrelated candidates are excluded. Focused trace privacy, serialization, and recorded-decision tests pass. |
| CDM-028 | Original decision options/constraints are captured in a session-authenticated, digest-only append-only event receipt; capture verifies the event sequence/ID, tenant, policy and complete record digest against the hash chain; post-hoc option/event tampering and unflagged option injection refuse |
| CDM-029 | Decision receipts bind policy ID, source/configuration digest and schema; `execute_recorded` resolves only the exact local built-in policy and refuses mismatched or unavailable implementations; positive and tampered digest tests pass |
| CDM-030 | Full stdlib MT19937 state and internal position are captured in `RNGSnapshot`, round-trip through canonical records and reproduce the next draws; missing state is explicitly marked non-replayable and exact recorded replay refuses |
| CDM-031 | Typed tool observations carry the closed exogenous/simulated-endogenous/opaque determinism class inside the authenticated decision receipt; exact replay refuses unhandled tool continuations; class and refusal tests pass |
| CDM-032 | Canonical JSON and SHA-256 commitments in `types.py`; order/invalid-number tests |
| CDM-033 | Registered v1 records use strict stdlib JSON parse/serialize with unknown-field rejection |
| CDM-034 | Capture explicitly labels source admissibility as a snapshot; `replay_captured` re-captures and rechecks current authorization/erasure before use. `tests/test_cdm_interventions.py::test_withhold_is_time_bounded_and_requires_current_authorized_capture` verifies replay refusal after quarantine. |
| CDM-036 | Digest-only checkpoint contract and current authorization/erasure revalidation |
| CDM-037 | `tests/test_cdm_capture.py::test_bitemporal_capture_separates_known_time_from_valid_time` uses real versioned history to distinguish knowledge sequence from valid time; the correction is absent before its event, available for its validity interval afterward, and only digests/versions enter the artifact |
| CDM-038 | `tests/test_cdm_capture.py` cross-tenant, private-memory, and revoked-session fixtures assert generic refusals with no evidence ID, content, or record metadata |
| CDM-039 | `tests/test_cdm_capture.py` proves a decision with missing evidence cannot be recorded and missing policy implementation refuses `execute_recorded`; `tests/test_cdm_bayes.py::test_incomplete_replay_cannot_be_certified` refuses an incomplete trace as EXACT |
| CDM-040 | `docs/CAUSAL_REPLAY_API.md` includes canonical JSON record, executable round-trip/unknown-field refusal, capture limits/statuses, migration behavior, and generated belief-state schema fixture checked by tests |
| CDM-041 | Deterministic pure `update` transition with immutable typed inputs |
| CDM-042 | `ThresholdPolicy` emits validated `DecisionProposal` and no action authority |
| CDM-043 | `BeliefState` now includes normalized variables, posterior uncertainty, evidence references and an updater/policy digest; generated schema fixture plus strict validation/round-trip and malformed-record tests pass |
| CDM-044 | Stdlib finite Bayesian enumeration with conditioning and numerical guards |
| CDM-045 | Battery world separates cooling failure, overheating, sensor bias and sensor observations in its DAG |
| CDM-046 | Same-origin duplicates are deduplicated; battery fixture gives independent sensors distinct reliability CPTs |
| CDM-047 | Zero-probability evidence refuses explicitly |
| CDM-048 | Deterministic state transition has no clock or mutable global dependency |
| CDM-049 | Canonical state fingerprint binds observations, posterior and policy ID |
| CDM-050 | Toy monitor/investigate/diagnose thresholds; proposal only |
| CDM-051 | Threshold output wraps existing `DecisionProposal.validate` |
| CDM-052 | `tests/test_cdm_replay.py::test_belief_state_probabilities_cannot_change_governance_or_access` shows belief values cannot change lifecycle or authorize quarantined evidence; API docs state the boundary explicitly |
| CDM-053 | Contradictory sources stay in the trace; the conflicted variable is not conditioned, preserving prior uncertainty |
| CDM-054 | Registered CPT sensitivity sweep recomputes exact posteriors across explicit parameter values |
| CDM-055 | Separate exact rational known-answer oracle tests plus recursive benchmark oracle |
| CDM-056 | `tests/test_cdm_bayes.py::test_noncommuting_same_origin_updates_follow_recorded_sequence` proves input permutation is neutral for fixed sequence, while a changed recorded order selects the predicted earliest same-origin evidence and changes the posterior accordingly |
| CDM-057 | Same-origin duplicate test |
| CDM-058 | Unrelated weather observation leaves fault posterior unchanged |
| CDM-059 | `tests/test_cdm_bayes.py::test_policy_swap_is_separate_from_evidence_intervention` verifies policy swap preserves evidence and changes policy identity, while suppression preserves policy identity and changes evidence; intervention digests remain distinct |
| CDM-060 | `docs/COUNTERFACTUAL_DECISION_MEMORY.md` records the finite binary DAG/CPT and evidence assumptions, conflict handling, and explicitly states that illustrative posterior confidence is not clinically or physically calibrated/validated |
| CDM-061 | Immutable digest checkpoint binds source head, tenant, evidence, updater and policy commitments |
| CDM-062 | Deterministic from-genesis event replay with exact final fingerprint checking |
| CDM-063 | Live locally minted `ExecutionCheckpoint` binds its exact prefix, per-step trace, final belief state, simulator and policy. `verify_prefix=False` refuses copied/tampered checkpoints, skips prefix policy transitions, and matches cold replay at every seeded cut point, including empty prefix/suffix. |
| CDM-064 | Archival checkpoint stores complete stdlib RNG state, algorithm and position; restore matches eight seeded continuation draws and rejects digest/algorithm mismatch |
| CDM-065 | Exact-checkpoint readiness requires current authorization/evidence, matching updater and policy digests, exact observation-trace digest, and explicit complete RNG or deterministic applicability |
| CDM-066 | Replay event budget refuses whole traces instead of returning partial success |
| CDM-067 | Stable event order is sequence then observation ID |
| CDM-068 | `execute_captured` reads the exact currently authorized historical content and derives typed observations only through the registered canonical JSON boolean adapter; caller overlays must match exactly. Adapter ID/source digest, malformed/unknown adapter refusal, and value mismatch are covered by `tests/test_cdm_replay.py`. |
| CDM-069 | Recorded replay pins policy ID/source digest; unregistered or changed policy and unhandled tool versions raise typed `NON_REPLAYABLE` |
| CDM-070 | Per-step proposal and belief fingerprints are recorded |
| CDM-071 | Replay results label local deterministic recomputation as `policy_reexecution`; recorded selection text cannot substitute for the computed proposal, and no hosted path is used |
| CDM-072 | Checkpoint digest tampering test refuses |
| CDM-073 | Checkpoint verification rejects erased references and lost authorization |
| CDM-074 | Bounded replay trace records sequence, belief hash and proposal hash |
| CDM-075 | Three fixed seeded traces match cold replay at every internal checkpoint cut for final state, exact status and complete per-step choices |
| CDM-076 | `issue_verified_recorded_replay` revalidates the current authorized capture and source receipt, binds observations one-to-one to evidence, derives only supported overlays, and independently verifies both traces; captured RNG continuations refuse until a verified stochastic handler exists |
| CDM-077 | Required evidence that is erased, inaccessible, or revoked refuses generically; capture returns commitments only and never fabricates reconstructed text |
| CDM-078 | Checkpoint verification rejects the old evidence version after a source memory is versioned, even though the archival checkpoint digest remains unchanged |
| CDM-079 | Full per-event executor traces measured at 100/1k/10k/100k with CPU/wall time, live allocations, peak traced memory, complete step count, canonical final fingerprint guard, and independent posterior oracle fidelity (zero error); raw rows and hashes in `research/results/cdm/replay-overhead/executor-overhead.json` and `executor-manifest.json`. 100k: 88.77s wall, 87.13s CPU, 404,259 live blocks, 91,451,213 peak traced bytes. | Complete. Cost is high at 100k; evidence is synthetic and local. |
| CDM-080 | `CAUSAL_REPLAY_LIMITATIONS.md` defines deterministic exact replay, full local RNG restoration limits, opaque/incomplete refusal statuses, and the no-hosted execution boundary |
| CDM-081 | Tagged immutable intervention operations validate declared parameters |
| CDM-082 | Suppression changes only disposable replay input |
| CDM-083 | Immutable `ReplacementFixture` validates a typed observation, explicit fixture ID/provenance, and target ID; replay requires target sequence match and changes only a disposable tuple; source-safe fixture test passes |
| CDM-084 | Delay changes hypothetical sequence and leaves source observation unchanged |
| CDM-085 | Time-bounded `withhold` requires a fresh authorized capture, exact source/evidence mapping and a valid inclusive interval; in-window masking, out-of-window visibility, malformed interval and erased-source refusal are tested |
| CDM-086 | `SensitivityFixture` changes one registered CPT entry and is labelled `model_assumption_change`; factual observations remain unchanged and suppression remains a distinct `evidence_change`; regression test proves the distinction |
| CDM-087 | Policy swap is explicit and changes policy fingerprint separately |
| CDM-088 | No-op replay matches factual state fingerprint |
| CDM-089 | Replay operates on immutable copy-on-write tuples and does not mutate Fabric state |
| CDM-090 | Replay overlays are function-local immutable tuples with no disk/temp/cache persistence; successful and refused replay lifecycle tests confirm source observations remain unchanged and overlay references naturally leave scope. |
| CDM-091 | `compose_interventions` validates each operation digest, rejects repeated evidence targets and multiple policy swaps before replay, and supports non-overlapping evidence batches; conflict and independent suppress/delay tests pass |
| CDM-092 | `earliest_affected_index` and `replay_frontier` traverse supplied dependency closure including source-to-derived-belief-to-downstream-decision links; incomplete graphs fall back to genesis; dedicated derived-link regression passes |
| CDM-093 | `execute` recomputes every per-event proposal from modified evidence; a conflicting factual trace versus changed-evidence trace proves downstream proposal changes and no stale selection reuse |
| CDM-094 | Versioned data-only `DeterministicEnvironment` regenerates typed endogenous observations and digest-bound tool outputs after changed actions; unknown transitions refuse; no callbacks or real tool execution |
| CDM-095 | `continue_counterfactual` returns `UNDEFINED_CONTINUATION` for an altered action with dependent future evidence and no simulator; registered environment regenerates and version-binds the replacement observation |
| CDM-096 | First-party `battery_sensor_environment` provides synthetic cooling-failure sensing and diagnostics via a versioned data-only transition table; no physical, CAN, filesystem, HTTP, shell or vehicle handler exists |
| CDM-097 | Replay source-log/lifecycle immutability regression |
| CDM-098 | Direct control matrix checks noop identity, irrelevant-event invariance, and replacement/suppression effects while source evidence remains unchanged |
| CDM-099 | Certificate regression rejects `physical_counterfactual_unsupported`; simulated-world certificates remain explicit and verifiable |
| CDM-100 | API intervention algebra documents each operator’s preconditions, overlay effect, refusal/control, batch behavior, and unsupported physical boundary |
| CDM-101 | `verifier.py` recomputes every belief/proposal step with separate enumeration code |
| CDM-102 | Verifier requires explicit deterministic RNG-not-applicable declaration and checks final state |
| CDM-103 | issuer verifies intervention digest and requires the target reference in the authenticated DecisionRecord evidence; explicit target-outside-receipt refusal regression in tests/test_cdm_replay.py |
| CDM-104 | issuer recomputes capture canonical digest, compares intervention digest, validates policy ID/source digest and independent factual/counterfactual trace verification; tamper refusal regressions in tests/test_cdm_replay.py |
| CDM-105 | Verifier refuses traces claiming real actions; replay has no action handler |
| CDM-106 | issuer recaptures evidence under current principal/tenant authorization; explicit revoked-session and post-capture erased-evidence refusal regressions in tests/test_cdm_replay.py |
| CDM-107 | Verifier checks exact status, completeness, consumed count and full step count |
| CDM-108 | Replay certificate v1 digest-bound schema includes authenticated capture/intervention, factual/counterfactual fingerprints, updater/policy, estimand, world semantics, non-authorizing boundary and explicit limitations; round-trip and tamper refusal tested. |
| CDM-109 | Replay certificate canonical JSON and content digest with round-trip verification |
| CDM-110 | Certificate always sets `action_entitlement=False`; tampering is refused |
| CDM-111 | Certificate schema distinguishes exact, approximate, undefined continuation, erased, unauthorized and non-replayable status values |
| CDM-112 | Certificate binds declared estimand and simulator/agent/unsupported-physical world semantics; unsupported physical claims do not verify |
| CDM-113 | Independent minimality verifier checks complete <=10-player proposal tables for sufficient, inclusion-minimal and cardinality-minimum subsets; certificate issuance requires matching verified proof, and bound-table tampering/incomplete-table failures tested |
| CDM-114 | Separate verifier recomputes exact small-N Shapley from complete coalition tables, checks efficiency and rejects tampering; AND interaction covered |
| CDM-115 | Certificate changes to capture digest, intervention digest and policy ID fail content-digest verification |
| CDM-116 | Tampered RNG applicability metadata is rejected by the independent verifier |
| CDM-117 | Forged replay-certificate payload passed through real `ActionGate.execute` is refused even for a granted tool; side-effect callback remains uncalled |
| CDM-118 | Masked certificate export omits source digests, updater/policy IDs and certificate hashes; retains no action entitlement |
| CDM-119 | Standalone stdlib CLI verifies local full certificate JSON and prints only VERIFIED/REFUSED; valid and tampered cases tested |
| CDM-120 | Local certificate acceptance matrix covers genuine, tampered, unsupported, authority-forgery and truncated cases; 1 TP, 6 TN, 0 FP/FN |
| CDM-121 | Exact leave-one-out attribution primitive by paired factual/counterfactual comparison; brute-force fixtures |
| CDM-122 | Decision-flip estimand compares policy proposals explicitly |
| CDM-123 | Total variation validates support and distributions; identity and maximum-distance fixtures |
| CDM-124 | Utility-difference estimand returns counterfactual minus factual utility and stays undefined when outcome values are missing |
| CDM-125 | Exhaustive exact Shapley enumerator capped at 10 players; efficiency and symmetric interaction verified |
| CDM-126 | Seeded permutation-sampled Shapley returns reproducible estimates |
| CDM-127 | Pairwise exact interaction screen distinguishes tested AND, OR, redundant and suppressor value-table fixtures |
| CDM-128 | Paired CF-F estimator requires a valid manifest-declared coupling ID and records replication/skipped counts |
| CDM-129 | Unpaired stochastic effect reports separate replication/skipped counts, CF-F mean and sampling standard error |
| CDM-130 | Seeded paired-bootstrap coverage sanity fixture over 60 experiments with known 0.3 coupled Bernoulli effect; 90% interval threshold fixed at 75% minimum observed coverage |
| CDM-131 | Wilson binomial interval handles edge proportions 0 and 1 exactly and finitely |
| CDM-132 | Missing dependency completeness or unverified replay yields `NON_IDENTIFIABLE` |
| CDM-133 | Exposure labels remain explicit; only complete, verified cases receive identified effects |
| CDM-134 | `measure_computation` records CPU/wall nanoseconds, tracemalloc peak, transitions, simulated calls, certificate bytes, artifact disk bytes, and fixed zero model/API/external costs; focused tests cover values and invalid counters |
| CDM-135 | Lineage candidate pruning retains all candidates and disables exact claims when dependency completeness is unknown |
| CDM-136 | Irrelevant evidence identity fixture verifies zero effect under equal distributions |
| CDM-137 | Two-way AND interaction yields symmetric half-credit under declared value function |
| CDM-138 | Attribution groups copied evidence under one source root and reports ambiguous lineage without an independence count |
| CDM-139 | Paired bootstrap is seeded and deterministic; budget/input refusals are explicit |
| CDM-140 | R7 preregistered 20-seed paired benchmark compares leave-one-out, exact subset, exact/sampled Shapley, random, recency and full-suffix replay; raw CSV/JSON, cost fields and hashed manifest retained. Negative utility differences reported with intervals; synthetic-only scope explicit |
| CDM-141 | Typed outcome assessment accepts only observed outcome records; hidden truth is not an evaluator input |
| CDM-142 | Deterministic outcome assessment returns separate reward and safety dimensions and abstains on missing results |
| CDM-143 | Feedback-frequency contribution comparator is tagged predictive-only and returns undefined without feedback |
| CDM-144 | First-party TAME-inspired evaluator–executor in `benchmarks/cdm_tame_inspired.py` uses local replay/policy execution, post-proposal outcome scoring, trust annotations and a capped EMA experience update; deterministic/disjoint-seed, visibility, safety, missing-feedback and cap tests pass in `tests/test_cdm_tame.py`. Not an official reproduction. |
| CDM-145 | TAME-inspired comparator contract freezes score equation, cap, training/holdout seeds, visibility, budget and safety rules in R6 preregistration; runnable prequential comparator, paired uncertainty report, raw CSV/JSON and manifest verified by focused tests and offline gate |
| CDM-146 | Missing/incomplete outcomes return typed `UNDECIDABLE`, never positive credit |
| CDM-147 | Outcome assessment and digest-based fidelity check are distinct APIs and types |
| CDM-148 | Brier score and ECE filter to complete, valid, held-out outcome records; empty eligible set is undefined |
| CDM-149 | `execute_full_suffix` in `executor.py` replays the entire affected suffix from an integrity-bound unchanged prefix and is explicitly labeled a correctness oracle; a five-event fixture matches cold replay steps, final fingerprint and consumed count at every cut. |
| CDM-150 | `execute_step_intervention` is a first-party CAR-inspired baseline: suppresses one declared step, preserves the prefix, replays the complete remaining suffix, returns paired exact traces and explicitly states agent-internal/physical-world/non-official limits; missing-target and source-immutability controls pass. |
| CDM-151 | Seeded `select_random` and deterministic `select_recency` enforce the same candidate budget; selector repeatability/budget tests pass, and paired architecture benchmark includes random/recency arms with one identical removal budget per world. |
| CDM-152 | `select_centrality` ranks only by visible neighbor count with stable ID tie-break; regression changes risk/relevance/uncertainty while preserving selection. |
| CDM-153 | `select_priority` implements deterministic 0.5 risk + 0.3 relevance + 0.2 uncertainty over pre-replay Candidate fields, with bounded k and stable ties; tests verify feature ordering and input-order independence. |
| CDM-154 | R8 freezes matched worlds, one-removal budget, paired simulator utility estimand, truth visibility, safety constraints and cost accounting. Twenty fresh seeds produce 140 paired arm rows, seven cost-quality points, a non-dominated frontier, zero side-effect counters, and verified protocol/report/CSV hashes; full offline gate passes. |
| CDM-155 | R9 tests one genuine and eight fabricated/incomplete certificate fixtures against the self-certifying executor and a separate stdlib verifier. Baseline accepts 8/8 negatives; independent verifier has 0 false accepts/rejects. Per-case records, protocol hash and confusion matrices retained; full gate passes. |
| CDM-156 | R10 compares fresh authorization-aware capture with stale snapshot reuse on valid, revoked, erased and cross-tenant fixtures. Governance-aware path has 0 false blocks, unauthorized accepts or metadata exposures; weak path has 2 stale accepts, 3 unauthorized accepts and 3 metadata exposures. Sanitized report, protocol/output hashes and full-gate evidence retained. |
| CDM-157 | R11 v2 preregistered five deterministic synthetic seeds and compares factual, fixed-continuation LOO, and executed replay. All 5 replay arms change proposals and improve stipulated utility by 0.5 versus LOO; LOO changes none. Focused regression (2 tests) and standalone run pass; manifest binds protocol/report/generator/config hashes and zero safety counters. Report SHA-256 `6ec70a2f5ac963603c8b1991df83df0d5b9597f9c9536dd0a3a2310143aa24ba`. Finite synthetic mechanism evidence only. |
| CDM-158 | Frozen R12 factorial ablation (`research/prereg/cdm-r12-trust-feedback-ablation.md`) compares annotation/feedback on/off across 10 training and 10 held-out seeds, clean, annotation inversion and feedback inversion. Clean mean utility: 0.22 no-annotation controls, 0.24 annotation arms; correct-memory withholding is separately 9/10 vs 8/10. Full arm utility is unchanged by feedback inversion and rises 0.09 under annotation inversion on this sample; no efficacy/robustness benefit claimed. Three focused tests, Ruff and mypy pass; one-removal oracle not exceeded. Manifest/report/CSV/summary hashes recorded in the R12 result manifest. |
| CDM-159 | CDM-R5 v3 superiority hypothesis frozen in `research/prereg/cdm-r5-evaluator-executor-ablations.md` before new runs. It fixes LOO vs exact Shapley primary contrast, 20% positive oracle-headroom margin, one-removal evaluator-only ceiling, all arms/seeds, a five-seed development preflight, disjoint 20-seed confirmatory set, null/ceiling-failure outcomes, zero-exceedance requirement and new-version/fresh-seed rule. Protocol SHA-256 `1818be9971bd6065170cb3fd096d39991da6d326c8acd5cb4502933d78b57227`; CDM-160 reports the subsequent registered run and null result. |
| CDM-160 | CDM-R5 v3 report is published under `research/results/cdm/architecture-superiority-r5v3/` with development and disjoint confirmatory reports, per-seed CSVs, manifests, source/config/protocol/output hashes, costs and scope. Confirmatory exact-Shapley minus LOO utility is +0.055 (95% interval −0.0528 to +0.1628); positive oracle headroom 0.26 gives frozen margin 0.052; 0 oracle exceedances. Decision: does not support superiority. Confirmatory report SHA-256 `b60a93b55e2c99ba7df67bfdc8cc0ed46d261c29a0212957bfa80ff621921f52`; CSV SHA-256 `2152a99c024598026403e2d3db7ae9eeb776bf4eadd4c0aa04b96eeb6a27efcb`; summary SHA-256 `a6a3983cc853f153afeebf85be0078f01a47d04ed3fdf6007ab62a4b24aeda92`. Conceptual first-party baselines only; no real-world transfer claim. |
| CDM-163 | `dependency_frontier` validates complete topological dependency maps and returns transitive descendants in O(V+E); `execute_dependency_frontier` recomputes affected proposals, reuses unaffected proposals, rebuilds all trace fingerprints/final state, and falls back to exhaustive replay when completeness is unknown. Four regression tests compare all steps and final state with exhaustive replay on five seeded worlds, cover replacement/suppression and refusal; 31 replay/scheduler/frontier tests, Ruff and mypy pass. The integrated 14-stage offline gate includes the frontier suite. |
| CDM-165 | Frozen `research/prereg/cdm-checkpoint-granularity.md` and `benchmarks/cdm_checkpoint_granularity.py` measure every-1/5/10/25/50/100 and terminal-only schedules on a deterministic 100-event trace. Report records checkpoint count, canonical payload bytes, construction time, interval lengths, digest rows, and actual current prefix-verification work. Every-event uses 1,963,880 bytes/5,050 prefix events; terminal-only uses 38,620 bytes/100 prefix events. No restore-speedup claim: current verifier replays stored prefixes. One focused regression passes; integrated gate includes benchmark/test. |
| CDM-161 | `ReplayBudget` validates event, attempt, wall time, memory estimate, node and zero-tool-call limits |
| CDM-162 | Earliest affected event is found by exhaustive dependency closure |
| CDM-164 | Unknown dependency completeness falls back to replay from genesis |
| CDM-166 | Bounded content-addressed checkpoint cache binds tenant/principal, versions, updater/policy, RNG and intervention commitments |
| CDM-167 | Explicit invalidation drops checkpoints referencing corrected, withdrawn or erased memory IDs |
| CDM-168 | Cache keys bind tenant/principal and lookups revalidate current authorization and versions |
| CDM-169 | Top-K selectors expose Branch Recall@K against supplied executed-oracle pivotal IDs; benchmark-scale results remain open |
| CDM-170 | Stable pre-replay feature record captures risk, relevance, uncertainty and graph neighbors |
| CDM-171 | Deterministic priority selector enforces the requested candidate count |
| CDM-172 | Early-pivotal fixture derives the oracle set by leave-one-out executed replay; at k=1, recency misses the sequence-1 pivotal event (Branch Recall@K 0), while pre-replay priority selects it (1). |
| CDM-173 | Low-centrality fixture derives the pivotal ID through executed leave-one-out replay; at k=1, centrality selects higher-degree distractors and misses the degree-zero pivotal event (recall 0), while priority includes it (1). Ten scheduler tests pass. |
| CDM-174 | No-signal candidate fixture verifies stable uninformative tie behavior |
| CDM-175 | Local 10/100/1000 candidate scaling report includes selector/frontier timings, memory, recall and per-seed raw rows |
| CDM-176 | Frozen `research/prereg/cdm-budgeted-inference.md` compares exact 8-node/256-state enumeration with likelihood-weighted sampling on equal 32/128/256 assignment budgets and 20 seeds. Exact refuses below 256; at 32 approximate mean absolute posterior error is 0.10/decision agreement 0.95; at 128, 0.04/1.00; at 256, 0.03/1.00; exact error is zero. Raw per-seed rows and effective sample sizes are recorded. Focused regression, Ruff and mypy pass; integrated gate includes it. Results are finite synthetic measurements, not production efficacy or wall-time/memory caps. |
| CDM-178 | A local CPU-bound worker is interrupted at a 0.1s parent wall-time cap; the started marker proves entry, process wait confirms termination, and isolated repository temp directory is removed. Focused test and runnable report pass. This verifies wall-time teardown only, not an OS CPU quota or arbitrary descendant-process tree cleanup; integrated gate includes the regression and report. |
| CDM-177 | Cross-tenant key collision is a miss; valid committed entry acceptance and current auth revalidation are tested |
| CDM-186 | `docs/CDM_INVALIDATION_CLASSIFICATION.md` distinguishes required affected-entry invalidation from harmful blanket cache clearing. A regression creates affected and independent valid checkpoints: targeted invalidation evicts only the affected one; blanket clear also discards the unrelated checkpoint and forces unnecessary recomputation. Current authorization/version checks remain mandatory; broad invalidation stays justified when dependency completeness is unknown. Focused checkpoint suite passes. |
| CDM-187 | `docs/CDM_REEVALUATION_CLASSIFICATION.md` distinguishes collateral cost from causal false positives. On a declared complete graph, exact frontier replays both retained dependents with zero collateral; unknown completeness falls back over four retained events, yielding two intentional conservative re-evaluations. Regression compares against the explicit dependency fixture; full gate includes it. |
| CDM-188 | `benchmarks/cdm_dependency_shapes.py` generates eight-event chain, star, and fork DAGs with alternating competing evidence from three synthetic sources; report records graph edges, exact target frontier and independent event counts. Regression confirms topology and expected frontier sizes 7/1/3. Preregistration and report are checked in; Ruff/mypy and integrated gate pass. These declared synthetic graphs do not establish application-level dependency completeness. |
| CDM-193 | `docs/CDM_MISSING_REMOTE_EVIDENCE.md` specifies that unavailable remote provenance yields `AMBIGUOUS_LINEAGE` and null independent-root count; no unknown remote is treated as absent or independent, and CDM performs no network fetch. Regression omits the remote root mapping and verifies count refusal while preserving the known local diagnostic group. Focused attribution test and integrated gate pass. |
| CDM-194 | Added authorized `assess_fabric_source_roots`: revalidates current read access, resolves recognized local copies/derivations via source-root lineage, and follows federation root metadata only for true imported provenance records. End-to-end regression proves imported evidence plus a local derivation remain one portable source root; forged federation context on a local record cannot mint a remote root. API contract is in `docs/CDM_FEDERATED_PROVENANCE.md`; Ruff/mypy and gate test pass. No network lookup or remote-currentness claim. |
| CDM-195 | Added `assess_federated_versions` and typed bindings for local version, portable source root, and imported origin version. An end-to-end two-store test imports source v1, revises and imports v2, then reports `MIXED_ORIGIN_VERSIONS` while preserving local v1/v1 bindings and local-snapshot replayability. Contract and limitations are documented in `docs/CDM_MIXED_VERSION_FEDERATION.md`; no remote consistency claim. |
| CDM-196 | Partition fixture imports an original and differently worded derivative, quarantines the origin without delivering retraction, and confirms both recipient snapshots remain locally active while `assess_fabric_source_roots` reports one shared source root. This prevents stale imported paraphrases from becoming misleading independent corroboration; it does not claim remote freshness during the partition. Regression is included in the federation provenance gate stage. |
| CDM-197 | Regression captures a valid source-root assessment and cache hit, erases the evidence without calling cache invalidation, then confirms the next cache lookup misses and the provenance assessment raises generic `Erased`. Current local erasure/access policy therefore dominates prior cached state; checkpoint suite and full gate cover the regression. |
| CDM-198 | `docs/CDM_CORRECTION_COMPARISON.md` and a deterministic three-decision/two-source-policy fixture compare blanket review (3 records), existing dependence (2 touched: 1 depended/1 would-stand), and CDM review output (2 ranked, explicitly labeled rows; unrelated work omitted). The comparison found and fixed tenant omission in dependence counterfactual certificate verification. CDM remains review-only and performs no action/correction. Focused test and integrated gate pass. |
| CDM-199 | Frozen `research/prereg/cdm-correction-aware-utility.md` fixes the dependent/false-review/miss costs, per-review cost, seeds, and GO rule: ≥0.10 paired gain per action, 20 confirmatory pairs, paired 95% bootstrap lower bound >0, zero missed dependent actions, and zero safety/authority violations. Scorer and boundary tests are in `benchmarks/cdm_correction_utility.py`; CDM-198 fixture utilities are 2.567 blanket, 3.300 dependence, 2.933 CDM. This is a preregistered threshold, not an efficacy result. |
| CDM-179 | Limitations document distinguishes estimated budget/memory and conservative frontier from hard caps or proven speedup |
| CDM-180 | Efficiency manifest records source/output/workload hashes, Python/platform/CPU, seeds, limits and no remote telemetry |
| CDM-181 | Tenant-scoped correction report uses influence graph actual retrieval/citation/authorization labels |
| CDM-182 | Verifier evidence sufficiency remains distinct from replayed choice dependence in report language |
| CDM-183 | Deterministic risk-ranked review worklist surfaced without action authority |
| CDM-184 | Correction report is explicitly review-only; tests verify authority unchanged |
| CDM-185 | Generated copied-source fixtures preserve a single independent provenance root |
| CDM-189 | Two-agent shared-source case maps copied observations to the same root |
| CDM-190 | Seeded 2/3/10/50-agent trace worlds preserve roles and source provenance |
| CDM-191 | Conflicting evidence after a decision is absent from that earlier decision's visible inputs |
| CDM-192 | Delayed retraction fixture models offline peer visibility until explicit sync |
| CDM-200 | Distributed scope and unavailable history limitations documented without omniscience claims |
| CDM-201 | Capture intersects historical projection visibility with current access and erasure checks |
| CDM-202 | Tenant-bound sessions and cross-tenant refusal covered |
| CDM-203 | Current session + current version + erasure checks invalidate checkpoints |
| CDM-204 | Replay accepts only built-in deterministic data configuration; no tool executor exists |
| CDM-205 | Behavioral replay test forbids socket, process and shell construction |
| CDM-206 | `causal_replay.tempfiles` resolves and confines parent/workspace paths beneath `research/results/cdm`, rejects outside and symlink-escape parents, and scopes cleanup with a context manager; interruption benchmark uses it; focused tests are part of the offline gate. |
| CDM-209 | `CacheKey` includes `policy_id` in its canonical digest and cache retrieval compares the checkpoint ID; regression proves two IDs with the same implementation digest cannot collide. |
| CDM-211 | Decision-record RNG snapshots are bound into the append-only receipt digest; substitution of a different well-formed RNG state fails receipt verification and recorded replay. This protects post-record integrity; a writer's initial RNG-state claim is not independently attested. |
| CDM-213 | Built-in policy parameters reject booleans, non-finite thresholds, malformed identifiers and extra constructor parameters; replay refuses policy subclasses that could inject behavior. Focused adversarial regressions are in the offline gate. |
| CDM-236 | `docs/CDM_KNOWN_FINDINGS.md` indexes preregistered negative/null outcomes and operational limits without converting synthetic results into efficacy claims. |
| CDM-237 | `tests.test_cdm_in_process_compatibility` runs normal Memory Fabric writes/reads before and after the read-only CDM capture facade in one interpreter and verifies capture does not append to the store log. |
| CDM-238 | `tools.cdm_offline_gate` requires `--all` and verifies its script root matches the local Git checkout before qualifying; no remote query is part of qualification. |
| CDM-240 | `docs/CDM_INTERNAL_GO_NO_GO.md` issues a scoped internal GO for offline synthetic research and NO-GO for deployment, efficacy claims, autonomous correction, physical-world causality, and action authority; latest required checkout qualification is PASS, recorded in the authoritative manifest. |
| CDM-207 | Capture artifact tests prove private content and credential signatures are absent |
| CDM-208 | Replay certificates explicitly have no action entitlement; no action method is exposed |
| CDM-210 | Duplicate observation IDs refuse in executor/verifier; reordered step sequence fails independent per-step verification |
| CDM-212 | Canonical input validator rejects deep, non-finite and non-JSON replacement values |
| CDM-214 | Evaluator API is typed diagnostic-only and has no store/action dependency; cannot mutate authority or mint certificates |
| CDM-215 | Inaccessible and erased evidence collapse to a generic refusal without IDs/counts |
| CDM-216 | Repeated capture/revoke/erase cycles are covered by `tests/test_cdm_privacy.py` |
| CDM-217 | Compromised-agent fixture cannot convert replay certificate into current action authority; repeated replay leaves source log/version unchanged |
| CDM-218 | CDM privacy/replay attack fixtures are required by the local offline qualification gate |
| CDM-219 | Threat matrix and residual risks are in `docs/CAUSAL_REPLAY_SECURITY.md` |
| CDM-220 | Internal-only scope and absence of independent security certification are explicit |
| CDM-221 | Seeded battery demonstrator reports three times and a proposal-changing evidence intervention |
| CDM-222 | Battery demonstrator checks posterior against its separate recursive factor enumerator with 1e-12 tolerance |
| CDM-223 | Trace generator includes irrelevant, correlated-copy, duplicate, copied, delayed and policy-swap negative controls |
| CDM-224 | Fixed-seed local benchmark runner records paired synthetic cases |
| CDM-225 | Benchmark writes raw JSON and CSV for all seven arms and outcomes |
| CDM-226 | Paired utility deltas, normal-approximation intervals, counts and refusals are reported |
| CDM-227 | `research/prereg/cdm-r3-evidence-bounded-certificates.md` frozen before held-out run |
| CDM-228 | `research/prereg/cdm-r4-decision-outcome-impact.md` frozen before held-out run |
| CDM-229 | `research/prereg/cdm-r5-evaluator-executor-ablations.md` freezes local comparator budgets |
| CDM-230 | Result manifest includes source, oracle, config and output digests |
| CDM-231 | Seven arms executed on the disjoint preregistered 10-seed held-out set |
| CDM-232 | Timeline view model shows evidence/version, belief, policy, proposal and intervention divergence |
| CDM-233 | Self-contained local viewer has no remote assets, escaped data, user value/how-to guidance and no-action labels |
| CDM-234 | Bounded in-process CDM request dispatcher supports read-only capture/review only; unknown fields/ops refused |
| CDM-235 | Fresh-checkout quickstart uses existing local Python commands and stdlib only |
| CDM-239 | User-facing differentiator limited to traceable evidence, belief revision and reviewable alternatives |

## Partial (3)

| Task | Remaining acceptance evidence |
|---|---|
| CDM-009 | Focused tests and the 22-stage gate are recorded; `research/results/cdm/full-suite-attempt/manifest.json` records the interrupted 2,437-test whole-repository attempt, source snapshot, observed socket failures, and preserved output SHA-256. | A complete non-interrupted whole-repository regression run and final artifact hash remain outstanding. |
| CDM-020 | `research/results/cdm/task-evidence-inventory.json` binds every evidence row to the exact source-tree SHA-256, local Git HEAD and dirty-state flag; explicit artifacts include file SHA-256 and last committed revision. Inventory stability, source snapshot, and artifact checks are tested. | Direct task-specific implementation-file references are still absent from many ledger rows; global source snapshot links do not replace those per-task mappings. |
| CDM-035 | Capture refusals for missing, private, withdrawn, and erased IDs now match in type, message, and serialized size (`tests/test_cdm_capture.py::test_missing_private_withdrawn_and_erased_ids_share_one_refusal`). Correction reports omit private descendant and grandchild IDs (`tests/test_cdm_api.py::test_correction_report_redacts_private_descendant_lineage`). | A broader timing and cache side-channel audit remains open; equal response shape does not establish constant-time behavior. |

## Open (0)

No open task IDs remain. The three partial tasks retain the acceptance gaps listed above.
