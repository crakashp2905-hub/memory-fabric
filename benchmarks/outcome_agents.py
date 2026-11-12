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

from memory_fabric.adapters.ollama import DEFAULT_MODEL, CallRecord, OllamaClient
from memory_fabric.actions import ActionExecution, ActionGate, ActionRequest, Grant
from memory_fabric.agent_outcomes import AgentObservation, AgentStep
from memory_fabric.agent_outcomes.observations import SCHEMA_ID
from memory_fabric.certificates import EvidenceCertificate
from memory_fabric.enforcement import RiskLevel
from memory_fabric.model import Memory
from memory_fabric.service import Session


class ActorRole(StrEnum):
    OBSERVER = "observer"
    PLANNER = "planner"
    EXECUTOR = "executor"


class ActorToolDenied(ValueError):
    """A role or task observation does not permit the requested tool."""


class EvidenceVersionChanged(ValueError):
    """The evidence changed or lost current authorization after planning."""


class AgentAdapter(Protocol):
    """A decision source that receives only an actor-visible observation."""

    def __call__(self, observation: AgentObservation) -> AgentStep: ...


_OLLAMA_AGENT_SYSTEM = (
    "You are one role in a bounded task agent. The user message contains the only "
    "task observation you may use. Return exactly one JSON AgentStep matching the "
    "provided schema. Copy its task_id and use your assigned actor_id. Set "
    "arguments.tool to one of the permitted tools or `abstain`. Set evidence_versions "
    "to [] unless exact evidence IDs and non-negative integer versions appear in the "
    "observation; never invent evidence or versions. Do not add fields."
)


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
            },
            "prompt_sha256": call.prompt_sha256,
            "system_prompt_sha256": hashlib.sha256(
                _OLLAMA_AGENT_SYSTEM.encode("utf-8")
            ).hexdigest(),
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
        schema = {
            "type": "object",
            "required": ["schema_id", "task_id", "actor_id", "step_id", "intent",
                         "arguments", "evidence_versions"],
            "additionalProperties": False,
            "properties": {
                "schema_id": {"const": SCHEMA_ID},
                "task_id": {"const": observation.task_id},
                "actor_id": {"const": self.actor_id},
                "step_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "intent": {"type": "string", "enum": [
                    "retrieve", "inspect", "request_refresh", "ask", "propose", "abstain",
                ]},
                "arguments": {
                    "type": "object",
                    "required": ["tool"],
                    "properties": {"tool": {
                        "type": "string",
                        "enum": [*observation.permitted_tools, "abstain"],
                    }},
                },
                "evidence_versions": {"type": "array", "items": {
                    "type": "array", "minItems": 2, "maxItems": 2,
                    "prefixItems": [
                        {"type": "string", "minLength": 1, "maxLength": 128},
                        {"type": "integer", "minimum": 0},
                    ],
                }},
            },
        }
        metadata_reader = getattr(self.client, "model_metadata", None)
        if not callable(metadata_reader):
            raise ValueError("Ollama client must provide model metadata for a qualified run")
        metadata = metadata_reader(self.model)
        if not isinstance(metadata, Mapping):
            raise ValueError("Ollama model metadata must be an object")
        self._model_metadata = MappingProxyType(dict(metadata))
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
                raise ValueError("Ollama response reached its output token limit")
        message = response.get("message") if isinstance(response, Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str):
            raise ValueError("Ollama response must contain JSON assistant content")
        step = AgentStep.from_json(content)
        if step.task_id != observation.task_id or step.actor_id != self.actor_id:
            raise ValueError("Ollama AgentStep must match the current task and actor")
        if step.intent != "abstain":
            tool = step.arguments.get("tool")
            if not isinstance(tool, str) or tool not in observation.permitted_tools:
                raise ActorToolDenied("Ollama AgentStep must name a permitted tool")
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
