"""Operator-safe traces and post-episode outcome metrics."""

from __future__ import annotations

from typing import Any

from .outcomes import OutcomeAssessment
from .recovery import RecoveryEpisode

__stability__ = "experimental"


_DETAIL_FIELDS: dict[str, frozenset[str]] = {
    "recovery_budget": frozenset({
        "max_steps", "enabled", "max_attempts", "max_recoveries", "max_events",
        "max_event_bytes", "deadline_seconds",
    }),
    "evidence_blocked": frozenset({
        "cause_code", "failure_class", "source_id", "next_action",
    }),
    "alternate_search_plan": frozenset({"cause_code", "failure_class"}),
    "alternate_search_suppressed": frozenset({"cause_code", "failure_class"}),
    "propose": frozenset({"tool", "key"}),
    "action_gate": frozenset({"outcome", "reason_codes"}),
    "recovery_failed": frozenset({"reason"}),
    "operator_handoff": frozenset({"cause_code", "failure_class", "reason_code"}),
}
_RECOVERY_ACTIONS = frozenset({
    "refresh", "re_retrieve", "ask", "replan", "operator_handoff",
    "request_current_observation", "inspect_provenance",
})


def operator_trace(
    episode: RecoveryEpisode,
    assessment: OutcomeAssessment,
) -> dict[str, Any]:
    """Return an allowlisted operator stream plus a separate post-run verdict.

    The operator stream contains no evaluator acceptance labels. The assessment
    is attached only in ``evaluator_view_after_episode`` after grading.
    """
    if not isinstance(episode, RecoveryEpisode):
        raise TypeError("episode must be a RecoveryEpisode")
    if not isinstance(assessment, OutcomeAssessment) or assessment.task_id != episode.task_id:
        raise ValueError("assessment must belong to the recovery episode")

    events: list[dict[str, Any]] = []
    for raw in episode.trace:
        kind = raw.get("kind")
        if kind not in _DETAIL_FIELDS and kind not in _RECOVERY_ACTIONS:
            continue
        permitted = _DETAIL_FIELDS.get(
            kind, frozenset({"progress_key", "cause_code", "failure_class"})
        )
        event: dict[str, Any] = {"kind": kind}
        detail = raw.get("detail", {})
        if isinstance(detail, dict):
            safe_detail = {
                key: detail[key] for key in sorted(permitted) if key in detail
            }
            if safe_detail:
                event["detail"] = safe_detail
        for key in permitted:
            if key in raw:
                event[key] = raw[key]
        events.append(event)

    return {
        "schema_id": "memory-fabric.agent-outcome-operator-trace.v1",
        "task_id": episode.task_id,
        "operator_events": events,
        "evaluator_view_after_episode": {
            "status": assessment.status.value,
            "completion": assessment.completion,
            "safety_violations": assessment.safety_violations,
            "reason_code": assessment.reason_code,
            "result_digest": assessment.result_digest,
        },
        "model_status": "REAL_AGENT_NOT_RUN",
    }
