"""Typed, scripted Observer/Planner/Executor roles for offline experiments.

These actors receive only an ``AgentObservation`` and their own authenticated
``Session``. Tool declarations restrict each role; the host retains grant
issuance and every protected effect still passes through ``ActionGate``.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from memory_fabric.actions import ActionExecution, ActionGate, ActionRequest, Grant
from memory_fabric.agent_outcomes import AgentObservation, AgentStep
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
