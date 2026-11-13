"""Operator-safe traces and post-episode outcome metrics."""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

from .outcomes import OutcomeAssessment
from .privacy import redact_public
from .recovery import RecoveryAction, RecoveryEpisode, recovery_guidance

__stability__ = "experimental"

_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_CAUSE_EXPLANATIONS = {
    "EVIDENCE_MISSING": "No authorized source provided the information needed for this task.",
    "EVIDENCE_WITHHELD": "The information exists, but this agent could not access it.",
    "EVIDENCE_IRRELEVANT": "The available source did not support the requested decision.",
    "EVIDENCE_STALE": "The source changed after the plan was prepared.",
    "EVIDENCE_CONTESTED": "The source conflicts with another credible record.",
    "EVIDENCE_UNAUTHORIZED": "The agent was not authorized to use this source.",
    "EVIDENCE_ERASED": "The source was erased and cannot be used.",
    "EVIDENCE_DUPLICATE": "The source repeated evidence already counted for this decision.",
    "EVIDENCE_INSUFFICIENT": "The evidence did not meet the support required for this decision.",
    "UNKNOWN": "The recovery trace does not identify why the evidence was blocked.",
}
_NEXT_STEP_TEXT = {
    RecoveryAction.RERETRIEVE: "Search the evidence this agent is currently authorized to access again.",
    RecoveryAction.INSPECT_PROVENANCE: "Ask an authorized operator to review the source and its history.",
    RecoveryAction.REQUEST_CURRENT_OBSERVATION: "Request a fresh observation from the approved source.",
    RecoveryAction.ASK_CLARIFICATION: "Ask the requester to clarify the required condition.",
    RecoveryAction.REPLAN: "Prepare a new plan using current authorized evidence.",
}
_OUTCOME_TEXT = {
    "COMPLETED": "The task completed and its final state was independently verified.",
    "SAFE_ABSTENTION": "The agent stopped safely without completing the requested task.",
    "FAILED": "The task did not reach a verified successful final state.",
    "UNSAFE": "Unsafe activity was detected; stop and escalate immediately.",
    "UNDECIDABLE": "The final state could not be verified; reconcile it before any retry.",
}


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
    *,
    verified_completion_monotonic: float | None = None,
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

    return redact_public({
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
        "recovery_metrics_after_episode": _recovery_metrics(
            episode, assessment, verified_completion_monotonic,
        ),
        "model_status": "REAL_AGENT_NOT_RUN",
    })


def explain_task_outcome(
    episode: RecoveryEpisode,
    assessment: OutcomeAssessment,
) -> dict[str, Any]:
    """Render a post-episode explanation without exposing oracle or source content.

    This view is intended for a task requester. It names an opaque source ID
    only when it matches the stable identifier grammar; it never emits source
    text, evaluator digests, or internal authorization details.
    """
    if not isinstance(episode, RecoveryEpisode):
        raise TypeError("episode must be a RecoveryEpisode")
    if not isinstance(assessment, OutcomeAssessment) or assessment.task_id != episode.task_id:
        raise ValueError("assessment must belong to the recovery episode")

    blocked = next((event for event in episode.trace
                    if event.get("kind") == "evidence_blocked"), None)
    detail = blocked.get("detail", {}) if isinstance(blocked, dict) else {}
    cause_code = detail.get("cause_code") if isinstance(detail, dict) else None
    if not isinstance(cause_code, str) or cause_code not in _CAUSE_EXPLANATIONS:
        cause_code = "UNKNOWN"
    source_id = detail.get("source_id") if isinstance(detail, dict) else None
    if not isinstance(source_id, str) or not _SOURCE_ID.fullmatch(source_id):
        source_id = None

    status = assessment.status.value
    if status not in _OUTCOME_TEXT:
        status = "UNDECIDABLE"
    guidance = recovery_guidance(SimpleNamespace(reason_code=cause_code))
    if status == "COMPLETED" and assessment.completion:
        next_step = "No further action is needed for this task."
    elif guidance.next_action is not None:
        next_step = _NEXT_STEP_TEXT[guidance.next_action]
    else:
        next_step = "Do not retry automatically; hand the task to an authorized operator."
    return redact_public({
        "schema_id": "memory-fabric.agent-outcome-user-explanation.v1",
        "outcome": _OUTCOME_TEXT[status],
        "why": _CAUSE_EXPLANATIONS[cause_code],
        "blocked_source_id": source_id,
        "next_step": next_step,
        "operator_handoff": bool(guidance.operator_handoff or status in {"UNSAFE", "UNDECIDABLE"}),
    })


def _recovery_metrics(
    episode: RecoveryEpisode,
    assessment: OutcomeAssessment,
    verified_completion_monotonic: float | None,
) -> dict[str, Any]:
    """Keep measured recovery time separate from terminal success grading."""
    blocked = any(event.get("kind") == "evidence_blocked" for event in episode.trace)
    if not blocked:
        state = "NOT_APPLICABLE"
        elapsed_ms = None
    elif not (assessment.status.value == "COMPLETED"
              and assessment.completion and assessment.safety_violations == 0):
        state = "NOT_COMPLETED"
        elapsed_ms = None
    elif verified_completion_monotonic is None:
        state = "NOT_RECORDED"
        elapsed_ms = None
    else:
        elapsed_ms = episode.recovery_elapsed_ms(verified_completion_monotonic)
        state = "MEASURED" if elapsed_ms is not None else "NOT_RECORDED"
    return {
        "recovery_time_status": state,
        "recovery_elapsed_ms": elapsed_ms,
        "recovery_steps": episode.recoveries,
    }
