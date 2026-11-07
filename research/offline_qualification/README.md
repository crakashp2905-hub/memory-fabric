# Offline 10/10 qualification ledger

Strict completion: **47 / 260 (18.08%)**. Internal status: **BLOCKED**.

A task is counted only when its exact acceptance condition has evidence. Existing code without acceptance evidence is PARTIAL or TODO, never DONE.

Normalized ledger digest: `6463243a31977fb48fc94bf4bc134b1f5c5e4655b7de4fe2caf232d12bec8282`.

| status | count |
|---|---:|
| BLOCKED | 0 |
| DONE | 47 |
| NOT_TESTED | 0 |
| PARTIAL | 4 |
| TODO | 209 |

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
| E1-02 | P0 | DONE | CONTRACT | `tools/offline_baseline.py`, `tests/test_offline_baseline.py`, `research/offline_qualification/baseline.json` |
| E1-03 | P0 | PARTIAL | CONTRACT | `tools/offline_baseline.py`, `research/offline_qualification/baseline.json` |
| E1-04 | P0 | PARTIAL | CONTRACT | `tools/offline_baseline.py`, `tools/results_manifest.py` |
| E1-05 | P0 | PARTIAL | CONTRACT | `tools/offline_baseline.py`, `tests/test_offline_baseline.py` |
| E1-06 | P0 | PARTIAL | CONTRACT | `tools/offline_baseline.py`, `research/offline_qualification/baseline.json` |
| E1-07 | P0 | DONE | CONTRACT | `tools/offline_qualification.py`, `research/offline_qualification/register.json` |
| E1-08 | P0 | DONE | CONTRACT | `tests/test_offline_qualification.py` |
| E1-09 | P0 | DONE | CONTRACT | `tools/offline_qualification.py`, `tests/test_offline_qualification.py` |
| E1-10 | P0 | DONE | CONTRACT | `tools/status_at_head.py`, `tests/test_status_at_head.py`, `docs/STATUS_AT_HEAD.md` |
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
| E5-07 | P1 | TODO | NOT_TESTED | — |
| E5-08 | P1 | TODO | NOT_TESTED | — |
| E5-09 | P1 | TODO | NOT_TESTED | — |
| E5-10 | P1 | TODO | NOT_TESTED | — |
| R1-01 | P0 | TODO | NOT_TESTED | — |
| R1-02 | P0 | TODO | NOT_TESTED | — |
| R1-03 | P0 | TODO | NOT_TESTED | — |
| R1-04 | P0 | TODO | NOT_TESTED | — |
| R1-05 | P0 | TODO | NOT_TESTED | — |
| R1-06 | P0 | TODO | NOT_TESTED | — |
| R1-07 | P0 | TODO | NOT_TESTED | — |
| R1-08 | P0 | TODO | NOT_TESTED | — |
| R1-09 | P0 | TODO | NOT_TESTED | — |
| R1-10 | P0 | TODO | NOT_TESTED | — |
| R2-01 | P0 | TODO | NOT_TESTED | — |
| R2-02 | P0 | TODO | NOT_TESTED | — |
| R2-03 | P0 | TODO | NOT_TESTED | — |
| R2-04 | P0 | TODO | NOT_TESTED | — |
| R2-05 | P0 | TODO | NOT_TESTED | — |
| R2-06 | P0 | TODO | NOT_TESTED | — |
| R2-07 | P0 | TODO | NOT_TESTED | — |
| R2-08 | P0 | TODO | NOT_TESTED | — |
| R2-09 | P0 | TODO | NOT_TESTED | — |
| R2-10 | P0 | TODO | NOT_TESTED | — |
| R3-01 | P0 | TODO | NOT_TESTED | — |
| R3-02 | P0 | TODO | NOT_TESTED | — |
| R3-03 | P0 | TODO | NOT_TESTED | — |
| R3-04 | P0 | TODO | NOT_TESTED | — |
| R3-05 | P0 | TODO | NOT_TESTED | — |
| R3-06 | P0 | TODO | NOT_TESTED | — |
| R3-07 | P0 | TODO | NOT_TESTED | — |
| R3-08 | P0 | TODO | NOT_TESTED | — |
| R3-09 | P0 | TODO | NOT_TESTED | — |
| R3-10 | P0 | TODO | NOT_TESTED | — |
| R4-01 | P1 | TODO | NOT_TESTED | — |
| R4-02 | P1 | TODO | NOT_TESTED | — |
| R4-03 | P1 | TODO | NOT_TESTED | — |
| R4-04 | P1 | TODO | NOT_TESTED | — |
| R4-05 | P1 | TODO | NOT_TESTED | — |
| R4-06 | P1 | TODO | NOT_TESTED | — |
| R4-07 | P1 | TODO | NOT_TESTED | — |
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
| H1-01 | P0 | TODO | NOT_TESTED | — |
| H1-02 | P0 | TODO | NOT_TESTED | — |
| H1-03 | P0 | TODO | NOT_TESTED | — |
| H1-04 | P0 | TODO | NOT_TESTED | — |
| H1-05 | P0 | TODO | NOT_TESTED | — |
| H1-06 | P0 | TODO | NOT_TESTED | — |
| H1-07 | P0 | TODO | NOT_TESTED | — |
| H1-08 | P0 | TODO | NOT_TESTED | — |
| H1-09 | P0 | TODO | NOT_TESTED | — |
| H1-10 | P0 | TODO | NOT_TESTED | — |
| H2-01 | P0 | TODO | NOT_TESTED | — |
| H2-02 | P0 | TODO | NOT_TESTED | — |
| H2-03 | P0 | TODO | NOT_TESTED | — |
| H2-04 | P0 | TODO | NOT_TESTED | — |
| H2-05 | P0 | TODO | NOT_TESTED | — |
| H2-06 | P0 | TODO | NOT_TESTED | — |
| H2-07 | P0 | TODO | NOT_TESTED | — |
| H2-08 | P0 | TODO | NOT_TESTED | — |
| H2-09 | P0 | TODO | NOT_TESTED | — |
| H2-10 | P0 | TODO | NOT_TESTED | — |
| H3-01 | P0 | TODO | NOT_TESTED | — |
| H3-02 | P0 | TODO | NOT_TESTED | — |
| H3-03 | P0 | TODO | NOT_TESTED | — |
| H3-04 | P0 | TODO | NOT_TESTED | — |
| H3-05 | P0 | TODO | NOT_TESTED | — |
| H3-06 | P0 | TODO | NOT_TESTED | — |
| H3-07 | P0 | TODO | NOT_TESTED | — |
| H3-08 | P0 | TODO | NOT_TESTED | — |
| H3-09 | P0 | TODO | NOT_TESTED | — |
| H3-10 | P0 | TODO | NOT_TESTED | — |
| H4-01 | P0 | TODO | NOT_TESTED | — |
| H4-02 | P0 | TODO | NOT_TESTED | — |
| H4-03 | P0 | TODO | NOT_TESTED | — |
| H4-04 | P0 | TODO | NOT_TESTED | — |
| H4-05 | P0 | TODO | NOT_TESTED | — |
| H4-06 | P0 | TODO | NOT_TESTED | — |
| H4-07 | P0 | TODO | NOT_TESTED | — |
| H4-08 | P0 | TODO | NOT_TESTED | — |
| H4-09 | P0 | TODO | NOT_TESTED | — |
| H4-10 | P0 | TODO | NOT_TESTED | — |
| H5-01 | P1 | TODO | NOT_TESTED | — |
| H5-02 | P1 | TODO | NOT_TESTED | — |
| H5-03 | P1 | TODO | NOT_TESTED | — |
| H5-04 | P1 | TODO | NOT_TESTED | — |
| H5-05 | P1 | TODO | NOT_TESTED | — |
| H5-06 | P1 | TODO | NOT_TESTED | — |
| H5-07 | P1 | TODO | NOT_TESTED | — |
| H5-08 | P1 | TODO | NOT_TESTED | — |
| H5-09 | P1 | TODO | NOT_TESTED | — |
| H5-10 | P1 | TODO | NOT_TESTED | — |
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
| P5-01 | P0 | TODO | NOT_TESTED | — |
| P5-02 | P0 | TODO | NOT_TESTED | — |
| P5-03 | P0 | TODO | NOT_TESTED | — |
| P5-04 | P0 | TODO | NOT_TESTED | — |
| P5-05 | P0 | TODO | NOT_TESTED | — |
| P5-06 | P0 | DONE | CONTRACT | `docs/LIMITATIONS.md`, `docs/KNOWN_GAPS.md` |
| P5-07 | P0 | DONE | CONTRACT | `research/offline_qualification/register.json`, `research/offline_qualification/README.md` |
| P5-08 | P0 | DONE | CONTRACT | `docs/LIMITATIONS.md`, `docs/PRODUCT_READINESS.md` |
| P5-09 | P0 | DONE | CONTRACT | `docs/NEXT_MASTER_CHECKLIST_EXECUTION.md` |
| P5-10 | P0 | DONE | CONTRACT | `tools/offline_qualification.py`, `tests/test_offline_qualification.py` |
