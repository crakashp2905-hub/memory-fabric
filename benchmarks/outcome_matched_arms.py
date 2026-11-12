"""Comparability contracts for paired real-agent memory arms.

This module does not score outcomes or claim efficacy. It freezes the task,
prompt frame, model checkpoint, decoding settings, and output budget before a
paired arm runner executes the two memory interventions.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any

from memory_fabric.agent_outcomes import AgentObservation

from .outcome_agents import OLLAMA_AGENT_SYSTEM_SHA256

_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_DIGEST = re.compile(r"(?:sha256:)?[0-9a-f]{64}")


def _sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class MatchedAgentArm:
    """One arm's actor-visible input and fixed inference controls.

    Memory intervention events are marked by ``source`` and must form a
    suffix of ``visible_events``. This gives paired arms the same task and
    world framing while allowing their memory evidence to differ.
    """

    arm_id: str
    intervention_id: str
    actor_id: str
    observation: AgentObservation
    model: str
    model_digest: str
    output_token_budget: int
    seed: int
    temperature: float = 0.0
    top_p: float = 0.9
    num_ctx: int = 4096
    think: bool | None = False
    system_prompt_sha256: str = OLLAMA_AGENT_SYSTEM_SHA256

    def __post_init__(self) -> None:
        for label, value in (("arm_id", self.arm_id),
                             ("intervention_id", self.intervention_id)):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a stable lowercase identifier")
        if (not isinstance(self.actor_id, str)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", self.actor_id) is None):
            raise ValueError("actor_id must be a stable identifier")
        if not isinstance(self.observation, AgentObservation):
            raise TypeError("arm observation must be an AgentObservation")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty name")
        if not isinstance(self.model_digest, str) or _DIGEST.fullmatch(self.model_digest) is None:
            raise ValueError("model_digest must be a pinned SHA-256 digest")
        if (not isinstance(self.output_token_budget, int)
                or isinstance(self.output_token_budget, bool)
                or not 1 <= self.output_token_budget <= 16_000):
            raise ValueError("output_token_budget must be between 1 and 16000")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) \
                or not 0 <= self.seed <= 0xffffffff:
            raise ValueError("seed must be a 32-bit non-negative integer")
        if (not isinstance(self.temperature, (int, float))
                or isinstance(self.temperature, bool)
                or not math.isfinite(self.temperature) or not 0 <= self.temperature <= 2):
            raise ValueError("temperature must be finite and between 0 and 2")
        if (not isinstance(self.top_p, (int, float)) or isinstance(self.top_p, bool)
                or not math.isfinite(self.top_p) or not 0 < self.top_p <= 1):
            raise ValueError("top_p must be finite and between 0 and 1")
        if (not isinstance(self.num_ctx, int) or isinstance(self.num_ctx, bool)
                or not 1 <= self.num_ctx <= 1_048_576):
            raise ValueError("num_ctx must be between 1 and 1048576")
        if self.think is not None and not isinstance(self.think, bool):
            raise ValueError("think must be a boolean or None")
        if (not isinstance(self.system_prompt_sha256, str)
                or _DIGEST.fullmatch(self.system_prompt_sha256) is None
                or self.system_prompt_sha256 != OLLAMA_AGENT_SYSTEM_SHA256):
            raise ValueError("system prompt hash must match the pinned Ollama agent prompt")

    @property
    def prompt_frame_sha256(self) -> str:
        """Hash the shared task framing without memory evidence content."""
        return _sha256({
            "actor_id": self.actor_id,
            "task_id": self.observation.task_id,
            "instruction": self.observation.instruction,
            "permitted_tools": list(self.observation.permitted_tools),
            "budget": self.observation.to_dict()["budget"],
            "system_prompt_sha256": self.system_prompt_sha256,
        })

    @property
    def observation_sha256(self) -> str:
        return hashlib.sha256(self.observation.canonical_json().encode("utf-8")).hexdigest()

    def inference_controls(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "model": self.model,
            "model_digest": self.model_digest,
            "output_token_budget": self.output_token_budget,
            "seed": self.seed,
            "temperature": float(self.temperature),
            "top_p": float(self.top_p),
            "num_ctx": self.num_ctx,
            "think": self.think,
            "system_prompt_sha256": self.system_prompt_sha256,
        }


@dataclass(frozen=True)
class PairedAgentArmDesign:
    """A validated pair where memory input is the declared difference."""

    baseline: MatchedAgentArm
    treatment: MatchedAgentArm
    memory_event_sources: tuple[str, ...] = ("memory_service",)
    schema_id: str = "memory-fabric.matched-agent-arm-pair.v1"

    def __post_init__(self) -> None:
        if not isinstance(self.baseline, MatchedAgentArm) \
                or not isinstance(self.treatment, MatchedAgentArm):
            raise TypeError("paired arms must use MatchedAgentArm values")
        if self.baseline.arm_id == self.treatment.arm_id:
            raise ValueError("paired arms need distinct arm identifiers")
        if self.baseline.intervention_id == self.treatment.intervention_id:
            raise ValueError("paired arms need distinct intervention identifiers")
        if (not isinstance(self.memory_event_sources, tuple)
                or not self.memory_event_sources
                or any(not isinstance(source, str) or not source
                       for source in self.memory_event_sources)
                or len(set(self.memory_event_sources)) != len(self.memory_event_sources)):
            raise ValueError("memory_event_sources must be a non-empty unique tuple")
        if self.schema_id != "memory-fabric.matched-agent-arm-pair.v1":
            raise ValueError("unsupported paired-arm schema")
        self._validate_pair()

    def _partition_events(self, arm: MatchedAgentArm) -> tuple[list[dict[str, Any]],
                                                               list[dict[str, Any]]]:
        world_events: list[dict[str, Any]] = []
        memory_events: list[dict[str, Any]] = []
        memory_started = False
        sources = set(self.memory_event_sources)
        for event in arm.observation.to_dict()["visible_events"]:
            copied = dict(event)
            if copied.get("source") in sources:
                memory_started = True
                memory_events.append(copied)
            else:
                if memory_started:
                    raise ValueError("memory intervention events must follow shared world events")
                world_events.append(copied)
        return world_events, memory_events

    def _validate_pair(self) -> None:
        left, right = self.baseline, self.treatment
        if left.observation.task_id != right.observation.task_id:
            raise ValueError("paired arms must use the same task identifier")
        if left.observation.instruction != right.observation.instruction:
            raise ValueError("paired arms must use identical task prompt framing")
        if left.observation.permitted_tools != right.observation.permitted_tools:
            raise ValueError("paired arms must use identical permitted tools")
        if left.observation.to_dict()["budget"] != right.observation.to_dict()["budget"]:
            raise ValueError("paired arms must use identical task budgets")
        if left.inference_controls() != right.inference_controls():
            raise ValueError("paired arms must use identical model and inference controls")
        left_world, left_memory = self._partition_events(left)
        right_world, right_memory = self._partition_events(right)
        if left_world != right_world:
            raise ValueError("paired arms may differ only in declared memory intervention events")
        if not left_memory or not right_memory or left_memory == right_memory:
            raise ValueError("paired arms must supply different declared memory evidence")

    def to_dict(self) -> dict[str, Any]:
        left_world, left_memory = self._partition_events(self.baseline)
        right_world, right_memory = self._partition_events(self.treatment)
        return {
            "schema_id": self.schema_id,
            "task_id": self.baseline.observation.task_id,
            "status": "PAIRED_CONTROLS_VALIDATED",
            "arms": [
                {
                    "arm_id": arm.arm_id,
                    "intervention_id": arm.intervention_id,
                    "observation_sha256": arm.observation_sha256,
                    "memory_input_sha256": _sha256(memory_events),
                    "memory_event_count": len(memory_events),
                    "prompt_frame_sha256": arm.prompt_frame_sha256,
                    "inference_controls": arm.inference_controls(),
                }
                for arm, memory_events in ((self.baseline, left_memory),
                                           (self.treatment, right_memory))
            ],
            "shared_world_context_sha256": _sha256(left_world),
            "prompt_framing_controlled": (
                self.baseline.prompt_frame_sha256 == self.treatment.prompt_frame_sha256
            ),
            "output_token_budgets_equal": (
                self.baseline.output_token_budget == self.treatment.output_token_budget
            ),
            "only_declared_difference": "memory_intervention_events",
            "memory_event_sources": list(self.memory_event_sources),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                          allow_nan=False)


def pair_agent_arms(
    baseline: MatchedAgentArm,
    treatment: MatchedAgentArm,
    *,
    memory_event_sources: tuple[str, ...] = ("memory_service",),
) -> PairedAgentArmDesign:
    """Validate pair parity before a benchmark makes either model call."""
    return PairedAgentArmDesign(
        baseline=baseline,
        treatment=treatment,
        memory_event_sources=memory_event_sources,
    )
