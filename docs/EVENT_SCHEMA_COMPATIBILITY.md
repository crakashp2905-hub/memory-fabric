# Event schema compatibility and refusal matrix

| Input condition | Reader behavior | Qualification fixture |
|---|---|---|
| Older event with absent optional memory fields | Explicit defaults preserve old behavior | `tests/test_version_skew.py::EveryAddedFieldHasAnAbsentMeaning` |
| Same-schema event with unknown additive memory field | Ignore the optional field and replay known state | `tests/test_event_schema_hardening.py::test_unknown_additive_memory_field_replays` |
| Unknown event type with a supported schema version | Retain it in the append-only log; older projections ignore it | `tests/test_event_schema_hardening.py::test_duplicate_event_id_is_rejected_atomically` |
| Duplicate event ID | Database uniqueness rejects the whole append | `tests/test_event_schema_hardening.py::test_duplicate_event_id_is_rejected_atomically` |
| Missing, empty, or malformed event schema version | Refuse before append or during replay | `tests/test_event_schema_hardening.py::test_missing_or_malformed_version_is_refused_before_write`, `::test_malformed_persisted_version_refuses_replay` |
| Well-formed schema newer than installed code | `doctor` exits 5 and forbids acting on a potentially partial projection | `tests/test_version_skew.py::test_a_newer_schema_is_refused_rather_than_half_read` |
| Supported older schema | Replay, write current events, back up, and restore mixed-version history | `tests/test_version_skew.py::EveryShippedVersionUpgradesThenBacksUp` |
| Rollback after incompatible upgrade | Restore the pre-upgrade backup; old state remains readable | `tests/test_event_schema_hardening.py::test_backup_rollback_restores_readable_pre_upgrade_state`, `experiments/rollback_drill.py` |
| Unsupported protocol version | Parse fails with an explicit protocol error | `tests/test_version_skew.py::test_an_unsupported_protocol_version_is_refused` |

Schema versions are mandatory numeric `major.minor.patch` strings. Additive
fields are the only backward-compatible event evolution. A required field
change needs an explicit migration and major schema bump. Event identity is
immutable and unique; retries must reuse the original outcome rather than
append a second event with the same ID.

Rollback never rewrites the event log. Operators take a pre-upgrade backup,
allow newer code to append, and restore the backup if older code must run
again. The full real-release procedure is `experiments/rollback_drill.py`.
