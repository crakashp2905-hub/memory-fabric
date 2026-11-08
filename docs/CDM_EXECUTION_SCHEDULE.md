# CDM execution schedule

The 240-task master plan is executed in dependency order. This schedule is a
local work queue; each checkpoint updates `CDM_TASK_LEDGER.md` with evidence.
No calendar dates or external service are required to keep the work moving.

| Order | Work package | Task range | Exit evidence |
|---|---|---|---|
| 1 | Baseline, contracts, privacy capture | 001–040 | Local baseline, security contract, bounded current-authorized capture, schema/privacy tests |
| 2 | Belief state and factual replay | 041–080 | Independent oracle, exact replay, checkpoint integrity, deterministic trace and budget tests |
| 3 | Interventions and certificates | 081–120 | Intervention controls, separate verifier, non-authorizing certificates, failure fixtures |
| 4 | Attribution and evaluator | 121–140 | Blinded held-out evaluator, calibration/refusal reporting, preregistered outcomes |
| 5 | Architecture comparisons | 141–160 | Matched local baselines, budget fairness, raw paired reports and null findings |
| 6 | Scheduling and efficiency | 161–180 | Replay budget/scheduler, cache invalidation, scaling and performance evidence |
| 7 | Correction and multi-agent governance | 181–200 | Shared-source/copy worlds, review-only correction reports, partial-history refusals |
| 8 | Security and privacy hardening | 201–220 | Local adversarial matrix, current-policy dominance, side-effect and metadata tests |
| 9 | Research, product UI, qualification and GO/NO-GO | 221–240 | Battery and trace suites, timeline viewer, compatibility and full offline manifest |

## Current queue

Checkpoint: 206 complete, 12 partial, 22 open. The previous full offline qualification passed 14 stages before CDM-163. R5 v3 development and confirmatory results are recorded; CDM-163's focused equivalence tests, Ruff and mypy pass. CDM-165 measures local checkpoint schedule storage/construction tradeoffs and confirms the current verification path still replays stored prefixes; no speedup is claimed. The integrated gate includes its benchmark and regression; the current qualification manifest is authoritative for the latest tree digest. Evaluator abstention,
basic attribution, bounded checkpoint cache, review-only correction queue,
synthetic multi-agent worlds, local viewer, bounded dispatcher, and selector
scaling are implemented. Certificate statuses and world semantics are bound;
minimality claims require a matching verified proof over a complete bounded
coalition table; the verifier attests only to the supplied table.
The frozen first-party TAME-inspired comparator now runs separate training
seeds and prequential held-out seeds with matched proposal/removal budgets,
factual, random, recency, leave-one-out and oracle-ceiling arms. It reports raw
cases, per-arm and paired utility intervals, annotation state, and explicit
safety fields. On this 10-seed synthetic holdout the TAME-inspired arm mean is
0.48 utility (normal-approximation 95% interval 0.124–0.836), equal to random;
this is weak synthetic evidence, not official TAME replication or an efficacy
claim. Local cost instrumentation records CPU/wall time, peak traced memory,
transitions, simulated calls, certificate bytes, artifact footprint, and zero
model/API/external charges. The R7 architecture comparison is complete on 20
fresh seeds: all evidence-removal arms had negative mean utility differences;
the exact subset/CAR-style arm was -0.355 (95% interval -0.639 to -0.071),
while recency was -0.125 (-0.297 to 0.047). The result warns that a measured
change is not automatically a beneficial correction. Continue remaining
architecture comparison work (121–160), replay efficiency with proven
equivalence (161–180), and correction replay integration (181–200). CDM-163
stays open until optimized state is proven equivalent to exhaustive replay.
CDM-005's threat paths are mapped to controls and negative tests, CDM-019
defines schema major/minor compatibility, and CDM-028/029 write and verify
immutable decision receipts with exact policy source resolution. The next
resolved dependency CDM-030/031 records full RNG state when available and
classifies tool/environment determinism; unhandled continuations refuse exact
replay. CDM-037/039 are covered by real versioned-history and fail-closed
replay fixtures. CDM-038/040 are complete with linked evidence. CDM-043 adds
the versioned belief-state contract and generated schema fixture. CDM-063 now
has digest-bound exact-prefix continuation and cold-replay equivalence tests,
but remains partial until safe prefix skipping is verified. CDM-064 completes
full RNG state restoration and CDM-065 gates exact readiness on complete current
inputs, including a digest of the exact observation trace. CDM-068 now blocks
live Fabric/projection objects from the pure executor, but remains partial
until materialized observations are bound to an authorized historical capture.
CDM-069 now pins local policy source/configuration and refuses unresolved tool
versions with `NON_REPLAYABLE`. Continue with the remaining CDM-068 integration,
then CDM-072/073 checkpoint integrity and current authorization/erasure checks.
CDM-071 now labels replay as local policy recomputation and never substitutes
the recorded selection text. CDM-075 validates seeded cold/checkpoint equality
at all internal cuts. CDM-076 now gates exact certificates on independently
verified deterministic replay and refuses unsupported RNG/tool continuations.
CDM-077 verifies unreadable evidence refusal. Next, advance past CDM-078 stale-checkpoint
invalidation to the next unresolved replay requirement. CDM-080 now documents
the actual deterministic/RNG/opaque-history envelope. CDM-079 full per-event executor overhead is measured at 100/1k/10k/100k with exact posterior fidelity; 100k uses about 89s and 91.5MB peak traced memory.
The local socket restriction means HTTP-based legacy adversarial families
remain unavailable in this run.

Execution rule: continue the dependency queue from the current checkout and
append evidence here after each package. The schedule is a persistent local
work queue; it is not a detached background process.

## Checkpoint rule

After each package: update task states from artifacts, run its focused
standard-library tests, run Ruff/mypy, refresh result hashes, and publish a
progress checkpoint. `PASS` applies only to the checks named in that artifact;
it does not imply the final internal GO decision.











Latest checkpoint (2026-11-09): 205 complete, 12 partial, 23 open. R12 and R5 v3 qualification previously passed 14 stages; CDM-163 now adds focused five-seed step/fingerprint equivalence checks, and the integrated gate includes them. Ruff, mypy and the focused replay/scheduler/frontier tests pass. The R5 v3 confirmatory interval crosses its frozen 0.052 margin, so superiority is not supported. CDM-103/104/106/108 are complete with direct issuer and schema regressions. Continue remaining tasks in dependency order. HTTP loopback adversarial families remain sandbox-blocked; no secret-scan pass is claimed.


CDM-103/104/106 completion: the verified issuer now has direct regression coverage for an intervention target outside the authenticated receipt, capture/intervention/policy digest validation, current-session revocation, and evidence erased after the original capture. Replay and capture focused suites passed (14 tests); the full offline gate is being refreshed. Ledger coverage is normalized to all 240 unique task IDs: 189 complete, 12 partial, 39 open.


CDM-108 completion: replay certificate v1 now binds estimator, original capture/intervention commitments, factual/counterfactual fingerprints, updater/policy, world semantics, no-action-authority and limitation labels into the content digest. Verification rejects missing/tampered limitations; masked export preserves limitations. API/verifier/replay suites pass (27 tests); Ruff/mypy pass. Full offline gate passes all nine stages with 133 tests, Python 3.13.5, 1,100 files and source digest 0800087cccdf0c2f51efc61035d9a4dbab96bbcc93223bddafc859b1bec7437e.



CDM-090 completion: local interventions use only immutable function-scoped tuple overlays and do not create temporary files or persistent/cache entries. New success/refusal lifecycle regression confirms factual input remains unchanged; intervention suite (8 tests), Ruff/mypy pass. All nine offline qualification stages pass with 139 focused tests; source digest c265b4c5b9285dcc52c32df9f7356122d2675718031d7361406f7fef32536953.


CDM-144 completion: the frozen first-party comparator is a self-contained evaluator–executor baseline with local policy execution, post-proposal evaluator feedback, trust annotations and bounded experience learning. Its focused tests verify deterministic disjoint seeds, delayed feedback visibility, safety fields, missing-feedback behavior and cap; full gate TAME comparison passes. The implementation is in `benchmarks/cdm_tame_inspired.py, not official TAME code. Ledger now has 192 complete, 12 partial, 36 open.


CDM-149 completion: added `execute_full_suffix, which replays all events from a validated affected index using an integrity-bound prefix and full suffix continuation. Six cut-point comparisons match cold replay exactly; focused test, Ruff/mypy and all nine offline stages pass. Gate: 135 tests, 1,100 files, digest c265b4c5b9285dcc52c32df9f7356122d2675718031d7361406f7fef32536953.


CDM-150 completion: added a locally authored CAR-inspired step-intervention comparator in `src/memory_fabric/causal_replay/executor.py`. It performs a declared evidence suppression, preserves the unaffected prefix, replays the complete dependent suffix using the full-suffix oracle, and returns both traces with explicit limitations. Focused controls, Ruff/mypy, and all nine offline stages pass; 139 focused tests, 1,100 files, digest c265b4c5b9285dcc52c32df9f7356122d2675718031d7361406f7fef32536953.



CDM-151 completion: seeded random and deterministic recency selectors use equal k budgets; paired benchmark arms use the same one-removal budget per generated world. Selector tests and the latest all-stage offline gate pass. Ledger now records 196 complete, 12 partial and 32 open.


CDM-154 completion: R8 matched cost-quality comparison frozen in `research/prereg/cdm-r8-cost-quality-pareto.md`, run on 20 fresh seeds (20261401–20261420). Seven arms share worlds, one-removal budget, paired utility-difference estimand and explicit safety constraints. It emits 140 matched rows, all seven cost-quality operating points and a verified non-dominated frontier; selector plus replay CPU/wall and peak memory are recorded. Protocol/report/CSV hashes and safety/budget invariants verify. The full nine-stage gate passes (139 focused tests, 1,100 files, source digest `c265b4c5b9285dcc52c32df9f7356122d2675718031d7361406f7fef32536953`). The evidence is synthetic and does not establish real-world efficacy.



CDM-152/153 completion: centrality selection is proven independent of risk/relevance/uncertainty and uses visible neighbor structure with stable ties; System 1 priority selection uses the declared deterministic pre-replay feature score and bounded candidate count. Scheduler tests, Ruff/mypy and all nine offline stages pass (139 focused tests; source digest `c265b4c5b9285dcc52c32df9f7356122d2675718031d7361406f7fef32536953`). Ledger: 198 complete, 12 partial, 30 open.

CDM-155 completion: R9 verifier ablation has one genuine and eight fabricated/incomplete cases. The self-certifying executor accepts all eight negatives (8 false accepts); the separately coded stdlib first-party verifier accepts the genuine case and rejects all eight negatives (zero false accepts/rejects). No human or third-party reviewer is used. Standalone and gate confusion matrices agree; R9 protocol hash and artifacts are recorded. Full gate passes all nine stages and 138 tests (1,104 files; digest `c265b4c5b9285dcc52c32df9f7356122d2675718031d7361406f7fef32536953`). This finite fixture result is not a real-world attack-rate estimate or security certification.

CDM-156 completion: frozen R10 capture ablation compares fresh current-policy capture against stale snapshot reuse on valid, revoked, erased and cross-tenant cases. Governance-aware capture has zero valid-case false blocks, unauthorized accepts and metadata exposures; the weaker baseline has two stale accepts and exposes three denied evidence references. The sanitized report includes no IDs/plaintext. Focused regression, Ruff/mypy and all ten offline gate stages pass (139 tests, 1,104 files, digest `c265b4c5b9285dcc52c32df9f7356122d2675718031d7361406f7fef32536953`).

CDM-157 completion: R11 v2 freezes five seeded synthetic worlds and compares factual proposal, leave-one-out with factual continuation fixed, and executed replay with continuation regenerated under the altered action. Replay improves stipulated utility by 0.5 versus LOO in each world (mean 0.5; normal interval [0.5, 0.5]); LOO never changes the proposal and replay changes it in all five. Focused regression (2 tests) and standalone report/manifest pass. Protocol SHA-256 `44dcf1db53ffc879b5ebaf2a6b97d4b3a72863f28e8b20dffc9696e15f48ba05`, report SHA-256 `6ec70a2f5ac963603c8b1991df83df0d5b9597f9c9536dd0a3a2310143aa24ba`, generator SHA-256 `5979aa22f573710867967ddbbb6265d449d0de0f36d1ef4c2e0088579d873891`, config SHA-256 `d032785828438200382d8552567e4f78bb580ed4db1c7140cfc4393e78c7f33e`. This is finite synthetic mechanism evidence, not population efficacy. Full gate and Ruff/mypy are being refreshed. Next open task: CDM-158.

CDM-158 completion: frozen R12 factorial ablation compares trust annotations and evaluator feedback independently across 4 arms and 3 held-out conditions, with 10 disjoint training and 10 held-out seeds. The one-removal oracle was not exceeded. Clean utility is 0.22 in both no-annotation arms and 0.24 in both annotation arms; correct-memory withholding is independently 9/10 and 8/10, respectively. In the full arm, annotation inversion improves utility by 0.09 on these fixtures and feedback inversion leaves utility unchanged while withholding shifts from 8/10 to 7/10. These are mixed finite-synthetic results, not efficacy evidence. Three focused tests, Ruff and targeted mypy pass. Protocol SHA-256 `7abab3d2b60f30a3d5b477a688096cf14bb6f7c9681f398556b2483ae279502c`; generator SHA-256 `9e645c2e2220b1d10be18429ddb6db31eedf3c374208542891321d2795a91ac1`; report SHA-256 `b095690f53bd0eb5c032cddcafc4f92fd3aba0516f3e6635c41f7ecc10d9baff`; summary SHA-256 `1f4c901faad9034ce92828fd2460d5444a05ff41aa44f263e8eb9987f8cc619e`; rows SHA-256 `3233d4268e11397cf449b0d9459398eaa88af83965c5b2ffb956e9d21e35788f`. Full gate refresh pending. Next open task: CDM-159.

CDM-159 completion: CDM-R5 v3 freezes a directional exact-Shapley-over-LOO hypothesis, primary paired-utility estimand, 20%-of-positive-oracle-headroom superiority threshold, equal one-removal budgets, evaluator-only oracle, per-world oracle-exceedance invalidation, five disjoint development seeds and 20 disjoint confirmatory seeds. Development runs cannot be pooled or used to modify thresholds; null, failure and zero-headroom results remain publishable. Protocol SHA-256 `1818be9971bd6065170cb3fd096d39991da6d326c8acd5cb4502933d78b57227`.

CDM-160 completion: the v3 development report uses seeds 20261901–20261905 and passes the positive-headroom preflight (0.12; fixed margin 0.024). Confirmatory seeds 20261911–20261930 are disjoint. Exact-Shapley minus LOO utility is +0.055 with a normal-approximation 95% interval [−0.0528, +0.1628]; the oracle headroom is 0.26, fixed margin 0.052, and no arm exceeds the one-removal ceiling. Decision is null: the interval crosses the margin. Both split reports publish per-seed rows, measured costs, source/config/protocol/output hashes and explicit synthetic-only limits under `research/results/cdm/architecture-superiority-r5v3/`. Protocol SHA-256 `1818be9971bd6065170cb3fd096d39991da6d326c8acd5cb4502933d78b57227`; confirmatory report SHA-256 `b60a93b55e2c99ba7df67bfdc8cc0ed46d261c29a0212957bfa80ff621921f52`; CSV SHA-256 `2152a99c024598026403e2d3db7ae9eeb776bf4eadd4c0aa04b96eeb6a27efcb`; summary SHA-256 `a6a3983cc853f153afeebf85be0078f01a47d04ed3fdf6007ab62a4b24aeda92`. New development/confirmatory stages are wired into the offline gate.

CDM-163 completion: `dependency_frontier` computes a validated transitive descendant closure in O(V+E); `execute_dependency_frontier` reuses only unaffected proposal decisions while rebuilding full-prefix fingerprints and the canonical final belief state. Unknown completeness falls back to exhaustive execution. Regression comparisons match exhaustive steps/fingerprints/final state on five seeded fixtures, covering target suppression and replacement, plus incomplete-graph fallback and malformed/unrelated mutation refusal. Ruff, mypy and 31 focused replay/scheduler/frontier tests pass. Full gate manifest after this update is authoritative. Next open task: CDM-165.
