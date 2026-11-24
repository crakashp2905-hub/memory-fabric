"""Opt-in high-level outcome API (W20-01, W20-03, W20-04, W20-05, W20-06, W20-09).

Five operations over the canonical episode runtime, for a developer who wants
"run this task and tell me what happened" without wiring the runner:

``run_task``          run one task on a governed store; returns a ``TaskResult``
``get_outcome``       the host's record of a task (never the evaluator's grade)
``inspect_failure``   why a task stopped, as a typed diagnosis plus next steps
``get_evidence``      the evidence a task's proposal cited, as the actor may see it
``resume_recovery``   run a stopped task again on current evidence

Requests are plain JSON objects checked against a versioned schema
(``docs/schemas/outcome-api.v1.json``). Unknown fields are refused, and so is any
authority-bearing or executable field (a grant, certificate, callback, code):
effects are host-registered callables chosen by name, never supplied in a
request. No incomplete task is reported as success: every result has one
explicit status, and every refusal is an ``OutcomeApiError`` with one of the
codes in ``ERRORS``.

``handle(operation, payload)`` is the single JSON entry point. ``mcp_call`` and
``utcp_call`` adapt MCP- and UTCP-shaped tool calls onto it, so all three
surfaces share one decision path.
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .diagnosis import Diagnosis, classify
from .episode import (
    DecisionFunction, EpisodeLimits, EpisodeRecord, GovernedMemoryPort, HostOutcome,
    TaskEnvelope, default_tools, run_episode,
)

SCHEMA_VERSION = "outcome-api.v1"
ERRORS = {
    "INVALID_REQUEST": "The request does not match the schema; nothing ran.",
    "UNKNOWN_TASK": "No task with this id has run through this API.",
    "NOT_RUN": "The operation needs a task that has run; this one has not.",
    "NON_REPLAYABLE": "The recorded task cannot be resumed: its trace is incomplete.",
    "BLOCKED": "The task cannot be resumed: its stop is not recoverable by re-running.",
    "UNDECIDABLE": "Whether the effect happened is unknown; reconcile before anything else.",
    "BUDGET_EXCEEDED": "The task used its whole budget; the host must decide to extend it.",
}
REQUEST_FIELDS = {"task_id": str, "objective": str, "objective_id": str, "limits": dict,
                  "recovery": bool}
REQUIRED_FIELDS = {"task_id", "objective"}
AUTHORITY_FIELDS = frozenset({"grant", "certificate", "approval", "credential", "token",
                              "session", "callback", "code", "python", "callable", "handler",
                              "effect", "effects", "evaluator", "oracle", "policy", "role"})
LIMIT_FIELDS = {"max_steps", "max_tool_calls", "max_context_bytes", "max_wall_ms",
                "max_recoveries"}
STATUS = {
    HostOutcome.EFFECT_EXECUTED: "EFFECT_EXECUTED",
    HostOutcome.ABSTAINED: "ABSTAINED",
    HostOutcome.FAILED: "BLOCKED",
    HostOutcome.BUDGET_EXHAUSTED: "BUDGET_EXCEEDED",
    HostOutcome.EFFECT_UNKNOWN: "UNDECIDABLE",
}
NEXT_STEPS: Mapping[str, tuple[str, ...]] = {
    "withdrawn": ("re-retrieve current evidence", "re-plan on what is current"),
    "superseded": ("re-retrieve the current version", "re-plan on it"),
    "contested": ("wait for an independent source", "ask an operator to review the dispute"),
    "untrusted": ("find evidence from a source with standing for this use",),
    "not_available": ("ask an operator for access if the task needs it", "do not retry as is"),
    "no_permission": ("ask the host to grant this tool to the acting agent", "do not retry as is"),
    "no_evidence": ("observe again or ask for the missing fact", "abstain if none exists"),
    "retrieval_miss": ("search again with the exact identifier",),
    "stale_lease": ("refresh the remote evidence lease, then re-verify",),
    "malformed_assertion": ("rebuild the proposal from retrieved evidence only",),
    "contradictory_observations": ("wait for a correction", "ask an operator to review"),
    "budget": ("ask the host for a larger budget; do not loop",),
    "effect_unknown": ("reconcile the effect with the target system before any retry",),
    "tool": ("use a declared tool your role may call",),
}
REASON_DIAGNOSIS = {
    "evidence_not_retrieved": "malformed_assertion", "tool_not_declared": "tool",
    "tool_not_permitted_for_role": "tool", "malformed_tool_arguments": "tool",
    "proposal_commitment_mismatch": "malformed_assertion",
}


class OutcomeApiError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERRORS:
            raise ValueError(f"unknown API error code {code}")
        super().__init__(f"{code}: {detail or ERRORS[code]}")
        self.code, self.detail = code, detail or ERRORS[code]

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.code, "detail": self.detail, "schema": SCHEMA_VERSION}


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: str
    reason: str
    diagnosis: str | None
    next_steps: tuple[str, ...] = ()
    schema: str = field(default=SCHEMA_VERSION)

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "status": self.status, "reason": self.reason,
                "diagnosis": self.diagnosis, "next_steps": list(self.next_steps),
                "schema": self.schema}


def validate_request(payload: Any) -> dict[str, Any]:
    """The request schema, enforced with the standard library only."""
    if not isinstance(payload, Mapping):
        raise OutcomeApiError("INVALID_REQUEST", "the request must be a JSON object")
    authority = sorted(set(payload) & AUTHORITY_FIELDS)
    if authority:
        raise OutcomeApiError("INVALID_REQUEST",
                              f"authority-bearing or executable fields are refused: {authority}")
    unknown = sorted(set(payload) - set(REQUEST_FIELDS))
    if unknown:
        raise OutcomeApiError("INVALID_REQUEST", f"unknown fields: {unknown}")
    missing = sorted(REQUIRED_FIELDS - set(payload))
    if missing:
        raise OutcomeApiError("INVALID_REQUEST", f"missing fields: {missing}")
    for name, kind in REQUEST_FIELDS.items():
        if name in payload and (not isinstance(payload[name], kind)
                                or (kind is not bool and isinstance(payload[name], bool))):
            raise OutcomeApiError("INVALID_REQUEST", f"{name} must be {kind.__name__}")
    limits = payload.get("limits", {})
    if set(limits) - LIMIT_FIELDS or not all(isinstance(v, int) and not isinstance(v, bool)
                                             for v in limits.values()):
        raise OutcomeApiError("INVALID_REQUEST", "limits must map known limit names to integers")
    return dict(payload)


ACTION_PERMISSION = frozenset({"tool_not_granted", "execute_permission_missing",
                               "credential_invalid", "grant_required", "grant_unknown",
                               "grant_revoked", "wrong_agent"})
"""The caller's own permission to act: safe to name, unlike evidence it may not see."""


def _last_verification(record: EpisodeRecord) -> list[str]:
    codes: list[str] = []
    for event in record.trace.get("events", []):
        if event.get("kind") == "verified" and not event["payload"].get("ok", True):
            codes = [c for c in event["payload"].get("reason_codes", [])
                     if c != "new_observations_since_plan"] or codes
    return codes


def _diagnose(record: EpisodeRecord) -> str | None:
    reason = record.reason
    if record.host_outcome is HostOutcome.EFFECT_EXECUTED:
        return None
    if record.host_outcome is HostOutcome.BUDGET_EXHAUSTED:
        return "budget"
    if record.host_outcome is HostOutcome.EFFECT_UNKNOWN:
        return "effect_unknown"
    if ":" in reason:  # planner_abstained:<reason>
        return reason.split(":", 1)[1]
    if reason in REASON_DIAGNOSIS:
        return REASON_DIAGNOSIS[reason]
    codes = [reason]
    if reason in {"recovery_disabled", "no_progress"}:
        codes = _last_verification(record) or codes
    if any(code in ACTION_PERMISSION for code in codes):
        return "no_permission"
    try:
        diagnosis = classify(codes)
    except ValueError:
        return "no_evidence" if "abstained" in reason else None
    if diagnosis is Diagnosis.NO_PERMISSION:
        return "not_available"
    return None if diagnosis is Diagnosis.ANSWERABLE else diagnosis.value


class OutcomeAPI:
    def __init__(self, fabric: Any, *, effects: Mapping[str, Callable[[str, Mapping[str, Any]], Any]],
                 team: DecisionFunction | None = None, tenant_id: str = "tn_default",
                 protected_tool: str = "set_target", semantic_advisor: Any = None,
                 semantic_mode: str = "OFF") -> None:
        from .semantic_advisory import check_mode

        if protected_tool not in effects:
            raise ValueError("the protected tool's effect must be host-registered")
        self.semantic_advisor, self.semantic_mode = semantic_advisor, check_mode(semantic_mode)
        self.semantic_shadow_log: list[dict[str, Any]] = []
        self.fabric, self.effects, self.team = fabric, dict(effects), team
        self.tenant_id, self.protected_tool = tenant_id, protected_tool
        self._records: dict[str, EpisodeRecord] = {}
        self._ports: dict[str, GovernedMemoryPort] = {}
        self._requests: dict[str, dict[str, Any]] = {}

    # -- operations --------------------------------------------------------------

    def run_task(self, payload: Mapping[str, Any], *, feed: Callable[[int], Sequence[Mapping[str, Any]]],
                 decide: DecisionFunction | None = None) -> TaskResult:
        request = validate_request(payload)
        decide = decide or self.team
        if decide is None:
            raise OutcomeApiError("INVALID_REQUEST", "no decision function is registered")
        tools = default_tools(self.protected_tool)
        envelope = TaskEnvelope(
            task_id=request["task_id"], objective_id=request.get("objective_id", "objective"),
            objective=request["objective"], public_context=(),
            role_tools={role: tuple(sorted(n for n in tools._specs  # noqa: SLF001
                                           if role in tools._specs[n].roles))  # noqa: SLF001
                        for role in ("observer", "planner", "executor")},
            limits=EpisodeLimits(**request.get("limits", {})))
        port = GovernedMemoryPort(self.fabric, envelope.task_id, protected_tools=(self.protected_tool,),
                                  tenant_id=self.tenant_id)
        record = run_episode(envelope, decide, port, feed=feed, effects=self.effects, tools=tools,
                             recovery_enabled=bool(request.get("recovery", True)))
        self._records[envelope.task_id] = record
        self._ports[envelope.task_id] = port
        self._requests[envelope.task_id] = request
        return self._result(record)

    def get_outcome(self, task_id: str) -> dict[str, Any]:
        record = self._record(task_id)
        return {**self._result(record).to_dict(), "phases": list(record.phases),
                "effect_outcome": record.effect_outcome, "budget": dict(record.budget),
                "evaluator_grade": "NOT_AVAILABLE_TO_ACTORS"}

    def inspect_failure(self, task_id: str) -> dict[str, Any]:
        from .semantic_advisory import annotate

        result = self._result(self._record(task_id))
        if result.status == "EFFECT_EXECUTED":
            return {**result.to_dict(), "failure": None}
        return annotate({**result.to_dict(), "failure": result.diagnosis},
                        advisor=self.semantic_advisor, mode=self.semantic_mode,
                        shadow_log=self.semantic_shadow_log)

    def get_evidence(self, task_id: str) -> list[dict[str, Any]]:
        record = self._record(task_id)
        if record.proposal is None:
            return []
        out = []
        for memory_id, version in record.proposal["evidence"]:
            read = self.fabric.use(memory_id, "planner", tenant_id=self.tenant_id)
            usable = read.memory is not None and read.memory.version == version
            out.append({"memory_id": memory_id, "version": version,
                        "status": "current" if usable else "not_available"})
        return out

    def resume_recovery(self, task_id: str, *, feed: Callable[[int], Sequence[Mapping[str, Any]]],
                        decide: DecisionFunction | None = None) -> TaskResult:
        record = self._record(task_id)
        result = self._result(record)
        if not record.trace.get("events"):
            raise OutcomeApiError("NON_REPLAYABLE")
        if result.status == "EFFECT_EXECUTED":
            raise OutcomeApiError("BLOCKED", "the effect already ran; nothing to resume")
        if result.status in {"UNDECIDABLE", "BUDGET_EXCEEDED"}:
            raise OutcomeApiError(result.status)
        request = dict(self._requests[task_id])
        request["task_id"] = f"{task_id}.r{sum(1 for k in self._records if k.startswith(task_id))}"
        return self.run_task(request, feed=feed, decide=decide)

    # -- one JSON entry point and its transport adapters ---------------------------

    def handle(self, operation: str, payload: Mapping[str, Any], *,
               feed: Callable[[int], Sequence[Mapping[str, Any]]] | None = None) -> dict[str, Any]:
        try:
            if operation == "run_task":
                if feed is None:
                    raise OutcomeApiError("INVALID_REQUEST", "run_task needs a host feed")
                return self.run_task(payload, feed=feed).to_dict()
            task_id = payload.get("task_id") if isinstance(payload, Mapping) else None
            if not isinstance(task_id, str) or set(payload) != {"task_id"}:
                raise OutcomeApiError("INVALID_REQUEST", "expected exactly {task_id}")
            if operation == "get_outcome":
                return self.get_outcome(task_id)
            if operation == "inspect_failure":
                return self.inspect_failure(task_id)
            if operation == "get_evidence":
                return {"task_id": task_id, "evidence": self.get_evidence(task_id)}
            raise OutcomeApiError("INVALID_REQUEST", f"unknown operation {operation!r}")
        except OutcomeApiError as exc:
            return exc.to_dict()

    def mcp_call(self, call: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
        """An MCP ``tools/call`` shape: ``{"name": op, "arguments": {...}}``."""
        return self.handle(str(call.get("name")), call.get("arguments") or {}, **kwargs)

    def utcp_call(self, tool: str, arguments: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
        """A UTCP manual tool call: ``outcome.<op>`` with an arguments object."""
        operation = tool.split(".", 1)[1] if tool.startswith("outcome.") else tool
        return self.handle(operation, arguments, **kwargs)

    # -- helpers -----------------------------------------------------------------

    def _record(self, task_id: str) -> EpisodeRecord:
        if task_id not in self._records:
            raise OutcomeApiError("UNKNOWN_TASK")
        return self._records[task_id]

    def _result(self, record: EpisodeRecord) -> TaskResult:
        diagnosis = _diagnose(record)
        return TaskResult(record.task_id, STATUS[record.host_outcome], record.reason, diagnosis,
                          NEXT_STEPS.get(diagnosis or "", ()))
