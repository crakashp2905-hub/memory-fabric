# Memory Fabric — Offline-Executable 10/10 Engineering, Research, Novelty, Hardening & Product Checklist

**Version:** 1.0 · **Audit baseline:** 2026-11-07 · **Repository:** [`crakashp2905-hub/memory-fabric`](https://github.com/crakashp2905-hub/memory-fabric) · **`main` SHA:** `d4fd174ac9056865c8b73abd857fa681daa6a0d7`  
**Scope:** 260 atomic tasks, 26 workstreams, five pillars, with executable acceptance conditions. The checklist is a plan, **not a claim that tasks are done**.

> **Read first:** It is possible to make the software exceptionally strong using only local code, checked-in fixtures, SQLite, test tooling, adversarial simulation and synthetic agents. It is *not* scientifically defensible to certify a universal **10/10**, demonstrate independent security, establish absolute novelty over all prior work, prove real-world demand, or substantiate hosted-model results without external evidence. The highest achievable status from this document alone is **OFFLINE-QUALIFIED RESEARCH / RELEASE CANDIDATE**. External validation remains a separately recorded gate, never silently marked complete.

## 0. Non-negotiable working contract

1. **No external inputs needed to execute tasks:** no API keys, model providers, paid compute, user-uploaded datasets, credentials, customer accounts, outside human reviewers, or network access. Use only code/fixtures already in repository or generated locally. Optional installed tools can be used, but absence must be reported.
2. **Do not hide, bypass, or weaken controls to improve benchmarks.** Every claimed utility improvement must be measured with original and new safety policies, identical task sets, and adverse test families.
3. **Do not misrepresent simulation as real-agent evidence.** Deterministic agents, stubbed model outputs, local mock tools and scripted adversaries are useful; label all results `SIMULATED` or `CONTRACT`.
4. **Do not duplicate implemented features.** The repo already contains action fences, provenance, correction propagation, tenant routing, evidence checks, decision proposals and a constrained UTCP/Code Mode subset. Inspect each target file and add regression evidence or a missing capability, not a parallel system.
5. **No invented third-party facts.** Novelty claims remain `CANDIDATE` pending full prior-art review. Security claims remain `INTERNAL_TESTED` pending independent review. Packaging approval remains with the owner.
6. **No direct changes to default safety semantics without paired tests and versioned migration.** Prototype new algorithms behind opt-in feature flags.
7. **No task is 'done' because code compiles.** It needs the acceptance evidence described below, passing focused regression, exact-SHA report, and correctly scoped documentation.
8. **One bounded PR per cohesive work item.** Prefer 1–5 related tasks, tests first, record before/after measurements and known regressions. Avoid giant unreviewable rewrites.

## 1. Grounded baseline and immediate reasons for this checklist

- `main` is alpha `0.14.0` in development. Exact-commit CI was successful, but external publication is explicitly **NO-GO** in `docs/MEMORY_FABRIC_RELEASE_CHECKLIST.md`.
- Open PR #30 contains additional **unmerged** benchmark evidence. Its reported local 50-agent task success is **58.4%**, valid evidence withheld **16.8%**, zero observed stale actions, HTTP throughput **32.6 ops/sec**, and HTTP **p99 3.86 seconds**, with capacity/effectiveness targets failed. These values are provisional benchmark observations, not current merged `main` metrics.
- Existing decision routing is a deterministic contract fixture; `research/results/decision-routing-contract-v1.json` explicitly says Laya/Jev/encoder arms were **not run**.
- Existing constrained Code Mode intentionally prohibits arbitrary code, loops, imports and network/file access. It is **not** a general sandboxed interpreter. The proposed tasks preserve this safe default.
- Historical research has negative findings: live governed memory underperformed pooled memory in a phase; credit-driven retention did not improve retention; abstention remains weak in some cases. Do **not** rewrite those histories into successful results.
- `docs/KNOWN_GAPS.md`, `docs/LIMITATIONS.md`, `docs/PRODUCT_READINESS.md`, `research/SCORECARD.md` and `docs/DECISION_MODELS_AND_UTCP.md` must remain the source of truth for unmet external gates and known limitations.

### Initial numerical targets (provisional, freeze before tuning)

| Axis | Starting observation | Proposed offline acceptance target | Important qualification |
|---|---|---|---|
| Task effectiveness | 58.4% in unmerged 50-agent study | ≥80% on new held-out scripted scenarios **and** better than strongest matched baseline | Aspirational; do not weaken safety or game fixtures |
| Valid evidence withheld | 16.8% in same study | ≤5% on held-out valid-evidence cases | No material stale-action increase; report risk bands |
| Stale actions | 0 observed in same study | 0 observed in registered stress set | Never describe as universal zero risk; report denominator/confidence bound |
| HTTP throughput | 32.6 ops/s in same study | ≥100 ops/s on a declared fixed local workload | Hardware and run configuration must be pinned |
| HTTP p99 | 3.86 s in same study | ≤1.0 s under same fixed workload | Set realistic target after reproducible profiling; regression-safe |
| Memory compression | Existing compaction, bounded fidelity | ≥30% byte reduction where lossless is feasible | Preserve all relevant provenance and policy-required evidence |
| Reproducibility | Mixed historical result lineage | 100% of *new* accepted results carry source/input digests | Preserve and label older incomplete results, don't fabricate metadata |
| Product quality | Alpha, no external review | Offline clean install, docs, upgrade/restore, incident, attack gates all pass | Still NOT production-certified or independently reviewed |

## 2. Suggested Codex implementation contract

Use the following block as the standing instruction in the repository's coding-agent environment:

```text
You are implementing MEMORY_FABRIC_OFFLINE_10_OF_10_CHECKLIST.md, not inventing
success claims. Work only on the repository and generated local fixtures.
No internet, credentials, paid APIs, user questions, customer data, external
models, third-party datasets, hardware beyond this machine, or human input.
Before coding a task:
  1. Locate current implementation and relevant regression tests.
  2. Record whether capability EXISTS / PARTIAL / ABSENT with exact paths.
  3. Write a failing test, adversarial case or quantitative acceptance harness.
  4. Implement smallest improvement behind opt-in flag where risk warrants.
  5. Run focused tests and python tools/check.py --full when environment permits.
  6. Produce deterministic results/manifests with exact checkout SHA.
  7. Update docs/KNOWN_GAPS.md, docs/LIMITATIONS.md and scorecard as needed.
  8. Never soften release/security gates or drop failing benchmarks to pass.
  9. Mark task DONE only with test path, result path and measured acceptance.
 10. If limited by absent optional tool, retain NOT_TESTED and continue other tasks.
Never claim external audit, live-model evidence, independent novelty verification
or a real customer pilot from local synthetic tests.
```

**Reference command (run from repository root):**

```bash
python tools/check.py --full
python -m unittest discover -s tests -t .
python tools/adversarial_gate.py
```

Run only commands supported in the current checkout; record missing optional dependencies as `NOT_TESTED`, not PASS. Never run `publish` or destructive commands against a non-sandbox database.

## 3. Prioritized 10-task starter sequence (before adding more features)

1. **E1-01 → E1-04:** freeze main/PR baseline, exact-SHA results and dataset digests.
2. **R2-01 → R2-04:** attribute every false withholding to the actual rule(s) that caused it.
3. **E3-01 → E3-02:** reproduce lexical/hybrid failure cases and define retriever comparators.
4. **R3-01 → R3-04:** reconstruct the 50-agent outcome failures under a common workload.
5. **E4-01 → E4-04:** profile p99 and throughput before attempting performance changes.
6. **H2-01 → H2-04:** verify action/retry/crash safety against new decision paths.
7. **R1-01 → R1-05:** build leakage-resistant synthetic research evaluation.
8. **N1-01 → N1-05:** prototype correction-aware decision records and affected-action graph.
9. **N2-01 → N2-05:** prototype minimal evidence-requirements and missing-evidence explanations.
10. **P1-01 → P1-03:** prove the whole product journey without a key or API.

The remaining workstreams are ordered for coverage, **not** as a request to execute 260 tasks in one enormous code change.


## 4. Atomic implementation checklist


---

### ENGINEERING


#### E1 — Reproducible baseline, evidence integrity and CI truth [P0]

**Existing reference points:** `tools/check.py`, `tools/results_manifest.py`, `tools/status_at_head.py`, `docs/STATUS_AT_HEAD.md`, `research/results/MANIFEST.json`.

- [ ] **E1-01** · **P0** · Freeze main SHA and record PR #30 as unmerged baseline evidence, never as production behavior. **Acceptance:** Machine-readable baseline states commit, branch, date, dataset provenance, workload and caveats..
- [ ] **E1-02** · **P0** · Create one offline command that generates a clean read-only baseline report from the checkout. **Acceptance:** Clean checkout runs it twice and obtains byte-identical normalized findings and hashes..
- [x] **E1-03** · **P0** · Capture Python, OS, SQLite, CPU, thread count and process count in every benchmark manifest. **Acceptance:** Manifest parser rejects missing environment fields and excludes nondeterministic timestamps from digest. Evidence: `benchmarks/manifest.py`, `tests/test_benchmarks.py`, `docs/BENCHMARK_MANIFEST_ENVIRONMENT.md`, `research/results/e1-03-manifest-environment.json`, `research/results/e1-03-manifest-environment.xml`, `research/results/bench_runs/legacy/index.json` (DONE: all five active manifests were rerun from clean commit `9260e482e05831db72afdada5820220448c15003`; each includes Python, OS, SQLite, logical CPU, thread and process counts, exact SHA, clean state and input digests; 27 benchmark manifest tests pass. Pre-capture files remain byte-preserved in the explicitly excluded legacy archive; no historical host facts were guessed)..
- [x] **E1-04** · **P0** · Stamp every new result with exact source commit and dirty-tree state. **Acceptance:** Reports reject unknown SHA or dirty state except explicitly labelled exploratory results. Evidence: `benchmarks/provenance.py`, `benchmarks/manifest.py`, `tests/test_result_provenance.py`, `tests/test_benchmarks.py`, `docs/RESULT_PROVENANCE.md`, `research/results/e1-04-result-provenance.json`, `research/results/e1-04-result-provenance.xml` (DONE: exact 40-character source SHA and dirty state are stamped; unknown SHA and dirty non-exploratory results are rejected. Fifty-five historical rows remain non-reconstructible and are not upgraded by inference)..
- [x] **E1-05** · **P0** · Digest generated datasets, agent scripts, policy presets and query fixtures. **Acceptance:** Tampering any declared input causes manifest verification to fail before score aggregation. Evidence: `benchmarks/manifest.py`, `benchmarks/scoreboard.py`, `benchmarks/evidence_completeness.py`, `tests/test_benchmarks.py`, `docs/BENCHMARK_MANIFEST_ENVIRONMENT.md`, `research/results/BENCHMARK_SCOREBOARD.md`, `research/results/e1-05-input-digests.json`, `research/results/e1-05-input-digests.xml` (DONE: manifests hash generator and declared input files; input tampering is rejected before scoreboard aggregation. Five historical manifests and legacy rows lack complete truthful input inventories and remain unqualified)..
- [ ] **E1-06** · **P0** · Capture package versions and optional-dependency skips separately from test passes. **Acceptance:** Summary reports passed, failed, skipped, unavailable, and why each unavailable arm matters..
- [ ] **E1-07** · **P0** · Build a single acceptance-ledger generator reading tests, metrics and evidence paths. **Acceptance:** Every claim links to one machine-verifiable artifact; missing artifacts produce INCOMPLETE..
- [ ] **E1-08** · **P0** · Add a negative-control self-test that intentionally corrupts one expected result. **Acceptance:** Acceptance checker fails the manipulated run and restores normal passing state..
- [ ] **E1-09** · **P0** · Detect result cherry-picking by comparing declared seed manifest against results on disk. **Acceptance:** Missing, repeated, or extra seed outputs block research acceptance..
- [ ] **E1-10** · **P0** · Regenerate test count and feature status from source, not manually maintained prose. **Acceptance:** Exact-head CI fails if README, registry or status contradict actual package/test inventory..


#### E2 — Event sourcing, consistency, corrections and historical belief [P0]

**Existing reference points:** `src/memory_fabric/eventlog.py`, `projections.py`, `correction.py`, `history_query.py`, `branching.py`, `tests/test_transactions.py`.

- [ ] **E2-01** · **P0** · Write a minimal formal state-transition table for append, correct, withdraw, erase, branch, and merge. **Acceptance:** Every transition has defined preconditions, postconditions and invariant-bearing tests..
- [ ] **E2-02** · **P0** · Add replay-equivalence property tests from event log to materialized projections. **Acceptance:** Different randomized append/correction/merge histories replay to identical canonical state and digests..
- [ ] **E2-03** · **P0** · Test withdrawn-parent then derived-child sequences in all permitted orderings. **Acceptance:** No descendant becomes actionable when required premises were already withdrawn..
- [ ] **E2-04** · **P0** · Test correction-before-copy, copy-before-correction and copied re-ingestion with changing identifiers. **Acceptance:** No alternate identity bypasses withdrawal within supported exact/subset-copy semantics..
- [ ] **E2-05** · **P0** · Specify bitemporal valid-time versus transaction-time semantics for historical reads. **Acceptance:** Fixtures prove late corrections never rewrite the historical belief record or grant current access..
- [ ] **E2-06** · **P0** · Implement current-authorization intersection for all historical read surfaces. **Acceptance:** Revoked identities and erased content remain inaccessible through historical APIs and exports..
- [ ] **E2-07** · **P0** · Add portable tombstone exchange format for store-to-store transfer with opt-in import. **Acceptance:** A recipient cannot resurrect withdrawn memory when importing snapshots plus tombstones..
- [ ] **E2-08** · **P0** · Harden event schema upgrades against unknown fields, duplicate events and missing versions. **Acceptance:** Version-skew table and rollback fixtures test backwards-safe refusal or explicit migration..
- [ ] **E2-09** · **P0** · Create crash-at-every-write-boundary harness for core lifecycle events. **Acceptance:** Reopen yields either entirely committed operation or no effect, with intact integrity chain..
- [ ] **E2-10** · **P0** · Test transaction-boundary races between correction, retrieval, and action authorization. **Acceptance:** Deterministic barriers prove no knowingly stale locally visible evidence can authorize a fenced action..


#### E3 — Retrieval quality and evidence construction [P0]

**Existing reference points:** `src/memory_fabric/answerability.py`, `retrieval_profiles.py`, `retrievers.py`, `relevance.py`, `evidence_completeness.py`, `benchmarks/evidence_completeness.py`.

- [ ] **E3-01** · **P0** · Build taxonomy of retrieval errors: absent, near-miss, wrong version, missing intermediate, wrong scope and overblocking. **Acceptance:** Each class has at least five seeded minimal counterexamples and a stable oracle label..
- [ ] **E3-02** · **P0** · Keep lexical as a measured baseline rather than assuming vector or hybrid superiority. **Acceptance:** Held-out per-family reports compare lexical, vector, hybrid, and chain at identical budget..
- [ ] **E3-03** · **P0** · Implement query-family routing behind opt-in flag with deterministic fallback. **Acceptance:** Router cannot lower core governance and reverts to lexical on unrecognized query shapes..
- [ ] **E3-04** · **P0** · Repair evidence-chain selection when a necessary bridge shares no query terms. **Acceptance:** Four-hop examples recover bridging evidence or return a precise insufficient-chain reason..
- [ ] **E3-05** · **P0** · Preserve answer-modifying facts that do not restate the original question. **Acceptance:** Multi-hop modifier fixtures can change a result without disappearing from the retrieved package..
- [ ] **E3-06** · **P0** · Separate retrieval ranking scores from evidence validity and decision readiness. **Acceptance:** API returns three independent fields with non-interchangeable type and test contracts..
- [ ] **E3-07** · **P0** · Extend evidence checks to paraphrased parameters using local bounded equivalence tables. **Acceptance:** Known paraphrase fixtures reduce wrong refusal; novel text remains UNDETERMINED, never fabricated certainty..
- [ ] **E3-08** · **P0** · Make explicit UNKNOWN, CONFLICTING and UNDETERMINED behavior testable for every read surface. **Acceptance:** CLI, SDK, MCP and HTTP return the same semantic reason codes..
- [ ] **E3-09** · **P0** · Measure and cap the evidence package's useful-token or byte budget without dropping mandatory dependencies. **Acceptance:** Fixed-budget tests retain every required citation or fail with a missing-evidence explanation..
- [ ] **E3-10** · **P0** · Prevent deleted, retracted, untrusted, out-of-scope memories from entering any retrieval cache. **Acceptance:** Eviction/invalidation fixtures cover corrections, erasure, tenant changes and cache restarts..


#### E4 — Concurrency, profiling, scaling and federation [P0]

**Existing reference points:** `src/memory_fabric/txn.py`, `outbox.py`, `federation.py`, `freshness.py`, `tools/`, `benchmarks/federation_world.py`.

- [ ] **E4-01** · **P0** · Reproduce reported 32.6 ops/s and p99 3.86s branch benchmark before optimizing. **Acceptance:** Same local harness logs operation mix, warmup, contention, and throughput confidence bounds..
- [ ] **E4-02** · **P0** · Create per-stage tracing for auth, event append, projection, copy lookup, serialization and transport. **Acceptance:** Each end-to-end request has balanced stage durations and total latency reconciliation..
- [ ] **E4-03** · **P0** · Run controlled profiler with 1, 10, 50 and 100 concurrent local clients. **Acceptance:** Show CPU, lock wait, I/O, allocation and p50/p95/p99 per scenario..
- [ ] **E4-04** · **P0** · Remove dominant contention by measurement with before/after regression proof. **Acceptance:** On identical hardware and seeds, optimization improves target latency without invariant regression..
- [ ] **E4-05** · **P0** · Validate SQLite busy timeout, WAL mode, checkpoint strategy and transaction sizes. **Acceptance:** Stress run sustains no silent lost write or unbounded busy retry across 50 processes..
- [ ] **E4-06** · **P0** · Build bounded paginated query/scan benchmarks at 1k, 10k and 100k memories. **Acceptance:** Complexity trend and memory budget are plotted; failing scale regimes recorded honestly..
- [ ] **E4-07** · **P0** · Simulate three logical hosts using distinct localhost processes and stores. **Acceptance:** Corrections converge after partitions heal with all acknowledgements accounted for; not called physical-host proof..
- [ ] **E4-08** · **P0** · Test reordered, duplicated, delayed and permanently dropped federation messages. **Acceptance:** Replay and idempotency preserve state; dead-letter and repair outcomes are observable..
- [ ] **E4-09** · **P0** · Inject clock skew and stale or forged signed freshness leases. **Acceptance:** Consequential actions fail closed on invalid or expired leases while safe reads remain possible..
- [ ] **E4-10** · **P0** · Create long-duration deterministic soak with crash/restart cycles and strict disk/resource ceilings. **Acceptance:** Detect leaks, growing queues and p99 drift; restore succeeds without reconciliation gaps..


#### E5 — SDK, protocol contracts, packaging and maintainability [P1]

**Existing reference points:** `src/memory_fabric/sdk.py`, `agent_api.py`, `adapters/mcp.py`, `tool_protocol.py`, `docs/SDK_CONTRACTS_0.14.md`, `pyproject.toml`.

- [ ] **E5-01** · **P1** · Create canonical public API inventory and tag each symbol stable, beta or experimental. **Acceptance:** Generated SDK reference and tests reject accidental public signature change without migration note..
- [ ] **E5-02** · **P1** · Ensure typed Python wheel includes py.typed and passes type-check smoke use outside checkout. **Acceptance:** Build wheel locally; isolated temporary install can import and type-check published public interfaces..
- [ ] **E5-03** · **P1** · Test consistent error codes and reason payloads across SDK, MCP, HTTP, CLI. **Acceptance:** Contract matrix catches identity, invalid evidence, unavailable tool, and stale-preview mismatches..
- [ ] **E5-04** · **P1** · Harden feature flags so experimental code cannot silently become default after upgrade. **Acceptance:** Snapshot tests assert default preset configuration and explicitly opt-in unsafe changes..
- [ ] **E5-05** · **P1** · Introduce a protocol-neutral tool schema converter with strict unsupported-case reporting. **Acceptance:** UTCP/MCP descriptors round-trip supported fields; unknown security fields never silently drop..
- [ ] **E5-06** · **P1** · Fail closed on unsupported UTCP manual versions, dangerous transports, or malformed tool descriptors. **Acceptance:** Local malicious-manual corpus exercises version, host, duplicate, schema and transport faults..
- [ ] **E5-07** · **P1** · Add build-from-sdist and build-from-wheel parity verification with generated reports. **Acceptance:** Both artifacts pass import, CLI, doctor and deterministic smoke without relying on checkout path..
- [ ] **E5-08** · **P1** · Create historical compatibility fixtures for all publicly released event/schema versions present in repo. **Acceptance:** Upgrader reads authentic fixture versions and refuses corrupt or incompatible stores cleanly..
- [ ] **E5-09** · **P1** · Refactor only proven high-churn modules using characterization tests before code motion. **Acceptance:** Behavior snapshots unchanged; complexity and code duplication metrics demonstrably improve..
- [ ] **E5-10** · **P1** · Test Windows/macOS/Linux path and encoding assumptions using portable local fixtures. **Acceptance:** Text, unicode, separators, line endings and case-collision guards pass across available CI matrix..


---

### RESEARCH


#### R1 — Benchmark scientific validity and leakage prevention [P0]

**Existing reference points:** `benchmarks/`, `research/prereg/`, `research/results/`, `tools/results_manifest.py`, `benchmarks/registry.py`.

- [ ] **R1-01** · **P0** · Create preregistered test families for correction, multi-hop evidence, action safety and team coordination. **Acceptance:** Each family states hypothesis, outcome, baseline, split, seeds and failure condition before candidate tuning..
- [ ] **R1-02** · **P0** · Separate deterministic scripted-agent scores from real model-agent experiments in all generated reports. **Acceptance:** No chart mixes populations or treats scripted-agent success as model-agent evidence..
- [ ] **R1-03** · **P0** · Build a fully local synthetic environment generator with scenario provenance and seeded randomness. **Acceptance:** Independent train/dev/test generators yield schema-valid disjoint worlds with recorded hashes..
- [ ] **R1-04** · **P0** · Prevent train/test leakage via entity, template, graph-topology and seed separation. **Acceptance:** Leakage detector fails deliberately duplicated motifs, not just identical question strings..
- [x] **R1-05** · **P0** · Include a broken retrieval arm, random evidence arm and permissive authorization arm. **Acceptance:** Every suite detects at least one known failure; broken controls cannot match a sensible oracle..

R1-05 completion evidence: shared broken-retrieval, seeded-random-evidence and permissive-authorization arms detect planted failures across the 40-case preregistered synthetic families; control coverage passes for all 11 benchmark registry suites. Evidence: `benchmarks/offline_research.py`, `experiments/external_bench.py`, `experiments/longmemeval_bench.py`, `tools/r1_control_coverage.py`, `tests/test_offline_research.py`, `tests/test_r1_control_coverage.py`, `tests/test_r1_external_negative_controls.py`, `tests/test_r1_known_failure_controls.py`, `research/results/r1-05-suite-control-coverage.json`, `research/results/r1-05-full-unit-tests.txt`, `research/results/r1-05-full-unit-tests.json`. External benchmark negative-control fixtures are synthetic and small; full external dataset results remain separately qualified.
- [ ] **R1-06** · **P0** · Add intentionally impossible requests that should lead to abstention, not action. **Acceptance:** Evaluation penalizes unsupported actions and overconfident completion independently from non-completion..
- [ ] **R1-07** · **P0** · Include genuinely valid but non-lexically obvious evidence to expose overblocking. **Acceptance:** Every test split has paraphrases, derived knowledge and indirect-but-supported actions..
- [ ] **R1-08** · **P0** · Publish exact task-level success, false refusal, stale-action and cost denominators. **Acceptance:** Zero events always reported with sample size and confidence bound, never as universal guarantee..
- [ ] **R1-09** · **P0** · Freeze benchmark registry and disallow post-hoc deletion of failing cases from summary. **Acceptance:** CI checks registered case count and archived negative results..
- [ ] **R1-10** · **P0** · Produce one-command offline replication instructions and machine-readable results comparison. **Acceptance:** A fresh local checkout regenerates deterministic suite and explains unavoidable timing variance..


#### R2 — False-withholding diagnosis and intervention study [P0]

**Existing reference points:** `src/memory_fabric/answerability.py`, `enforcement.py`, `independence.py`, `authority.py`, `research/results/`, `tests/test_answerability.py`.

- [ ] **R2-01** · **P0** · Import or locally encode the PR #30 16.8% valid-withholding examples with exact provenance. **Acceptance:** Each reproducible case has action, evidence, blocker reason and oracle-supported outcome..
- [ ] **R2-02** · **P0** · Classify refusals by provenance, independence, freshness, authority, poisoning, retrieval and missing dependency. **Acceptance:** Attribution sums to the observed denominator; ambiguous cases are explicitly multi-causal..
- [ ] **R2-03** · **P0** · Add a counterfactual dry-run explaining which individual guard blocked an action. **Acceptance:** Report preserves live policy and does not authorize or execute the trial action..
- [ ] **R2-04** · **P0** · Run guard-by-guard and leave-one-out ablations on frozen offline cases. **Acceptance:** Report recovered valid tasks together with additional unsafe action count and uncertainty..
- [ ] **R2-05** · **P0** · Define a partial-order lattice of evidence states instead of a single binary validity flag. **Acceptance:** Tests distinguish unknown, disputed, withdrawn, stale, supported and independently corroborated..
- [ ] **R2-06** · **P0** · Experiment with targeted quarantine of exact claims rather than blanket author withholding. **Acceptance:** Supported sibling evidence survives unless its exact dependency chain is compromised..
- [ ] **R2-07** · **P0** · Measure independent-support failures when several notes share the same upstream origin. **Acceptance:** Source-copy clusters count as one support root while independent notes remain independently usable..
- [ ] **R2-08** · **P0** · Add risk-sensitive evidence policies for read, summarize, recommend and externally consequential execute. **Acceptance:** Low-risk tasks are not blocked by high-risk execution-only restrictions; protected actions remain gated..
- [ ] **R2-09** · **P0** · Tune thresholds only on development seeds and freeze the best candidate before held-out test. **Acceptance:** Test-only threshold selection is rejected by evaluation tool..
- [x] **R2-10** · **P0** · Set promotion gate to <=5% valid withholding with no observed stale-action regression on held-out worlds. **Acceptance:** If unattainable, publish Pareto frontier and retain the safer existing policy. Evidence: `docs/WITHHOLDING_PROMOTION_GATE.md`, `research/results/r2-withholding-promotion-gate.json` (17.2% observed; hold existing policy)..


#### R3 — Agent-team downstream effectiveness and outcome metrics [P0]

**Existing reference points:** `benchmarks/federation_world.py`, `benchmarks/memoryworld2.py`, `experiments/`, `research/results/p3b-agent-teams.md`.

- [ ] **R3-01** · **P0** · Build local 5, 10, 25, 50 and 100-agent scripted environments with identical tasks. **Acceptance:** All agent counts run from seed manifests and report task-family composition..
- [ ] **R3-02** · **P0** · Define matched local-only, pooled memory, blanket-retraction, Memory Fabric and oracle arms. **Acceptance:** Equal information exposure, runtime permissions and context budgets are enforced..
- [ ] **R3-03** · **P0** · Separate completion failures into retrieval, insufficient evidence, policy refusal, coordination and tool error. **Acceptance:** Every failure belongs to at least one audited class with source trace..
- [ ] **R3-04** · **P0** · Measure outcomes across correction timing: before discovery, before planning and immediately before action. **Acceptance:** Report time-sensitive failures and prevent timing-dependent benchmark shortcuts..
- [ ] **R3-05** · **P0** · Add minority-agent and rare-source scenario families to catch majority consensus errors. **Acceptance:** Success and false refusal reported for minority agent separately from population mean..
- [ ] **R3-06** · **P0** · Include real tradeoffs where safety prevents legitimate completion. **Acceptance:** Combined utility shows successful tasks, unsafe actions, wasted calls and delayed decisions..
- [ ] **R3-07** · **P0** · Use local deterministic policy agents for continuous regression, not as substitutes for model results. **Acceptance:** Reports label these as simulation and explicitly state model-free limitations..
- [ ] **R3-08** · **P0** · Implement a transport-agnostic agent adapter so external-model trials can be added later unchanged. **Acceptance:** Offline scripted adapter passes interface tests with all network/model calls disabled..
- [ ] **R3-09** · **P0** · Set a research target >=80% task success on new held-out 50-agent scenarios, with safety unchanged. **Acceptance:** Treat threshold as aspirational; report failures and compare against strongest matched baseline..
- [ ] **R3-10** · **P0** · Measure per-agent minimum success, tail latency and worst-case fairness, not only mean success. **Acceptance:** Overall gain fails promotion if high-risk minority cases or least-successful agent regress materially..


#### R4 — Statistical rigor, adversarial experimental design and negative results [P1]

**Existing reference points:** `benchmarks/stats.py`, `benchmarks/manifest.py`, `research/prereg/`, `research/SCORECARD.md`.

- [x] **R4-01** · **P1** · Implement Wilson or exact binomial intervals for completion and false-block rates. **Acceptance:** CI validates formulas on known reference cases including zero-event observations. Evidence: `benchmarks/stats.py`, `tests/test_statistical_intervals.py`, `tools/qualify_statistical_intervals.py`, `research/results/r4-01-binomial-intervals.json` (DONE: 3 focused tests pass; seven machine-checked Wilson/exact-zero-event reference cases pass, including zero-event and zero-denominator cases. Zero denominator remains fully uncertain; workload power is not claimed)..
- [x] **R4-02** · **P1** · Use paired bootstrap intervals for per-task improvement against matched baselines. **Acceptance:** Report effect, 95% CI, sample size, correlation assumptions and split identity. Evidence: `benchmarks/paired_agent_bootstrap.py`, `benchmarks/stats.py`, `research/prereg/matched-agent-arms-v1.md`, `tests/test_paired_agent_bootstrap.py`, `research/results/r3-02-matched-agent-arms.json`, `research/results/r4-02-paired-agent-bootstrap.json` (DONE: paired 95% cluster-bootstrap effects reported against three matched baselines using 24 task cases and 1,200 agent attempts per arm. Resampling unit, exchangeability assumption, fixed seed and split identity are recorded. Results are synthetic and descriptive)..
- [ ] **R4-03** · **P1** · Correct multi-family hypothesis comparisons or declare a small number of primary outcomes. **Acceptance:** Results distinguish primary, secondary and exploratory measurements without p-value fishing..
- [ ] **R4-04** · **P1** · Predefine minimal meaningful improvement and disallowed regression margins for every hypothesis. **Acceptance:** Gate logic is stable before test data execution and fails under boundary test values. Evidence: `benchmarks/heldout_agent_qualification.py`, `research/prereg/heldout-agent-qualification-v1.md`, `tests/test_heldout_agent_qualification.py`, `research/results/r3-09-10-heldout-qualification.json` (PARTIAL: the heldout promotion gate now has boundary tests for the 80% target, no-gain tie, safety/stale-action counts, and 10-point least-agent/high-risk fairness margins. A shared threshold registry across all hypotheses is not yet present, and the tested seed split must be reconciled with the v1 preregistration)..
- [ ] **R4-05** · **P1** · Include adversarial near-misses and semantically irrelevant distractors generated by a separate seed stream. **Acceptance:** Models cannot win purely from repeated string templates or identifier ordering..
- [ ] **R4-06** · **P1** · Randomize answer order, tool order and agent identifiers to detect trivial heuristics. **Acceptance:** Permutation tests flag behavior changes beyond predeclared tolerance..
- [x] **R4-07** · **P1** · Add deterministic mutation tests to benchmark evaluator itself, not merely product implementation. **Acceptance:** Removing check for stale action, source scope or abstention changes benchmark verdict to FAIL. Evidence: `benchmarks/decision_verdict.py`, `benchmarks/evaluator_mutations.py`, `tests/test_benchmarks.py`, `tools/benchmark_evaluator_mutations.py`, `research/results/r4-07-evaluator-mutations.json`, `research/results/r4-07-evaluator-mutation-tests.xml` (DONE: three evaluator mutations, stale action/source scope/false abstention, all changed a failing benchmark verdict to PASS in the mutated implementation and were killed by deterministic tests; this contract suite validates the evaluator predicate, not product-system security)..
- [ ] **R4-08** · **P1** · Control for context size, retrieval count, wall time and number of tool calls across ablation arms. **Acceptance:** Efficiency gains are normalized and cannot result from hidden additional information..
- [ ] **R4-09** · **P1** · Track seed variance and report worst-seed failures next to averages. **Acceptance:** Promotion requires robustness across registered seeds, not one favorable run..
- [ ] **R4-10** · **P1** · Preserve killed and inconclusive hypotheses with causal explanation and next test boundary. **Acceptance:** Research scorecard remains candid; impossible-to-measure claims are labelled NOT_TESTED..


#### R5 — Paper-quality evidence, limitations and contribution isolation [P1]

**Existing reference points:** `research/SCORECARD.md`, `research/prereg/`, `research/results/MANIFEST.json`, `docs/INDEPENDENT_EVALUATION.md`.

- [ ] **R5-01** · **P1** · Write one falsifiable main contribution sentence for each selected research direction. **Acceptance:** The sentence specifies the novelty hypothesis relative to existing repo mechanisms..
- [ ] **R5-02** · **P1** · Create a contribution-by-component table identifying which mechanism predates the experiment. **Acceptance:** Existing correction propagation, action gates and evidence completeness are credited as baselines..
- [ ] **R5-03** · **P1** · Run one-component removal studies on dependency graphs, routing and compression. **Acceptance:** Result shows marginal effect rather than attributing a whole integrated gain to one module..
- [ ] **R5-04** · **P1** · Create self-contained appendix with environment, seeds, data generator, protocol and run commands. **Acceptance:** All result tables can be regenerated without API keys or external datasets..
- [ ] **R5-05** · **P1** · Write failure taxonomy from every negative outcome, including historical H2, PA and PB1 failures. **Acceptance:** Paper draft states which apparent gains did not generalize and why..
- [ ] **R5-06** · **P1** · Record tradeoffs as Pareto curves for safety, task success, latency and memory cost. **Acceptance:** Candidate is not declared superior when another arm dominates it on stated objectives..
- [ ] **R5-07** · **P1** · Add contamination tests ensuring scenario labels are not leaked through memory text, IDs or tool names. **Acceptance:** A deliberately leaked label is detected and invalidates that experiment..
- [ ] **R5-08** · **P1** · Implement manuscript claim checker mapping each quantitative sentence to an immutable result file. **Acceptance:** Missing data, wrong denominator or outdated SHA prevents 'supported' claim status..
- [ ] **R5-09** · **P1** · Prepare a limitations table splitting mathematical proof, model-free tests and untested real-world use. **Acceptance:** No deterministic simulation is described as a live-model or independent experiment..
- [ ] **R5-10** · **P1** · Prepare an offline reproducibility package and internal reviewer checklist while retaining EXTERNAL gates. **Acceptance:** Local reruns can pass; third-party originality, security and user validation remain explicitly pending..


---

### NOVELTY


#### N1 — Decision-memory graphs and correction-aware decision continuity [P1]

**Existing reference points:** `src/memory_fabric/influence.py`, `lineage.py`, `justification.py`, `context_receipt.py`, `decision_models.py`, `actions.py`.

- [ ] **N1-01** · **P1** · Define first-class DecisionRecord schema with goal, candidate options, chosen option, evidence versions and constraints. **Acceptance:** Schema validation and migration reject missing critical identity and decision-time fields..
- [ ] **N1-02** · **P1** · Record decision-to-claim and decision-to-tool-effect edges separately from observed exposure. **Acceptance:** Graph distinguishes 'seen', 'relied upon', 'authorized' and 'executed' with typed edge tests..
- [ ] **N1-03** · **P1** · Implement deterministic decision-impact query triggered by correction or retraction. **Acceptance:** Returns affected decisions with proof paths, not every action that merely shared a source..
- [ ] **N1-04** · **P1** · Build incremental dependency indexes and compare against full-scan reference. **Acceptance:** 10k-decision fuzz cases return identical affected sets; update cost is bounded..
- [ ] **N1-05** · **P1** · Treat alternatives as evidence-dependent hypotheses, not silently deleted discarded branches. **Acceptance:** Query shows why alternatives lost and which might become viable after correction..
- [ ] **N1-06** · **P1** · Define statuses proposed, approved, executed, superseded and requires-reconsideration. **Acceptance:** Illegal status transitions fail with typed reason and preserve append-only history..
- [ ] **N1-07** · **P1** · Expose machine-readable re-evaluation receipt with exact changed premise and current decision status. **Acceptance:** Receipt deterministically reproduces after event-log replay, without granting authority..
- [ ] **N1-08** · **P1** · Add partial-order consistency tests for simultaneous conflicting corrections. **Acceptance:** Independent orderings produce a defensible conflict or equivalent result, not silent last-writer wins..
- [ ] **N1-09** · **P1** · Benchmark decision-continuity against simple memory versioning and blanket invalidation. **Acceptance:** Report unnecessary re-evaluations, stale decisions, correctness and update cost..
- [ ] **N1-10** · **P1** · Preregister novelty hypothesis: lineage-aware decision repair improves safe completion at equal budget. **Acceptance:** Claim is NOT_PROVEN unless held-out, matched experiments isolate it from baseline governance..


#### N2 — Evidence-requirement graphs and decision-aware sufficiency [P1]

**Existing reference points:** `src/memory_fabric/evidence_completeness.py`, `answerability.py`, `certificates.py`, `typedclaims.py`, `dependence.py`.

- [ ] **N2-01** · **P1** · Define minimal RequirementGraph grammar for AND, OR, independent-source and temporal constraints. **Acceptance:** Parser checks acyclic rules, bounded size and descriptive error handling..
- [ ] **N2-02** · **P1** · Map each consequential action to required claims and provenance strength through static local policies. **Acceptance:** Evidence missing one mandatory leaf never accidentally grants a protected action..
- [ ] **N2-03** · **P1** · Generate minimal missing-evidence sets explaining why an action remains blocked. **Acceptance:** For small graphs compare output against exhaustive oracle enumeration..
- [ ] **N2-04** · **P1** · Add counterexamples where retrieved facts are relevant but do not support the requested action. **Acceptance:** Gate abstains or reports missing evidence rather than treating similarity as support..
- [ ] **N2-05** · **P1** · Handle conflicting independent claims with explicit disputed status and operator-facing reasons. **Acceptance:** No arbitrary alphabetical source ordering resolves factual conflict..
- [ ] **N2-06** · **P1** · Build bounded graph-evidence packer that retains necessary intermediate links. **Acceptance:** At fixed context budget, covered dependencies never go missing without surfaced failure status..
- [ ] **N2-07** · **P1** · Test source dependence using shared roots and copied evidence instead of note count. **Acceptance:** Two copies of one source cannot satisfy a two-independent-source requirement..
- [ ] **N2-08** · **P1** · Support policy-specific safe degradation when evidence is insufficient but action is read-only. **Acceptance:** Protected execution remains blocked; advisory path contains explicit insufficiency disclosure..
- [ ] **N2-09** · **P1** · Measure false abstention, false authorization, task success and latency against current answerability baseline. **Acceptance:** Evaluate held-out cases; any win must report its extra evidence cost..
- [ ] **N2-10** · **P1** · Propose a proof-carrying decision receipt binding requirement version, evidence IDs and authorization digest. **Acceptance:** Replayed receipt either verifies against original snapshot or records precise invalidation reason..


#### N3 — Counterfactual memory credit and offline policy evaluation [P2]

**Existing reference points:** `src/memory_fabric/influence.py`, `estimators.py`, `dependence.py`, `research/prereg/h1-causal-credit.md`, `research/prereg/h2-credit-driven-retention.md`.

- [ ] **N3-01** · **P2** · Define intervention variables for include/exclude memory, routing option, and escalation level. **Acceptance:** Counterfactual estimands and assumptions are written before algorithms..
- [ ] **N3-02** · **P2** · Construct small exact-oracle decision worlds where all permitted memory subsets can be enumerated. **Acceptance:** Estimator output is tested against oracle causal differences, not mere source co-occurrence..
- [ ] **N3-03** · **P2** · Compare leave-one-out, Shapley approximation, propensity weighting and naive recency under matched cost. **Acceptance:** Accuracy, compute and variance reported; infeasible methods remain optional research..
- [ ] **N3-04** · **P2** · Test confounding by making important memories more likely to appear in successful runs. **Acceptance:** Estimator detects or exposes bias rather than crediting correlated presence as causation..
- [ ] **N3-05** · **P2** · Add stochastic randomized intervention harness with deterministic seed control. **Acceptance:** Treatment assignment and observation probability are reproducible and inspectable..
- [ ] **N3-06** · **P2** · Check stability of credit estimates under irrelevant memory duplication. **Acceptance:** Attributions should not increase solely because a note is copied repeatedly..
- [ ] **N3-07** · **P2** · Separate outcome feedback from source authority; success cannot retroactively certify false facts. **Acceptance:** Injection and false-source fixtures maintain existing authority invariant..
- [ ] **N3-08** · **P2** · Evaluate policy learned from past simulated tasks on entirely new world families. **Acceptance:** Guard against historical H2 failed retention hypothesis; require beating smoothed-success baseline..
- [ ] **N3-09** · **P2** · Enforce off-policy support checks; refuse estimates when logged actions lack overlap. **Acceptance:** Unsupported counterfactual estimates are labelled NON_IDENTIFIABLE, never numeric confidence..
- [ ] **N3-10** · **P2** · Only graduate causal policy learning if it reduces regret without increasing unsafe actions or runtime cost excessively. **Acceptance:** Failure is archived as research result rather than changed into a qualitative victory..


#### N4 — Correction-safe compression and memory ecology [P1]

**Existing reference points:** `src/memory_fabric/lossless_compaction.py`, `compaction.py`, `context_map.py`, `objective_v2.py`, `tests/test_lossless_compaction.py`.

- [ ] **N4-01** · **P1** · Define compression invariant: every consequential fact in summary maps back to active original versions. **Acceptance:** Reconstructed dependency map passes exact oracle tests on generated summaries..
- [ ] **N4-02** · **P1** · Build deterministic hierarchical summaries of long histories with explicit summary-to-source edge certificates. **Acceptance:** Correction invalidates only summaries affected by changed source roots..
- [ ] **N4-03** · **P1** · Measure bytes and actual model-token estimates separately, with no model-cost claims from byte counts. **Acceptance:** Reports show bytes and optional tokenizer provenance and label missing tokenizer results..
- [ ] **N4-04** · **P1** · Add contested-fact fixtures that retain minority alternatives rather than compressing to majority narrative. **Acceptance:** Disputed hypotheses remain discoverable after compaction..
- [ ] **N4-05** · **P1** · Add preference changes, corrections and temporal qualifiers where newest text is not always current truth. **Acceptance:** Summary keeps valid-time distinction and original source identity..
- [ ] **N4-06** · **P1** · Implement budget-aware extraction that returns structured failure when important material cannot fit. **Acceptance:** It never silently skips a compulsory dependency to meet token budget..
- [ ] **N4-07** · **P1** · Compare no compaction, naive recency, extractive summary and provenance-preserving summary. **Acceptance:** Report task success, false stale actions, compression factor and reconstruction fidelity..
- [ ] **N4-08** · **P1** · Try lossy compaction only for non-consequential text while preserving exact evidence certificate. **Acceptance:** Strict policies fail closed if summaries lose required proof edges..
- [ ] **N4-09** · **P1** · Profile incremental summary refresh versus complete rebuild under repeated corrections. **Acceptance:** Affected-summary recomputation remains bounded and deterministic..
- [ ] **N4-10** · **P1** · Preregister novelty hypothesis: provenance-preserving compression improves decision-per-context cost at equal safety. **Acceptance:** Do not assert novelty or improvement unless comparisons survive unseen history families..


#### N5 — Diversity-preserving multi-agent epistemic memory [P2]

**Existing reference points:** `src/memory_fabric/federation.py`, `independence.py`, `consensus.py`, `trust.py`, `research/prereg/h4-topology-and-diversity.md`.

- [ ] **N5-01** · **P2** · Represent support origin clusters distinctly from how many agents repeat a claim. **Acceptance:** Ten replicas of one source have the support weight of one source by default..
- [ ] **N5-02** · **P2** · Preserve incompatible plausible claims as competing hypotheses with independent provenance. **Acceptance:** No automatic majority vote converts disagreement into authenticated fact..
- [ ] **N5-03** · **P2** · Create adversarial echo-chamber graph generator for star, chain and clustered teams. **Acceptance:** Same source rumor propagates with controlled topology and timings..
- [ ] **N5-04** · **P2** · Benchmark majority, reputation, independent-root and evidence-quality aggregation policies. **Acceptance:** Measure accuracy, convergence, minority preservation and action errors..
- [ ] **N5-05** · **P2** · Introduce disagreement budget for context assembly without forcing all contested alternatives into every prompt. **Acceptance:** Budgeted selector preserves action-relevant uncertainty or returns an explicit insufficiency marker..
- [ ] **N5-06** · **P2** · Simulate Byzantine agents who lie, replay, copy or selectively withdraw evidence. **Acceptance:** Safety results are conditional on explicit threat model and fault fraction..
- [ ] **N5-07** · **P2** · Implement source-root deduplication across multiple federation hops with cycle guards. **Acceptance:** A copied memo never acquires spurious independence through relaying..
- [ ] **N5-08** · **P2** · Add minority-origin resilience tests where one uncommon correct claim opposes many correlated wrong claims. **Acceptance:** The correct independent alternative remains retrievable and flagged for validation..
- [ ] **N5-09** · **P2** · Measure stale knowledge during partition under lease-validity and reconnection scenarios. **Acceptance:** Reports state consistency/availability tradeoffs rather than promising zero stale knowledge offline..
- [ ] **N5-10** · **P2** · Preregister whether diversity preservation improves recovery after false consensus. **Acceptance:** Compare preexisting H4b mechanisms and require incremental causal contribution..


#### N6 — System 1 decisions, UTCP and governed Code Mode [P1]

**Existing reference points:** `src/memory_fabric/decision_models.py`, `tool_protocol.py`, `adapters/systemone.py`, `tests/test_decision_models.py`, `tests/test_tool_protocol.py`.

- [ ] **N6-01** · **P1** · Keep the existing decision schema and evaluate typed confidence, abstention and escalation on new tasks. **Acceptance:** Every invalid probability vector fails; no selected option authorizes itself..
- [ ] **N6-02** · **P1** · Build dependency-free System 1 router from local features: risk, evidence gaps, tool class and budget. **Acceptance:** Repeated runs are deterministic and avoid new mandatory dependencies..
- [ ] **N6-03** · **P1** · Compare deterministic routing to simulated calibrated and miscalibrated probability sources. **Acceptance:** Safety and utility gains survive deliberately overconfident and reordered predictions..
- [ ] **N6-04** · **P1** · Define feature provenance contracts so poisoned memory cannot directly rewrite policy or tool authority. **Acceptance:** All model/policy outputs remain proposals behind ActionGate..
- [ ] **N6-05** · **P1** · Construct local HTTP/MCP/UTCP equivalent workflows using only loopback mock providers. **Acceptance:** Identical tool semantics, work and permissions; benchmark avoids paid services..
- [ ] **N6-06** · **P1** · Add transport policy checker for dangerous UTCP manuals and unsupported versions. **Acceptance:** Local malicious manual corpus is rejected before any socket or file access..
- [ ] **N6-07** · **P1** · Retain constrained CodeModePlan as default; introduce optional bounded branching only after verification. **Acceptance:** Static analyzer limits loop iterations, recursion, I/O and dynamic tool access with fail-closed behavior..
- [ ] **N6-08** · **P1** · Bind every Code Mode effect to independently checked ActionRequest and per-effect idempotency key. **Acceptance:** Rollback/retry/injected argument tests cannot reuse prior authorization after evidence changes..
- [ ] **N6-09** · **P1** · Measure actual orchestration cost, calls, bytes, latency, and safe completion for direct SDK, MCP and UTCP. **Acceptance:** Results compare equivalent flows without claiming token savings absent model calls..
- [ ] **N6-10** · **P1** · Preregister a novel research claim only around provenance-linked authorization of generated programs. **Acceptance:** Show additional security/utility benefit beyond ordinary sandboxing and simple policy-wrapped tool calls..


---

### PRODUCT HARDENING


#### H1 — Trust boundaries, poisoning and injection [P0]

**Existing reference points:** `src/memory_fabric/governance/`, `authority.py`, `trust.py`, `tools/adversarial_gate.py`, `tests/test_injection_patterns.py`.

- [x] **H1-01** · **P0** · Map untrusted entry points: ingestion, imported memory, tool output, federation, summary and generated plan. **Acceptance:** Threat model names trust boundaries, adversary controls, assets and expected defenses for each. Evidence: `docs/SAFETY_AND_SECURITY.md` §3.1, `tests/test_security_regression.py`, `tests/test_retraction_protocol.py`, `tests/test_adapters.py`, `tests/test_privacy_federation.py`, `tests/test_code_mode_fuzz.py`, `tests/test_action_fence.py`, `research/results/h1-01-trust-boundaries.xml` (DONE: explicit map covers controlled inputs, assets, expected controls and verification tests across memory ingestion/revision, federation, tool output, derived summaries, generated plans and credential/grant configuration; 132 tests and 53 subtests pass; semantic truth and model compliance remain outside the guarantee)..
- [x] **H1-02** · **P0** · Add prompt-injection corpus with role spoofing, source laundering, encoded payload and nested quotation. **Acceptance:** Each case records whether content is blocked, quarantined or safely treated as data. Evidence: `tests/data/prompt_injection_corpus.json`, `tests/test_injection_patterns.py`, `research/results/h1-02-injection-corpus-tests.xml` (DONE: eight frozen cases cover all requested families plus near-misses; direct role spoof and nested injection quarantine; source-laundered and encoded payloads remain non-authoritative candidates; two ordinary near-misses are quarantined as false-withholding examples; 9 tests and 28 subtests pass. This is a local pattern/deterministic contract, not semantic truth verification)..
- [x] **H1-03** · **P0** · Prove untrusted instruction text can never mint grant, change policy, or become system authority. **Acceptance:** Differential tests verify identical grants and rights before and after malicious import. Evidence: `tests/test_authority.py::TheBoundarySurvivesEveryTransformation`, `tests/test_authority.py::test_malicious_import_does_not_change_policy_or_grant_rights`, `tests/test_confused_deputy.py`, `research/results/h1-03-04-authority-delayed-poisoning.xml` (DONE: imported untrusted content preserves the preexisting grant set and remains unusable as action evidence; effective identity is separately bound to authenticated session; 9 focused tests pass. This verifies local policy behavior, not arbitrary host code modification)..
- [x] **H1-04** · **P0** · Test delayed poisoning where benign content becomes malicious after later edits or summarization. **Acceptance:** Provenance retains origin and trust level across transformations and revisions. Evidence: `tests/test_authority.py::TheBoundarySurvivesEveryTransformation`, `tests/test_authority.py::DelayedActivation`, `tests/test_security_regression.py::TestInjection`, `research/results/h1-03-04-authority-delayed-poisoning.xml` (DONE: benign-to-instruction revision becomes untrusted and quarantined; derived summary, tool copy and federation import preserve hostile source lineage and cannot authorize the governed tool; 9 focused tests pass)..
- [x] **H1-05** · **P0** · Reject fake evidence claims based on clean-looking unfamiliar authors without pretending semantic truth verification. **Acceptance:** Unknown claims stay provisional under consequential policies; unrelated safe reads remain usable. Evidence: `tests/test_authority.py::Elevation.test_unfamiliar_claim_stays_unverified_under_strict_policy`, `tests/test_authority.py::Elevation.test_a_reviewer_elevates_a_soft_reason_and_the_gate_then_allows`, `research/results/h1-05-unfamiliar-claim-tests.xml` (DONE: unfamiliar claim remains UNVERIFIED and a consequential policy requiring ELEVATED authority refuses it; a separate safe memory remains readable, and explicit reviewer elevation is exercised; 6 focused tests pass. This establishes provenance/approval handling, not semantic truth)..
- [x] **H1-06** · **P0** · Run replayed-copy and near-duplicate laundering attacks with changing identifiers. **Acceptance:** Exact and supported subset copies preserve lineage; unsupported semantic paraphrase explicitly flagged as limitation. Evidence: `tests/test_duplicates.py::TestTheRule`, `tests/test_duplicates.py::TestInAStore`, `tests/test_duplicates.py::EncodingNoise`, `docs/LIMITATIONS.md`, `research/results/h1-06-copy-laundering-tests.xml` (DONE: exact/annotated copies and Unicode encoding variants resolve to their original source root; re-ingestion after withdrawal arrives contested; corrected values are not merged; 19 tests and 12 subtests pass. Semantic paraphrase remains explicitly unsupported)..
- [x] **H1-07** · **P0** · Add malicious malformed metadata fields, oversized arrays, cyclic references and decoding errors. **Acceptance:** Parser rejects safely within bounded CPU and memory without stack overflow. Evidence: `tests/test_certificates.py::TestMalformed`, `tests/test_code_mode_fuzz.py`, `tests/test_agent_api.py::TestTransportDefences.test_credential_decode_errors_are_refused_cleanly`, `research/results/h1-07-malformed-input-tests.xml` (DONE: malformed fields, 65-entry evidence arrays, cyclic mapping, 600 seeded certificate mutations, bounded Code Mode source/argument/call sizes and malformed credential decoding are refused; 10 tests and 649 subtests pass. Protocol-level caps and recursion rejection are measured; process-wide RSS is not measured)..
- [x] **H1-08** · **P0** · Simulate compromised established writer and revocation racing with action execution. **Acceptance:** High-risk gate blocks post-revocation effects under stated local consistency contract. Evidence: `tests/test_action_race_barriers.py::DeterministicCorrectionRetrievalActionRaces.test_compromised_established_writer_cannot_execute_after_poisoning_revision`, `tests/test_action_race_barriers.py::test_correction_after_retrieval_invalidates_later_action`, `tests/test_action_race_barriers.py::test_fenced_action_commits_before_waiting_correction`, `docs/ACTION_RACE_SERIALIZATION.md`, `research/results/h1-08-compromised-writer-race.xml` (DONE: a legitimate established writer's injected revision is quarantined after retrieval; stale high-risk action is refused and has zero effects; concurrent action/retraction ordering is separately barrier-tested; 4 race tests pass. Guarantee is local and transactionally serialized; remote unseen revocations remain subject to freshness contracts)..
- [x] **H1-09** · **P0** · Run attack mutation test where one critical origin/authority check is disabled. **Acceptance:** Security suite fails conclusively; a green run without effective security assertions is rejected. Evidence: `tools/mutation_check.py`, `tests/test_authority.py`, `research/results/h1-09-authority-mutation.json` (DONE: current-source run killed all 21/21 critical guard mutants, including “authority is not inherited from sources”; zero survivors; the harness requires each baseline test group to pass before it treats a mutant as killed)..
- [x] **H1-10** · **P0** · Publish observed detection, false positives and bypass categories by attack family. **Acceptance:** No blanket 'prompt-injection proof' claim, and defenses cannot hide high false-withholding costs. Evidence: `tests/data/prompt_injection_corpus.json`, `tests/test_injection_patterns.py`, `tools/prompt_injection_corpus_report.py`, `research/results/h1-10-injection-outcomes.json` (DONE: all 8 fixture expectations matched; 2/2 near-misses were quarantined (observed false-withholding examples); encoded and source-laundered cases remained non-authoritative candidates; family-level counts and bypass categories are published. This tiny deterministic contract sample is not a real-world precision/recall estimate and explicitly supports no prompt-injection-proof claim)..


#### H2 — Action safety, tool execution and sandboxed Code Mode [P0]

**Existing reference points:** `src/memory_fabric/actions.py`, `action_receipt.py`, `tool_protocol.py`, `tests/test_action_fence.py`, `tests/test_tool_protocol.py`.

- [x] **H2-01** · **P0** · Test that authorize-then-execute uses live revalidation rather than a stale authorization snapshot. **Acceptance:** Correction between planning and execution blocks consequential effect. Evidence: `tests/test_action_race_barriers.py`, `docs/ACTION_RACE_SERIALIZATION.md`..
- [x] **H2-02** · **P0** · Bind each action to exact tool name, target, argument digest, tenant, agent and grant expiry. **Acceptance:** Any mutation of one bound field invalidates execution request. Evidence: `tests/test_authority.py`, `docs/ACTION_GRANT_BINDING.md`..
- [x] **H2-03** · **P0** · Reject duplicate action keys with mismatched payloads and make same-payload retries idempotent. **Acceptance:** Local mock side effect executes once despite client retries and injected failures. Evidence: `tests/test_action_fence.py`, `tests/test_action_crash.py`, `docs/ACTION_IDEMPOTENCY.md`..
- [x] **H2-04** · **P0** · Document crash-after-side-effect ambiguity and add reconciliation ledger for simulated external effects. **Acceptance:** Recovery distinguishes completed, unknown and definitely unexecuted states without promising atomic external systems. Evidence: `src/memory_fabric/actions.py`, `tests/test_action_reconciliation.py`, `tests/test_action_crash.py`, `docs/ACTION_RECONCILIATION.md`..
- [x] **H2-05** · **P0** · Build strict Code Mode parser fuzz suite: imports, eval, attribute access, comprehensions, reflection. **Acceptance:** Unsupported constructs fail before execution; no generic interpreter access is introduced. Evidence: `tests/data/code_mode_malicious_plans.json`, `tests/test_code_mode_fuzz.py`, `docs/DECISION_MODELS_AND_UTCP.md`..
- [x] **H2-06** · **P0** · Enforce per-tool allowlists, maximum calls, argument depth, byte size and recursion/branch limits. **Acceptance:** Time/memory and call-count limits hold against generated pathological plans. Evidence: `src/memory_fabric/tool_protocol.py`, `tests/test_code_mode_fuzz.py`, `docs/DECISION_MODELS_AND_UTCP.md`..
- [x] **H2-07** · **P0** · Disable non-loopback outbound network for offline sandbox smoke tests and test blocked egress. **Acceptance:** Unsupported network attempt produces clear denial and no host resource access. Evidence: `tools/offline_network_guard.py`, `tests/test_offline_network_guard.py`, `docs/DECISION_MODELS_AND_UTCP.md`..
- [x] **H2-08** · **P0** · Reject SSRF, localhost redirect, file URL, command injection and unexpected URI schemes in UTCP transport. **Acceptance:** Manual parsing is side-effect-free and transport validation is explicit. Evidence: `src/memory_fabric/tool_protocol.py`, `tests/data/utcp_malicious_manuals.json`, `tests/test_tool_protocol.py`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/h2-08-utcp-transport.json`, `research/results/h2-08-utcp-transport-tests.xml`..
- [x] **H2-09** · **P0** · Verify execution receipt stores evidence version, policy version, tool digest and outcome without secrets. **Acceptance:** Replay and redaction tests preserve auditability and confidentiality. Evidence: `src/memory_fabric/actions.py`, `src/memory_fabric/events.py`, `tests/test_action_execution_receipt.py`, `docs/ACTION_RECONCILIATION.md`, `research/results/h2-09-execution-receipt.json`, `research/results/h2-09-execution-receipt-tests.xml`..
- [x] **H2-10** · **P0** · Test 'confused deputy' where low-trust agent asks privileged tool to execute via another agent's descriptor. **Acceptance:** Tool resolves effective identity at execution and rejects privilege crossing. Evidence: `src/memory_fabric/actions.py`, `src/memory_fabric/tool_protocol.py`, `tests/test_confused_deputy.py`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/h2-10-confused-deputy.json`, `research/results/h2-10-confused-deputy-tests.xml`..


#### H3 — Tenant isolation, privacy and erasure [P0]

**Existing reference points:** `src/memory_fabric/tenancy.py`, `governance/erasure.py`, `identity.py`, `governance/cipher.py`, `tests/test_erasure_residue.py`.

- [x] **H3-01** · **P0** · Create cross-tenant read/write/delete/infer matrix across SDK, HTTP, MCP, query and dashboard. **Acceptance:** Every surface refuses unauthorized scope without revealing whether foreign data exists. Evidence: `src/memory_fabric/_fabric/core.py`, `src/memory_fabric/observability/control.py`, `tests/test_cross_tenant_surface_matrix.py`, `tests/test_privacy_federation.py`, `docs/SAFETY_AND_SECURITY.md`, `research/results/h3-01-cross-tenant-matrix.json`, `research/results/h3-01-cross-tenant-matrix-tests.xml`..
- [x] **H3-02** · **P0** · Add metadata side-channel probes using result count, timing class, errors and search suggestions. **Acceptance:** Cross-tenant protected identifiers do not leak through response shape or detail. Evidence: `tests/test_metadata_sidechannels.py`, `tests/test_metadata_leakage.py`, `docs/SAFETY_AND_SECURITY.md`, `research/results/h3-02-metadata-sidechannels.json`, `research/results/h3-02-metadata-sidechannels-tests.xml`..
- [x] **H3-03** · **P0** · Validate physically separated local tenant stores have distinct keys, paths and backup destinations. **Acceptance:** Arbitrary tenant ID cannot escape store directory or alias another tenant's key. Evidence: `src/memory_fabric/tenancy.py`, `tests/test_tenancy.py`, `tests/test_backup_custody.py`, `research/results/h3-03-physical-tenancy.json`, `research/results/h3-03-physical-tenancy-tests.xml`..
- [x] **H3-04** · **P0** · Rotate/revoke credentials during active session and retried action. **Acceptance:** Permissions are re-evaluated and revoked identities cannot use already-cached authorization. Evidence: `tests/test_credential_rotation_actions.py`, `tests/test_service.py`, `tests/test_action_fence.py`, `research/results/h3-04-credential-rotation-tests.xml`, `research/results/h3-04-credential-rotation.json`..
- [x] **H3-05** · **P0** · Test personal-data redaction in logs, exceptions, artifacts, traces and support exports. **Acceptance:** Automated scanner finds zero injected synthetic secrets outside explicitly encrypted fixture. Evidence: `tests/test_personal_data_redaction.py`, `tools/scan_secrets.py`, `research/results/h3-05-personal-data-redaction.json`, `research/results/h3-05-personal-data-redaction-tests.xml`..
- [x] **H3-06** · **P0** · Implement retention policy fuzzing with zero, boundary and very large TTL. **Acceptance:** Purges occur at documented time; legal/audit preservation is explicitly separate and disclosed. Evidence: `src/memory_fabric/governance/retention.py`, `tests/test_retention_boundaries.py`, `docs/RETENTION_AND_AUDIT_PRESERVATION.md`, `research/results/h3-06-retention-boundaries.json`, `research/results/h3-06-retention-boundaries-tests.xml`..
- [x] **H3-07** · **P0** · Run erasure residue scans over snapshots, indexes, caches, compaction, branch heads and pending federation queues. **Acceptance:** Erased records never reappear through supported read surfaces after purge. Evidence: `src/memory_fabric/events.py`, `src/memory_fabric/_fabric/core.py`, `src/memory_fabric/retrievers.py`, `tests/test_erasure_residue.py`, `tests/test_retrievers.py`, `research/results/h3-07-erasure-residue.json` (DONE: indexes, built-in embedding caches including interrupted-erasure replay, topic cache, compaction summaries, branch history and pending federation queues are probed; custom embedder caches must implement the erasure hooks)..
- [x] **H3-08** · **P0** · Document backup erasure limits and implement local restore-with-tombstone reconciliation. **Acceptance:** Restoring an older backup never silently restores previously erased actionable data. Evidence: `src/memory_fabric/cli.py`, `tests/test_restore_erasure_reconciliation.py`, `docs/RETENTION_AND_AUDIT_PRESERVATION.md`, `research/results/h3-08-backup-erasure-limits.json`..
- [x] **H3-09** · **P0** · Add small k-anonymity-style aggregation leak probes for metrics dashboards. **Acceptance:** Tenant metrics cannot reveal one other tenant's content or activity by exact sparse counts. Evidence: `src/memory_fabric/observability/metrics.py`, `tests/test_metrics.py`, `tests/test_control_center.py`, `docs/OPERATIONS.md`, `research/results/h3-09-sparse-metrics.json`, `research/results/h3-09-sparse-metrics-tests.xml` (DONE: metrics expose store-wide totals only; sparse canaries are absent and a k=3 tenant identity permutation produces byte-identical metrics. Endpoint remains operator-token-only)..
- [x] **H3-10** · **P0** · Test cryptographic key-loss, wrong key and ciphertext corruption behavior. **Acceptance:** Errors are controlled, no plaintext fallback, and recovery instructions are accurate. Evidence: `tests/test_cipher.py`, `tests/test_event_schema_hardening.py`, `tests/test_doctor.py`, `docs/TROUBLESHOOTING.md`, `docs/RUNBOOKS.md`, `research/results/h3-10-key-loss.json`, `research/results/h3-10-key-loss-tests.xml`..


#### H4 — Resilience, recovery and consistency limits [P0]

**Existing reference points:** `src/memory_fabric/outbox.py`, `eventlog.py`, `freshness.py`, `tools/`, `tests/test_backup.py`, `tests/test_multiprocess_crash.py`.

- [x] **H4-01** · **P0** · Run fault injection after every stage of append, correction, erase and action receipt. **Acceptance:** Replay restores valid prefix with no partial logical operation. Evidence: `tests/test_write_fault_injection.py`, `research/results/h4-01-stage-fault-injection.json`, `research/results/h4-01-stage-fault-injection-tests.xml`..
- [x] **H4-02** · **P0** · Test power-loss simulation using abruptly terminated writer processes. **Acceptance:** Reopen integrity and consistency checks pass; corrupted stores fail clearly and read-only. Evidence: `tests/test_multiprocess_crash.py`, `tests/crashworker.py`, `tests/test_cipher.py`, `tests/test_event_schema_hardening.py`, `research/results/h4-02-power-loss.json`, `research/results/h4-02-power-loss-tests.xml` (abrupt process termination tested; physical power-loss/storage-cache behavior is not simulated)..
- [x] **H4-03** · **P0** · Exercise disk-full, permission-denied, readonly filesystem and malformed storage path. **Acceptance:** User gets specific actionable error; no silent partial success. Evidence: `src/memory_fabric/eventlog.py`, `tests/test_storage_failure_modes.py`, `research/results/h4-03-storage-failure.json`, `research/results/h4-03-storage-failure-tests.xml` (DONE: Windows ACL denial now produces a path-specific permission/storage diagnostic and leaves no partial store; malformed path, SQLite full rollback and read-only refusal are also tested)..
- [x] **H4-04** · **P0** · Simulate network partition with correction pending and old lease still valid. **Acceptance:** Contract accurately bounds stale exposure; high-risk action expires lease rather than inventing awareness. Evidence: `src/memory_fabric/freshness.py`, `docs/FRESHNESS_LEASES.md`, `tests/test_freshness.py`, `tests/test_tombstone_exchange.py`, `research/results/h4-04-partition-lease-timing.json`, `research/results/h4-04-partition-lease-timing-tests.xml` (DONE: a v1→v2 correction remains queued while the peer retains v1; with a 10,000 ms lease, high-risk action is allowed at 9,999 ms and refused at 10,000 ms, while safe local reads remain available; 26 tests and 12 subtests pass. This is a deterministic in-process partition model, not a physical network SLO)..
- [x] **H4-05** · **P0** · Apply duplicate/reordered correction messages across a 3-process local federation. **Acceptance:** Converges idempotently and records outstanding acknowledgements accurately. Evidence: `tests/test_tombstone_exchange.py`, `tests/test_multiprocess_crash.py`, `research/results/h4-05-reordered-corrections.json`, `research/results/h4-05-reordered-corrections-tests.xml`..
- [x] **H4-06** · **P0** · Test retry storms and dead-letter replay under worker crashes. **Acceptance:** Queue length remains bounded; alerts and repair procedure expose irrecoverable items. Evidence: `src/memory_fabric/outbox.py`, `tests/test_federation_transport.py`, `tests/test_retraction_protocol.py`, `research/results/h4-06-retry-deadletter.json`, `research/results/h4-06-retry-deadletter-tests.xml` (HTTP transport socket tests were unavailable in this sandbox; dead-letter retry is operator initiated)..
- [x] **H4-07** · **P0** · Verify checkpoint tampering and replay of old signed checkpoints. **Acceptance:** Current trust anchor detects unauthorized rewrite; local-only anchor limitations are disclosed. Evidence: `tests/test_checkpoint_rewrite.py`, `tests/test_integrity_chain.py`, `tests/test_freshness.py`, `research/results/h4-07-checkpoint-trust.json`, `research/results/h4-07-checkpoint-trust-tests.xml` (anchor must be held beyond the store writer's reach)..
- [x] **H4-08** · **P0** · Perform backup, restore, schema upgrade and rollback drill in isolated temporary directories. **Acceptance:** Verify data, grants, tombstones, audited versions and event hashes before accepting restored state. Evidence: `tests/test_backup.py`, `tests/test_version_skew.py`, `tests/test_historical_fixtures.py`, `tests/test_backup_restore_qualification.py`, `research/results/h4-08-backup-upgrade.json`, `research/results/h4-08-backup-upgrade-tests.xml`, `research/results/p5-04-upgrade-rollback-smoke.json` (DONE: authenticated v0.11.0 data upgrades and restores with the same event-chain head; quarantined state, pending retraction, v2 audited evidence and durable action grants survive; used and unused grant behavior is checked after restore; package rollback after a post-upgrade correction and append also passes; 35 tests and 20 subtests pass. Static ActionPolicy configuration must be supplied by the host during restore)..
- [x] **H4-09** · **P0** · Simulate time moving backward/forward and malformed clocks in expiry checks. **Acceptance:** Monotonic or explicit wall-clock assumptions are documented and tested. Evidence: `src/memory_fabric/freshness.py`, `docs/FRESHNESS_LEASES.md`, `tests/test_freshness.py`, `tests/test_certificates.py`, `tests/test_identity.py`, `research/results/h4-09-clock-skew.json`, `research/results/h4-09-clock-skew-tests.xml` (DONE: invalid and raising wall/monotonic callbacks fail closed, backwards monotonic movement permanently expires held leases until renewed, safe reads remain usable, and forward/backward expiry assumptions are documented; 89 tests and 619 subtests pass)..
- [x] **H4-10** · **P0** · Create a local incident-replay command that reconstructs all events for one decision. **Acceptance:** Produces timeline and cause without executing tools or exposing unredacted confidential data. Evidence: `src/memory_fabric/incident.py`, `src/memory_fabric/response.py`, `src/memory_fabric/cli.py`, `tests/test_incident.py`, `tests/test_response.py`, `research/results/h4-10-incident-replay.json`, `research/results/h4-10-incident-replay-tests.xml` (dependencies are not asserted as causation; content is excluded)..


#### H5 — Secure SDLC, static analysis and adversarial release gates [P1]

**Existing reference points:** `tools/scan_secrets.py`, `tools/adversarial_gate.py`, `tools/check.py`, `.github/workflows/`, `SECURITY.md`.

- [ ] **H5-01** · **P1** · Generate dependency and build provenance inventory for core and optional extras from local lock metadata. **Acceptance:** Every released artifact has package list, source SHA and reproducible build instructions. Evidence: `pyproject.toml`, `tools/dependency_provenance.py`, `research/results/h5-01-dependency-provenance.json` (PARTIAL: project and installed package inventory exists; no lock metadata or reproducible artifact build is available)..
- [x] **H5-02** · **P1** · Enable static lint/type/security checks already locally available as hard release gates. **Acceptance:** Missing executable is shown as UNAVAILABLE rather than silently counted green. Evidence: `tools/check.py`, `tools/adversarial_gate.py`, `tests/test_secure_sdlc_inventory.py`, `research/results/h5-02-adversarial-gate.json`, `research/results/h5-02-static-security-gates.json`, `research/results/h5-01-02-local-tool-inventory-tests.xml`, `research/results/p5-02-local-checks.txt` (DONE: Ruff, mypy (176 files/0 issues), secret scan (127 examined/0 unexpected), security AST scan (16 modules/0 findings), internal findings gate, documentation tests and adversarial gate (21/21 families, 279 tests) pass. `pip-audit` and `bandit` are explicitly reported UNAVAILABLE, not counted green)..
- [x] **H5-03** · **P1** · Add AST-based scan for dangerous deserialization, subprocess, eval and unsafe path joins in security modules. **Acceptance:** Verified known-positive fixture causes scan failure and approved exceptions require rationale. Evidence: `tools/security_ast_scan.py`, `tools/security_ast_exceptions.json`, `tests/test_security_ast_scan.py`, `research/results/h5-03-security-ast.json`, `research/results/h5-03-security-ast-tests.xml` (DONE: 16 security modules scanned; zero unapproved findings; known-positive and rationale-matched exception tests pass; static pattern checks do not establish general taint safety)..
- [x] **H5-04** · **P1** · Validate package assets contain no real secrets, test corpora credentials or unexpected binary files. **Acceptance:** Inspect generated wheel/sdist and fail on allowlist violations. Evidence: `tools/audit_package_assets.py`, `tests/test_package_asset_audit.py`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/publish-pypi.yml`, `research/results/h5-04-package-asset-audit.json`, `research/results/h5-04-package-asset-tests.xml` (DONE: built wheel and sdist contain only allowed text assets, no high-severity secret findings, corpora, or binary assets; mutation fixtures fail as required)..
- [x] **H5-05** · **P1** · Add mutation testing on ActionGate, authority, erasure, identity and network filters. **Acceptance:** Critical mutations are killed by tests; surviving mutation list becomes prioritized bug backlog. Evidence: `tools/mutation_check.py`, `tests/test_enforcement_tenant.py`, `tests/test_erasure_key_destroy.py`, `tests/test_transport_auth.py`, `research/results/h5-05-mutation-qualification.json`, `research/results/h5-05-mutation-contract-tests.xml` (DONE: all 21 curated critical guard mutations killed; prioritized survivor backlog empty; socket-dependent HTTP integration is still blocked by this sandbox)..
- [x] **H5-06** · **P1** · Freeze adversarial test registry with attack-family completeness check. **Acceptance:** A missing attack family cannot accidentally turn the gate green. Evidence: `tests/data/adversarial_family_registry.json`, `tools/adversarial_gate.py`, `tests/test_adversarial_registry.py`, `research/results/h5-06-adversarial-registry.json`, `research/results/h5-06-adversarial-registry-tests.xml` (DONE: 21 frozen families and their test selectors validate; removing a family, changing selectors, empty selectors, and duplicate families fail the registry check)..
- [x] **H5-07** · **P1** · Run fuzzing from checked-in seed corpus under strict memory/time budget. **Acceptance:** Crashes, hangs, data leaks and unauthorized actions are regression fixtures. Evidence: `tests/data/security_fuzz_seeds.json`, `tests/data/code_mode_malicious_plans.json`, `tools/fuzz_security_boundaries.py`, `tests/test_security_fuzz.py`, `.github/workflows/ci.yml`, `research/results/h5-07-security-fuzz.json`, `research/results/h5-07-security-fuzz-tests.xml` (DONE: 600 deterministic cases; 0.28s; 214,341-byte peak traced heap under a 64 MiB cap; 48 action-gate denials; zero handler executions/findings; failures persist as replayed regression seeds; RSS is not measured by the Python heap cap)..
- [x] **H5-08** · **P1** · Build deterministic endpoint rate-limit and quota tests under credential cycling. **Acceptance:** Rejected excess traffic causes no partial write or uncontrolled memory growth. Evidence: `src/memory_fabric/agent_api.py`, `src/memory_fabric/limits.py`, `tests/test_agent_api_rate_limit.py`, `tools/rate_limit_qualification.py`, `.github/workflows/ci.yml`, `research/results/h5-08-rate-limit-qualification.json`, `research/results/h5-08-rate-limit-tests.xml` (DONE: 128 credential cycle yields 2 writes/126 rate refusals with one agent bucket; store quota rejects 30/32 writes without event changes; 500 address keys remain capped at configured 16; auth refusals do not write)..
- [x] **H5-09** · **P1** · Ensure production-safe defaults require explicit opt-in for experimental model checks or dynamic tools. **Acceptance:** Fresh install passes configuration audit and exposes no default remote listeners. Evidence: `tools/audit_production_defaults.py`, `tests/data/default_features.json`, `tests/test_presets.py`, `.github/workflows/ci.yml`, `research/results/h5-09-production-defaults.json` (DONE: isolated fresh wheel install passes 10/10 checks; model/rerank and dynamic MCP defaults are off; listener factories default to loopback; import starts no sockets or threads)..
- [x] **H5-10** · **P1** · Generate machine-readable internal security findings with severity, exploit preconditions and verified fixes. **Acceptance:** Unresolved critical/high findings block local-ready label; independent audit remains external. Evidence: `research/security/internal_findings.json`, `tools/security_findings.py`, `tests/test_security_findings.py`, `tools/check.py`, `research/results/h5-10-internal-security-findings.json`, `research/results/h5-10-finding-verification.xml` (DONE: register covers 8 historical high and 7 accepted/external items; gate fails closed for limited/unresolved critical/high evidence and records the external audit separately; focused available checks 81 passed and 280 subtests passed; HTTP concurrency test was blocked by WinError 10013 and emitted thread warnings, so F1 remains a local-ready blocker; F16 multihop HTTP remains unverified in this socket-restricted environment)..


---

### PRODUCT


#### P1 — First-run experience and developer integration [P1]

**Existing reference points:** `src/memory_fabric/cli.py`, `tour.py`, `demo.py`, `sdk.py`, `docs/QUICKSTART.md`, `docs/COOKBOOK.md`.

- [x] **P1-01** · **P1** · Create one verified 60-second zero-credential getting-started path using only bundled fixtures. **Acceptance:** Clean offline install can initialize, ingest, correct, recall and see changed action status..

P1-01 completion evidence: a clean temporary target install uses no index, runtime dependencies, credentials, hosted model, or external endpoint. The deterministic fixture initializes a store, ingests and retrieves a reviewed fact, authorizes an action, corrects the fact, observes the prior action become blocked, and retrieves the replacement. A CI test asserts installation plus the example complete within 60 seconds. Evidence: `examples/getting_started.py`, `docs/QUICKSTART.md`, `tests/test_examples_run.py`, `research/results/p1-01-example-tests.json`, `research/results/p1-01-example-tests.txt`. The local build backend prerequisite is setuptools>=77 already available in the Python environment.
- [x] **P1-02** · **P1** · Provide three executable examples: personal agent, multi-agent team and governed decision. **Acceptance:** Examples run in CI without any hosted model or external endpoint..

P1-02 completion evidence: the offline example suite runs the personal-agent, multi-agent-team, and governed-action examples as clean subprocesses; the multi-agent example uses fixed fixtures and no hosted model or external endpoint. The CI workflow runs the same test suite. Evidence: `examples/reference_agent.py`, `examples/multi_agent_team.py`, `examples/action_gate.py`, `examples/README.md`, `tests/test_examples_run.py`, `research/results/p1-02-example-tests.json`, `research/results/p1-02-example-tests.txt`. CI is configured to run these tests; this branch has not yet received a GitHub CI run.
- [x] **P1-03** · **P1** · Make every example label simulated agents and deterministic fixtures visibly. **Acceptance:** Examples cannot imply live-LLM success or independently verified compliance..

P1-03 completion evidence: every runnable example prints a `DEMO ONLY` label at startup. The labels distinguish deterministic or scripted examples from the local Ollama model demonstration and explicitly disclaim independent evaluation or certification. `tests/test_examples_run.py` checks the marker in every example source and every offline example's actual output. Evidence: `examples/*.py`, `examples/README.md`, `tests/test_examples_run.py`, `research/results/p1-03-example-labels.json`, `research/results/p1-03-example-labels.txt`.
- [x] **P1-04** · **P1** · Expose minimal SDK API for add, recall, correct, explain, decide and safe execute. **Acceptance:** Public typed methods have documented errors and runnable sample tests..

P1-04 completion evidence: `examples/sdk_workflow.py` composes typed agent add/recall, operator explain/review, correction, deterministic decision proposal, and `ActionGate.execute`; the stale action is refused and no second effect occurs. `docs/SDK_WORKFLOW.md` documents typed refusals/errors and the agent/operator separation. The CI example runner executes the sample. Evidence: `src/memory_fabric/sdk.py`, `src/memory_fabric/decision_models.py`, `src/memory_fabric/actions.py`, `src/memory_fabric/correction.py`, `examples/sdk_workflow.py`, `docs/SDK_WORKFLOW.md`, `tests/test_sdk.py`, `tests/test_examples_run.py`, `research/results/p1-04-sdk-workflow.json`, `research/results/p1-04-sdk-workflow.txt`.
- [x] **P1-05** · **P1** · Introduce setup doctor with actionable checks for store, keys, schema, ports and disk limits. **Acceptance:** Each injected misconfiguration identifies a concrete repair command without data loss..

P1-05 completion evidence: the doctor retains its store, key and schema checks and adds opt-in local port and disk-floor checks. Injected occupied-port and low-disk conditions return concrete repairs; tests confirm the event log is unchanged. Evidence: `src/memory_fabric/cli.py`, `tests/test_doctor.py`, `docs/OPERATIONS.md`, `docs/CLI.md`, `research/results/p1-05-setup-doctor.json`, `research/results/p1-05-setup-doctor.txt`. Port availability is a time-of-check probe, and disk capacity for PostgreSQL must be checked on the database host.
- [x] **P1-06** · **P1** · Ensure path, key and identity defaults are safe on Windows, macOS and Linux. **Acceptance:** Tests cover home directory, temp paths, spaces and unicode..

P1-06 completion evidence: portability fixtures cover a mocked per-user home containing spaces and Unicode, temporary store/import/lease paths, first-run initialization with external key custody below a Unicode path, reopen/decryption, UTF-8 identities and the default tenant. The exact-commit Windows run passed. CI is configured for Windows, macOS and Linux with Python 3.11–3.13; no GitHub run is available for this branch yet. Evidence: `tests/test_connect.py`, `tests/test_portable_paths.py`, `tests/test_first_run.py`, `.github/workflows/ci.yml`, `research/results/p1-06-portable-paths.json`, `research/results/p1-06-portable-paths.txt`.
- [x] **P1-07** · **P1** · Add 'why was this blocked?' example with per-rule reason codes and evidence pointers. **Acceptance:** Developer reproduces failure and repair path without inspecting eventlog internals..

P1-07 completion evidence: the runnable `why_blocked.py` fixture refuses a stale certificate, prints the configured tool rule, `evidence_withdrawn` reason, public human-readable explanation, full memory pointer and a concrete re-certification repair. It then demonstrates the repair with a newly reviewed memory. The example uses `reasons.describe` and does not read the event log directly; the offline example suite asserts these outputs. Evidence: `examples/why_blocked.py`, `examples/README.md`, `tests/test_examples_run.py`, `tests/test_reasons.py`, `docs/TROUBLESHOOTING.md`, `research/results/p1-07-why-blocked.json`, `research/results/p1-07-why-blocked.txt`. The fixture is deterministic and performs no external action.
- [x] **P1-08** · **P1** · Implement explicit offline mode preventing any accidental API or network dependency. **Acceptance:** Offline test fails if forbidden socket/network access occurs during quickstart..

P1-08 completion evidence: `memory_fabric.offline.offline_mode()` temporarily blocks Python DNS, TCP connection and socket-send paths, restores prior behavior on exit, and raises `NetworkAccessDenied` at the attempted access. The runnable quickstart uses this guard; tests exercise blocked TCP, UDP and DNS plus a successful full quickstart while guarded. The scope is accidental Python-level network use, not a security sandbox for child processes or untrusted native code. Evidence: `src/memory_fabric/offline.py`, `examples/quickstart.py`, `tests/test_quickstart.py`, `docs/QUICKSTART.md`, `docs/API.md`, `research/results/p1-08-offline-mode.json`, `research/results/p1-08-offline-mode.txt`.
- [x] **P1-09** · **P1** · Include local memory-vs-simple-store demonstration using exactly equal test information. **Acceptance:** Script prints both task utility and safety outcomes without cherry-picked labels..

P1-09 completion evidence: `memory_vs_json.py` feeds one shared, two-record fixture to a JSON-style last-write-wins map and Memory Fabric, prints corrected-setting utility and stale-action safety for both, and demonstrates fresh action authorization. It labels the JSON baseline's missing gate and explicitly says the one-case counts are not general performance evidence. The offline example runner asserts input equality, both safety outcomes and the scope label. Evidence: `examples/memory_vs_json.py`, `examples/README.md`, `tests/test_examples_run.py`, `research/results/p1-09-memory-vs-json.json`, `research/results/p1-09-memory-vs-json.txt`.
- [x] **P1-10** · **P1** · Provide a 15-minute migration guide from basic JSON/vector recall to governed memory. **Acceptance:** Test fixture migrates sample records, validates ownership and preserves original data..

P1-10 completion evidence: the 15-minute guide explains a reversible export/import/review/canary path and the limits of vector-index migration. Its fixture covers Mem0, LangChain and plain JSON shapes. The test verifies source bytes/hash unchanged, imported authors/source IDs/tenant attribution, candidate visibility before review, reviewed visibility and cross-tenant isolation. Evidence: `docs/guides/migrate-from-json-vector.md`, `docs/MIGRATION.md`, `examples/fixtures/basic-memory-export.jsonl`, `tests/test_migration_guide.py`, `research/results/p1-10-migration-guide.json`, `research/results/p1-10-migration-guide.txt`.


#### P2 — Control Center and decision observability UX [P1]

**Existing reference points:** `src/memory_fabric/observability/`, `docs/images/`, `tests/test_control_center_ui.py`, `src/memory_fabric/context_receipt.py`.

- [x] **P2-01** · **P1** · Add a decision-centric detail view with action, evidence, provenance and current support status. **Acceptance:** UI snapshot test verifies reason codes and identity scope from API fixture..

P2-01 completion evidence: action detail API responses now bind each gate record to agent, tenant and claim scope and include each cited memory's historical/current versions, current lifecycle, claim assessment, sanitized content, provenance, origin authority and support recomputation. The dashboard renders those fields and explicitly separates support status from permission to act. An API/UI fixture asserts `evidence_withdrawn`, identity scope, provenance, support and non-usable state, and verifies that viewing details writes no events. Evidence: `src/memory_fabric/observability/control.py`, `src/memory_fabric/observability/static/dashboard.html`, `tests/test_control_center_ui.py`, `tests/test_control_center.py`, `research/results/p2-01-decision-detail.json`, `research/results/p2-01-decision-detail.txt`.
- [x] **P2-02** · **P1** · Display source history and correction propagation using stable event IDs, not guessed summaries. **Acceptance:** Every graph edge opens a corresponding logged event..

P2-02 completion evidence: lineage graph and map edges carry immutable event IDs and sequence numbers; the read-only event detail endpoint resolves each ID to the matching event; timeline entries open the corresponding event detail. Twenty-two control-center tests pass on exact source commit `6776203b67c551f695e8533b3e5a140da2c52bb2`. Topic similarity links are not provenance edges and are not presented as event-backed lineage. Evidence: `src/memory_fabric/observability/control.py`, `src/memory_fabric/observability/server.py`, `src/memory_fabric/observability/static/dashboard.html`, `tests/test_control_center_ui.py`, `research/results/p2-02-event-links.json`, `research/results/p2-02-event-links.txt`.
- [ ] **P2-03** · **P1** · Show 'blocked because' reasons with a distinction between absent evidence and policy restriction. **Acceptance:** UI never describes unknown truth as false or unsupported as malicious..
- [ ] **P2-04** · **P1** · Add before/after correction impact preview using current preview-digest validation. **Acceptance:** Applying stale preview fails and UI requests a fresh preview..
- [ ] **P2-05** · **P1** · Surface the proportion of valid decisions withheld, not merely blocked attempts. **Acceptance:** Dashboard metrics include denominators, risk class and synthetic-vs-live label..
- [ ] **P2-06** · **P1** · Display per-tool authorization timeline and idempotency receipt state. **Acceptance:** Operators can distinguish executed, denied, retried and reconciliation-needed effects..
- [ ] **P2-07** · **P1** · Create accessible keyboard navigation, color-independent status labels and screen-reader names. **Acceptance:** Automated local accessibility checks and keyboard smoke tests pass..
- [ ] **P2-08** · **P1** · Test large histories, empty state, conflicting evidence and corrupted evidence without UI hangs. **Acceptance:** Pagination and error boundaries preserve data privacy and show recoverable messages..
- [ ] **P2-09** · **P1** · Ensure dashboard read-only by default and require explicit privileged path for mutations. **Acceptance:** Default access cannot correct, erase or approve actions by hidden endpoint..
- [ ] **P2-10** · **P1** · Add offline export of redacted incident report for one selected decision. **Acceptance:** Export includes integrity digests and omits synthetic secret canaries..


#### P3 — Operational self-service, diagnostics and supportability [P1]

**Existing reference points:** `src/memory_fabric/observability/metrics.py`, `src/memory_fabric/manager.py`, `docs/OPERATIONS.md`, `docs/RUNBOOKS.md`.

- [ ] **P3-01** · **P1** · Create SLO dashboard for local latency, error rate, blocked actions, queue depth and correction lag. **Acceptance:** Metrics have explicit denominators, units and test fixtures..
- [ ] **P3-02** · **P1** · Define service health levels healthy, degraded, unsafe-to-execute and unavailable. **Acceptance:** Fault injections map to correct level and do not mask failure as healthy..
- [ ] **P3-03** · **P1** · Add operator explain command for every consequential refusal reason. **Acceptance:** Command shows which policy/evidence was checked and safe remediation..
- [ ] **P3-04** · **P1** · Implement safe dry-run upgrade and schema compatibility diagnosis. **Acceptance:** State remains byte-identical after dry run; incompatibilities are enumerated..
- [ ] **P3-05** · **P1** · Create backup/restore wizard-like CLI procedure with verification checkpoints. **Acceptance:** Offline fixture follows runbook successfully end-to-end with corruption case handled..
- [ ] **P3-06** · **P1** · Make incident replay deterministic for customer support on redacted artifacts. **Acceptance:** Same event history yields same explanation under two runs..
- [ ] **P3-07** · **P1** · Add resource budget knobs for retention, request size, memory count and worker concurrency. **Acceptance:** Invalid settings reject at startup; defaults documented and safe..
- [ ] **P3-08** · **P1** · Test safe behavior for no disk space, disabled optional dependency and offline mode. **Acceptance:** Feature degrades with named reason instead of crashing or silently skipping control..
- [ ] **P3-09** · **P1** · Provide secure support-bundle export that contains no raw sensitive text by default. **Acceptance:** Canary scan confirms export includes schema/metrics but no protected memory..
- [ ] **P3-10** · **P1** · Add runbook drill scripts for outage, key loss, corrupted DB, and mass retraction. **Acceptance:** Each drill has pass/fail proof and includes explicit irrecoverable-case guidance..


#### P4 — Differentiation, comparison harness and buyer use cases [P1]

**Existing reference points:** `benchmarks/scoreboard.py`, `docs/product/CAPABILITY_REGISTRY.md`, `docs/COOKBOOK.md`, `research/results/`.

- [ ] **P4-01** · **P1** · Define three product jobs-to-be-done: correction continuity, governed tool use, and multi-agent knowledge sharing. **Acceptance:** Each has seeded workflow, buyer benefit, baseline and measurable outcome..
- [ ] **P4-02** · **P1** · Build reference ordinary-memory adapter over SQLite/JSON using exactly the same evidence input. **Acceptance:** Comparable workflows avoid artificially weakening the baseline..
- [ ] **P4-03** · **P1** · Benchmark basic retrieval against governed memory on task completion as well as stale actions. **Acceptance:** Claims reflect joint safety/utility results, not only one favorable metric..
- [ ] **P4-04** · **P1** · Add local comparison arms for naive correction deletion and blanket invalidation. **Acceptance:** Show collateral damage and false blocking as first-class costs..
- [ ] **P4-05** · **P1** · Create demo for document correction invalidating one action while sparing unrelated action. **Acceptance:** Deterministic replay proves different outcomes from same evidence lineage..
- [ ] **P4-06** · **P1** · Create multi-agent dispute demo where many copies do not outweigh one independent verified source. **Acceptance:** Explains provenance-aware aggregation without unverified truth claims..
- [ ] **P4-07** · **P1** · Document where plain vector retrieval is sufficient and Memory Fabric adds unnecessary overhead. **Acceptance:** Product comparison avoids over-selling use cases without provenance or protected actions..
- [ ] **P4-08** · **P1** · Measure full installation size, startup time, storage growth and baseline CPU usage. **Acceptance:** Published local-environment table includes methodology and failure thresholds..
- [ ] **P4-09** · **P1** · Create capability matrix marked implemented, experimental, simulated and externally unverified. **Acceptance:** Unsupported sales claims cause automated docs check failure..
- [ ] **P4-10** · **P1** · Write pricing/packaging hypotheses as options without inventing demand or revenue numbers. **Acceptance:** Product plan lists potential free/local/team/enterprise tiers with unvalidated labels..


#### P5 — Release quality, packaging, documentation and internal acceptance [P0]

**Existing reference points:** `docs/MEMORY_FABRIC_RELEASE_CHECKLIST.md`, `docs/PRODUCT_READINESS.md`, `tools/release_bundle.py`, `pyproject.toml`, `docs/LIMITATIONS.md`.

- [x] **P5-01** · **P0** · Build exact-candidate artifact from frozen clean SHA with deterministic build inputs. **Acceptance:** Wheel and sdist contents match allowlist and have signed/hashed internal evidence record. Evidence: `tools/normalize_sdist.py`, `tests/test_normalize_sdist.py`, `research/results/p5-01-exact-candidate.json`, `research/results/p5-01-package-assets.json`, `research/results/p5-01-reproducible-sdist-tests.xml`, `research/results/p5-01-fresh-machine.txt` (DONE: candidate built from clean frozen SHA `2ef5273093b22298e8a8f31de1c03139f6ec0fa8`; independent builds reproduce wheel and normalized sdist hashes; 149 wheel/155 sdist members pass allowlist audit with 0 findings; fresh isolated install/use/doctor/uninstall passes. Candidate artifacts are retained locally under `dist/candidate-2ef5273`; publication remains separately gated)..
- [x] **P5-02** · **P0** · Run full local check suite, lint, docs, adversarial tests and optional-capability audit. **Acceptance:** Any FAIL or unexpectedly SKIPPED critical check blocks candidate. Evidence: `tools/check.py`, `research/results/p5-02-local-checks.txt`, `research/results/p5-02-full-unit-tests.txt`, `research/results/p5-02-adversarial-gate.json`, `research/results/p5-02-local-qualification.json`, `research/results/h5-09-production-defaults.json` (DONE: full unittest discovery on exact pushed source SHA `cc2d1610c54fd71f623e4dc4481d2cfbcdba87bc` passed 2,458 tests with 17 disclosed capability/platform skips and 0 failures; `tools/check.py` passed docs, branding, Ruff, mypy (176 files/0 issues), secret scan, security AST, internal findings gate, documentation tests and adversarial gate (21/21 families, 279 tests). Skips require Anthropic SDK (5), PostgreSQL service (7), Agents SDK framework runtime (1), or POSIX environment (4). `pip-audit` and `bandit` are reported `UNAVAILABLE`; external review remains separately required)..
- [ ] **P5-03** · **P0** · Confirm 3.11, 3.12 and 3.13 compatibility only when actual interpreter is locally available. **Acceptance:** Missing interpreter remains NOT_TESTED; CI evidence needed for full matrix claim. Evidence: `tools/python_compatibility.py`, `research/results/p5-03-python-compatibility.json` (PARTIAL: Python 3.13.5 import smoke passes; 3.11 and 3.12 remain NOT_TESTED because no interpreter is installed/discoverable; a smoke import is not a full compatibility suite)..
- [x] **P5-04** · **P0** · Exercise install/upgrade/rollback from existing supported baseline with persistent data. **Acceptance:** No loss of records, corrections, grants, tombstones or audit evidence in local simulation. Evidence: `tools/upgrade_rollback_smoke.py`, `research/results/p5-04-upgrade-rollback-smoke.json` (DONE: isolated v0.11.0 → v0.14.0 upgrade and rollback preserve the corrected v3 record, quarantined record, appended active record, tombstone history, exact-action GrantIssued event and verified 11-event chain; report binds baseline/candidate wheel hashes and clean driver commit. Host ActionPolicy configuration is separate from the persisted grant event; external effects remain outside this local simulation)..
- [x] **P5-05** · **P0** · Regenerate all user documentation from current API and test code examples. **Acceptance:** Examples run and any broken command prevents local release qualification. Evidence: `tools/gen_stability.py`, `tools/gen_reference.py`, `tests/test_examples_run.py`, `tests/test_doc_examples.py`, `tests/test_reference_docs.py`, `tests/test_user_docs_no_research.py`, `research/results/p5-05-documentation-examples.xml` (DONE: current stability/API/CLI references regenerated with no stale diffs; executable user examples and documentation checks pass, 6 tests and 110 subtests)..
- [ ] **P5-06** · **P0** · Create known-limitations page with measured retrieval, security, latency and federation caveats. **Acceptance:** Nothing is silently removed because a metric is unfavorable..
- [ ] **P5-07** · **P0** · Build release candidate evidence index mapping every 10/10 internal requirement to tests and results. **Acceptance:** Any failed gate is visible in summary and linkable to exact artifact..
- [ ] **P5-08** · **P0** · Document legal/privacy/security compliance as NOT_ASSESSED without outside counsel or auditor. **Acceptance:** No self-certified regulatory or independent security claims appear in README..
- [ ] **P5-09** · **P0** · Generate external-validation handoff packet without claiming it has happened. **Acceptance:** Human review, production pilot, real model benchmark, prior-art review and physical multi-host testing remain OPEN..
- [ ] **P5-10** · **P0** · Assign final status 'OFFLINE-QUALIFIED' only if all internal gates pass; never automatically publish or label production-certified. **Acceptance:** Script refuses full 10/10 attestation without independent evidence and explicit owner approval..


## 5. Five offline graduation gates — must pass together

**Gate G1 — Reproducibility (engineering):** exact-SHA manifests; deterministic and seeded replay; fresh checkout smoke; all critical test failures fixed; appropriate optional skips disclosed. Relevant: E1, E2, E5, P5.

**Gate G2 — Safe utility (research):** held-out 50-agent utility improves over the strongest *matched* arm; unsafe and stale actions do not regress; valid evidence withholding decreases; negative and minority cases remain visible. Relevant: R1, R2, R3, E3, N2.

**Gate G3 — Failure resistance (hardening):** tenant isolation, authorization, correction races, Code Mode, injection, backup/restore and fault simulations pass; high severity internally reproducible issues resolved or explicitly block release. Relevant: H1–H5, E2, E4.

**Gate G4 — Differentiated innovation (novelty):** at least **two** novel *candidate* mechanisms beat nontrivial internal baselines in held-out preregistered ablations while retaining the same safety. Results report causal contribution and negative findings. This justifies an internal research milestone, **not** verified originality over global prior art. Relevant: N1–N6, R4, R5.

**Gate G5 — Offline product qualification (product):** zero-key onboarding, upgrade and restore, operator explanations, Control Center, packaging, docs and developer samples run in an isolated local environment; generated evidence packet has no critical omission. Relevant: P1–P5.

**Internal status logic:**
- `BLOCKED`: one or more P0 tasks/gates fail, or a critical safety regression is known.
- `EXPERIMENTAL`: P0 safety baseline passes but research/product targets not met.
- `OFFLINE-QUALIFIED`: G1–G5 all pass with exact-SHA evidence; **not equivalent to certified production readiness**.
- `EXTERNALLY-VALIDATED`: cannot be achieved under the no-external-input constraint. Requires independent security review, representative users, real model-agent studies, external testbed/pilot and source-aware prior-art review.

## 6. Minimal evidence structure to create and maintain

```text
research/offline_qualification/
  README.md                       # scope, host, scripted-vs-model status
  register.json                   # predeclared experiments, seed splits and targets
  baseline.json                   # SHA, measurements, experimental claims and caveats
  results/                       # generated per-seed machine-readable output
  ablations/                     # matched baseline comparisons and negative controls
  reports/                       # task, latency, security, memory, agent-team scorecards
  claims.json                    # claim -> input digest -> exact result -> status
  release_gates.json             # G1..G5 pass/fail/not-tested and concrete evidence
  known_unverified.json          # things local validation cannot establish
```

Recommended task ledger format:

```json
{
  "task_id": "R2-04",
  "status": "TODO",
  "baseline_sha": "d4fd174ac9056865c8b73abd857fa681daa6a0d7",
  "implementation_paths": [],
  "test_paths": [],
  "result_paths": [],
  "test_command": null,
  "acceptance_passed": false,
  "safety_regression": false,
  "evidence_level": "NOT_TESTED",
  "limitations": []
}
```

**Allowed `evidence_level`:** `NOT_TESTED`, `SIMULATED`, `CONTRACT`, `INTERNAL_INTEGRATION`, `EXTERNAL_INDEPENDENT`. Never auto-assign `EXTERNAL_INDEPENDENT` from repository CI.

## 7. Highest-value paper tracks after the offline gates

| Candidate research contribution | Necessary novel part | Required internal comparison | Paper-ready outcome |
|---|---|---|---|
| **Correction-aware decision continuity** | Incremental decision dependency + justified repair | Current lineage-only, plain versioned memory, blanket invalidation | Fewer stale decisions and fewer unnecessary re-evaluations |
| **Proof-carrying evidence sufficiency** | Minimal action-specific requirement certificates | Existing `answerability`, fixed-budget retrieval, policy-only guards | Safer action decisions without excessive valid withholding |
| **Counterfactual memory value** | Identifiable intervention on decision outcomes | Leave-one-out, recency, smoothed success, H2 prior failure | Lower regret or cost with robust held-out improvement |
| **Provenance-preserving compression** | Correction-safe compressed history with retained dependency proof | Exact history, extractive summary, ordinary compaction | Comparable decision success at smaller bytes/context |
| **Diversity-preserving collective belief** | Source-root-aware preservation of contested alternatives | Majority vote, naive reputation, independent-roots, H4b existing method | Better recovery from correlated misinformation |
| **Governed programmatic action** | Per-effect evidence authorization across generated code plans | SDK, MCP, UTCP, generic policy sandbox | Lower orchestration cost at equivalent authorization correctness |

**Prior-art caution:** memory graphs, causal credit, multi-agent consensus, adaptive routing, and tool governance are existing research areas. A paper must isolate an incremental mechanism, compare it with the strongest existing alternative, and undergo genuine prior-art review before claiming novelty. Benchmark designs can be inspired by public long-horizon agent-memory research, but the implementations here require no data download.

## 8. Explicitly excluded from automatic 10/10 claims

- External penetration test, external safety certification, statutory compliance signoff, or independent code audit.
- Real-users usability sessions, market validation, pilots, enterprise willingness to pay, and live SLO measurements.
- Real frontier-model agent evaluation (unless a model and its weights already exist locally, which is not assumed here).
- True cross-physical-host availability and fault tolerance.
- Novelty over the full published scientific literature, patentability or publication acceptance.
- Absolute zero defects, zero unsafe actions in all circumstances, or mathematically proven perfect accuracy.
- PyPI account configuration, trusted publishing and external release approval.

**Completion principle:** shipping *less* code with stronger evidence is better than shipping more unvalidated modules. If a workstream fails its preregistered test, keep that failure, fix the hypothesis or revert the feature. The highest-impact improvement is still: **increase valid task completion while maintaining robust withdrawal/correction safety and transparent evidence about every claim**.
