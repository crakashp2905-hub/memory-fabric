"""One end-to-end agent episode: observe, retrieve, plan, verify, act or recover, stop.

Checklist W03. This is the host side of an episode. It runs three roles -
``observer``, ``planner`` and ``executor`` - through one typed decision
interface, a declared tool registry and one shared budget, and stops in exactly
one host outcome. It never imports evaluator code: the world's public feed and
its simulated effect functions are handed in as plain callables, and terminal
*grading* (completed, safely abstained, failed, undecidable, unsafe) is done by a
separate evaluator from its own state (``benchmarks/outcome_episode.py``).

Phases and their only legal transitions (:data:`TRANSITIONS`)::

    OBSERVE -> RETRIEVE -> PLAN -> VERIFY -> EXECUTE -> TERMINAL
                  ^          |        |         |
                  +------- RECOVER <--+---------+

Every decision, tool call and recovery is charged to one :class:`EpisodeBudget`
shared by all roles, so no role or sub-loop can run on after the episode is out
of budget, and a cycle through ``RECOVER`` always consumes budget. A recovery
that returns to an already-seen state fingerprint stops with ``no_progress``.

Actors never call tools or effects directly. They emit :class:`AgentStep`
values; the host validates each against the :class:`ToolRegistry` before any
handler runs. A plan is a :class:`Proposal` bound to the task, actor, objective,
tool, target, parameters and exact evidence versions; the executor must name
its commitment, and the protected effect runs only through the memory port's
gate (``ActionGate`` for governed memory). A gate refusal leads to recovery; an
uncertain effect ends the episode as ``EFFECT_UNKNOWN`` and is never retried
automatically.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol, Sequence

from .observations import AgentObservation, AgentStep, _canonical, _no_oracle_fields

EPISODE_SCHEMA_ID = "memory-fabric.agent-episode.v1"
TRACE_SCHEMA_ID = "memory-fabric.agent-episode-trace.v1"
ROLES = ("observer", "planner", "executor")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


class Phase(StrEnum):
    OBSERVE = "OBSERVE"
    RETRIEVE = "RETRIEVE"
    PLAN = "PLAN"
    VERIFY = "VERIFY"
    EXECUTE = "EXECUTE"
    RECOVER = "RECOVER"
    TERMINAL = "TERMINAL"


TRANSITIONS: Mapping[Phase, frozenset[Phase]] = {
    Phase.OBSERVE: frozenset({Phase.RETRIEVE, Phase.TERMINAL}),
    Phase.RETRIEVE: frozenset({Phase.PLAN, Phase.RECOVER, Phase.TERMINAL}),
    Phase.PLAN: frozenset({Phase.VERIFY, Phase.RETRIEVE, Phase.RECOVER, Phase.TERMINAL}),
    Phase.VERIFY: frozenset({Phase.EXECUTE, Phase.RECOVER, Phase.TERMINAL}),
    Phase.EXECUTE: frozenset({Phase.TERMINAL, Phase.RECOVER}),
    Phase.RECOVER: frozenset({Phase.OBSERVE, Phase.RETRIEVE, Phase.TERMINAL}),
    Phase.TERMINAL: frozenset(),
}


class HostOutcome(StrEnum):
    """What the host saw. Not a grade: only the evaluator decides completion."""

    EFFECT_EXECUTED = "EFFECT_EXECUTED"
    EFFECT_UNKNOWN = "EFFECT_UNKNOWN"
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class TerminalStatus(StrEnum):
    """Evaluator-only terminal vocabulary (W03-08); never computed by the host."""

    COMPLETED = "COMPLETED"
    SAFE_ABSTAINED = "SAFE_ABSTAINED"
    FAILED = "FAILED"
    UNDECIDABLE = "UNDECIDABLE"
    UNSAFE_EXECUTED = "UNSAFE_EXECUTED"


class EpisodeError(Exception):
    """Base for host-side stops; carries a stable reason code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BudgetExhausted(EpisodeError):
    pass


class ToolRejected(EpisodeError):
    pass


class IllegalTransition(EpisodeError):
    pass


ACTOR_BACKEND_CODES = frozenset({
    "model_malformed_output", "model_truncated", "model_timeout", "model_context_overflow",
    "model_out_of_memory", "model_unavailable", "model_call_budget_exhausted", "model_error",
})


class ActorBackendError(EpisodeError):
    """A decision backend (a local model) that produced no valid step (W12-06).

    Each code is a distinct incomplete outcome that stays in the denominator; the
    runtime keeps the code instead of folding it into ``decision_failed``, and
    never substitutes another answer.
    """

    def __init__(self, code: str) -> None:
        if code not in ACTOR_BACKEND_CODES:
            raise ValueError(f"unknown actor backend code: {code}")
        super().__init__(code)


def _check_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{label} must be a stable identifier")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


# --- budget -----------------------------------------------------------------


@dataclass(frozen=True)
class EpisodeLimits:
    max_steps: int = 32
    max_tool_calls: int = 32
    max_context_bytes: int = 64_000
    max_wall_ms: int = 30_000
    max_recoveries: int = 3

    def __post_init__(self) -> None:
        for name in ("max_steps", "max_tool_calls", "max_context_bytes", "max_wall_ms",
                     "max_recoveries"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_steps > 256 or self.max_tool_calls > 256 or self.max_recoveries > 32:
            raise ValueError("episode limits exceed the supported ceiling")

    def to_dict(self) -> dict[str, int]:
        return {"max_steps": self.max_steps, "max_tool_calls": self.max_tool_calls,
                "max_context_bytes": self.max_context_bytes, "max_wall_ms": self.max_wall_ms,
                "max_recoveries": self.max_recoveries}


class EpisodeBudget:
    """One budget for every role and sub-loop of an episode (W03-07)."""

    def __init__(self, limits: EpisodeLimits, clock: Callable[[], float] = time.monotonic) -> None:
        self.limits = limits
        self._clock = clock
        self._started = clock()
        self.steps = 0
        self.tool_calls = 0
        self.recoveries = 0
        self.peak_context_bytes = 0
        self.steps_by_role: dict[str, int] = {role: 0 for role in ROLES}

    def _check_wall(self) -> None:
        if (self._clock() - self._started) * 1000 > self.limits.max_wall_ms:
            raise BudgetExhausted("wall_time_exhausted")

    def charge_step(self, role: str, context_bytes: int) -> None:
        self._check_wall()
        if self.steps >= self.limits.max_steps:
            raise BudgetExhausted("step_budget_exhausted")
        if context_bytes > self.limits.max_context_bytes:
            raise BudgetExhausted("context_budget_exhausted")
        self.steps += 1
        self.steps_by_role[role] = self.steps_by_role.get(role, 0) + 1
        self.peak_context_bytes = max(self.peak_context_bytes, context_bytes)

    def charge_tool(self) -> None:
        self._check_wall()
        if self.tool_calls >= self.limits.max_tool_calls:
            raise BudgetExhausted("tool_budget_exhausted")
        self.tool_calls += 1

    def charge_recovery(self) -> None:
        if self.recoveries >= self.limits.max_recoveries:
            raise BudgetExhausted("recovery_budget_exhausted")
        self.recoveries += 1

    def remaining(self) -> dict[str, int]:
        return {"steps": self.limits.max_steps - self.steps,
                "tool_calls": self.limits.max_tool_calls - self.tool_calls,
                "recoveries": self.limits.max_recoveries - self.recoveries}

    def usage(self) -> dict[str, Any]:
        return {"steps": self.steps, "tool_calls": self.tool_calls,
                "recoveries": self.recoveries, "peak_context_bytes": self.peak_context_bytes,
                "steps_by_role": dict(sorted(self.steps_by_role.items()))}


# --- task envelope ------------------------------------------------------------

STOP_CONDITIONS = frozenset({"abstain", "effect_executed", "effect_unknown", "budget_exhausted",
                             "no_progress", "invalid_step"})


@dataclass(frozen=True)
class TaskEnvelope:
    """Everything an actor may know about a task; evaluator truth is refused (W03-02)."""

    task_id: str
    objective_id: str
    objective: str
    public_context: tuple[Mapping[str, Any], ...]
    role_tools: Mapping[str, tuple[str, ...]]
    limits: EpisodeLimits = field(default_factory=EpisodeLimits)
    stop_conditions: tuple[str, ...] = tuple(sorted(STOP_CONDITIONS))

    def __post_init__(self) -> None:
        _check_id(self.task_id, "task_id")
        _check_id(self.objective_id, "objective_id")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be non-empty text")
        if set(self.role_tools) - set(ROLES):
            raise ValueError("role_tools may only name observer, planner and executor")
        for role, tools in self.role_tools.items():
            for tool in tools:
                _check_id(tool, f"{role} tool")
        if not set(self.stop_conditions) <= STOP_CONDITIONS:
            raise ValueError("unknown stop condition")
        if not isinstance(self.limits, EpisodeLimits):
            raise TypeError("limits must be EpisodeLimits")
        _no_oracle_fields(self.to_public_dict())
        object.__setattr__(self, "public_context", tuple(dict(item) for item in self.public_context))
        object.__setattr__(self, "role_tools",
                           {role: tuple(tools) for role, tools in sorted(self.role_tools.items())})

    def to_public_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "objective_id": self.objective_id,
                "objective": self.objective,
                "public_context": [dict(item) for item in self.public_context],
                "role_tools": {role: list(tools) for role, tools in self.role_tools.items()},
                "limits": self.limits.to_dict(), "stop_conditions": list(self.stop_conditions)}

    def observation(self, role: str, events: Sequence[Mapping[str, Any]],
                    budget: EpisodeBudget) -> AgentObservation:
        """The role's view: objective, public context, its own events and remaining budget."""
        if role not in ROLES:
            raise ValueError("unknown role")
        return AgentObservation(
            task_id=self.task_id, instruction=self.objective,
            visible_events=(*self.public_context, *events),
            permitted_tools=self.role_tools.get(role, ()),
            budget={**budget.remaining(), "role_steps_used": budget.steps_by_role.get(role, 0)})


# --- tools --------------------------------------------------------------------

_TYPES: Mapping[str, tuple[type, ...]] = {"str": (str,), "int": (int,), "bool": (bool,),
                                          "list": (list, tuple), "object": (dict, Mapping)}


@dataclass(frozen=True)
class ToolSpec:
    """A host-declared tool: who may call it, its argument schema and its effect class."""

    name: str
    roles: frozenset[str]
    fields: Mapping[str, str]
    required: frozenset[str]
    protected: bool = False
    idempotent: bool = True
    audited: bool = True

    def __post_init__(self) -> None:
        _check_id(self.name, "tool name")
        if not self.roles or not set(self.roles) <= set(ROLES):
            raise ValueError("tool roles must be a non-empty subset of the episode roles")
        if any(kind not in _TYPES for kind in self.fields.values()):
            raise ValueError("tool field types must be str, int, bool, list or object")
        if not set(self.required) <= set(self.fields):
            raise ValueError("required tool fields must be declared")
        object.__setattr__(self, "roles", frozenset(self.roles))
        object.__setattr__(self, "required", frozenset(self.required))
        object.__setattr__(self, "fields", dict(self.fields))


class ToolRegistry:
    """Validates every tool request before any handler runs (W03-04)."""

    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        names = [spec.name for spec in specs]
        if len(set(names)) != len(names):
            raise ValueError("tool names must be unique")
        self._specs = {spec.name: spec for spec in specs}

    def spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def validate(self, role: str, step: AgentStep) -> tuple[ToolSpec, dict[str, Any]]:
        arguments = json.loads(step.canonical_json())["arguments"]
        name = arguments.pop("tool", None)
        if not isinstance(name, str):
            raise ToolRejected("tool_not_named")
        spec = self._specs.get(name)
        if spec is None:
            raise ToolRejected("tool_not_declared")
        if role not in spec.roles:
            raise ToolRejected("tool_not_permitted_for_role")
        missing = spec.required - set(arguments)
        unknown = set(arguments) - set(spec.fields)
        if missing or unknown:
            raise ToolRejected("malformed_tool_arguments")
        for key, value in arguments.items():
            kinds = _TYPES[spec.fields[key]]
            if not isinstance(value, kinds) or (spec.fields[key] == "int" and isinstance(value, bool)):
                raise ToolRejected("malformed_tool_arguments")
        return spec, arguments


# --- proposals ------------------------------------------------------------------


@dataclass(frozen=True)
class Proposal:
    """A plan bound to everything that justifies it (W03-06); any change is a new proposal."""

    task_id: str
    actor_id: str
    objective_id: str
    tool: str
    target: str
    parameters: Mapping[str, Any]
    evidence: tuple[tuple[str, int], ...]
    world_epoch: int

    def __post_init__(self) -> None:
        for label in ("task_id", "actor_id", "objective_id", "tool", "target"):
            _check_id(getattr(self, label), label)
        if not self.evidence:
            raise ValueError("a proposal must name the evidence it rests on")
        pairs = []
        for item in self.evidence:
            if (not isinstance(item, (tuple, list)) or len(item) != 2
                    or not isinstance(item[0], str) or isinstance(item[1], bool)
                    or not isinstance(item[1], int) or item[1] < 0):
                raise ValueError("evidence must be (memory_id, version) pairs")
            pairs.append((item[0], item[1]))
        if isinstance(self.world_epoch, bool) or not isinstance(self.world_epoch, int) \
                or self.world_epoch < 0:
            raise ValueError("world_epoch must be a non-negative integer")
        _no_oracle_fields(dict(self.parameters))
        object.__setattr__(self, "evidence", tuple(pairs))
        object.__setattr__(self, "parameters", json.loads(_canonical(dict(self.parameters))))

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "actor_id": self.actor_id,
                "objective_id": self.objective_id, "tool": self.tool, "target": self.target,
                "parameters": dict(self.parameters),
                "evidence": [list(pair) for pair in self.evidence],
                "world_epoch": self.world_epoch}

    def commitment(self) -> str:
        return _digest({"schema_id": EPISODE_SCHEMA_ID, "proposal": self.to_dict()})


# --- actor-visible trace --------------------------------------------------------


class ActorTrace:
    """Replayable, content-safe trace of what actors saw and did (W03-09).

    Event IDs are stable (sequence and kind); payloads are checked to carry no
    evaluator fields. The digest is over canonical JSON, so an equivalent trace
    with different key order has the same digest and any edit changes it.
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = _check_id(task_id, "task_id")
        self.events: list[dict[str, Any]] = []

    def add(self, kind: str, role: str | None, payload: Mapping[str, Any]) -> dict[str, Any]:
        _check_id(kind, "trace event kind")
        body = json.loads(_canonical(dict(payload)))
        _no_oracle_fields(body)
        event = {"event_id": f"{self.task_id}:{len(self.events):04d}:{kind}", "kind": kind,
                 "role": role, "payload": body}
        self.events.append(event)
        return event

    def digest(self) -> str:
        return trace_digest(self.task_id, self.events)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_id": TRACE_SCHEMA_ID, "task_id": self.task_id, "events": self.events,
                "digest": self.digest()}


def trace_digest(task_id: str, events: Sequence[Mapping[str, Any]]) -> str:
    return _digest({"schema_id": TRACE_SCHEMA_ID, "task_id": task_id, "events": list(events)})


# --- memory port ------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceRef:
    memory_id: str
    version: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"memory_id": self.memory_id, "version": self.version, "text": self.text}


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    reason_codes: tuple[str, ...]
    certificate: Any = None


@dataclass(frozen=True)
class EffectOutcome:
    """The host's view of one protected effect attempt."""

    outcome: str  # EXECUTED, REFUSED, UNCERTAIN, ALREADY_EXECUTED, TIMED_OUT, FAILED
    reason_codes: tuple[str, ...]
    receipt: Mapping[str, Any] = field(default_factory=dict)


class MemoryPort(Protocol):
    """What an episode may do with memory. Arms differ only in this port."""

    name: str

    def record(self, role: str, text: str, corrects: Sequence[str] = (),
               restricted: bool = False) -> tuple[str, int]: ...

    def retrieve(self, role: str, query: str, k: int) -> list[EvidenceRef]: ...

    def verify(self, proposal: Proposal) -> VerifyResult: ...

    def execute(self, proposal: Proposal, verified: VerifyResult,
                run: Callable[[str], Any], key: str) -> EffectOutcome: ...


class GovernedMemoryPort:
    """Memory Fabric with correction propagation and the ActionGate (the A4/A5 memory).

    A recorded correction quarantines what it corrects; verification uses the
    certificate verifier; a protected effect runs only through ``ActionGate.execute``
    with a host-issued grant bound to the exact request and certificate.
    """

    name = "governed"

    def __init__(self, fabric: Any, task_id: str, *, executor_id: str = "executor",
                 protected_tools: Sequence[str] = (), tenant_id: str = "tn_default",
                 restricted_tenant: str = "tn_restricted") -> None:
        from memory_fabric.actions_typed import ActionGate, ActionPolicy, ToolRule
        from memory_fabric.certificates import CertificateVerifier

        self.fabric = fabric
        self.task_id = task_id
        self.executor_id = executor_id
        self.tenant_id = tenant_id
        self.restricted_tenant = restricted_tenant
        self._sessions: dict[str, Any] = {}
        self.verifier = CertificateVerifier(fabric)
        self.gate = ActionGate(fabric, ActionPolicy(
            tools={tool: ToolRule(tool, requires_grant=True) for tool in protected_tools},
            grants={executor_id: frozenset(protected_tools)}))

    def _session(self, role: str) -> Any:
        if role not in self._sessions:
            self._sessions[role] = self.fabric.session(role, self.task_id, seed=0)
        return self._sessions[role]

    def record(self, role: str, text: str, corrects: Sequence[str] = (),
               restricted: bool = False) -> tuple[str, int]:
        from memory_fabric.model import WithdrawalBasis

        # A restricted observation belongs to its owning tenant, not this team's.
        memory_id = self.fabric.remember(
            role, text, scope="team",
            tenant_id=self.restricted_tenant if restricted else self.tenant_id)
        for old in corrects:
            self.fabric.quarantine(old, "corrected by a newer observation", actor=role,
                                   basis=WithdrawalBasis.CONTRADICTED)
        return memory_id, 1

    def withdraw_external(self, memory_id: str) -> None:
        """Another team withdrew this memory; governance propagates it to this store."""
        from memory_fabric.model import WithdrawalBasis

        self.fabric.quarantine(memory_id, "withdrawn by another team", actor="remote-team",
                               basis=WithdrawalBasis.CONTRADICTED)

    def retrieve(self, role: str, query: str, k: int) -> list[EvidenceRef]:
        result = self.fabric.retrieve(agent_id=role, query=query, k=k, tenant_id=self.tenant_id)
        return [EvidenceRef(memory.id, memory.version, memory.content) for memory in result.exposed]

    def verify(self, proposal: Proposal) -> VerifyResult:
        ids = [memory_id for memory_id, _ in proposal.evidence]
        certificate = self.fabric.certify(f"{proposal.tool} {proposal.target}", ids,
                                          self.executor_id, tenant_id=self.tenant_id)
        held = {(e.memory_id, e.version) for e in certificate.evidence}
        if held != set(proposal.evidence):
            return VerifyResult(False, ("evidence_version_moved",), None)
        verification = self.verifier.verify(certificate, self.executor_id,
                                            tenant_id=self.tenant_id)
        return VerifyResult(bool(verification.ok), tuple(verification.reason_codes), certificate)

    def execute(self, proposal: Proposal, verified: VerifyResult,
                run: Callable[[str], Any], key: str) -> EffectOutcome:
        from memory_fabric.actions_typed import ActionRequest

        request = ActionRequest(proposal.target, dict(proposal.parameters))
        try:
            grant = self.gate.issue_grant(proposal.tool, self.executor_id, issuer="host",
                                          certificate=verified.certificate, request=request,
                                          tenant_id=self.tenant_id)
        except ValueError:
            return EffectOutcome("REFUSED", ("grant_refused",))
        execution = self.gate.execute(proposal.tool, self.executor_id, run, verified.certificate,
                                      key=key, request=request, grant=grant,
                                      tenant_id=self.tenant_id,
                                      receipt_context=f"{self.task_id}:effect")
        reasons: tuple[str, ...] = tuple(execution.decision.reason_codes) if execution.decision else ()
        if not reasons and execution.error:
            # Refusals made before authorization (an idempotency conflict, a
            # retry required) carry their code in the error text.
            reasons = (str(execution.error).split(":", 1)[0],)
        receipt = execution.result if isinstance(execution.result, Mapping) else {}
        return EffectOutcome(str(execution.outcome).upper(), tuple(reasons), dict(receipt))


# --- decisions --------------------------------------------------------------------

DecisionFunction = Callable[[str, AgentObservation], AgentStep]
"""One typed decision interface for scripted and model-backed actors (W03-03)."""

JsonDecisionFunction = Callable[[str, AgentObservation], str]


def json_decisions(decide_json: JsonDecisionFunction) -> DecisionFunction:
    """Adapt a backend that answers in JSON text (a local model) to the same interface.

    The text is parsed against the strict ``AgentStep`` schema; anything else is
    an invalid step. There is no fallback to a scripted answer.
    """

    def decide(role: str, observation: AgentObservation) -> AgentStep:
        return AgentStep.from_json(decide_json(role, observation))

    return decide


@dataclass(frozen=True)
class EpisodeRecord:
    """Host record of one episode. Content-safe; carries no evaluator state."""

    task_id: str
    memory: str
    host_outcome: HostOutcome
    reason: str
    phases: tuple[str, ...]
    proposal: Mapping[str, Any] | None
    commitment: str | None
    effect_outcome: str | None
    effect_key: str | None
    budget: Mapping[str, Any]
    trace: Mapping[str, Any]
    steps: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {"schema_id": EPISODE_SCHEMA_ID, "task_id": self.task_id, "memory": self.memory,
                "host_outcome": self.host_outcome.value, "reason": self.reason,
                "phases": list(self.phases), "proposal": self.proposal,
                "commitment": self.commitment, "effect_outcome": self.effect_outcome,
                "effect_key": self.effect_key, "budget": dict(self.budget),
                "trace": dict(self.trace), "steps": list(self.steps)}


def default_tools(protected: str = "set_target") -> ToolRegistry:
    return ToolRegistry([
        ToolSpec("record_observations", frozenset({"observer"}), {"claims": "list"},
                 frozenset({"claims"}), protected=False, idempotent=False),
        ToolSpec("recall", frozenset({"planner"}), {"query": "str", "k": "int"},
                 frozenset({"query"})),
        ToolSpec(protected, frozenset({"planner"}),
                 {"target": "str", "parameters": "object", "evidence": "list"},
                 frozenset({"target", "parameters", "evidence"}), protected=True),
        ToolSpec("execute_proposal", frozenset({"executor"}), {"commitment": "str"},
                 frozenset({"commitment"}), protected=True, idempotent=True),
    ])


class EpisodeRunner:
    """Run one episode to exactly one host outcome."""

    def __init__(self, envelope: TaskEnvelope, decide: DecisionFunction, memory: MemoryPort, *,
                 feed: Callable[[int], Sequence[Mapping[str, Any]]],
                 effects: Mapping[str, Callable[[str, Mapping[str, Any]], Mapping[str, Any]]],
                 tools: ToolRegistry | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 recovery_enabled: bool = True,
                 store_events: Callable[[int], Sequence[str]] | None = None) -> None:
        self.envelope = envelope
        self.recovery_enabled = recovery_enabled
        self.store_events = store_events
        self.applied_store_events: set[str] = set()
        self.seen_at_proposal = 0
        self.decide = decide
        self.memory = memory
        self.feed = feed
        self.effects = effects
        self.tools = tools or default_tools()
        self.budget = EpisodeBudget(envelope.limits, clock)
        self.trace = ActorTrace(envelope.task_id)
        self.phase = Phase.OBSERVE
        self.phases: list[str] = [Phase.OBSERVE.value]
        self.tick = 0
        self.events: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
        self.recorded: dict[str, str] = {}  # public event id -> memory id
        self.retrieved: set[tuple[str, int]] = set()  # every (memory id, version) shown to the planner
        self.seen_events: set[str] = set()
        self.world_epoch = 0
        self.proposal: Proposal | None = None
        self.verified: VerifyResult | None = None
        self.steps: list[dict[str, Any]] = []
        self.step_ids: set[str] = set()
        self.recovery_fingerprints: set[str] = set()
        self.effect_outcome: str | None = None
        self.effect_key: str | None = None

    # -- mechanics --

    def _move(self, target: Phase) -> None:
        if target not in TRANSITIONS[self.phase]:
            raise IllegalTransition(f"illegal_transition_{self.phase.value}_to_{target.value}")
        self.phase = target
        self.phases.append(target.value)
        self.tick += 1

    def _ask(self, role: str) -> AgentStep:
        try:
            observation = self.envelope.observation(role, self.events[role], self.budget)
        except (TypeError, ValueError) as exc:
            # A tool output or world event carrying evaluator-shaped fields never
            # reaches an actor; the episode stops instead (W03-05, W04-06).
            raise EpisodeError("actor_payload_rejected") from exc
        size = len(observation.canonical_json().encode("utf-8"))
        self.budget.charge_step(role, size)
        try:
            step = self.decide(role, observation)
        except ActorBackendError:
            raise
        except Exception as exc:  # a broken backend is an invalid step, not a crash
            raise EpisodeError("decision_failed") from exc
        if (not isinstance(step, AgentStep) or step.task_id != self.envelope.task_id
                or step.actor_id != role or step.step_id in self.step_ids):
            raise EpisodeError("invalid_step")
        self.step_ids.add(step.step_id)
        self.steps.append({"role": role, "phase": self.phase.value, "step": step.to_dict()})
        self.trace.add("decision", role, {"phase": self.phase.value, "intent": step.intent,
                                          "step_digest": step.request_digest()})
        return step

    def _tool(self, role: str, step: AgentStep) -> tuple[ToolSpec, dict[str, Any]]:
        spec, arguments = self.tools.validate(role, step)
        self.budget.charge_tool()
        return spec, arguments

    def _store_changes(self) -> None:
        """Apply changes another team made to the shared store (not seen by this team)."""
        if self.store_events is None:
            return
        for event_id in self.store_events(self.tick):
            if event_id in self.applied_store_events or event_id not in self.recorded:
                continue
            self.applied_store_events.add(event_id)
            withdraw = getattr(self.memory, "withdraw_external", None)
            if callable(withdraw):
                withdraw(self.recorded[event_id])

    def _observe(self) -> None:
        """Deliver unseen public events to the observer and record what it reports."""
        fresh = [dict(item) for item in self.feed(self.tick)
                 if str(item.get("event_id")) not in self.seen_events]
        if not fresh:
            return
        for item in fresh:
            self.seen_events.add(str(item.get("event_id")))
            epoch = item.get("revision_epoch")
            if isinstance(epoch, int) and not isinstance(epoch, bool):
                self.world_epoch = max(self.world_epoch, epoch)
        self.events["observer"].append({"source": "world", "events": fresh})
        self.trace.add("world_events", "observer",
                       {"event_ids": [str(item.get("event_id")) for item in fresh]})
        step = self._ask("observer")
        if step.intent == "abstain":
            return
        spec, arguments = self._tool("observer", step)
        if spec.name != "record_observations":
            raise ToolRejected("tool_not_permitted_for_role")
        recorded = []
        for claim in arguments["claims"]:
            if not isinstance(claim, Mapping) or not isinstance(claim.get("text"), str) \
                    or not isinstance(claim.get("event_id"), str):
                raise ToolRejected("malformed_tool_arguments")
            corrects = [self.recorded[event_id] for event_id in claim.get("corrects", [])
                        if isinstance(event_id, str) and event_id in self.recorded]
            memory_id, version = self.memory.record("observer", claim["text"], corrects,
                                                    bool(claim.get("restricted", False)))
            self.recorded[claim["event_id"]] = memory_id
            recorded.append({"event_id": claim["event_id"], "memory_id": memory_id,
                             "version": version, "corrected": corrects})
        self.events["observer"].append({"source": "tool", "tool": spec.name,
                                        "output": {"recorded": recorded}})
        self.trace.add("observations_recorded", "observer",
                       {"recorded": [{k: v for k, v in item.items()} for item in recorded]})

    # -- run --

    def run(self) -> EpisodeRecord:
        outcome, reason = HostOutcome.FAILED, "not_started"
        try:
            outcome, reason = self._loop()
        except BudgetExhausted as exc:
            outcome, reason = HostOutcome.BUDGET_EXHAUSTED, exc.code
        except (ToolRejected, IllegalTransition, EpisodeError) as exc:
            outcome, reason = HostOutcome.FAILED, exc.code
        except ValueError:
            outcome, reason = HostOutcome.FAILED, "invalid_step"
        if self.phase is not Phase.TERMINAL:
            self.phase = Phase.TERMINAL
            self.phases.append(Phase.TERMINAL.value)
        self.trace.add("host_terminal", None, {"host_outcome": outcome.value, "reason": reason})
        return EpisodeRecord(
            task_id=self.envelope.task_id, memory=getattr(self.memory, "name", "unknown"),
            host_outcome=outcome, reason=reason, phases=tuple(self.phases),
            proposal=self.proposal.to_dict() if self.proposal else None,
            commitment=self.proposal.commitment() if self.proposal else None,
            effect_outcome=self.effect_outcome, effect_key=self.effect_key,
            budget=self.budget.usage(), trace=self.trace.to_dict(), steps=tuple(self.steps))

    def _loop(self) -> tuple[HostOutcome, str]:
        self._observe()
        self._move(Phase.RETRIEVE)
        while True:
            self._store_changes()
            self._observe()
            if self.phase is Phase.RETRIEVE:
                step = self._ask("planner")
                if step.intent == "abstain":
                    self._move(Phase.TERMINAL)
                    return HostOutcome.ABSTAINED, "planner_abstained"
                spec, arguments = self._tool("planner", step)
                if spec.name != "recall":
                    raise ToolRejected("expected_recall")
                found = self.memory.retrieve("planner", arguments["query"],
                                             int(arguments.get("k", 5)))
                self.events["planner"].append({
                    "source": "tool", "tool": "recall", "world_epoch": self.world_epoch,
                    "output": {"evidence": [ref.to_dict() for ref in found]}})
                self.retrieved.update((ref.memory_id, ref.version) for ref in found)
                self.trace.add("retrieved", "planner", {"evidence": [
                    [ref.memory_id, ref.version] for ref in found]})
                self._move(Phase.PLAN)
            elif self.phase is Phase.PLAN:
                step = self._ask("planner")
                if step.intent == "abstain":
                    self._move(Phase.TERMINAL)
                    return HostOutcome.ABSTAINED, "planner_abstained"
                spec, arguments = self._tool("planner", step)
                if spec.name == "recall":
                    self._move(Phase.RETRIEVE)
                    continue
                if not spec.protected or step.intent != "propose":
                    raise ToolRejected("expected_proposal")
                cited = arguments["evidence"]
                if not all(isinstance(pair, (list, tuple)) and len(pair) == 2
                           and isinstance(pair[0], str) and isinstance(pair[1], int)
                           and not isinstance(pair[1], bool) for pair in cited):
                    raise ToolRejected("malformed_tool_arguments")
                if any((pair[0], pair[1]) not in self.retrieved for pair in cited):
                    # Evidence the planner was never shown: invented or carried in
                    # from elsewhere. Refused before verification (W12-06).
                    raise ToolRejected("evidence_not_retrieved")
                self.proposal = Proposal(
                    task_id=self.envelope.task_id, actor_id="planner",
                    objective_id=self.envelope.objective_id, tool=spec.name,
                    target=arguments["target"], parameters=arguments["parameters"],
                    evidence=tuple(tuple(pair) for pair in arguments["evidence"]),
                    world_epoch=self.world_epoch)
                commitment = self.proposal.commitment()
                self.seen_at_proposal = len(self.seen_events)
                self.trace.add("proposed", "planner", {"commitment": commitment,
                                                       "evidence": arguments["evidence"]})
                self.events["executor"].append({"source": "host", "kind": "proposal",
                                                "commitment": commitment,
                                                "proposal": self.proposal.to_dict()})
                self._move(Phase.VERIFY)
            elif self.phase is Phase.VERIFY:
                assert self.proposal is not None
                if self.recovery_enabled and len(self.seen_events) > self.seen_at_proposal:
                    # New observations arrived after the plan: re-plan before acting.
                    # A recovery affordance every memory arm gets, not a governance one.
                    self.trace.add("verified", None, {"ok": False,
                                                      "reason_codes": ["new_observations_since_plan"]})
                    self.events["planner"].append({"source": "host", "kind": "replan_requested",
                                                   "reason_codes": ["new_observations_since_plan"]})
                    self._move(Phase.RECOVER)
                    continue
                self.verified = self.memory.verify(self.proposal)
                self.trace.add("verified", None, {"ok": self.verified.ok,
                                                  "reason_codes": list(self.verified.reason_codes)})
                if self.verified.ok:
                    self._move(Phase.EXECUTE)
                else:
                    self.events["planner"].append({"source": "host", "kind": "verification_failed",
                                                   "reason_codes": list(self.verified.reason_codes)})
                    self._move(Phase.RECOVER)
            elif self.phase is Phase.EXECUTE:
                assert self.proposal is not None and self.verified is not None
                step = self._ask("executor")
                if step.intent == "abstain":
                    self._move(Phase.TERMINAL)
                    return HostOutcome.ABSTAINED, "executor_abstained"
                spec, arguments = self._tool("executor", step)
                if spec.name != "execute_proposal" or step.intent != "propose":
                    raise ToolRejected("expected_execute_proposal")
                if arguments["commitment"] != self.proposal.commitment():
                    raise ToolRejected("proposal_commitment_mismatch")
                effect = self.effects.get(self.proposal.tool)
                if effect is None:
                    raise ToolRejected("effect_not_provided_by_host")
                proposal_public = self.proposal.to_dict()
                key = f"{self.envelope.task_id}:{self.proposal.commitment()[:24]}"
                self.effect_key = key
                outcome = self.memory.execute(self.proposal, self.verified,
                                              lambda k: effect(k, proposal_public), key)
                self.effect_outcome = outcome.outcome
                self.trace.add("effect", "executor", {"outcome": outcome.outcome,
                                                      "reason_codes": list(outcome.reason_codes),
                                                      "key": key})
                self.events["executor"].append({"source": "host", "kind": "effect_result",
                                                "outcome": outcome.outcome,
                                                "receipt": dict(outcome.receipt)})
                if outcome.outcome in {"EXECUTED", "ALREADY_EXECUTED"}:
                    self._move(Phase.TERMINAL)
                    return HostOutcome.EFFECT_EXECUTED, "effect_executed"
                if outcome.outcome == "REFUSED":
                    self.events["planner"].append({"source": "host", "kind": "effect_refused",
                                                   "reason_codes": list(outcome.reason_codes)})
                    self._move(Phase.RECOVER)
                else:
                    self._move(Phase.TERMINAL)
                    return HostOutcome.EFFECT_UNKNOWN, "effect_outcome_unknown"
            elif self.phase is Phase.RECOVER:
                if not self.recovery_enabled:
                    self._move(Phase.TERMINAL)
                    return HostOutcome.FAILED, "recovery_disabled"
                self.budget.charge_recovery()
                fingerprint = _digest({"seen": sorted(self.seen_events),
                                       "evidence": self.proposal.to_dict()["evidence"]
                                       if self.proposal else None})
                if fingerprint in self.recovery_fingerprints:
                    self._move(Phase.TERMINAL)
                    return HostOutcome.FAILED, "no_progress"
                self.recovery_fingerprints.add(fingerprint)
                self.trace.add("recovery", "planner", {"fingerprint": fingerprint})
                self.proposal, self.verified = None, None
                self._move(Phase.RETRIEVE)
            else:  # pragma: no cover - TERMINAL never loops
                raise IllegalTransition("terminal_reentered")


def run_episode(envelope: TaskEnvelope, decide: DecisionFunction, memory: MemoryPort, *,
                feed: Callable[[int], Sequence[Mapping[str, Any]]],
                effects: Mapping[str, Callable[[str, Mapping[str, Any]], Mapping[str, Any]]],
                tools: ToolRegistry | None = None,
                clock: Callable[[], float] = time.monotonic,
                recovery_enabled: bool = True,
                store_events: Callable[[int], Sequence[str]] | None = None) -> EpisodeRecord:
    """Run one episode; see :class:`EpisodeRunner`."""
    return EpisodeRunner(envelope, decide, memory, feed=feed, effects=effects, tools=tools,
                         clock=clock, recovery_enabled=recovery_enabled,
                         store_events=store_events).run()
