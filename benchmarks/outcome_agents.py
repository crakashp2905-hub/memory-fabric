"""Typed, scripted Observer/Planner/Executor roles for offline experiments.

These actors receive only an ``AgentObservation`` and their own authenticated
``Session``. Tool declarations restrict each role; the host retains grant
issuance and every protected effect still passes through ``ActionGate``.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, Sequence

from memory_fabric.adapters.ollama import DEFAULT_MODEL, CallRecord, OllamaClient, OllamaError
from memory_fabric.actions import EXECUTED, ActionExecution, ActionGate, ActionRequest, Grant
from memory_fabric.agent_outcomes import AgentObservation, AgentStep
from memory_fabric.agent_outcomes.observations import SCHEMA_ID
from memory_fabric.certificates import EvidenceCertificate
from memory_fabric.enforcement import RiskLevel
from memory_fabric.model import Memory
from memory_fabric.service import MemoryService, Session


class ActorRole(StrEnum):
    OBSERVER = "observer"
    PLANNER = "planner"
    EXECUTOR = "executor"


class ActorToolDenied(ValueError):
    """A role or task observation does not permit the requested tool."""

    failure_code = "tool_misuse"

    def __init__(self, message: str, *, attempted_tool: str | None = None) -> None:
        super().__init__(message)
        self.attempted_tool = attempted_tool


class AgentOutputFailure(ValueError):
    """A content-safe classification for a model response rejected by the host."""

    def __init__(
        self,
        failure_code: str,
        message: str = "agent output was rejected",
        *,
        attempted_tool: str | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_code = failure_code
        self.attempted_tool = attempted_tool


class EvidenceVersionChanged(ValueError):
    """The evidence changed or lost current authorization after planning."""


class AgentAdapter(Protocol):
    """A decision source that receives only an actor-visible observation."""

    def __call__(self, observation: AgentObservation) -> AgentStep: ...


_OLLAMA_AGENT_SYSTEM = (
    "You are one role in a bounded task agent. The user message contains the only "
    "task observation you may use. Return exactly one JSON AgentStep matching the "
    "provided schema. Copy its task_id, actor_id, and step_id constants exactly. Set "
    "arguments.tool to one of the permitted tools or `abstain`. Set evidence_versions "
    "to [] unless exact evidence IDs and non-negative integer versions appear in the "
    "observation; never invent evidence or versions. Do not add fields."
)
OLLAMA_AGENT_SYSTEM_SHA256 = hashlib.sha256(
    _OLLAMA_AGENT_SYSTEM.encode("utf-8")
).hexdigest()
_INTENT_FOR_TOOL = {
    "remember_evidence": "inspect",
    "retrieve_evidence": "retrieve",
    "propose_action": "propose",
    "certify_evidence": "inspect",
    "set_target": "propose",
    "inspect": "inspect",
}
_ARGUMENT_FIELDS_FOR_TOOL: dict[str, dict[str, Any]] = {
    "remember_evidence": {
        "content": {"type": "string", "minLength": 1, "maxLength": 8000},
    },
    "retrieve_evidence": {
        "query": {"type": "string", "minLength": 1, "maxLength": 8000},
        "k": {"type": "integer", "minimum": 1, "maximum": 20},
    },
    "propose_action": {
        "action_tool": {"type": "string", "minLength": 1, "maxLength": 64},
        "parameters": {"type": "object"},
        "claim": {"type": "string", "minLength": 1, "maxLength": 8000},
    },
    "set_target": {"parameters": {"type": "object"}},
}
_ALL_AGENT_INTENTS = ("retrieve", "inspect", "request_refresh", "ask", "propose", "abstain")


class OllamaAgentAdapter:
    """Ask a local Ollama model for one strictly validated, task-only next step."""

    def __init__(
        self,
        actor_id: str,
        *,
        model: str = DEFAULT_MODEL,
        client: Any = None,
        temperature: float = 0.0,
        top_p: float = 0.9,
        seed: int = 0,
        num_ctx: int = 4096,
        num_predict: int = 256,
        think: bool | None = None,
    ) -> None:
        if not isinstance(actor_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}",
                                                             actor_id):
            raise ValueError("actor_id must be a stable identifier")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty name")
        if (not isinstance(temperature, (int, float)) or isinstance(temperature, bool)
                or not 0 <= temperature <= 2):
            raise ValueError("temperature must be between 0 and 2")
        if (not isinstance(top_p, (int, float)) or isinstance(top_p, bool)
                or not 0 < top_p <= 1):
            raise ValueError("top_p must be between 0 and 1")
        if (not isinstance(seed, int) or isinstance(seed, bool)
                or not 0 <= seed <= 0xffffffff):
            raise ValueError("seed must be a 32-bit non-negative integer")
        if (not isinstance(num_ctx, int) or isinstance(num_ctx, bool)
                or not 1 <= num_ctx <= 1_048_576):
            raise ValueError("num_ctx must be between 1 and 1048576")
        if (not isinstance(num_predict, int) or isinstance(num_predict, bool)
                or not 1 <= num_predict <= 16_000):
            raise ValueError("num_predict must be between 1 and 16000")
        if think is not None and not isinstance(think, bool):
            raise ValueError("think must be a boolean or None")
        self.actor_id = actor_id
        self.model = model
        self.client = client if client is not None else OllamaClient()
        self.temperature = float(temperature)
        self.top_p = float(top_p)
        self.seed = seed
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.think = think
        self._model_metadata: Mapping[str, Any] = MappingProxyType({})
        self._schema_sha256: str | None = None
        self._step_counter = 0

    @property
    def calls(self) -> tuple[CallRecord, ...]:
        """Return the Ollama client's recorded model calls without prompt text."""
        calls = getattr(self.client, "calls", ())
        return tuple(calls)

    @property
    def model_metadata(self) -> Mapping[str, Any]:
        """Installed model identity loaded before the latest inference call."""
        return self._model_metadata

    def __call__(self, observation: AgentObservation) -> AgentStep:
        return self.next_step(observation)

    def inference_manifest(self, call: CallRecord) -> dict[str, Any]:
        """Return pinned model, prompt hash, and explicit decoding provenance."""
        if not isinstance(call, CallRecord) or self._schema_sha256 is None:
            raise ValueError("inference metadata is unavailable before a completed model call")
        model = dict(self._model_metadata)
        return {
            "model": model,
            "decoder": "ollama:/api/chat",
            "options": {
                "temperature": self.temperature,
                "top_p": self.top_p,
                "seed": self.seed,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
                "think": self.think,
                "stream": False,
                "keep_alive": getattr(self.client, "keep_alive", None),
                "format": "json_schema",
                "constrained": call.constrained,
            },
            "usage": {
                "prompt_tokens": call.prompt_tokens,
                "completion_tokens": call.completion_tokens,
                "total_tokens": call.tokens,
                "wall_seconds": call.seconds,
                "retry_count": call.retry_count,
                "request_succeeded": call.succeeded,
            },
            "prompt_sha256": call.prompt_sha256,
            "system_prompt_sha256": OLLAMA_AGENT_SYSTEM_SHA256,
            "response_schema_sha256": self._schema_sha256,
            "nondeterminism_disclosure": (
                "A fixed seed and sampling configuration do not guarantee bitwise-identical "
                "outputs across Ollama versions, model runtimes, or hardware."
            ),
        }

    def next_step(self, observation: AgentObservation) -> AgentStep:
        """Generate one schema-checked intent from the public observation only."""
        if not isinstance(observation, AgentObservation):
            raise TypeError("OllamaAgentAdapter accepts only AgentObservation")
        reset_retry_count = getattr(self.client, "reset_chat_retry_count", None)
        if callable(reset_retry_count):
            reset_retry_count()
        mapped_intents = {
            _INTENT_FOR_TOOL[tool] for tool in observation.permitted_tools
            if tool in _INTENT_FOR_TOOL
        }
        allowed_intents = ([intent for intent in _ALL_AGENT_INTENTS
                            if intent == "abstain" or intent in mapped_intents]
                           if mapped_intents else list(_ALL_AGENT_INTENTS))
        argument_properties: dict[str, Any] = {
            "tool": {
                "type": "string",
                "enum": [*observation.permitted_tools, "abstain"],
            },
        }
        required_arguments = ["tool"]
        if len(observation.permitted_tools) == 1:
            expected_fields = _ARGUMENT_FIELDS_FOR_TOOL.get(observation.permitted_tools[0], {})
            argument_properties.update({key: dict(value) for key, value in expected_fields.items()})
            required_arguments.extend(expected_fields)
            if observation.permitted_tools[0] == "propose_action":
                visible_events = observation.to_dict()["visible_events"]
                declarations = [
                    event for event in visible_events
                    if event.get("source") == "tool_declaration"
                    and isinstance(event.get("tool"), str)
                ]
                if declarations:
                    argument_properties["action_tool"] = {
                        "type": "string",
                        "enum": [event["tool"] for event in declarations],
                    }
                    parameter_schema = declarations[0].get("parameters_schema")
                    if isinstance(parameter_schema, Mapping):
                        argument_properties["parameters"] = dict(parameter_schema)
            elif observation.permitted_tools[0] == "set_target":
                approved_plans = [
                    event for event in observation.to_dict()["visible_events"]
                    if event.get("source") == "planner_proposal"
                    and event.get("certificate_verified") is True
                    and isinstance(event.get("parameters"), Mapping)
                ]
                if len(approved_plans) == 1:
                    argument_properties["parameters"] = {
                        "const": dict(approved_plans[0]["parameters"]),
                    }
        visible_versions: set[tuple[str, int]] = set()
        for event in observation.visible_events:
            memory_id, version = event.get("memory_id"), event.get("version")
            if (isinstance(memory_id, str) and isinstance(version, int)
                    and not isinstance(version, bool) and version >= 0):
                visible_versions.add((memory_id, version))
            event_versions = event.get("evidence_versions")
            if isinstance(event_versions, (list, tuple)):
                for pair in event_versions:
                    if (isinstance(pair, (list, tuple)) and len(pair) == 2
                            and isinstance(pair[0], str) and isinstance(pair[1], int)
                            and not isinstance(pair[1], bool) and pair[1] >= 0):
                        visible_versions.add((pair[0], pair[1]))
        exact_versions = [list(pair) for pair in sorted(visible_versions)]
        schema: dict[str, Any] = {
            "type": "object",
            "required": ["schema_id", "task_id", "actor_id", "step_id", "intent",
                         "arguments", "evidence_versions"],
            "additionalProperties": False,
            "properties": {
                "schema_id": {"const": SCHEMA_ID},
                "task_id": {"const": observation.task_id},
                "actor_id": {"const": self.actor_id},
                "step_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "intent": {"type": "string", "enum": allowed_intents},
                "arguments": {
                    "type": "object",
                    "required": required_arguments,
                    "properties": argument_properties,
                },
                "evidence_versions": {"type": "array", "const": exact_versions},
            },
        }
        metadata_reader = getattr(self.client, "model_metadata", None)
        if not callable(metadata_reader):
            raise AgentOutputFailure("model_provenance_incomplete")
        self._model_metadata = MappingProxyType({})
        try:
            metadata = metadata_reader(self.model)
        except OllamaError:
            raise
        except Exception as exc:
            raise AgentOutputFailure("model_provenance_incomplete") from exc
        if not isinstance(metadata, Mapping):
            raise AgentOutputFailure("model_provenance_incomplete")
        self._model_metadata = MappingProxyType(dict(metadata))
        self._step_counter += 1
        step_material = f"{observation.task_id}:{self.actor_id}:{self._step_counter}"
        model_step_id = "mf-step-" + hashlib.sha256(
            step_material.encode("utf-8")
        ).hexdigest()[:24]
        schema["properties"]["step_id"] = {"const": model_step_id}
        self._schema_sha256 = hashlib.sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":"),
                       allow_nan=False).encode("utf-8")
        ).hexdigest()
        prior_calls = getattr(self.client, "calls", None)
        call_count = len(prior_calls) if isinstance(prior_calls, Sequence) else None
        response = self.client.chat(
            self.model,
            [
                {"role": "system", "content": _OLLAMA_AGENT_SYSTEM},
                {"role": "user", "content": observation.canonical_json()},
            ],
            temperature=self.temperature,
            top_p=self.top_p,
            seed=self.seed,
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
            schema=schema,
            think=self.think,
        )
        recorded_calls = getattr(self.client, "calls", None)
        if (call_count is not None and isinstance(recorded_calls, Sequence)
                and len(recorded_calls) > call_count):
            latest = recorded_calls[-1]
            truncated = (latest.get("truncated", False) if isinstance(latest, Mapping)
                         else getattr(latest, "truncated", False))
            if truncated:
                raise AgentOutputFailure(
                    "invalid_agent_step", "Ollama response reached its output token limit",
                )
        message = response.get("message") if isinstance(response, Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str):
            raise AgentOutputFailure("invalid_json")
        def reject_constant(value: str) -> None:
            raise ValueError(f"invalid JSON constant: {value}")

        try:
            json.loads(content, parse_constant=reject_constant)
        except (json.JSONDecodeError, RecursionError, ValueError) as exc:
            raise AgentOutputFailure("invalid_json") from exc
        try:
            step = AgentStep.from_json(content)
        except (TypeError, ValueError) as exc:
            raise AgentOutputFailure("invalid_agent_step", str(exc)) from exc
        if step.task_id != observation.task_id or step.actor_id != self.actor_id:
            raise AgentOutputFailure(
                "invalid_agent_step", "Ollama AgentStep must match the current task and actor",
            )
        if step.step_id != model_step_id:
            raise AgentOutputFailure(
                "invalid_agent_step", "Ollama AgentStep must use its assigned step identifier",
            )
        if step.intent not in allowed_intents:
            attempted_tool = step.arguments.get("tool")
            raise AgentOutputFailure(
                "tool_misuse",
                "Ollama AgentStep intent must match the current tool scope",
                attempted_tool=attempted_tool if isinstance(attempted_tool, str) else None,
            )
        if any(not isinstance(memory_id, str) or not isinstance(version, int)
               or isinstance(version, bool) or version < 0
               for memory_id, version in step.evidence_versions):
            raise AgentOutputFailure("invalid_agent_step")
        if any(pair not in visible_versions for pair in step.evidence_versions):
            raise AgentOutputFailure(
                "hallucinated_evidence",
                "Ollama AgentStep evidence must match visible evidence versions",
            )
        if [list(pair) for pair in step.evidence_versions] != exact_versions:
            raise AgentOutputFailure(
                "invalid_agent_step",
                "Ollama AgentStep evidence must match visible evidence versions",
            )
        if step.intent != "abstain":
            tool = step.arguments.get("tool")
            if not isinstance(tool, str):
                raise AgentOutputFailure("invalid_agent_step")
            if tool not in observation.permitted_tools:
                raise ActorToolDenied(
                    "Ollama AgentStep must name a permitted tool", attempted_tool=tool,
                )
            if _INTENT_FOR_TOOL.get(tool) != step.intent:
                raise ActorToolDenied(
                    "Ollama AgentStep intent does not match its permitted tool",
                    attempted_tool=tool,
                )
        elif step.arguments.get("tool") != "abstain":
            raise AgentOutputFailure("invalid_agent_step")
        return step


@dataclass(frozen=True)
class ToolDeclaration:
    name: str
    roles: frozenset[ActorRole]
    required_fields: frozenset[str]
    optional_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name):
            raise ValueError("tool declaration names must be stable identifiers")
        if (not self.roles or any(not isinstance(role, ActorRole) for role in self.roles)
                or self.required_fields & self.optional_fields):
            raise ValueError("tool declarations need roles and disjoint argument fields")


TOOL_DECLARATIONS: Mapping[str, ToolDeclaration] = MappingProxyType({
    "remember_evidence": ToolDeclaration(
        "remember_evidence", frozenset({ActorRole.OBSERVER}), frozenset({"content"})),
    "retrieve_evidence": ToolDeclaration(
        "retrieve_evidence", frozenset({ActorRole.OBSERVER, ActorRole.PLANNER}),
        frozenset({"query"}), frozenset({"k"})),
    "propose_action": ToolDeclaration(
        "propose_action", frozenset({ActorRole.PLANNER}),
        frozenset({"tool", "parameters", "evidence_versions"})),
    "certify_evidence": ToolDeclaration(
        "certify_evidence", frozenset({ActorRole.EXECUTOR}),
        frozenset({"claim", "evidence_versions"})),
    "set_target": ToolDeclaration(
        "set_target", frozenset({ActorRole.EXECUTOR}), frozenset({"value"})),
})


@dataclass(frozen=True)
class PlannedAction:
    task_id: str
    planner_id: str
    tool: str
    parameters: Mapping[str, Any]
    evidence_versions: tuple[tuple[str, int], ...]
    claim: str
    proposal: AgentStep


class _OutcomeActor:
    ROLE: ActorRole

    def __init__(self, session: Session, observation: AgentObservation) -> None:
        if not isinstance(observation, AgentObservation):
            raise TypeError("actors accept only a typed AgentObservation")
        principal = session.principal()
        self._session = session
        self.observation = observation
        self._actor_id = principal.agent_id
        self._tenant_id = principal.tenant_id
        self._steps: list[AgentStep] = []

    @property
    def actor_id(self) -> str:
        return self._actor_id

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    @property
    def steps(self) -> tuple[AgentStep, ...]:
        return tuple(self._steps)

    def require_tool(self, name: str, arguments: Mapping[str, Any]) -> ToolDeclaration:
        declaration = TOOL_DECLARATIONS.get(name)
        if (declaration is None or self.ROLE not in declaration.roles
                or name not in self.observation.permitted_tools):
            raise ActorToolDenied(f"{self.ROLE.value} may not call {name}")
        keys = set(arguments)
        if (not declaration.required_fields <= keys
                or keys - declaration.required_fields - declaration.optional_fields):
            raise ActorToolDenied(f"arguments do not match the declaration for {name}")
        return declaration

    def _step(
        self,
        intent: str,
        arguments: Mapping[str, Any],
        evidence_versions: Sequence[tuple[str, int]] = (),
    ) -> AgentStep:
        step = AgentStep(
            task_id=self.observation.task_id,
            actor_id=self.actor_id,
            step_id=f"{self.ROLE.value}-{len(self._steps) + 1}",
            intent=intent,
            arguments=arguments,
            evidence_versions=tuple(evidence_versions),
        )
        self._steps.append(step)
        return step


class ObserverActor(_OutcomeActor):
    """Writes and re-reads observations through the Observer's own Session."""

    ROLE = ActorRole.OBSERVER

    def remember(self, content: str) -> tuple[str, AgentStep]:
        self.require_tool("remember_evidence", {"content": content})
        memory_id = self._session.remember(content, scope="team")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        step = self._step("inspect", {
            "tool": "remember_evidence", "memory_id": memory_id,
            "content_sha256": digest,
        }, ((memory_id, 1),))
        return memory_id, step

    def retrieve(self, query: str, *, k: int = 5) -> tuple[tuple[Memory, ...], AgentStep]:
        self.require_tool("retrieve_evidence", {"query": query, "k": k})
        result = self._session.retrieve(query, k=k)
        memories = tuple(result.exposed)
        versions = tuple(sorted((memory.id, memory.version) for memory in memories))
        step = self._step("retrieve", {
            "tool": "retrieve_evidence",
            "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            "exposed_count": len(memories),
        }, versions)
        return memories, step


class PlannerActor(_OutcomeActor):
    """Retrieves current evidence and turns it into a typed action proposal."""

    ROLE = ActorRole.PLANNER

    def retrieve(self, query: str, *, k: int = 5) -> tuple[tuple[Memory, ...], AgentStep]:
        self.require_tool("retrieve_evidence", {"query": query, "k": k})
        result = self._session.retrieve(query, k=k)
        memories = tuple(result.exposed)
        versions = tuple(sorted((memory.id, memory.version) for memory in memories))
        step = self._step("retrieve", {
            "tool": "retrieve_evidence",
            "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            "exposed_count": len(memories),
        }, versions)
        return memories, step

    def propose(
        self,
        tool: str,
        parameters: Mapping[str, Any],
        evidence: Sequence[Memory],
        *,
        claim: str,
    ) -> PlannedAction:
        action_declaration = TOOL_DECLARATIONS.get(tool)
        if (action_declaration is None or ActorRole.EXECUTOR not in action_declaration.roles
                or tool not in self.observation.permitted_tools):
            raise ActorToolDenied(f"task does not permit proposed tool {tool}")
        self.require_tool("propose_action", {
            "tool": tool, "parameters": dict(parameters),
            "evidence_versions": [[memory.id, memory.version] for memory in evidence],
        })
        action_declaration = TOOL_DECLARATIONS[tool]
        action_declaration_fields = set(parameters)
        if (not action_declaration.required_fields <= action_declaration_fields
                or action_declaration_fields - action_declaration.required_fields
                - action_declaration.optional_fields):
            raise ActorToolDenied(f"parameters do not match the declaration for {tool}")
        versions = tuple(sorted((memory.id, memory.version) for memory in evidence))
        if not versions:
            raise ValueError("a protected action proposal must cite evidence")
        step = self._step("propose", {
            "tool": tool,
            "parameters": dict(parameters),
            "evidence_count": len(versions),
            "claim_sha256": hashlib.sha256(claim.encode("utf-8")).hexdigest(),
        }, versions)
        frozen_parameters = step.arguments["parameters"]
        return PlannedAction(
            task_id=self.observation.task_id,
            planner_id=self.actor_id,
            tool=tool,
            parameters=frozen_parameters,
            evidence_versions=versions,
            claim=claim,
            proposal=step,
        )


class ExecutorActor(_OutcomeActor):
    """Revalidates the plan evidence, certifies it, then delegates to ActionGate."""

    ROLE = ActorRole.EXECUTOR

    def certify(self, plan: PlannedAction) -> EvidenceCertificate:
        if plan.task_id != self.observation.task_id:
            raise ValueError("plan belongs to another task")
        self.require_tool("certify_evidence", {
            "claim": plan.claim,
            "evidence_versions": [[memory_id, version]
                                  for memory_id, version in plan.evidence_versions],
        })
        for memory_id, version in plan.evidence_versions:
            current = self._session.use(memory_id, risk=RiskLevel.HIGH)
            if (not current.usable or current.memory is None
                    or current.memory.version != version):
                raise EvidenceVersionChanged("planned evidence is no longer current and usable")
        certificate = self._session.certify(
            plan.claim, [memory_id for memory_id, _ in plan.evidence_versions])
        verification = self._session.verify_certificate(certificate)
        if not verification.ok:
            raise EvidenceVersionChanged("certificate evidence failed current verification")
        self._step("inspect", {
            "tool": "certify_evidence", "evidence_count": len(plan.evidence_versions),
            "certificate_sha256": certificate.digest(),
        }, plan.evidence_versions)
        return certificate

    def execute(
        self,
        plan: PlannedAction,
        certificate: EvidenceCertificate,
        gate: ActionGate,
        grant: Grant | str,
        run: Callable[[str], Any],
        *,
        key: str,
    ) -> ActionExecution:
        if plan.task_id != self.observation.task_id:
            raise ValueError("plan belongs to another task")
        self.require_tool(plan.tool, plan.parameters)
        current_versions = tuple(sorted(
            (item.memory_id, item.version) for item in certificate.evidence
        ))
        if current_versions != plan.evidence_versions:
            raise EvidenceVersionChanged("certificate does not match the planned evidence versions")
        request = ActionRequest(plan.tool, plan.parameters)
        execution = gate.execute(
            plan.tool, self.actor_id, run, certificate,
            key=key, request=request, tenant_id=self.tenant_id,
            grant=grant, session=self._session,
        )
        self._step("propose", {
            "tool": plan.tool,
            "parameters": dict(plan.parameters),
            "outcome": execution.outcome,
            "ran": execution.ran,
        }, plan.evidence_versions)
        return execution


@dataclass(frozen=True)
class SequentialRealAgentTeamRun:
    """Content-safe evidence for a sequential, shared-model three-role run."""

    task_id: str
    model: str
    model_digest: str
    quantization_level: str
    actor_ids: tuple[str, str, str]
    model_steps: tuple[AgentStep, ...]
    inference_manifests: tuple[Mapping[str, Any], ...]
    execution: ActionExecution
    schema_id: str = "memory-fabric.real-agent-team-report.v1"

    @property
    def status(self) -> str:
        return "PASS" if self.execution.outcome == EXECUTED else "FAIL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "population": "REAL_AGENT",
            "task_id": self.task_id,
            "status": self.status,
            "reason": "completed_sequential_team_run" if self.status == "PASS"
            else f"effect_{self.execution.outcome}",
            "model": self.model,
            "model_digest": self.model_digest,
            "quantization_level": self.quantization_level,
            "actor_ids": list(self.actor_ids),
            "model_steps": [step.to_dict() for step in self.model_steps],
            "orchestration": "sequential",
            "memory_service_interactions": {
                "observer_writes": 1,
                "planner_retrievals": 1,
                "executor_certifications": 1,
            },
            "model_calls": len(self.inference_manifests),
            "model_tokens": sum(
                int(manifest["usage"]["total_tokens"])
                for manifest in self.inference_manifests
            ),
            "shared_model_weights": True,
            "max_concurrent_model_calls": 1,
            "inference_manifests": [dict(manifest) for manifest in self.inference_manifests],
            "effect": {"outcome": self.execution.outcome, "ran": self.execution.ran},
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                          allow_nan=False)


def run_sequential_real_agent_team(
    service: MemoryService,
    observation: AgentObservation,
    gate: ActionGate,
    run_effect: Callable[[str], Any],
    *,
    model: str = DEFAULT_MODEL,
    client: Any = None,
    key: str,
    observer_id: str = "observer",
    planner_id: str = "planner",
    executor_id: str = "executor",
    issuer: str = "host",
    temperature: float = 0.0,
    top_p: float = 0.9,
    seed: int = 0,
    num_ctx: int = 4096,
    num_predict: int = 512,
    think: bool | None = False,
) -> SequentialRealAgentTeamRun:
    """Run Observer, Planner, and Executor in sequence over one local model.

    Only typed public observations reach each model call. Host methods perform
    memory access, certification, and the protected effect between decisions.
    All three distinct sessions share one client and one model digest.
    """
    actor_ids = (observer_id, planner_id, executor_id)
    if len(set(actor_ids)) != 3:
        raise ValueError("Observer, Planner, and Executor need distinct identities")
    if not isinstance(key, str) or not key:
        raise ValueError("effect idempotency key must be non-empty")
    required_tools = {
        "remember_evidence", "retrieve_evidence", "propose_action",
        "certify_evidence", "set_target",
    }
    if not required_tools <= set(observation.permitted_tools):
        raise ValueError("team observation must permit each declared role tool")
    shared_client = client if client is not None else OllamaClient()
    created_sessions: list[Session] = []

    def actor_session(actor_id: str) -> Session:
        session = service.session(service.issue(actor_id))
        created_sessions.append(session)
        return session

    steps: list[AgentStep] = []
    manifests: list[Mapping[str, Any]] = []
    adapters: dict[str, OllamaAgentAdapter] = {}
    try:
        observer = ObserverActor(actor_session(observer_id), observation)
        planner = PlannerActor(actor_session(planner_id), observation)
        executor = ExecutorActor(actor_session(executor_id), observation)
        if len({observer.tenant_id, planner.tenant_id, executor.tenant_id}) != 1:
            raise ValueError("sequential team actors must share one tenant")
        for actor_id in actor_ids:
            adapters[actor_id] = OllamaAgentAdapter(
                actor_id, model=model, client=shared_client, temperature=temperature,
                top_p=top_p, seed=seed, num_ctx=num_ctx, num_predict=num_predict,
                think=think,
            )

        def role_observation(
            role: str,
            tools: tuple[str, ...],
            events: Sequence[Mapping[str, Any]],
            instruction: str,
        ) -> AgentObservation:
            return AgentObservation(
                task_id=observation.task_id,
                instruction=f"{role.upper()}: {observation.instruction} {instruction}",
                visible_events=tuple(events),
                permitted_tools=tools,
                budget=observation.budget,
            )

        def decide(actor_id: str, task_observation: AgentObservation) -> AgentStep:
            adapter = adapters[actor_id]
            before = len(adapter.calls)
            step = adapter.next_step(task_observation)
            calls = adapter.calls
            if len(calls) != before + 1:
                raise ValueError("each sequential agent decision must record one model call")
            steps.append(step)
            manifests.append(adapter.inference_manifest(calls[-1]))
            return step

        observer_observation = role_observation(
            "observer", ("remember_evidence",),
            observation.visible_events,
            "As Observer, record the visible measurement exactly as evidence.",
        )
        observer_step = decide(observer_id, observer_observation)
        if observer_step.intent != "inspect" or observer_step.arguments.get(
                "tool") != "remember_evidence":
            raise ActorToolDenied("Observer must choose remember_evidence")
        content = observer_step.arguments.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ActorToolDenied("Observer must provide non-empty evidence content")
        memory_id, _ = observer.remember(content)
        written_memories, _ = observer.retrieve(content, k=1)
        written_memory = next((memory for memory in written_memories
                               if memory.id == memory_id), None)
        if written_memory is None:
            raise EvidenceVersionChanged("Observer evidence was not readable after writing")
        observer_event = {
            "source": "memory_service",
            "memory_id": written_memory.id,
            "version": written_memory.version,
            "content": written_memory.content,
        }

        planner_retrieve_observation = role_observation(
            "planner", ("retrieve_evidence",),
            (observer_event,),
            "As Planner, set arguments.query to the exact content string in the visible "
            "memory event so you retrieve that evidence.",
        )
        retrieve_step = decide(planner_id, planner_retrieve_observation)
        query = retrieve_step.arguments.get("query")
        k = retrieve_step.arguments.get("k", 5)
        if (retrieve_step.intent != "retrieve" or retrieve_step.arguments.get(
                "tool") != "retrieve_evidence" or not isinstance(query, str)
                or not query.strip() or not isinstance(k, int) or isinstance(k, bool)
                or not 1 <= k <= 20):
            raise ActorToolDenied("Planner must request a bounded evidence retrieval")
        evidence, _ = planner.retrieve(query, k=k)
        if not evidence:
            raise ActorToolDenied("Planner retrieval returned no usable evidence")
        versions = tuple(sorted((memory.id, memory.version) for memory in evidence))
        evidence_events = tuple({
            "source": "retrieved_memory", "memory_id": memory.id,
            "version": memory.version, "content": memory.content,
        } for memory in evidence)

        planner_proposal_observation = role_observation(
            "planner", ("propose_action",),
            (*evidence_events, {
                "source": "tool_declaration",
                "tool": "set_target",
                "parameters_schema": {
                    "type": "object", "required": ["value"],
                    "properties": {"value": {"type": "number"}},
                },
            }),
            "As Planner, propose one action using the tool and parameters schema provided. "
            "Set claim to a concise reason and cite exact evidence_versions.",
        )
        proposal_step = decide(planner_id, planner_proposal_observation)
        action_tool = proposal_step.arguments.get("action_tool")
        parameters = proposal_step.arguments.get("parameters")
        claim = proposal_step.arguments.get("claim")
        if (proposal_step.intent != "propose"
                or proposal_step.arguments.get("tool") != "propose_action"
                or not isinstance(action_tool, str) or not isinstance(parameters, Mapping)
                or not isinstance(claim, str) or not claim.strip()
                or tuple(sorted(proposal_step.evidence_versions)) != versions):
            raise ActorToolDenied("Planner proposal must bind the retrieved evidence versions")
        plan = planner.propose(action_tool, parameters, evidence, claim=claim)

        plan_event = {
            "source": "planner_proposal", "tool": plan.tool,
            "parameters": dict(plan.parameters), "claim": plan.claim,
            "evidence_versions": [[memory_id, version]
                                  for memory_id, version in plan.evidence_versions],
        }
        executor_observation = role_observation(
            "executor", ("certify_evidence",), (plan_event,),
            "As Executor, certify this exact plan against current evidence before acting.",
        )
        certify_step = decide(executor_id, executor_observation)
        if (certify_step.intent != "inspect"
                or certify_step.arguments.get("tool") != "certify_evidence"
                or tuple(sorted(certify_step.evidence_versions)) != versions):
            raise ActorToolDenied("Executor must certify the plan's exact evidence versions")
        certificate = executor.certify(plan)
        certificate_event = {
            **plan_event,
            "certificate_verified": True,
            "certificate_sha256": certificate.digest(),
        }
        execute_observation = role_observation(
            "executor", ("set_target",), (certificate_event,),
            "As Executor, apply only the exact approved set_target parameters and cite "
            "the same evidence_versions.",
        )
        execute_step = decide(executor_id, execute_observation)
        requested_parameters = execute_step.arguments.get("parameters")
        if (execute_step.intent != "propose"
                or execute_step.arguments.get("tool") != plan.tool
                or not isinstance(requested_parameters, Mapping)
                or dict(requested_parameters) != dict(plan.parameters)
                or tuple(sorted(execute_step.evidence_versions)) != versions):
            raise ActorToolDenied("Executor request must match the exact approved plan")
        request = ActionRequest(plan.tool, plan.parameters)
        grant = gate.issue_grant(
            plan.tool, executor_id, issuer=issuer, certificate=certificate,
            request=request, tenant_id=executor.tenant_id,
        )
        execution = executor.execute(
            plan, certificate, gate, grant, run_effect, key=key,
        )
        model_metadata = [manifest["model"] for manifest in manifests]
        names = {item.get("name") for item in model_metadata if isinstance(item, Mapping)}
        digests = {item.get("digest") for item in model_metadata if isinstance(item, Mapping)}
        quantizations = {
            item.get("quantization_level") for item in model_metadata
            if isinstance(item, Mapping)
        }
        if len(names) != 1 or len(digests) != 1 or len(quantizations) != 1:
            raise ValueError("sequential actors did not share one pinned model digest")
        pinned_name = next(iter(names))
        pinned_digest = next(iter(digests))
        pinned_quantization = next(iter(quantizations))
        if (not isinstance(pinned_name, str) or not pinned_name
                or not isinstance(pinned_digest, str) or not pinned_digest
                or not isinstance(pinned_quantization, str) or not pinned_quantization):
            raise ValueError("sequential model identity or quantization metadata is incomplete")
        if len({step.actor_id for step in steps}) != 3:
            raise ValueError("sequential model steps must come from three actor identities")
        return SequentialRealAgentTeamRun(
            task_id=observation.task_id,
            model=pinned_name,
            model_digest=pinned_digest,
            quantization_level=pinned_quantization,
            actor_ids=actor_ids,
            model_steps=tuple(steps),
            inference_manifests=tuple(manifests),
            execution=execution,
        )
    finally:
        # Sessions are owned by MemoryService and do not expose a close method.
        created_sessions.clear()
