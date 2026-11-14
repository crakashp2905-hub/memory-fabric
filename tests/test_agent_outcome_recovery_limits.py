from __future__ import annotations

from memory_fabric.outcome_protocol import RecoveryEpisode, RecoveryLimits, RecoveryStatus


def test_repeated_noop_recovery_fails_and_records_budget() -> None:
    episode = RecoveryEpisode("loop", enabled=True)
    assert episode.record("replan")

    assert not episode.record("replan")
    assert episode.status is RecoveryStatus.FAILED
    assert episode.trace[0]["kind"] == "recovery_budget"
    assert episode.trace[-1] == {
        "kind": "recovery_failed", "reason": "NO_MONOTONIC_PROGRESS",
    }


def test_repeated_progress_revision_fails_as_oscillation() -> None:
    episode = RecoveryEpisode("oscillation", enabled=True)
    assert episode.record("re_retrieve", {"progress_key": "revision-4"})

    assert not episode.record("replan", {"progress_key": "revision-4"})
    assert episode.trace[-1]["reason"] == "NO_MONOTONIC_PROGRESS"


def test_attempt_event_and_deadline_budgets_fail_deterministically() -> None:
    attempt_limited = RecoveryEpisode(
        "attempts", RecoveryLimits(max_steps=5, max_attempts=1), enabled=True
    )
    assert attempt_limited.record("evidence_blocked")
    assert not attempt_limited.record("abstain")
    assert attempt_limited.trace[-1]["reason"] == "ATTEMPT_LIMIT"

    event_limited = RecoveryEpisode(
        "events", RecoveryLimits(max_steps=5, max_events=2), enabled=True
    )
    assert event_limited.record("evidence_blocked")
    assert not event_limited.record("abstain")
    assert event_limited.trace[-1]["reason"] == "EVENT_LIMIT"

    now = [12.0]
    deadline_limited = RecoveryEpisode(
        "deadline", RecoveryLimits(deadline_seconds=1.0), enabled=True,
        _clock=lambda: now[0]
    )
    now[0] = 13.1
    assert not deadline_limited.record("evidence_blocked")
    assert deadline_limited.trace[-1]["reason"] == "DEADLINE_EXCEEDED"
