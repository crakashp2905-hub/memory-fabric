"""Versioned data-only simulated worlds for deterministic replay continuations."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass

from .state import Observation
from .certificates import ExplanationStatus
from .types import CDMError, ToolObservation, digest_json


@dataclass(frozen=True)
class WorldTransition:
    """One frozen state/action transition and its simulated observation."""
    state: str
    action: str
    next_state: str
    variable: str
    value: bool

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value
               for value in (self.state, self.action, self.next_state, self.variable)):
            raise CDMError("world transition identifiers must be non-empty strings")
        if type(self.value) is not bool:
            raise CDMError("world observation value must be boolean")


@dataclass(frozen=True)
class EnvironmentResult:
    simulator_id: str
    simulator_version: str
    next_state: str
    observation: Observation
    tool_observation: ToolObservation


@dataclass(frozen=True)
class ContinuationResult:
    status: ExplanationStatus
    continuation_kind: str
    simulated: EnvironmentResult | None = None


@dataclass(frozen=True)
class DeterministicEnvironment:
    """Pure lookup simulator; no callback, process, file, socket or real tool."""
    simulator_id: str
    version: str
    actor_id: str
    tool_id: str
    transitions: tuple[WorldTransition, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value
               for value in (self.simulator_id, self.version, self.actor_id, self.tool_id)):
            raise CDMError("simulator identity and version are required")
        if (type(self.transitions) is not tuple or not self.transitions
                or any(type(item) is not WorldTransition for item in self.transitions)):
            raise CDMError("simulator requires a non-empty immutable transition table")
        keys = [(item.state, item.action) for item in self.transitions]
        if len(set(keys)) != len(keys):
            raise CDMError("simulator transition keys must be unique")

    @property
    def schema_digest(self) -> str:
        return digest_json({"schema": "memory-fabric-deterministic-environment-v1",
            "simulator_id": self.simulator_id, "version": self.version,
            "transitions": [item.__dict__ for item in self.transitions]})

    def step(self, state: str, action: str, *, sequence: int) -> EnvironmentResult:
        if not isinstance(state, str) or not state or not isinstance(action, str) or not action:
            raise CDMError("simulated state and action are required")
        if type(sequence) is not int or sequence < 0:
            raise CDMError("simulated sequence must be a non-negative integer")
        transition = next((item for item in self.transitions
                           if item.state == state and item.action == action), None)
        if transition is None:
            raise CDMError("simulator has no registered transition for this state/action")
        observation_id = "sim-" + digest_json({"simulator": self.simulator_id,
            "version": self.version, "state": state, "action": action,
            "sequence": sequence})[:32]
        observation = Observation(observation_id, transition.variable, transition.value,
            f"sim:{self.simulator_id}:{self.version}", sequence,
            kind="simulated_endogenous")
        tool = ToolObservation(self.actor_id, self.tool_id, self.schema_digest,
            digest_json({"state": state, "action": action, "sequence": sequence}),
            digest_json({"next_state": transition.next_state,
                "observation": observation.__dict__}), "simulated_endogenous")
        return EnvironmentResult(self.simulator_id, self.version, transition.next_state,
                                 observation, tool)


def battery_sensor_environment() -> DeterministicEnvironment:
    """Synthetic cooling/diagnostic world; no physical battery integration."""
    return DeterministicEnvironment("synthetic-battery-world", "v1",
        "cdm-battery-agent", "cdm-battery-sensor", (
            WorldTransition("nominal", "inspect", "checked", "overheat", False),
            WorldTransition("cooling-failure", "inspect", "overheated", "overheat", True),
            WorldTransition("checked", "diagnose", "diagnosed-normal", "diagnosis_alarm", False),
            WorldTransition("overheated", "diagnose", "diagnosed-overheat", "diagnosis_alarm", True)))


def continue_counterfactual(recorded_action: str, hypothetical_action: str, *,
        dependent_later_observation: bool, state: str, sequence: int,
        simulator: DeterministicEnvironment | None = None) -> ContinuationResult:
    """Regenerate dependent future observations or refuse undefined continuation."""
    if (not isinstance(recorded_action, str) or not recorded_action
            or not isinstance(hypothetical_action, str) or not hypothetical_action
            or type(dependent_later_observation) is not bool):
        raise CDMError("continuation actions and dependency flag are required")
    if not dependent_later_observation or recorded_action == hypothetical_action:
        return ContinuationResult(ExplanationStatus.EXACT, "unchanged_or_independent")
    if simulator is None:
        return ContinuationResult(ExplanationStatus.UNDEFINED_CONTINUATION,
                                  "altered_action_without_world_simulator")
    simulated = simulator.step(state, hypothetical_action, sequence=sequence)
    return ContinuationResult(ExplanationStatus.EXACT, "regenerated_by_versioned_simulator",
                              simulated)
