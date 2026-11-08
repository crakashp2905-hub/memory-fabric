# Offline 10/10 qualification ledger

Strict completion: **126 / 260 (48.46%)**. Internal status: **BLOCKED**.

A task is counted only when its exact acceptance condition has evidence. Every artifact is SHA-256 bound; malformed or missing evidence is INCOMPLETE. Existing code without acceptance evidence is PARTIAL or TODO, never DONE.

Normalized ledger digest: `c3d603d690bbb4e48c8f2e7e070eef6ae7cd42b627e5945be549bec7f427a74d`.

| status | count |
|---|---:|
| BLOCKED | 0 |
| DONE | 126 |
| INCOMPLETE | 0 |
| NOT_TESTED | 0 |
| PARTIAL | 15 |
| TODO | 119 |

## Graduation gates

| gate | status |
|---|---|
| G1 | **BLOCKED** |
| G2 | **BLOCKED** |
| G3 | **BLOCKED** |
| G4 | **BLOCKED** |
| G5 | **BLOCKED** |

## Task ledger

| task | priority | status | evidence level | evidence |
|---|---|---|---|---|
| E1-01 | P0 | DONE | INTERNAL_INTEGRATION | `docs/NEXT_MASTER_CHECKLIST_EXECUTION.md`, `research/results/grand-50-agent-baseline-reproduction-v2.json` |
| E1-02 | P0 | DONE | CONTRACT | `tools/offline_baseline.py`, `tests/test_offline_baseline.py`, `research/offline_qualification/baseline.json`, `research/results/e5-10-portable-paths.xml` |
| E1-03 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/manifest.py`, `tests/test_benchmarks.py`, `docs/BENCHMARK_MANIFEST_ENVIRONMENT.md`, `research/results/e1-03-manifest-environment.json`, `research/results/e1-03-manifest-environment.xml`, `research/results/bench_runs/legacy/index.json` |
| E1-04 | P0 | PARTIAL | INTERNAL_INTEGRATION | `benchmarks/provenance.py`, `benchmarks/manifest.py`, `tests/test_result_provenance.py`, `tests/test_benchmarks.py`, `docs/RESULT_PROVENANCE.md`, `research/results/e1-04-result-provenance.json`, `research/results/e1-04-result-provenance.xml` |
| E1-05 | P0 | PARTIAL | INTERNAL_INTEGRATION | `benchmarks/manifest.py`, `benchmarks/scoreboard.py`, `benchmarks/evidence_completeness.py`, `tests/test_benchmarks.py`, `docs/BENCHMARK_MANIFEST_ENVIRONMENT.md`, `research/results/BENCHMARK_SCOREBOARD.md`, `research/results/e1-05-input-digests.json`, `research/results/e1-05-input-digests.xml` |
| E1-06 | P0 | DONE | INTERNAL_INTEGRATION | `tools/local_check_report.py`, `tests/test_local_check_report.py`, `docs/LOCAL_CHECK_REPORT.md`, `research/results/e1-06-local-check-report.json`, `research/results/e1-06-local-check-report.xml`, `research/results/e1-06-local-check-evidence.json` |
| E1-07 | P0 | DONE | CONTRACT | `tools/offline_qualification.py`, `tests/test_offline_qualification.py`, `research/results/e1-07-ledger-verification.json`, `research/results/e1-07-ledger-verification.xml` |
| E1-08 | P0 | DONE | INTERNAL_INTEGRATION | `tools/offline_qualification.py`, `tests/test_offline_qualification.py`, `research/results/e1-08-negative-control.json`, `research/results/e1-08-negative-control.xml` |
| E1-09 | P0 | DONE | INTERNAL_INTEGRATION | `tools/offline_qualification.py`, `tests/test_offline_qualification.py`, `docs/SEED_MANIFESTS.md`, `research/results/e1-09-seed-manifest.json`, `research/results/e1-09-seed-manifest.xml` |
| E1-10 | P0 | DONE | INTERNAL_INTEGRATION | `tools/count_tests.py`, `tools/status_at_head.py`, `tests/test_status_at_head.py`, `tests/test_suite_hygiene.py`, `.github/workflows/ci.yml`, `pyproject.toml`, `README.md`, `docs/VALIDATION.md`, `docs/STATUS_AT_HEAD.md`, `research/results/e1-10-full-suite.xml`, `research/results/e1-10-full-suite-report.json`, `research/results/e1-10-full-suite-evidence.json` |
| E2-01 | P0 | DONE | CONTRACT | `docs/STATE_TRANSITIONS.json`, `docs/STATE_TRANSITIONS.md`, `tests/test_state_transition_contract.py` |
| E2-02 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_replay_equivalence.py`, `tests/test_properties.py`, `tests/test_backup.py` |
| E2-03 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_withdrawn_parent_orderings.py`, `tests/test_justification.py` |
| E2-04 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_duplicates.py`, `tests/test_supersede.py`, `src/memory_fabric/duplicates.py` |
| E2-05 | P0 | DONE | INTERNAL_INTEGRATION | `docs/BITEMPORAL_HISTORY.md`, `src/memory_fabric/history_query.py`, `tests/test_history_query.py`, `tests/test_bitemporal.py` |
| E2-06 | P0 | DONE | INTERNAL_INTEGRATION | `docs/HISTORICAL_SURFACE_SECURITY.md`, `tests/test_history_query.py`, `tests/test_data_access_paths.py`, `tests/test_posture.py`, `tests/test_branching.py`, `tests/test_erasure_residue.py` |
| E2-07 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/tombstones.py`, `src/memory_fabric/outbox.py`, `src/memory_fabric/federation.py`, `tests/test_tombstone_exchange.py`, `docs/TOMBSTONE_EXCHANGE.md` |
| E2-08 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/eventlog.py`, `tests/test_event_schema_hardening.py`, `tests/test_version_skew.py`, `docs/EVENT_SCHEMA_COMPATIBILITY.md`, `experiments/rollback_drill.py` |
| E2-09 | P0 | DONE | INTERNAL_INTEGRATION | `tests/crashworker.py`, `tests/test_multiprocess_crash.py`, `docs/CRASH_BOUNDARY_MATRIX.md` |
| E2-10 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_action_race_barriers.py`, `tests/test_action_fence.py`, `tests/test_visibility_at_action.py`, `src/memory_fabric/actions.py`, `docs/ACTION_RACE_SERIALIZATION.md` |
| E3-01 | P0 | DONE | CONTRACT | `research/bench/retrieval_errors_v1/cases.json`, `research/bench/retrieval_errors_v1/build.py`, `research/bench/retrieval_errors_v1/README.md`, `tests/test_retrieval_error_taxonomy.py` |
| E3-02 | P0 | DONE | INTERNAL_INTEGRATION | `research/results/longmemeval.md`, `experiments/longmemeval_bench.py`, `docs/RETRIEVAL_BASELINE_QUALIFICATION.md`, `tests/test_retrieval_baseline_contract.py` |
| E3-03 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/retrieval_routing.py`, `src/memory_fabric/_fabric/retrieval.py`, `src/memory_fabric/retrieval_profiles.py`, `tests/test_retrieval_routing.py`, `docs/QUERY_ROUTING.md` |
| E3-04 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/chains.py`, `tests/test_chains.py`, `docs/EVIDENCE_CHAIN_SELECTION.md` |
| E3-05 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/relations.py`, `src/memory_fabric/_fabric/retrieval.py`, `tests/test_modifier_packages.py`, `tests/test_extraction.py`, `docs/MODIFIER_EVIDENCE_PACKAGES.md` |
| E3-06 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/evidence_status.py`, `src/memory_fabric/_fabric/common.py`, `tests/test_evidence_status.py`, `tests/test_answerability.py`, `docs/EVIDENCE_STATUS_API.md` |
| E3-07 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/answerability.py`, `src/memory_fabric/_fabric/common.py`, `tests/test_answerability.py`, `docs/PARAMETER_EQUIVALENCES.md` |
| E3-08 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/answerability.py`, `src/memory_fabric/sdk.py`, `src/memory_fabric/adapters/mcp.py`, `src/memory_fabric/agent_api.py`, `src/memory_fabric/cli.py`, `tests/test_read_surface_semantics.py`, `docs/READ_SURFACE_SEMANTICS.md` |
| E3-09 | P0 | DONE | CONTRACT | `src/memory_fabric/chains.py`, `tests/test_chains.py`, `docs/EVIDENCE_PACKAGE_BUDGETS.md` |
| E3-10 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/_fabric/core.py`, `src/memory_fabric/_fabric/writes.py`, `src/memory_fabric/_fabric/retrieval.py`, `tests/test_retrieval_index_invalidation.py`, `tests/test_cross_process_freshness.py`, `tests/test_erasure_residue.py`, `tests/test_access_matrix.py`, `docs/RETRIEVAL_INDEX_INVALIDATION.md` |
| E4-01 | P0 | DONE | INTERNAL_INTEGRATION | `research/results/master-checklist-http-capacity-v1.json`, `research/results/master-checklist-http-capacity-v1.md` |
| E4-02 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/stage_trace.py`, `src/memory_fabric/agent_api.py`, `src/memory_fabric/_fabric/core.py`, `src/memory_fabric/_fabric/writes.py`, `tests/test_stage_trace.py`, `docs/STAGE_TRACING.md` |
| E4-03 | P0 | DONE | INTERNAL_INTEGRATION | `experiments/p12b_api_load.py`, `src/memory_fabric/agent_api.py`, `src/memory_fabric/_fabric/core.py`, `src/memory_fabric/stage_trace.py`, `tests/test_agent_api.py`, `tests/test_p12b_api_load.py`, `tests/test_p12b_harness.py`, `research/results/e4-03-local-profile.json`, `research/results/e4-03-local-profile.md`, `research/results/e4-03-local-profile-manifest.json`, `research/results/e4-03-profile-tests.xml` |
| E4-04 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/integrity.py`, `tests/test_integrity_chain.py`, `tests/test_eventlog.py`, `tests/test_multiprocess_crash.py`, `research/results/e4-04-contention-before-after.json`, `research/results/e4-04-contention-before-after.md`, `research/results/e4-04-regression-tests.xml`, `research/results/e4-04-batched-chain-pilot.json`, `research/results/e4-04-100-client.json`, `research/results/e4-04-manifest.json` |
| E4-05 | P0 | DONE | INTERNAL_INTEGRATION | `experiments/e4_sqlite_stress.py`, `docs/OPERATIONS.md`, `tests/test_concurrency.py`, `tests/test_eventlog.py`, `research/results/e4-05-sqlite-qualification.json`, `research/results/e4-05-sqlite-qualification.md`, `research/results/e4-05-sqlite-5s.json`, `research/results/e4-05-sqlite-30s.json`, `research/results/e4-05-regression-tests.xml`, `research/results/e4-05-manifest.json` |
| E4-06 | P0 | DONE | INTERNAL_INTEGRATION | `experiments/e4_scan_benchmark.py`, `tests/test_eventlog.py`, `research/results/e4-06-page-scan.json`, `research/results/e4-06-page-scan.md`, `research/results/e4-06-page-scan.svg`, `research/results/e4-06-regression-tests.xml`, `research/results/e4-06-manifest.json` |
| E4-07 | P0 | DONE | INTERNAL_INTEGRATION | `experiments/e4_three_hosts.py`, `tests/test_federation_transport.py`, `tests/test_retraction_protocol.py`, `research/results/e4-07-three-hosts.json`, `research/results/e4-07-three-hosts.md`, `research/results/e4-07-regression-tests.xml`, `research/results/e4-07-manifest.json` |
| E4-08 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/outbox.py`, `tests/test_federation_transport.py`, `tests/test_retraction_protocol.py`, `docs/OPERATIONS.md`, `research/results/e4-08-federation-faults.json`, `research/results/e4-08-federation-faults.xml` |
| E4-09 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/freshness.py`, `tests/test_freshness.py`, `docs/FRESHNESS_LEASES.md`, `research/results/e4-09-freshness-clock-skew.json`, `research/results/e4-09-freshness-clock-skew.xml` |
| E4-10 | P0 | DONE | INTERNAL_INTEGRATION | `experiments/e4_soak.py`, `docs/E4_SOAK.md`, `tests/test_multiprocess_crash.py`, `tests/test_backup.py`, `research/results/e4-10-deterministic-soak.json`, `research/results/e4-10-deterministic-soak.md`, `research/results/e4-10-crash-backup-regressions.xml`, `research/results/e4-10-evidence.json` |
| E5-01 | P1 | DONE | INTERNAL_INTEGRATION | `tools/gen_reference.py`, `tools/gen_stability.py`, `docs/API_INVENTORY.json`, `docs/API.md`, `STABILITY.md`, `tests/test_reference_docs.py`, `tests/test_fabric_structure.py`, `tests/test_stability.py`, `research/results/e5-01-api-inventory.json`, `research/results/e5-01-api-inventory.xml` |
| E5-02 | P1 | DONE | INTERNAL_INTEGRATION | `pyproject.toml`, `src/memory_fabric/py.typed`, `tools/check_typed_consumer.py`, `research/results/e5-02-typed-wheel.json` |
| E5-03 | P1 | DONE | INTERNAL_INTEGRATION | `docs/ERROR_CONTRACT_MATRIX.md`, `src/memory_fabric/sdk.py`, `src/memory_fabric/adapters/mcp.py`, `src/memory_fabric/agent_api.py`, `src/memory_fabric/cli.py`, `tests/test_sdk.py`, `tests/test_mcp.py`, `tests/test_agent_api.py`, `tests/test_correction.py`, `research/results/e5-03-error-contracts.json`, `research/results/e5-03-error-contracts.xml` |
| E5-04 | P1 | DONE | INTERNAL_INTEGRATION | `docs/EXPERIMENTAL_DEFAULTS.md`, `tests/data/default_features.json`, `tests/test_presets.py`, `tests/test_stability.py`, `research/results/e5-04-default-flags.json`, `research/results/e5-04-default-flags.xml` |
| E5-05 | P1 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/tool_protocol.py`, `tests/test_tool_protocol.py`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/e5-05-tool-schema.json`, `research/results/e5-05-tool-schema.xml` |
| E5-06 | P1 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/tool_protocol.py`, `tests/test_tool_protocol.py`, `tests/data/utcp_malicious_manuals.json`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/e5-06-utcp-malicious.json`, `research/results/e5-06-utcp-malicious.xml` |
| E5-07 | P1 | DONE | INTERNAL_INTEGRATION | `tools/package_parity.py`, `docs/PACKAGE_PARITY.md`, `research/results/e5-07-package-parity.json` |
| E5-08 | P1 | DONE | INTERNAL_INTEGRATION | `docs/HISTORICAL_COMPATIBILITY_FIXTURES.md`, `tests/data/historical/manifest.json`, `tests/data/historical/v0.11.0.db.gz`, `tests/test_historical_fixtures.py`, `tests/test_version_skew.py`, `tests/test_integrity_chain.py`, `research/results/e5-08-historical-fixtures.json`, `research/results/e5-08-historical-fixtures.xml` |
| E5-09 | P1 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/agent_api.py`, `tests/test_agent_api.py`, `tests/data/agent_api_behavior.json`, `tools/agent_api_metrics.py`, `research/results/e5-09-agent-api-before.json`, `research/results/e5-09-agent-api-before.xml`, `research/results/e5-09-agent-api-after.json`, `research/results/e5-09-agent-api-after.xml`, `research/results/e5-09-agent-api-after-core.xml`, `research/results/e5-09-agent-api-refactor.json` |
| E5-10 | P1 | PARTIAL | INTERNAL_INTEGRATION | `src/memory_fabric/freshness.py`, `tests/test_portable_paths.py`, `docs/PORTABLE_PATHS.md`, `research/results/e5-10-portable-paths.xml` |
| R1-01 | P0 | DONE | CONTRACT | `research/prereg/offline-10-families-v1.md` |
| R1-02 | P0 | DONE | INTERNAL_INTEGRATION | `tools/results_manifest.py`, `benchmarks/scoreboard.py`, `tests/test_status_at_head.py`, `tests/test_benchmarks.py`, `research/results/MANIFEST.json`, `research/results/BENCHMARK_SCOREBOARD.md`, `research/results/r1-population-separation-tests.xml` |
| R1-03 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/offline_research.py`, `tests/test_offline_research.py`, `research/results/r1-offline-synthetic.json`, `research/results/r1-offline-synthetic-tests.xml` |
| R1-04 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/offline_research.py`, `tests/test_offline_research.py`, `research/results/r1-offline-synthetic-tests.xml` |
| R1-05 | P0 | PARTIAL | INTERNAL_INTEGRATION | `benchmarks/offline_research.py`, `tests/test_offline_research.py`, `research/results/r1-offline-synthetic.json`, `research/results/r1-offline-synthetic-tests.xml` |
| R1-06 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/offline_research.py`, `tests/test_offline_research.py`, `research/results/r1-offline-synthetic.json`, `research/results/r1-offline-synthetic-tests.xml` |
| R1-07 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/offline_research.py`, `tests/test_offline_research.py`, `research/results/r1-offline-synthetic.json`, `research/results/r1-offline-synthetic-tests.xml` |
| R1-08 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/offline_research.py`, `tests/test_offline_research.py`, `research/results/r1-offline-synthetic.json`, `research/results/r1-offline-synthetic-tests.xml` |
| R1-09 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/offline_research.py`, `tests/test_offline_research.py`, `research/results/r1-offline-synthetic.json`, `research/results/r1-offline-synthetic-tests.xml` |
| R1-10 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/offline_research.py`, `docs/OFFLINE_RESEARCH_BENCHMARK.md`, `tests/test_offline_research.py`, `research/results/r1-offline-synthetic.json`, `research/results/r1-offline-synthetic-tests.xml` |
| R2-01 | P0 | DONE | INTERNAL_INTEGRATION | `research/results/grand-50-agent-baseline-reproduction-v2.json`, `research/prereg/r2-false-withholding-v1.md`, `benchmarks/false_withholding.py`, `research/results/r2-false-withholding-ablation.json`, `benchmarks/pr30_case_extractor.py`, `tests/test_pr30_withheld_cases.py`, `docs/PR30_WITHHELD_CASES.md`, `research/results/pr30-withheld-cases.json`, `research/results/pr30-withheld-cases-tests.xml` |
| R2-02 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/false_withholding.py`, `research/prereg/r2-false-withholding-v1.md`, `tests/test_false_withholding.py`, `research/results/r2-false-withholding-tests.xml`, `research/results/r2-false-withholding-ablation.json` |
| R2-03 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/false_withholding.py`, `tests/test_false_withholding.py`, `research/results/r2-false-withholding-tests.xml`, `research/results/r2-false-withholding-ablation.json` |
| R2-04 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/false_withholding.py`, `research/prereg/r2-false-withholding-v1.md`, `tests/test_false_withholding.py`, `research/results/r2-false-withholding-tests.xml`, `research/results/r2-false-withholding-ablation.json` |
| R2-05 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/evidence_state.py`, `tests/test_evidence_state.py`, `research/results/r2-05-evidence-state.xml` |
| R2-06 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/certificates.py`, `src/memory_fabric/justification.py`, `tests/test_certificates.py`, `research/results/r2-06-07-support-tests.xml` |
| R2-07 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/justification.py`, `src/memory_fabric/certificates.py`, `tests/test_justification.py`, `tests/test_certificates.py`, `research/results/r2-06-07-support-tests.xml` |
| R2-08 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/enforcement.py`, `src/memory_fabric/sdk.py`, `src/memory_fabric/actions.py`, `tests/test_sdk.py`, `tests/test_action_fence.py`, `docs/EVIDENCE_OPERATION_RISK.md`, `research/results/r2-08-risk-sensitive-operations.xml`, `research/results/r2-08-action-fence.xml` |
| R2-09 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/evidence_completeness.py`, `research/prereg/ecv1-threshold.json`, `tests/test_ecv1_benchmark.py`, `research/results/r2-09-threshold-guard.xml` |
| R2-10 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/withholding_promotion_gate.py`, `research/prereg/r2-withholding-promotion-gate-v1.md`, `docs/WITHHOLDING_PROMOTION_GATE.md`, `tests/test_withholding_promotion_gate.py`, `research/results/r2-10-promotion-gate-tests.xml`, `research/results/r2-10-ledger-gate-tests.xml`, `research/results/r2-withholding-promotion-gate.json` |
| R3-01 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/agent_scale.py`, `tests/test_agent_scale.py`, `research/prereg/agent-scale-v1.md`, `docs/AGENT_SCALE_BENCHMARK.md`, `research/results/r3-01-agent-scale-tests.xml`, `research/results/r3-01-agent-scale.json` |
| R3-02 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/matched_agent_arms.py`, `benchmarks/agent_scale.py`, `research/prereg/matched-agent-arms-v1.md`, `docs/MATCHED_AGENT_ARMS.md`, `tests/test_matched_agent_arms.py`, `research/results/r3-02-matched-agent-arms-tests.xml`, `research/results/r3-02-matched-agent-arms.json` |
| R3-03 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/matched_agent_arms.py`, `research/prereg/failure-taxonomy-v1.md`, `docs/FAILURE_TAXONOMY.md`, `tests/test_matched_agent_arms.py`, `research/results/r3-03-failure-taxonomy-tests.xml`, `research/results/r3-03-failure-taxonomy.json` |
| R3-04 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/correction_timing.py`, `research/prereg/correction-timing-v1.md`, `docs/CORRECTION_TIMING_BENCHMARK.md`, `tests/test_correction_timing.py`, `research/results/r3-04-correction-timing-tests.xml`, `research/results/r3-04-correction-timing.json` |
| R3-05 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/minority_source.py`, `research/prereg/minority-source-v1.md`, `docs/MINORITY_SOURCE_BENCHMARK.md`, `tests/test_minority_source.py`, `research/results/r3-05-minority-source-tests.xml`, `research/results/r3-05-minority-source.json` |
| R3-06 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/safety_tradeoff.py`, `research/prereg/safety-tradeoff-v1.md`, `docs/SAFETY_COMPLETION_TRADEOFF.md`, `tests/test_safety_tradeoff.py`, `research/results/r3-06-safety-tradeoff-tests.xml`, `research/results/r3-06-safety-tradeoff.json` |
| R3-07 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_r3_simulation_labels.py`, `research/results/r3-simulation-labels-tests.xml`, `research/results/r3-01-agent-scale.json`, `research/results/r3-02-matched-agent-arms.json`, `research/results/r3-03-failure-taxonomy.json`, `research/results/r3-04-correction-timing.json`, `research/results/r3-05-minority-source.json`, `research/results/r3-06-safety-tradeoff.json` |
| R3-08 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/agent_adapter.py`, `docs/AGENT_ADAPTER.md`, `tests/test_agent_adapter.py`, `research/results/r3-agent-adapter-tests.xml` |
| R3-09 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/heldout_agent_qualification.py`, `research/prereg/heldout-agent-qualification-v1.md`, `tests/test_heldout_agent_qualification.py`, `research/results/r3-heldout-agent-qualification-tests.xml`, `research/results/r3-09-10-heldout-qualification.json` |
| R3-10 | P0 | DONE | INTERNAL_INTEGRATION | `benchmarks/matched_agent_arms.py`, `benchmarks/heldout_agent_qualification.py`, `research/prereg/heldout-agent-qualification-v1.md`, `tests/test_matched_agent_arms.py`, `tests/test_heldout_agent_qualification.py`, `research/results/r3-heldout-agent-qualification-tests.xml`, `research/results/r3-09-10-heldout-qualification.json` |
| R4-01 | P1 | TODO | NOT_TESTED | — |
| R4-02 | P1 | TODO | NOT_TESTED | — |
| R4-03 | P1 | TODO | NOT_TESTED | — |
| R4-04 | P1 | TODO | NOT_TESTED | — |
| R4-05 | P1 | TODO | NOT_TESTED | — |
| R4-06 | P1 | TODO | NOT_TESTED | — |
| R4-07 | P1 | DONE | CONTRACT | `benchmarks/decision_verdict.py`, `benchmarks/evaluator_mutations.py`, `tests/test_benchmarks.py`, `tools/benchmark_evaluator_mutations.py`, `research/results/r4-07-evaluator-mutations.json`, `research/results/r4-07-evaluator-mutation-tests.xml` |
| R4-08 | P1 | TODO | NOT_TESTED | — |
| R4-09 | P1 | TODO | NOT_TESTED | — |
| R4-10 | P1 | TODO | NOT_TESTED | — |
| R5-01 | P1 | TODO | NOT_TESTED | — |
| R5-02 | P1 | TODO | NOT_TESTED | — |
| R5-03 | P1 | TODO | NOT_TESTED | — |
| R5-04 | P1 | TODO | NOT_TESTED | — |
| R5-05 | P1 | TODO | NOT_TESTED | — |
| R5-06 | P1 | TODO | NOT_TESTED | — |
| R5-07 | P1 | TODO | NOT_TESTED | — |
| R5-08 | P1 | TODO | NOT_TESTED | — |
| R5-09 | P1 | TODO | NOT_TESTED | — |
| R5-10 | P1 | TODO | NOT_TESTED | — |
| N1-01 | P1 | TODO | NOT_TESTED | — |
| N1-02 | P1 | TODO | NOT_TESTED | — |
| N1-03 | P1 | TODO | NOT_TESTED | — |
| N1-04 | P1 | TODO | NOT_TESTED | — |
| N1-05 | P1 | TODO | NOT_TESTED | — |
| N1-06 | P1 | TODO | NOT_TESTED | — |
| N1-07 | P1 | TODO | NOT_TESTED | — |
| N1-08 | P1 | TODO | NOT_TESTED | — |
| N1-09 | P1 | TODO | NOT_TESTED | — |
| N1-10 | P1 | TODO | NOT_TESTED | — |
| N2-01 | P1 | TODO | NOT_TESTED | — |
| N2-02 | P1 | TODO | NOT_TESTED | — |
| N2-03 | P1 | TODO | NOT_TESTED | — |
| N2-04 | P1 | TODO | NOT_TESTED | — |
| N2-05 | P1 | TODO | NOT_TESTED | — |
| N2-06 | P1 | TODO | NOT_TESTED | — |
| N2-07 | P1 | TODO | NOT_TESTED | — |
| N2-08 | P1 | TODO | NOT_TESTED | — |
| N2-09 | P1 | TODO | NOT_TESTED | — |
| N2-10 | P1 | TODO | NOT_TESTED | — |
| N3-01 | P2 | TODO | NOT_TESTED | — |
| N3-02 | P2 | TODO | NOT_TESTED | — |
| N3-03 | P2 | TODO | NOT_TESTED | — |
| N3-04 | P2 | TODO | NOT_TESTED | — |
| N3-05 | P2 | TODO | NOT_TESTED | — |
| N3-06 | P2 | TODO | NOT_TESTED | — |
| N3-07 | P2 | TODO | NOT_TESTED | — |
| N3-08 | P2 | TODO | NOT_TESTED | — |
| N3-09 | P2 | TODO | NOT_TESTED | — |
| N3-10 | P2 | TODO | NOT_TESTED | — |
| N4-01 | P1 | TODO | NOT_TESTED | — |
| N4-02 | P1 | TODO | NOT_TESTED | — |
| N4-03 | P1 | TODO | NOT_TESTED | — |
| N4-04 | P1 | TODO | NOT_TESTED | — |
| N4-05 | P1 | TODO | NOT_TESTED | — |
| N4-06 | P1 | TODO | NOT_TESTED | — |
| N4-07 | P1 | TODO | NOT_TESTED | — |
| N4-08 | P1 | TODO | NOT_TESTED | — |
| N4-09 | P1 | TODO | NOT_TESTED | — |
| N4-10 | P1 | TODO | NOT_TESTED | — |
| N5-01 | P2 | TODO | NOT_TESTED | — |
| N5-02 | P2 | TODO | NOT_TESTED | — |
| N5-03 | P2 | TODO | NOT_TESTED | — |
| N5-04 | P2 | TODO | NOT_TESTED | — |
| N5-05 | P2 | TODO | NOT_TESTED | — |
| N5-06 | P2 | TODO | NOT_TESTED | — |
| N5-07 | P2 | TODO | NOT_TESTED | — |
| N5-08 | P2 | TODO | NOT_TESTED | — |
| N5-09 | P2 | TODO | NOT_TESTED | — |
| N5-10 | P2 | TODO | NOT_TESTED | — |
| N6-01 | P1 | TODO | NOT_TESTED | — |
| N6-02 | P1 | TODO | NOT_TESTED | — |
| N6-03 | P1 | TODO | NOT_TESTED | — |
| N6-04 | P1 | TODO | NOT_TESTED | — |
| N6-05 | P1 | TODO | NOT_TESTED | — |
| N6-06 | P1 | TODO | NOT_TESTED | — |
| N6-07 | P1 | TODO | NOT_TESTED | — |
| N6-08 | P1 | TODO | NOT_TESTED | — |
| N6-09 | P1 | TODO | NOT_TESTED | — |
| N6-10 | P1 | TODO | NOT_TESTED | — |
| H1-01 | P0 | DONE | CONTRACT | `docs/SAFETY_AND_SECURITY.md`, `tests/test_security_regression.py`, `tests/test_retraction_protocol.py`, `tests/test_adapters.py`, `tests/test_privacy_federation.py`, `tests/test_code_mode_fuzz.py`, `tests/test_action_fence.py`, `research/results/h1-01-trust-boundaries.xml` |
| H1-02 | P0 | DONE | CONTRACT | `tests/data/prompt_injection_corpus.json`, `tests/test_injection_patterns.py`, `research/results/h1-02-injection-corpus-tests.xml` |
| H1-03 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_authority.py`, `tests/test_confused_deputy.py`, `research/results/h1-03-04-authority-delayed-poisoning.xml` |
| H1-04 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_authority.py`, `tests/test_security_regression.py`, `research/results/h1-03-04-authority-delayed-poisoning.xml` |
| H1-05 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_authority.py`, `research/results/h1-05-unfamiliar-claim-tests.xml` |
| H1-06 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_duplicates.py`, `docs/LIMITATIONS.md`, `research/results/h1-06-copy-laundering-tests.xml` |
| H1-07 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_certificates.py`, `tests/test_code_mode_fuzz.py`, `tests/test_agent_api.py`, `research/results/h1-07-malformed-input-tests.xml` |
| H1-08 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_action_race_barriers.py`, `docs/ACTION_RACE_SERIALIZATION.md`, `research/results/h1-08-compromised-writer-race.xml` |
| H1-09 | P0 | DONE | INTERNAL_INTEGRATION | `tools/mutation_check.py`, `tests/test_authority.py`, `research/results/h1-09-authority-mutation.json` |
| H1-10 | P0 | DONE | CONTRACT | `tests/data/prompt_injection_corpus.json`, `tests/test_injection_patterns.py`, `tools/prompt_injection_corpus_report.py`, `research/results/h1-10-injection-outcomes.json` |
| H2-01 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/actions.py`, `tests/test_action_race_barriers.py`, `docs/ACTION_RACE_SERIALIZATION.md`, `research/results/h2-01-authorize-execute-race-tests.xml`, `research/results/r2-h2-acceptance-tests.xml` |
| H2-02 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/actions.py`, `tests/test_authority.py`, `docs/ACTION_GRANT_BINDING.md`, `research/results/h2-02-action-binding-tests.xml` |
| H2-03 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/actions.py`, `src/memory_fabric/events.py`, `tests/test_action_fence.py`, `tests/test_action_crash.py`, `docs/ACTION_IDEMPOTENCY.md`, `tools/action_idempotency_qualification.py`, `research/results/h2-03-idempotency-tests.xml`, `research/results/h2-03-action-idempotency.json`, `research/results/h2-03-action-compatibility-tests.xml` |
| H2-04 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/actions.py`, `tests/test_action_reconciliation.py`, `tests/test_action_crash.py`, `docs/ACTION_RECONCILIATION.md`, `tools/action_reconciliation_qualification.py`, `research/results/h2-04-action-reconciliation-tests.xml`, `research/results/h2-04-action-reconciliation.json` |
| H2-05 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/tool_protocol.py`, `tests/data/code_mode_malicious_plans.json`, `tests/test_code_mode_fuzz.py`, `tests/test_tool_protocol.py`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/h2-05-code-mode-parser-tests.xml`, `research/results/h2-05-code-mode-parser.json` |
| H2-06 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/tool_protocol.py`, `tests/test_code_mode_fuzz.py`, `tests/test_tool_protocol.py`, `tools/code_mode_parser_qualification.py`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/h2-05-code-mode-parser-tests.xml`, `research/results/h2-06-code-mode-bounds.json` |
| H2-07 | P0 | DONE | INTERNAL_INTEGRATION | `tools/offline_network_guard.py`, `tests/test_offline_network_guard.py`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/h2-07-offline-egress-tests.xml`, `research/results/h2-07-offline-egress.json` |
| H2-08 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/tool_protocol.py`, `tests/data/utcp_malicious_manuals.json`, `tests/test_tool_protocol.py`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/h2-08-utcp-transport.json`, `research/results/h2-08-utcp-transport-tests.xml` |
| H2-09 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/actions.py`, `src/memory_fabric/events.py`, `tests/test_action_execution_receipt.py`, `docs/ACTION_RECONCILIATION.md`, `research/results/h2-09-execution-receipt.json`, `research/results/h2-09-execution-receipt-tests.xml` |
| H2-10 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/actions.py`, `src/memory_fabric/tool_protocol.py`, `tests/test_confused_deputy.py`, `docs/DECISION_MODELS_AND_UTCP.md`, `research/results/h2-10-confused-deputy.json`, `research/results/h2-10-confused-deputy-tests.xml` |
| H3-01 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/_fabric/core.py`, `src/memory_fabric/observability/control.py`, `tests/test_cross_tenant_surface_matrix.py`, `tests/test_privacy_federation.py`, `docs/SAFETY_AND_SECURITY.md`, `research/results/h3-01-cross-tenant-matrix.json`, `research/results/h3-01-cross-tenant-matrix-tests.xml` |
| H3-02 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_metadata_sidechannels.py`, `tests/test_metadata_leakage.py`, `docs/SAFETY_AND_SECURITY.md`, `research/results/h3-02-metadata-sidechannels.json`, `research/results/h3-02-metadata-sidechannels-tests.xml` |
| H3-03 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/tenancy.py`, `tests/test_tenancy.py`, `tests/test_backup_custody.py`, `research/results/h3-03-physical-tenancy.json`, `research/results/h3-03-physical-tenancy-tests.xml` |
| H3-04 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_credential_rotation_actions.py`, `tests/test_service.py`, `tests/test_action_fence.py`, `research/results/h3-04-credential-rotation-tests.xml`, `research/results/h3-04-credential-rotation.json` |
| H3-05 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_personal_data_redaction.py`, `tools/scan_secrets.py`, `research/results/h3-05-personal-data-redaction.json`, `research/results/h3-05-personal-data-redaction-tests.xml` |
| H3-06 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/governance/retention.py`, `tests/test_retention_boundaries.py`, `docs/RETENTION_AND_AUDIT_PRESERVATION.md`, `research/results/h3-06-retention-boundaries.json`, `research/results/h3-06-retention-boundaries-tests.xml` |
| H3-07 | P0 | PARTIAL | INTERNAL_INTEGRATION | `tests/test_erasure_residue.py`, `tests/test_cipher.py`, `tests/test_tombstone_exchange.py`, `research/results/h3-07-erasure-residue.json`, `research/results/h3-07-erasure-residue-tests.xml` |
| H3-08 | P0 | PARTIAL | CONTRACT | `src/memory_fabric/_fabric/sealing.py`, `src/memory_fabric/tombstones.py`, `tests/test_tombstone_exchange.py`, `docs/RETENTION_AND_AUDIT_PRESERVATION.md`, `research/results/h3-08-backup-erasure-limits.json` |
| H3-09 | P0 | PARTIAL | INTERNAL_INTEGRATION | `src/memory_fabric/observability/metrics.py`, `tests/test_metrics.py`, `research/results/h3-09-sparse-metrics.json`, `research/results/h3-09-sparse-metrics-tests.xml` |
| H3-10 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_cipher.py`, `tests/test_event_schema_hardening.py`, `tests/test_doctor.py`, `docs/TROUBLESHOOTING.md`, `docs/RUNBOOKS.md`, `research/results/h3-10-key-loss.json`, `research/results/h3-10-key-loss-tests.xml` |
| H4-01 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_write_fault_injection.py`, `research/results/h4-01-stage-fault-injection.json`, `research/results/h4-01-stage-fault-injection-tests.xml` |
| H4-02 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_multiprocess_crash.py`, `tests/crashworker.py`, `tests/test_cipher.py`, `tests/test_event_schema_hardening.py`, `research/results/h4-02-power-loss.json`, `research/results/h4-02-power-loss-tests.xml` |
| H4-03 | P0 | PARTIAL | INTERNAL_INTEGRATION | `tests/test_storage_failure_modes.py`, `research/results/h4-03-storage-failure.json`, `research/results/h4-03-storage-failure-tests.xml` |
| H4-04 | P0 | PARTIAL | CONTRACT | `src/memory_fabric/freshness.py`, `tests/test_freshness.py`, `tests/test_tombstone_exchange.py` |
| H4-05 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_tombstone_exchange.py`, `tests/test_multiprocess_crash.py`, `research/results/h4-05-reordered-corrections.json`, `research/results/h4-05-reordered-corrections-tests.xml` |
| H4-06 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/outbox.py`, `tests/test_federation_transport.py`, `tests/test_retraction_protocol.py`, `research/results/h4-06-retry-deadletter.json`, `research/results/h4-06-retry-deadletter-tests.xml` |
| H4-07 | P0 | DONE | INTERNAL_INTEGRATION | `tests/test_checkpoint_rewrite.py`, `tests/test_integrity_chain.py`, `tests/test_freshness.py`, `research/results/h4-07-checkpoint-trust.json`, `research/results/h4-07-checkpoint-trust-tests.xml` |
| H4-08 | P0 | PARTIAL | INTERNAL_INTEGRATION | `tests/test_backup.py`, `tests/test_version_skew.py`, `tests/test_historical_fixtures.py`, `research/results/h4-08-backup-upgrade.json`, `research/results/h4-08-backup-upgrade-tests.xml` |
| H4-09 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/freshness.py`, `docs/FRESHNESS_LEASES.md`, `tests/test_freshness.py`, `tests/test_certificates.py`, `tests/test_identity.py`, `research/results/h4-09-clock-skew.json`, `research/results/h4-09-clock-skew-tests.xml` |
| H4-10 | P0 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/incident.py`, `src/memory_fabric/response.py`, `src/memory_fabric/cli.py`, `tests/test_incident.py`, `tests/test_response.py`, `research/results/h4-10-incident-replay.json`, `research/results/h4-10-incident-replay-tests.xml` |
| H5-01 | P1 | PARTIAL | CONTRACT | `pyproject.toml`, `tools/dependency_provenance.py`, `research/results/h5-01-dependency-provenance.json` |
| H5-02 | P1 | PARTIAL | INTERNAL_INTEGRATION | `tools/check.py`, `tools/adversarial_gate.py`, `tests/test_secure_sdlc_inventory.py`, `research/results/h5-02-adversarial-gate.json`, `research/results/h5-02-static-security-gates.json`, `research/results/h5-01-02-local-tool-inventory-tests.xml` |
| H5-03 | P1 | DONE | INTERNAL_INTEGRATION | `tools/security_ast_scan.py`, `tools/security_ast_exceptions.json`, `tests/test_security_ast_scan.py`, `tests/data/security_ast_positive.py`, `research/results/h5-03-security-ast.json`, `research/results/h5-03-security-ast-tests.xml` |
| H5-04 | P1 | DONE | INTERNAL_INTEGRATION | `tools/audit_package_assets.py`, `tests/test_package_asset_audit.py`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/publish-pypi.yml`, `research/results/h5-04-package-asset-audit.json`, `research/results/h5-04-package-asset-tests.xml` |
| H5-05 | P1 | DONE | INTERNAL_INTEGRATION | `tools/mutation_check.py`, `tests/test_enforcement_tenant.py`, `tests/test_erasure_key_destroy.py`, `tests/test_transport_auth.py`, `research/results/h5-05-mutation-qualification.json`, `research/results/h5-05-mutation-contract-tests.xml` |
| H5-06 | P1 | DONE | INTERNAL_INTEGRATION | `tests/data/adversarial_family_registry.json`, `tools/adversarial_gate.py`, `tests/test_adversarial_registry.py`, `research/results/h5-06-adversarial-registry.json`, `research/results/h5-06-adversarial-registry-tests.xml` |
| H5-07 | P1 | DONE | INTERNAL_INTEGRATION | `tests/data/security_fuzz_seeds.json`, `tests/data/code_mode_malicious_plans.json`, `tools/fuzz_security_boundaries.py`, `tests/test_security_fuzz.py`, `.github/workflows/ci.yml`, `research/results/h5-07-security-fuzz.json`, `research/results/h5-07-security-fuzz-tests.xml` |
| H5-08 | P1 | DONE | INTERNAL_INTEGRATION | `src/memory_fabric/agent_api.py`, `src/memory_fabric/limits.py`, `tests/test_agent_api_rate_limit.py`, `tools/rate_limit_qualification.py`, `.github/workflows/ci.yml`, `research/results/h5-08-rate-limit-qualification.json`, `research/results/h5-08-rate-limit-tests.xml` |
| H5-09 | P1 | DONE | INTERNAL_INTEGRATION | `tools/audit_production_defaults.py`, `tests/data/default_features.json`, `tests/test_presets.py`, `.github/workflows/ci.yml`, `research/results/h5-09-production-defaults.json` |
| H5-10 | P1 | DONE | INTERNAL_INTEGRATION | `research/security/internal_findings.json`, `tools/security_findings.py`, `tests/test_security_findings.py`, `tools/check.py`, `research/results/h5-10-internal-security-findings.json`, `research/results/h5-10-finding-verification.xml` |
| P1-01 | P1 | TODO | NOT_TESTED | — |
| P1-02 | P1 | TODO | NOT_TESTED | — |
| P1-03 | P1 | TODO | NOT_TESTED | — |
| P1-04 | P1 | TODO | NOT_TESTED | — |
| P1-05 | P1 | TODO | NOT_TESTED | — |
| P1-06 | P1 | TODO | NOT_TESTED | — |
| P1-07 | P1 | TODO | NOT_TESTED | — |
| P1-08 | P1 | TODO | NOT_TESTED | — |
| P1-09 | P1 | TODO | NOT_TESTED | — |
| P1-10 | P1 | TODO | NOT_TESTED | — |
| P2-01 | P1 | TODO | NOT_TESTED | — |
| P2-02 | P1 | TODO | NOT_TESTED | — |
| P2-03 | P1 | TODO | NOT_TESTED | — |
| P2-04 | P1 | TODO | NOT_TESTED | — |
| P2-05 | P1 | TODO | NOT_TESTED | — |
| P2-06 | P1 | TODO | NOT_TESTED | — |
| P2-07 | P1 | TODO | NOT_TESTED | — |
| P2-08 | P1 | TODO | NOT_TESTED | — |
| P2-09 | P1 | TODO | NOT_TESTED | — |
| P2-10 | P1 | TODO | NOT_TESTED | — |
| P3-01 | P1 | TODO | NOT_TESTED | — |
| P3-02 | P1 | TODO | NOT_TESTED | — |
| P3-03 | P1 | TODO | NOT_TESTED | — |
| P3-04 | P1 | TODO | NOT_TESTED | — |
| P3-05 | P1 | TODO | NOT_TESTED | — |
| P3-06 | P1 | TODO | NOT_TESTED | — |
| P3-07 | P1 | TODO | NOT_TESTED | — |
| P3-08 | P1 | TODO | NOT_TESTED | — |
| P3-09 | P1 | TODO | NOT_TESTED | — |
| P3-10 | P1 | TODO | NOT_TESTED | — |
| P4-01 | P1 | TODO | NOT_TESTED | — |
| P4-02 | P1 | TODO | NOT_TESTED | — |
| P4-03 | P1 | TODO | NOT_TESTED | — |
| P4-04 | P1 | TODO | NOT_TESTED | — |
| P4-05 | P1 | TODO | NOT_TESTED | — |
| P4-06 | P1 | TODO | NOT_TESTED | — |
| P4-07 | P1 | TODO | NOT_TESTED | — |
| P4-08 | P1 | TODO | NOT_TESTED | — |
| P4-09 | P1 | TODO | NOT_TESTED | — |
| P4-10 | P1 | TODO | NOT_TESTED | — |
| P5-01 | P0 | DONE | INTERNAL_INTEGRATION | `tools/normalize_sdist.py`, `tests/test_normalize_sdist.py`, `research/results/p5-01-exact-candidate.json`, `research/results/p5-01-package-assets.json`, `research/results/p5-01-reproducible-sdist-tests.xml`, `research/results/p5-01-fresh-machine.txt` |
| P5-02 | P0 | PARTIAL | INTERNAL_INTEGRATION | `tools/check.py`, `research/results/p5-02-local-checks.txt`, `research/results/p5-02-full-unit-tests.txt`, `research/results/p5-02-adversarial-gate.json`, `research/results/p5-02-local-qualification.json`, `research/results/h5-09-production-defaults.json` |
| P5-03 | P0 | PARTIAL | CONTRACT | `tools/python_compatibility.py`, `research/results/p5-03-python-compatibility.json` |
| P5-04 | P0 | PARTIAL | INTERNAL_INTEGRATION | `tools/upgrade_rollback_smoke.py`, `research/results/p5-04-upgrade-rollback-smoke.json` |
| P5-05 | P0 | DONE | INTERNAL_INTEGRATION | `tools/gen_stability.py`, `tools/gen_reference.py`, `tests/test_examples_run.py`, `tests/test_doc_examples.py`, `tests/test_reference_docs.py`, `tests/test_user_docs_no_research.py`, `research/results/p5-05-documentation-examples.xml` |
| P5-06 | P0 | DONE | CONTRACT | `docs/LIMITATIONS.md`, `docs/KNOWN_GAPS.md` |
| P5-07 | P0 | DONE | CONTRACT | `tests/test_offline_qualification.py` |
| P5-08 | P0 | DONE | CONTRACT | `docs/LIMITATIONS.md`, `docs/PRODUCT_READINESS.md` |
| P5-09 | P0 | DONE | CONTRACT | `docs/NEXT_MASTER_CHECKLIST_EXECUTION.md` |
| P5-10 | P0 | DONE | CONTRACT | `tools/offline_qualification.py`, `tests/test_offline_qualification.py` |
