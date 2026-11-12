"""Truth-free scripted actor roles for agent-outcome evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from memory_fabric.agent_outcomes.boundary import AgentPort
from memory_fabric.agent_outcomes.observations import AgentObservation, AgentStep
from memory_fabric.service import Session


class ActorRole(StrEnum):
    OBSERVER = "OBSERVER"
    PLANNER = "PLANNER"
    EXECUTOR = "EXECUTOR"


@dataclass(frozen=True)
class ToolDeclaration:
    name: str
    role: ActorRole
    argument_types: Mapping[str, type]
    protected: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("tool name must be non-empty")
        object.__setattr__(self, "role", ActorRole(self.role))
        if any(not isinstance(key, str) or not key or not isinstance(value, type)
               for key, value in self.argument_types.items()):
            raise ValueError("tool argument declarations must map names to types")
        if type(self.protected) is not bool:
            raise ValueError("protected must be boolean")
        object.__setattr__(self, "argument_types", MappingProxyType(dict(self.argument_types)))

    def validate_arguments(self, arguments: Mapping[str, Any]) -> None:
        if not isinstance(arguments, Mapping) or set(arguments) != set(self.argument_types):
            raise ValueError(f"arguments do not match tool declaration {self.name}")
        for name, expected_type in self.argument_types.items():
            value = arguments[name]
            if expected_type is int and isinstance(value, bool):
                raise ValueError(f"argument {name} has the wrong type")
            if not isinstance(value, expected_type):
                raise ValueError(f"argument {name} has the wrong type")


@dataclass
class _Actor:
    session: Session
    role: ActorRole
    declarations: tuple[ToolDeclaration, ...]
    steps: list[AgentStep] = field(default_factory=list, init=False)
    _counter: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.session, Session):
            raise TypeError("actors require a verified Memory Fabric Session")
        if any(not isinstance(item, ToolDeclaration) or item.role is not self.role
               for item in self.declarations):
            raise ValueError("each actor may hold declarations for its own role only")
        if len({item.name for item in self.declarations}) != len(self.declarations):
            raise ValueError("tool declarations must have unique names")
        self.declarations = tuple(self.declarations)

    @property
    def actor_id(self) -> str:
        # Session.agent_id is credential-bound; principal() refreshes validity on demand.
        self.session.principal()
        return self.session.agent_id

    @property
    def permitted_tools(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.declarations)

    def _record(self, task_id: str, intent: str, arguments: dict[str, Any],
                evidence_versions: tuple[tuple[str, int], ...] = ()) -> AgentStep:
        self._counter += 1
        step = AgentStep(task_id, self.actor_id,
                         f"{task_id}:{self.role.value.lower()}:{self._counter}",
                         intent, arguments, evidence_versions)
        AgentPort(
            AgentObservation(task_id, "Actor step validation.", (), self.permitted_tools, {}),
            self.actor_id,
        ).submit(step)
        self.steps.append(step)
        return step


class ObserverActor(_Actor):
    """Retrieves visible evidence through its own Session and records each use."""

    def __init__(self, session: Session, declarations: tuple[ToolDeclaration, ...]) -> None:
        super().__init__(session, ActorRole.OBSERVER, declarations)

    def observe(
        self,
        *,
        task_id: str,
        instruction: str,
        query: str,
        permitted_tools: tuple[str, ...],
        budget: Mapping[str, int],
        k: int = 5,
    ) -> AgentObservation:
        declaration = next((item for item in self.declarations if item.name == "retrieve"), None)
        if declaration is None:
            raise PermissionError("observer has no retrieve declaration")
        declaration.validate_arguments({"query": query})
        result = self.session.retrieve(query, k=k)
        events = tuple({"memory_id": memory.id, "version": memory.version,
                        "content": memory.content} for memory in result.exposed)
        observation = AgentObservation(task_id, instruction, events, permitted_tools,
                                       dict(budget))
        evidence = tuple((memory.id, memory.version) for memory in result.exposed)
        self._record(task_id, "retrieve", {"query": query, "returned": len(events)}, evidence)
        return observation


class PlannerActor(_Actor):
    """Turns one observation into a bounded, identity-bound proposal or abstention."""

    def __init__(self, session: Session, declarations: tuple[ToolDeclaration, ...]) -> None:
        super().__init__(session, ActorRole.PLANNER, declarations)

    def plan(self, observation: AgentObservation, *, tool: str | None,
             arguments: Mapping[str, Any] | None = None) -> AgentStep:
        if not isinstance(observation, AgentObservation):
            raise TypeError("planner input must be an AgentObservation")
        event_ids = {item.get("memory_id"): item.get("version")
                     for item in observation.visible_events
                     if isinstance(item.get("memory_id"), str)
                     and isinstance(item.get("version"), int)}
        versions = tuple(sorted(event_ids.items()))
        if tool is None:
            step = self._record(observation.task_id, "abstain", {"reason": "no_safe_plan"}, versions)
            return AgentPort(observation, self.actor_id).submit(step)
        if tool not in observation.permitted_tools:
            raise PermissionError("planner proposed a tool outside the observation grant")
        declaration = next((item for item in self.declarations if item.name == "propose"), None)
        if declaration is None:
            raise PermissionError("planner has no propose declaration")
        payload = {"tool": tool, **dict(arguments or {})}
        declaration.validate_arguments(payload)
        step = self._record(observation.task_id, "propose", payload, versions)
        return AgentPort(observation, self.actor_id).submit(step)


class ExecutorActor(_Actor):
    """Checks a planner proposal against its own tool declarations and identity."""

    def __init__(self, session: Session, declarations: tuple[ToolDeclaration, ...]) -> None:
        super().__init__(session, ActorRole.EXECUTOR, declarations)

    def accept(self, observation: AgentObservation, plan: AgentStep) -> AgentStep:
        AgentPort(observation, plan.actor_id).submit(plan)
        if plan.intent != "propose":
            raise ValueError("executor accepts only action proposals")
        tool = plan.arguments.get("tool")
        declaration = next((item for item in self.declarations if item.name == tool), None)
        if declaration is None or tool not in observation.permitted_tools:
            raise PermissionError("executor does not hold the proposed tool declaration")
        arguments = {name: value for name, value in plan.arguments.items() if name != "tool"}
        declaration.validate_arguments(arguments)
        accepted = self._record(plan.task_id, "propose", dict(plan.arguments),
                                plan.evidence_versions)
        return AgentPort(observation, self.actor_id).submit(accepted)
