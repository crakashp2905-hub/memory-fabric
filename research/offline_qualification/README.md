# Offline 10/10 qualification ledger

Strict completion: **19 / 260 (7.31%)**. Internal status: **BLOCKED**.

A task is counted only when its exact acceptance condition has evidence. Existing code without acceptance evidence is PARTIAL or TODO, never DONE.

Normalized ledger digest: `afdc4a4c7f911d01cda81b9649967350b08f35bd9a8b691ed063bddd0080a8b0`.

| status | count |
|---|---:|
| BLOCKED | 0 |
| DONE | 19 |
| NOT_TESTED | 0 |
| PARTIAL | 4 |
| TODO | 237 |

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
| E2-08 | P0 | TODO | NOT_TESTED | — |
| E2-09 | P0 | TODO | NOT_TESTED | — |
| E2-10 | P0 | TODO | NOT_TESTED | — |
| E3-01 | P0 | TODO | NOT_TESTED | — |
| E3-02 | P0 | TODO | NOT_TESTED | — |
| E3-03 | P0 | TODO | NOT_TESTED | — |
| E3-04 | P0 | TODO | NOT_TESTED | — |
| E3-05 | P0 | TODO | NOT_TESTED | — |
| E3-06 | P0 | TODO | NOT_TESTED | — |
| E3-07 | P0 | TODO | NOT_TESTED | — |
| E3-08 | P0 | TODO | NOT_TESTED | — |
| E3-09 | P0 | TODO | NOT_TESTED | — |
| E3-10 | P0 | TODO | NOT_TESTED | — |
| E4-01 | P0 | DONE | INTERNAL_INTEGRATION | `research/results/master-checklist-http-capacity-v1.json`, `research/results/master-checklist-http-capacity-v1.md` |
| E4-02 | P0 | TODO | NOT_TESTED | — |
| E4-03 | P0 | TODO | NOT_TESTED | — |
| E4-04 | P0 | TODO | NOT_TESTED | — |
| E4-05 | P0 | TODO | NOT_TESTED | — |
| E4-06 | P0 | TODO | NOT_TESTED | — |
| E4-07 | P0 | TODO | NOT_TESTED | — |
| E4-08 | P0 | TODO | NOT_TESTED | — |
| E4-09 | P0 | TODO | NOT_TESTED | — |
| E4-10 | P0 | TODO | NOT_TESTED | — |
| E5-01 | P1 | TODO | NOT_TESTED | — |
| E5-02 | P1 | TODO | NOT_TESTED | — |
| E5-03 | P1 | TODO | NOT_TESTED | — |
| E5-04 | P1 | TODO | NOT_TESTED | — |
| E5-05 | P1 | TODO | NOT_TESTED | — |
| E5-06 | P1 | TODO | NOT_TESTED | — |
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
