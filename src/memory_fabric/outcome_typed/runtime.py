"""Truth-free, bounded observe-decide-call-observe agent loop contracts.

The loop receives one public ``AgentObservation``, a decision callback, and
host-declared tools. It never accepts an evaluator task or a world object. Tool
handlers are trusted host integrations and must return only actor-visible data.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Mapping

from .observations import AgentObservation, AgentStep
from .privacy import scrub_public_json

MAX_RUNTIME_STEPS = 128
MAX_TOOL_ARGUMENT_BYTES = 16_000
MAX_TOOL_OUTPUT_BYTES = 16_000


class RuntimeStatus(StrEnum):
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class CounterfactualReplayStatus(StrEnum):
    SKIPPED = "SKIPPED"
    INVOKED = "INVOKED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    FAILED = "FAILED"


class CounterfactualReplayReason(StrEnum):
    DEPENDENCE_NOT_CHECKED = "dependence_not_checked"
    DECISION_INDEPENDENT = "decision_independent"
    NO_MATERIAL_ALTERNATIVE = "no_material_alternative"
    CDM_UNAVAILABLE = "cdm_unavailable"
    MATERIAL_ALTERNATIVE_AFTER_DEPENDENCE = "material_alternative_after_dependence"
    REPLAY_CALL_BUDGET_EXHAUSTED = "replay_call_budget_exhausted"
    REPLAY_RETRY_BUDGET_EXHAUSTED = "replay_retry_budget_exhausted"
    REPLAY_INPUT_TOO_LARGE = "replay_input_too_large"
    REPLAY_RESULT_TOO_LARGE = "replay_result_too_large"
    REPLAY_WALL_BUDGET_EXCEEDED = "replay_wall_budget_exceeded"
    REPLAY_CPU_BUDGET_EXCEEDED = "replay_cpu_budget_exceeded"
    REPLAY_CALLBACK_FAILED = "replay_callback_failed"
    REPLAY_CALLBACK_DISALLOWED = "replay_callback_disallowed"
    REPLAY_WORKER_UNAVAILABLE = "replay_worker_unavailable"
    REPLAY_WORKER_TIMED_OUT = "replay_worker_timed_out"
    REPLAY_WORKER_OUTPUT_EXCEEDED = "replay_worker_output_exceeded"
    REPLAY_RESULT_INVALID = "replay_result_invalid"


@dataclass(frozen=True)
class ReplayLimits:
    """Hard ceilings for one replay budget shared across a task's dispatches."""

    max_calls: int = 1
    max_retries: int = 0
    max_input_bytes: int = 32_000
    max_result_bytes: int = MAX_TOOL_OUTPUT_BYTES
    max_wall_ms: int = 30_000
    max_cpu_ms: int = 1_000

    def __post_init__(self) -> None:
        for name, value, maximum, allow_zero in (
            ("max_calls", self.max_calls, 8, False),
            ("max_retries", self.max_retries, 2, True),
            ("max_input_bytes", self.max_input_bytes, 32_000, False),
            ("max_result_bytes", self.max_result_bytes, MAX_TOOL_OUTPUT_BYTES, False),
            ("max_wall_ms", self.max_wall_ms, 30_000, False),
            ("max_cpu_ms", self.max_cpu_ms, 10_000, False),
        ):
            lower = 0 if allow_zero else 1
            if (not isinstance(value, int) or isinstance(value, bool)
                    or not lower <= value <= maximum):
                raise ValueError(f"{name} must be between {lower} and {maximum}")


@dataclass
class ReplayBudget:
    """Mutable per-task accounting passed to every replay dispatch."""

    limits: ReplayLimits = ReplayLimits()
    calls: int = 0
    retries: int = 0
    wall_ms: int = 0
    cpu_ms: int = 0

    def reserve(self, input_bytes: int, *, retry: bool) -> CounterfactualReplayReason | None:
        if input_bytes > self.limits.max_input_bytes:
            return CounterfactualReplayReason.REPLAY_INPUT_TOO_LARGE
        if self.calls >= self.limits.max_calls:
            return CounterfactualReplayReason.REPLAY_CALL_BUDGET_EXHAUSTED
        if retry and self.retries >= self.limits.max_retries:
            return CounterfactualReplayReason.REPLAY_RETRY_BUDGET_EXHAUSTED
        if self.wall_ms >= self.limits.max_wall_ms:
            return CounterfactualReplayReason.REPLAY_WALL_BUDGET_EXCEEDED
        if self.cpu_ms >= self.limits.max_cpu_ms:
            return CounterfactualReplayReason.REPLAY_CPU_BUDGET_EXCEEDED
        self.calls += 1
        if retry:
            self.retries += 1
        return None

    def record_usage(self, wall_ms: int, cpu_ms: int) -> None:
        self.wall_ms += wall_ms
        self.cpu_ms += cpu_ms


class ReplayContractStatus(StrEnum):
    REPLAYABLE = "REPLAYABLE"
    NON_REPLAYABLE = "NON_REPLAYABLE"


@dataclass(frozen=True)
class AuthorizedReplayContract:
    """Content-addressed replay inputs pinned to model, policy, and evidence epochs."""

    task_id: str
    decision_id: str
    actor_id: str
    model_id: str
    model_version: str
    model_sha256: str
    policy_id: str
    policy_version: str
    policy_sha256: str
    observation_sha256: str
    decision_sha256: str
    evidence_epochs: tuple[tuple[str, int], ...]
    authorization_sha256: str
    contract_sha256: str
    schema_id: str = "memory-fabric.authorized-replay.v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "task_id": self.task_id,
            "decision_id": self.decision_id,
            "actor_id": self.actor_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "model_sha256": self.model_sha256,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_sha256": self.policy_sha256,
            "observation_sha256": self.observation_sha256,
            "decision_sha256": self.decision_sha256,
            "evidence_epochs": [[memory_id, version]
                                for memory_id, version in self.evidence_epochs],
            "authorization_sha256": self.authorization_sha256,
            "contract_sha256": self.contract_sha256,
        }


@dataclass(frozen=True)
class ReplayContractBuild:
    status: ReplayContractStatus
    contract: AuthorizedReplayContract | None
    reasons: tuple[str, ...] = ()


_REPLAY_CONTRACT_FIELDS = frozenset({
    "task_id", "decision_id", "actor_id", "model_id", "model_version",
    "model_sha256", "policy_id", "policy_version", "policy_sha256",
    "observation_sha256", "decision_sha256", "evidence_epochs",
    "authorization_sha256",
})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def build_authorized_replay_contract(trace: Mapping[str, Any]) -> ReplayContractBuild:
    """Build a pinned replay contract, or mark an incomplete trace NON_REPLAYABLE.

    The authorization digest is an audit reference supplied by the trusted host;
    this builder checks completeness and integrity shape, not the host's policy.
    It never infers missing model, policy, observation, decision, or evidence data.
    """
    if not isinstance(trace, Mapping) or any(not isinstance(key, str) for key in trace):
        return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                   ("invalid_trace_shape",))
    missing = tuple(sorted(_REPLAY_CONTRACT_FIELDS - set(trace)))
    extra = tuple(sorted(set(trace) - _REPLAY_CONTRACT_FIELDS))
    if missing or extra:
        reasons = tuple(
            [*(f"missing:{field}" for field in missing),
             *(f"unknown:{field}" for field in extra)]
        )
        return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None, reasons)
    string_fields = _REPLAY_CONTRACT_FIELDS - {"evidence_epochs"}
    for field in string_fields:
        value = trace[field]
        if not isinstance(value, str) or not value:
            return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                       (f"invalid:{field}",))
    for field in ("task_id", "decision_id", "actor_id", "model_id", "policy_id"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", trace[field]):
            return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                       (f"invalid:{field}",))
    for field in ("model_sha256", "policy_sha256", "observation_sha256",
                  "decision_sha256", "authorization_sha256"):
        if not _SHA256.fullmatch(trace[field]):
            return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                       (f"invalid:{field}",))
    raw_epochs = trace["evidence_epochs"]
    if not isinstance(raw_epochs, (list, tuple)) or not raw_epochs:
        return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                   ("invalid:evidence_epochs",))
    epochs: list[tuple[str, int]] = []
    for item in raw_epochs:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or not isinstance(item[0], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", item[0])
                or not isinstance(item[1], int) or isinstance(item[1], bool)
                or item[1] < 0):
            return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                       ("invalid:evidence_epochs",))
        epochs.append((item[0], item[1]))
    if len({memory_id for memory_id, _ in epochs}) != len(epochs):
        return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                   ("duplicate:evidence_epochs",))
    fields: dict[str, Any] = {name: trace[name] for name in sorted(string_fields)}
    fields["evidence_epochs"] = [[memory_id, version] for memory_id, version in epochs]
    fields["schema_id"] = "memory-fabric.authorized-replay.v1"
    digest = hashlib.sha256(json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    contract = AuthorizedReplayContract(
        task_id=trace["task_id"], decision_id=trace["decision_id"],
        actor_id=trace["actor_id"], model_id=trace["model_id"],
        model_version=trace["model_version"], model_sha256=trace["model_sha256"],
        policy_id=trace["policy_id"], policy_version=trace["policy_version"],
        policy_sha256=trace["policy_sha256"],
        observation_sha256=trace["observation_sha256"],
        decision_sha256=trace["decision_sha256"], evidence_epochs=tuple(epochs),
        authorization_sha256=trace["authorization_sha256"], contract_sha256=digest,
    )
    return ReplayContractBuild(ReplayContractStatus.REPLAYABLE, contract)


@dataclass(frozen=True)
class CounterfactualReplayDispatch:
    """Host-side receipt describing whether the advisory replay was invoked."""

    status: CounterfactualReplayStatus
    reason: CounterfactualReplayReason
    decision_sha256: str | None = None
    alternative_sha256: str | None = None
    result: Any = None
    wall_ms: int = 0
    cpu_ms: int = 0
    calls_used: int = 0
    retries_used: int = 0
    isolation: str = "not_started"
    os_limits_enforced: bool = False


_REPLAY_WORKERS = frozenset({"proposal_echo"})


def _run_replay_worker(
    worker_id: str, decision: Mapping[str, Any], alternative: Mapping[str, Any],
    *, wall_ms: int, cpu_ms: int, output_bytes: int,
) -> tuple[Any, int, int, bool, CounterfactualReplayReason | None]:
    """Run a built-in worker in a short-lived subprocess with bounded files/time."""
    started_wall = time.perf_counter_ns()
    started_cpu = time.process_time_ns()
    worker = Path(__file__).with_name("replay_worker.py")
    with tempfile.TemporaryDirectory(prefix="mf-replay-") as tmp:
        request_path = Path(tmp) / "request.json"
        response_path = Path(tmp) / "response.json"
        request_path.write_text(json.dumps(
            {"worker_id": worker_id, "decision": decision, "alternative": alternative},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        ), encoding="utf-8")
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", str(worker), str(request_path), str(response_path),
                 str(cpu_ms)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, close_fds=True,
            )
        except OSError:
            elapsed_wall = int((time.perf_counter_ns() - started_wall) / 1_000_000)
            elapsed_cpu = int((time.process_time_ns() - started_cpu) / 1_000_000)
            return None, elapsed_wall, elapsed_cpu, False, CounterfactualReplayReason.REPLAY_WORKER_UNAVAILABLE
        os_limits_enforced = False
        deadline = time.monotonic() + wall_ms / 1000
        reason: CounterfactualReplayReason | None = None
        while process.poll() is None:
            if response_path.exists() and response_path.stat().st_size > output_bytes:
                reason = CounterfactualReplayReason.REPLAY_WORKER_OUTPUT_EXCEEDED
                process.kill()
                break
            if time.monotonic() >= deadline:
                reason = CounterfactualReplayReason.REPLAY_WORKER_TIMED_OUT
                process.kill()
                break
            time.sleep(0.005)
        process.wait()
        elapsed_wall = int((time.perf_counter_ns() - started_wall) / 1_000_000)
        elapsed_cpu = int((time.process_time_ns() - started_cpu) / 1_000_000)
        if reason is None and process.returncode != 0:
            reason = CounterfactualReplayReason.REPLAY_WORKER_UNAVAILABLE
        if reason is None:
            try:
                if response_path.stat().st_size > output_bytes:
                    reason = CounterfactualReplayReason.REPLAY_WORKER_OUTPUT_EXCEEDED
                else:
                    envelope = json.loads(response_path.read_text(encoding="utf-8"))
                    worker_cpu_ms = envelope.pop("_worker_cpu_ms", 0)
                    os_limits_enforced = envelope.pop("_worker_os_limits_enforced", False)
                    if not isinstance(worker_cpu_ms, int) or isinstance(worker_cpu_ms, bool):
                        raise ValueError("worker CPU usage is invalid")
                    if not isinstance(os_limits_enforced, bool):
                        raise ValueError("worker isolation report is invalid")
                    return (envelope, elapsed_wall, worker_cpu_ms, os_limits_enforced, None)
            except (OSError, ValueError):
                reason = CounterfactualReplayReason.REPLAY_WORKER_UNAVAILABLE
        return None, elapsed_wall, elapsed_cpu, os_limits_enforced, reason


def dispatch_counterfactual_replay(
    decision: Mapping[str, Any],
    alternative: Mapping[str, Any],
    *,
    dependence_checked: bool,
    depends_on_memory: bool,
    replay: Callable[[Mapping[str, Any], Mapping[str, Any]], Any] | None = None,
    worker_id: str | None = None,
    budget: ReplayBudget | None = None,
    retry: bool = False,
) -> CounterfactualReplayDispatch:
    """Run the advisory CDM only after cheap dependence checks find a material alternative.

    ``decision`` and ``alternative`` are host-owned action proposals. Only
    built-in worker IDs are executable; arbitrary callbacks are refused.
    """
    if not isinstance(dependence_checked, bool) or not isinstance(depends_on_memory, bool):
        raise ValueError("dependence check results must be booleans")
    if not dependence_checked:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.SKIPPED,
            CounterfactualReplayReason.DEPENDENCE_NOT_CHECKED,
        )
    if not depends_on_memory:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.SKIPPED,
            CounterfactualReplayReason.DECISION_INDEPENDENT,
        )
    current = _canonical_object(decision, max_bytes=MAX_TOOL_ARGUMENT_BYTES,
                                label="decision proposal")
    candidate = _canonical_object(alternative, max_bytes=MAX_TOOL_ARGUMENT_BYTES,
                                  label="alternative proposal")
    current_digest = hashlib.sha256(json.dumps(
        current, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    alternative_digest = hashlib.sha256(json.dumps(
        candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    if current_digest == alternative_digest:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.SKIPPED,
            CounterfactualReplayReason.NO_MATERIAL_ALTERNATIVE,
            current_digest, alternative_digest,
        )
    if replay is not None:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.FAILED,
            CounterfactualReplayReason.REPLAY_CALLBACK_DISALLOWED,
            current_digest, alternative_digest,
        )
    if worker_id is None:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.SKIPPED,
            CounterfactualReplayReason.CDM_UNAVAILABLE,
            current_digest, alternative_digest,
        )
    active_budget = ReplayBudget() if budget is None else budget
    if (not isinstance(active_budget, ReplayBudget) or not isinstance(retry, bool)
            or not isinstance(worker_id, str) or worker_id not in _REPLAY_WORKERS):
        if isinstance(worker_id, str) and worker_id not in _REPLAY_WORKERS:
            return CounterfactualReplayDispatch(
                CounterfactualReplayStatus.SKIPPED,
                CounterfactualReplayReason.REPLAY_WORKER_UNAVAILABLE,
                current_digest, alternative_digest,
            )
        raise ValueError("replay budget and retry flag are invalid")
    encoded_current = json.dumps(
        current, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    encoded_candidate = json.dumps(
        candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    exhausted = active_budget.reserve(len(encoded_current) + len(encoded_candidate),
                                      retry=retry)
    if exhausted is not None:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.BUDGET_EXHAUSTED, exhausted,
            current_digest, alternative_digest, calls_used=active_budget.calls,
            retries_used=active_budget.retries,
        )
    raw_result, wall_ms, cpu_ms, os_limits_enforced, worker_error = _run_replay_worker(
        worker_id, current, candidate,
        wall_ms=min(active_budget.limits.max_wall_ms - active_budget.wall_ms,
                    active_budget.limits.max_wall_ms),
        cpu_ms=min(active_budget.limits.max_cpu_ms - active_budget.cpu_ms,
                   active_budget.limits.max_cpu_ms),
        output_bytes=active_budget.limits.max_result_bytes,
    )
    active_budget.record_usage(wall_ms, cpu_ms)
    if worker_error is not None:
        return CounterfactualReplayDispatch(
            (CounterfactualReplayStatus.BUDGET_EXHAUSTED
             if worker_error in {
                 CounterfactualReplayReason.REPLAY_WORKER_TIMED_OUT,
                 CounterfactualReplayReason.REPLAY_WORKER_OUTPUT_EXCEEDED,
             } else CounterfactualReplayStatus.FAILED),
            worker_error,
            current_digest, alternative_digest, wall_ms=wall_ms, cpu_ms=cpu_ms,
            calls_used=active_budget.calls, retries_used=active_budget.retries,
            isolation="subprocess", os_limits_enforced=os_limits_enforced,
        )
    if wall_ms > active_budget.limits.max_wall_ms - (active_budget.wall_ms - wall_ms):
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.BUDGET_EXHAUSTED,
            CounterfactualReplayReason.REPLAY_WALL_BUDGET_EXCEEDED,
            current_digest, alternative_digest, wall_ms=wall_ms, cpu_ms=cpu_ms,
            calls_used=active_budget.calls, retries_used=active_budget.retries,
            isolation="subprocess", os_limits_enforced=os_limits_enforced,
        )
    if cpu_ms > active_budget.limits.max_cpu_ms - (active_budget.cpu_ms - cpu_ms):
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.BUDGET_EXHAUSTED,
            CounterfactualReplayReason.REPLAY_CPU_BUDGET_EXCEEDED,
            current_digest, alternative_digest, wall_ms=wall_ms, cpu_ms=cpu_ms,
            calls_used=active_budget.calls, retries_used=active_budget.retries,
            isolation="subprocess", os_limits_enforced=os_limits_enforced,
        )
    try:
        result = _canonical_object(
            raw_result, max_bytes=active_budget.limits.max_result_bytes,
            label="counterfactual replay result",
        )
        result = scrub_public_json(result)
    except ValueError as exc:
        too_large = "exceeds its byte limit" in str(exc)
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.BUDGET_EXHAUSTED if too_large
            else CounterfactualReplayStatus.FAILED,
            CounterfactualReplayReason.REPLAY_RESULT_TOO_LARGE if too_large
            else CounterfactualReplayReason.REPLAY_RESULT_INVALID,
            current_digest, alternative_digest, wall_ms=wall_ms, cpu_ms=cpu_ms,
            calls_used=active_budget.calls, retries_used=active_budget.retries,
            isolation="subprocess", os_limits_enforced=os_limits_enforced,
        )
    return CounterfactualReplayDispatch(
        CounterfactualReplayStatus.INVOKED,
        CounterfactualReplayReason.MATERIAL_ALTERNATIVE_AFTER_DEPENDENCE,
        current_digest, alternative_digest, result,
        wall_ms, cpu_ms, active_budget.calls, active_budget.retries,
        "subprocess", os_limits_enforced,
    )


@dataclass(frozen=True)
class RuntimeTool:
    """Host-owned handler declaration with strict JSON argument and output bounds."""

    name: str
    handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    required_fields: frozenset[str] = frozenset()
    optional_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name):
            raise ValueError("tool names must be stable identifiers")
        if not callable(self.handler):
            raise ValueError("tool handler must be callable")
        if (self.required_fields & self.optional_fields
                or any(not isinstance(key, str) for key in (
                    self.required_fields | self.optional_fields))):
            raise ValueError("tool argument declarations must be disjoint string fields")


@dataclass(frozen=True)
class ToolCallRecord:
    step_id: str
    tool: str
    status: str
    output_sha256: str


@dataclass(frozen=True)
class RuntimeResult:
    status: RuntimeStatus
    steps: tuple[AgentStep, ...]
    calls: tuple[ToolCallRecord, ...]
    observations: tuple[AgentObservation, ...]
    failure_code: str | None = None


DecisionFunction = Callable[[AgentObservation], AgentStep]
JsonDecisionFunction = Callable[[AgentObservation], str]


class _InvalidAgentJson(Exception):
    """Marks an invalid actor response separately from a failed decision callback."""


def _canonical_object(value: Any, *, max_bytes: int, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a JSON object with string keys")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError(f"{label} exceeds its byte limit")
        decoded = json.loads(encoded)
    except (RecursionError, TypeError, UnicodeEncodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must contain finite canonical JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must be a JSON object")
    return decoded


def run_agent_loop(
    initial: AgentObservation,
    actor_id: str,
    decide: DecisionFunction,
    tools: Mapping[str, RuntimeTool],
    *,
    max_steps: int | None = None,
) -> RuntimeResult:
    """Run bounded steps, exposing each tool result to the next decision only.

    A step with intent ``abstain`` stops the loop. Other intents must name one
    declared tool in ``arguments.tool``; invalid or unauthorized calls stop
    fail-closed without invoking a handler. A handler error becomes a generic
    visible result so the actor can decide what to do next.
    """
    if not isinstance(initial, AgentObservation):
        raise TypeError("initial input must be AgentObservation")
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError("actor_id must be non-empty text")
    if not callable(decide):
        raise ValueError("decide must be callable")
    if max_steps is not None and (
            isinstance(max_steps, bool) or not isinstance(max_steps, int)
            or not 0 <= max_steps <= MAX_RUNTIME_STEPS):
        raise ValueError(f"max_steps must be between 0 and {MAX_RUNTIME_STEPS}")
    if any(name != tool.name for name, tool in tools.items()):
        raise ValueError("tool registry keys must match declarations")
    budget_steps = initial.budget.get("steps", 0)
    if isinstance(budget_steps, bool) or not isinstance(budget_steps, int):
        raise ValueError("observation step budget must be an integer")
    step_limit = min(budget_steps, MAX_RUNTIME_STEPS)
    if max_steps is not None:
        step_limit = min(step_limit, max_steps)

    observation = initial
    observations = [initial]
    steps: list[AgentStep] = []
    calls: list[ToolCallRecord] = []
    seen_step_ids: set[str] = set()

    for call_index in range(step_limit):
        try:
            step = decide(observation)
        except _InvalidAgentJson:
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "invalid_agent_json")
        except Exception:
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "decision_failed")
        if (not isinstance(step, AgentStep) or step.task_id != initial.task_id
                or step.actor_id != actor_id or step.step_id in seen_step_ids):
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "invalid_agent_step")
        seen_step_ids.add(step.step_id)
        steps.append(step)
        if step.intent == "abstain":
            return RuntimeResult(RuntimeStatus.ABSTAINED, tuple(steps), tuple(calls),
                                 tuple(observations))

        try:
            arguments = json.loads(step.canonical_json())["arguments"]
            tool_name = arguments.get("tool")
            if not isinstance(tool_name, str) or tool_name not in initial.permitted_tools:
                raise ValueError("tool_not_permitted")
            declaration = tools.get(tool_name)
            if declaration is None:
                raise ValueError("tool_not_declared")
            tool_arguments = dict(arguments)
            tool_arguments.pop("tool")
            if (not declaration.required_fields <= set(tool_arguments)
                    or set(tool_arguments) - declaration.required_fields
                    - declaration.optional_fields):
                raise ValueError("invalid_tool_arguments")
            tool_arguments = _canonical_object(
                tool_arguments, max_bytes=MAX_TOOL_ARGUMENT_BYTES, label="tool arguments")
        except ValueError as exc:
            code = str(exc)
            if code not in {"tool_not_permitted", "tool_not_declared", "invalid_tool_arguments"}:
                code = "invalid_tool_arguments"
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), code)

        try:
            output = declaration.handler(tool_arguments)
            safe_output = _canonical_object(
                output, max_bytes=MAX_TOOL_OUTPUT_BYTES, label="tool output")
            status = "ok"
        except Exception:
            safe_output = {"ok": False, "reason": "tool_failed"}
            status = "failed"
        event = {"source": "tool", "tool": tool_name,
                 "call_index": call_index + 1, "output": safe_output}
        try:
            observation = AgentObservation(
                task_id=initial.task_id, instruction=initial.instruction,
                visible_events=(*observation.visible_events, event),
                permitted_tools=initial.permitted_tools, budget=initial.budget,
            )
        except (TypeError, ValueError):
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "tool_output_not_actor_visible")
        output_bytes = json.dumps(safe_output, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False, allow_nan=False).encode("utf-8")
        calls.append(ToolCallRecord(
            step_id=step.step_id, tool=tool_name, status=status,
            output_sha256=hashlib.sha256(output_bytes).hexdigest(),
        ))
        observations.append(observation)

    return RuntimeResult(RuntimeStatus.BUDGET_EXHAUSTED, tuple(steps), tuple(calls),
                         tuple(observations), "step_budget_exhausted")


def run_agent_json_loop(
    initial: AgentObservation,
    actor_id: str,
    decide_json: JsonDecisionFunction,
    tools: Mapping[str, RuntimeTool],
    *,
    max_steps: int | None = None,
) -> RuntimeResult:
    """Parse actor responses against AgentStep's strict schema before dispatch.

    Malformed, ambiguous, oversized, or schema-unknown JSON stops the loop
    before tool dispatch. Valid ``abstain`` steps retain explicit abstention.
    """
    if not callable(decide_json):
        raise ValueError("decide_json must be callable")

    def parse_decision(observation: AgentObservation) -> AgentStep:
        raw = decide_json(observation)
        try:
            return AgentStep.from_json(raw)
        except (TypeError, ValueError, UnicodeError) as exc:
            raise _InvalidAgentJson from exc

    return run_agent_loop(initial, actor_id, parse_decision, tools, max_steps=max_steps)
