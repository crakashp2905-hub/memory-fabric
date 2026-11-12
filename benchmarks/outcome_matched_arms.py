"""Comparability contracts for paired real-agent memory and replay arms.

It freezes task and resource parity, then reports descriptive matched outcomes.
It does not claim confirmatory efficacy or promotion.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from memory_fabric.agent_outcomes import AgentObservation

from .outcome_agents import OLLAMA_AGENT_SYSTEM_SHA256

_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_DIGEST = re.compile(r"(?:sha256:)?[0-9a-f]{64}")


@dataclass(frozen=True)
class AgentArmSpecification:
    """Preregistered identity for one arm in the matched A0–A7 design."""

    arm_id: str
    name: str
    memory_policy: str
    recovery_policy: str
    cdm_enabled: bool | None
    evaluator_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "name": self.name,
            "memory_policy": self.memory_policy,
            "recovery_policy": self.recovery_policy,
            "cdm_enabled": self.cdm_enabled,
            "evaluator_only": self.evaluator_only,
        }


CANONICAL_AGENT_ARM_SPECS: tuple[AgentArmSpecification, ...] = (
    AgentArmSpecification("A0", "no_memory", "none", "same_legal_tools", False),
    AgentArmSpecification("A1", "local_only", "private_per_agent", "same_legal_tools", False),
    AgentArmSpecification(
        "A2", "pooled_shared", "pooled_without_correction_gating", "same_legal_tools", False,
    ),
    AgentArmSpecification(
        "A3", "pooled_shared_plus_recovery", "pooled", "matched_recovery_budget", False,
    ),
    AgentArmSpecification(
        "A4", "memory_fabric", "governed", "current_abstention_policy", False,
    ),
    AgentArmSpecification(
        "A5", "memory_fabric_recovery", "governed", "explicit_recovery_replan", False,
    ),
    AgentArmSpecification(
        "A6", "memory_fabric_recovery_cdm", "governed", "explicit_recovery_replan", True,
    ),
    AgentArmSpecification(
        "A7", "oracle", "sealed_true_world", "idealized_legal_completion", None, True,
    ),
)
_ARM_SPECS_BY_ID = {spec.arm_id: spec for spec in CANONICAL_AGENT_ARM_SPECS}
RETRIEVAL_BASELINE_NAMES = {
    "R_RECENCY": "recency",
    "R_LEXICAL": "lexical",
    "R_FULL_CONTEXT": "full_context",
    "R_GOVERNED": "current_governed_memory",
}
REPLAY_ABLATION_STRATEGIES = (
    "random", "recency", "exact_dependence", "leave_one_out", "shapley",
    "budgeted_replay",
)
_RETRIEVAL_RESOURCE_KEYS = frozenset({
    "retrieval_calls", "retrieved_items", "context_tokens",
    "model_calls", "model_tokens", "output_tokens",
})


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
    observation_privileges_sha256: str | None = None
    evaluator_grading_sha256: str | None = None
    memory_policy: str | None = None
    recovery_policy: str | None = None
    cdm_enabled: bool | None = None
    cdm_work_budget: int = 0

    def __post_init__(self) -> None:
        for label, value in (("arm_id", self.arm_id),
                             ("intervention_id", self.intervention_id)):
            if not isinstance(value, str):
                raise ValueError(f"{label} must be a stable lowercase identifier")
            is_canonical_arm_id = label == "arm_id" and value in _ARM_SPECS_BY_ID
            if not is_canonical_arm_id and _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a stable lowercase identifier")
        arm_spec = _ARM_SPECS_BY_ID.get(self.arm_id)
        if arm_spec is not None:
            if arm_spec.evaluator_only:
                raise ValueError("A7 oracle is evaluator-only and cannot be an actor arm")
            if self.intervention_id != arm_spec.name:
                raise ValueError("canonical arm ID must use its preregistered intervention name")
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
        for label, digest in (
            ("observation_privileges_sha256", self.observation_privileges_sha256),
            ("evaluator_grading_sha256", self.evaluator_grading_sha256),
        ):
            if digest is not None and (
                not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None
            ):
                raise ValueError(f"{label} must be a SHA-256 digest when provided")
        for label, optional_value in (("memory_policy", self.memory_policy),
                                      ("recovery_policy", self.recovery_policy)):
            if (optional_value is not None
                    and (not isinstance(optional_value, str) or not optional_value.strip())):
                raise ValueError(f"{label} must be a non-empty string when provided")
        if self.cdm_enabled is not None and not isinstance(self.cdm_enabled, bool):
            raise ValueError("cdm_enabled must be a boolean when provided")
        if (not isinstance(self.cdm_work_budget, int) or isinstance(self.cdm_work_budget, bool)
                or not 0 <= self.cdm_work_budget <= 1_000_000):
            raise ValueError("cdm_work_budget must be between 0 and 1000000")

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


def _partition_arm_events(
    arm: MatchedAgentArm, memory_event_sources: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    world_events: list[dict[str, Any]] = []
    memory_events: list[dict[str, Any]] = []
    memory_started = False
    sources = set(memory_event_sources)
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
        return _partition_arm_events(arm, self.memory_event_sources)

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
        if left.observation_privileges_sha256 != right.observation_privileges_sha256:
            raise ValueError("paired arms must use identical observation privileges")
        if left.evaluator_grading_sha256 != right.evaluator_grading_sha256:
            raise ValueError("paired arms must use identical evaluator grading")
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
                    "observation_privileges_sha256": arm.observation_privileges_sha256,
                    "evaluator_grading_sha256": arm.evaluator_grading_sha256,
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


def match_arm_outcomes(
    outcomes_by_arm: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Bind evaluator-side outcomes from A0–A7 to one identical case set.

    Each arm supplies one JSON-object outcome per task ID. Task membership is
    identical across arms, but outcome values remain arm-specific. This maps
    and preserves completed results; it does not execute agents or score an
    efficacy contrast. The A7 oracle is represented only in this evaluator
    input and is never an actor-visible ``MatchedAgentArm``.
    """
    if not isinstance(outcomes_by_arm, Mapping):
        raise ValueError("matched outcomes must be supplied as an arm mapping")
    if any(not isinstance(arm_id, str) for arm_id in outcomes_by_arm):
        raise ValueError("matched arm identifiers must be strings")
    specs_by_id = {spec.arm_id: spec for spec in CANONICAL_AGENT_ARM_SPECS}
    expected_arm_ids = set(specs_by_id)
    if set(outcomes_by_arm) != expected_arm_ids:
        missing = sorted(expected_arm_ids - set(outcomes_by_arm))
        extra = sorted(set(outcomes_by_arm) - expected_arm_ids)
        raise ValueError(f"matched outcomes require exactly A0–A7; missing={missing}, extra={extra}")

    outcome_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for spec in CANONICAL_AGENT_ARM_SPECS:
        rows = outcomes_by_arm[spec.arm_id]
        if (isinstance(rows, (str, bytes, Mapping))
                or not isinstance(rows, Iterable)):
            raise ValueError(f"{spec.arm_id} outcomes must be a sequence of per-task rows")
        arm_outcomes: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError(f"{spec.arm_id} outcome rows must be mappings")
            task_id, outcome = row.get("task_id"), row.get("outcome")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError(f"{spec.arm_id} outcome rows require a non-empty task_id")
            if task_id in arm_outcomes:
                raise ValueError(f"duplicate task ID {task_id!r} in {spec.arm_id}")
            if not isinstance(outcome, Mapping):
                raise ValueError(f"{spec.arm_id} outcome for {task_id!r} must be a JSON object")
            normalized_outcome = dict(outcome)
            try:
                _sha256(normalized_outcome)
            except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
                raise ValueError(
                    f"{spec.arm_id} outcome for {task_id!r} must be canonical JSON data"
                ) from exc
            arm_outcomes[task_id] = normalized_outcome
        if not arm_outcomes:
            raise ValueError(f"{spec.arm_id} must contain at least one task outcome")
        outcome_maps[spec.arm_id] = arm_outcomes

    first_arm = CANONICAL_AGENT_ARM_SPECS[0].arm_id
    task_ids = sorted(outcome_maps[first_arm])
    task_id_set = set(task_ids)
    for spec in CANONICAL_AGENT_ARM_SPECS[1:]:
        if set(outcome_maps[spec.arm_id]) != task_id_set:
            raise ValueError("A0–A7 must map outcomes to the identical task-ID set")

    task_set_digest = _sha256(task_ids)
    arms = []
    for spec in CANONICAL_AGENT_ARM_SPECS:
        arm_outcomes = outcome_maps[spec.arm_id]
        arms.append({
            **spec.to_dict(),
            "task_ids": task_ids,
            "task_id_set_sha256": task_set_digest,
            "outcome_map_sha256": _sha256({
                task_id: arm_outcomes[task_id] for task_id in task_ids
            }),
            "outcomes_by_task": {
                task_id: arm_outcomes[task_id] for task_id in task_ids
            },
        })
    return {
        "schema_id": "memory-fabric.matched-agent-outcomes.v1",
        "status": "MATCHED_CASES_VALIDATED",
        "arm_registry": [spec.to_dict() for spec in CANONICAL_AGENT_ARM_SPECS],
        "task_population": {
            "name": "unique_matched_task_cases",
            "denominator": len(task_ids),
            "task_ids": task_ids,
            "task_id_set_sha256": task_set_digest,
        },
        "arms": arms,
        "all_arms_same_task_ids": True,
        "outcomes_bound_per_task_id": True,
        "claim_scope": "matched_case_mapping_only_no_efficacy_estimate",
    }


def validate_retrieval_baseline_matrix(
    retrieval_outcomes_by_arm: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Validate strong retrieval controls on identical cases and fixed budgets."""
    if (not isinstance(retrieval_outcomes_by_arm, Mapping)
            or any(not isinstance(key, str) for key in retrieval_outcomes_by_arm)):
        raise ValueError("retrieval baselines must map string arm IDs to task rows")
    expected_ids = set(RETRIEVAL_BASELINE_NAMES)
    if set(retrieval_outcomes_by_arm) != expected_ids:
        missing = sorted(expected_ids - set(retrieval_outcomes_by_arm))
        extra = sorted(set(retrieval_outcomes_by_arm) - expected_ids)
        raise ValueError(
            f"retrieval comparison requires recency, lexical, full-context, and "
            f"current governed-memory arms; missing={missing}, extra={extra}"
        )

    outcomes: dict[str, dict[str, dict[str, Any]]] = {}
    selected_hashes: dict[str, dict[str, str]] = {}
    usage_by_task: dict[str, dict[str, dict[str, int]]] = {}
    common_budget: dict[str, int] | None = None
    eligible_by_task: dict[str, tuple[str, ...]] = {}
    for arm_id, name in RETRIEVAL_BASELINE_NAMES.items():
        arm_outcomes: dict[str, dict[str, Any]] = {}
        arm_selected_hashes: dict[str, str] = {}
        arm_usage: dict[str, dict[str, int]] = {}
        rows = retrieval_outcomes_by_arm[arm_id]
        if isinstance(rows, (str, bytes, Mapping)) or not isinstance(rows, Iterable):
            raise ValueError(f"{arm_id} rows must be a sequence of retrieval outcomes")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError(f"{arm_id} retrieval rows must be mappings")
            task_id = row.get("task_id")
            eligible_raw = row.get("eligible_memory_ids")
            selected_raw = row.get("selected_memory_ids")
            budget_raw = row.get("resource_budget")
            usage_raw = row.get("resource_usage")
            outcome_raw = row.get("outcome")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError(f"{arm_id} rows require a non-empty task_id")
            if task_id in arm_outcomes:
                raise ValueError(f"duplicate task ID {task_id!r} in {arm_id}")
            if (not isinstance(eligible_raw, (list, tuple))
                    or any(not isinstance(item, str) or not item for item in eligible_raw)
                    or len(set(eligible_raw)) != len(eligible_raw)):
                raise ValueError(f"{arm_id} requires unique eligible memory IDs per task")
            if (not isinstance(selected_raw, (list, tuple))
                    or any(not isinstance(item, str) or not item for item in selected_raw)
                    or len(set(selected_raw)) != len(selected_raw)):
                raise ValueError(f"{arm_id} requires unique selected memory IDs per task")
            eligible, selected = tuple(eligible_raw), tuple(selected_raw)
            if not set(selected).issubset(set(eligible)):
                raise ValueError(f"{arm_id} selected memories outside the eligible corpus")
            prior_eligible = eligible_by_task.setdefault(task_id, eligible)
            if prior_eligible != eligible:
                raise ValueError("retrieval arms must use identical eligible memory corpora")
            if arm_id == "R_FULL_CONTEXT" and set(selected) != set(eligible):
                raise ValueError("full_context must include every eligible memory within its budget")
            if not isinstance(budget_raw, Mapping) or set(budget_raw) != _RETRIEVAL_RESOURCE_KEYS:
                raise ValueError(f"{arm_id} must declare every fixed retrieval/model resource budget")
            budget: dict[str, int] = {}
            for key, value in budget_raw.items():
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ValueError(f"{arm_id} resource budgets must be non-negative integers")
                budget[key] = value
            if common_budget is None:
                common_budget = budget
            elif common_budget != budget:
                raise ValueError("retrieval arms must use identical fixed resource budgets")
            if not isinstance(usage_raw, Mapping) or set(usage_raw) != _RETRIEVAL_RESOURCE_KEYS:
                raise ValueError(f"{arm_id} must report actual usage for every resource budget")
            usage: dict[str, int] = {}
            for key, value in usage_raw.items():
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ValueError(f"{arm_id} resource usage must be non-negative integers")
                if value > budget[key]:
                    raise ValueError(f"{arm_id} exceeded its {key} budget")
                usage[key] = value
            if usage["retrieved_items"] != len(selected):
                raise ValueError(f"{arm_id} retrieved_items usage must match selected memories")
            if not isinstance(outcome_raw, Mapping) or not isinstance(
                outcome_raw.get("completed"), bool,
            ):
                raise ValueError(f"{arm_id} outcomes require a boolean completed field")
            try:
                _sha256(dict(outcome_raw))
            except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
                raise ValueError(f"{arm_id} outcomes must be canonical JSON data") from exc
            arm_outcomes[task_id] = dict(outcome_raw)
            arm_selected_hashes[task_id] = _sha256(list(selected))
            arm_usage[task_id] = usage
        if not arm_outcomes:
            raise ValueError(f"{arm_id} must contain at least one task outcome")
        outcomes[arm_id] = arm_outcomes
        selected_hashes[arm_id] = arm_selected_hashes
        usage_by_task[arm_id] = arm_usage

    if common_budget is None:
        raise ValueError("retrieval baseline matrix must include task outcomes")
    task_ids = sorted(outcomes["R_RECENCY"])
    task_id_set = set(task_ids)
    for arm_id in RETRIEVAL_BASELINE_NAMES:
        if set(outcomes[arm_id]) != task_id_set:
            raise ValueError("retrieval baselines must cover identical task IDs")
    task_set_digest = _sha256(task_ids)
    return {
        "schema_id": "memory-fabric.retrieval-baseline-matrix.v1",
        "status": "FIXED_BUDGET_RETRIEVALS_VALIDATED",
        "task_population": {
            "denominator": len(task_ids),
            "task_ids": task_ids,
            "task_id_set_sha256": task_set_digest,
        },
        "resource_budget": common_budget,
        "resource_budget_sha256": _sha256(common_budget),
        "arms": [
            {
                "arm_id": arm_id,
                "name": RETRIEVAL_BASELINE_NAMES[arm_id],
                "task_id_set_sha256": task_set_digest,
                "outcomes_by_task": outcomes[arm_id],
                "selected_memory_set_sha256_by_task": selected_hashes[arm_id],
                "resource_usage_by_task": usage_by_task[arm_id],
            }
            for arm_id in RETRIEVAL_BASELINE_NAMES
        ],
        "claim_scope": "fixed_budget_retrieval_controls_only_no_efficacy_estimate",
    }


def validate_matched_arm_parity(
    arms: Mapping[str, MatchedAgentArm],
    *,
    memory_event_sources: tuple[str, ...] = ("memory_service",),
) -> dict[str, Any]:
    """Reject undeclared resource, access, world, or evaluator imbalance.

    A0–A6 are actor arms. Their task framing, world events, legal tools,
    observation privileges, task/model budgets, inference controls, and
    evaluator grading digest must match. Only the registry's memory,
    recovery, and CDM treatment dimensions may vary. A0 has no memory suffix;
    A1–A6 must have one. The A7 oracle is evaluator-only and is not accepted.
    """
    if not isinstance(arms, Mapping) or any(not isinstance(key, str) for key in arms):
        raise ValueError("parity inputs must map string arm IDs to actor arms")
    if (not isinstance(memory_event_sources, tuple) or not memory_event_sources
            or any(not isinstance(source, str) or not source
                   for source in memory_event_sources)
            or len(set(memory_event_sources)) != len(memory_event_sources)):
        raise ValueError("memory_event_sources must be a non-empty unique tuple")
    actor_arm_ids = tuple(spec.arm_id for spec in CANONICAL_AGENT_ARM_SPECS
                          if not spec.evaluator_only)
    expected_ids = set(actor_arm_ids)
    if set(arms) != expected_ids:
        missing = sorted(expected_ids - set(arms))
        extra = sorted(set(arms) - expected_ids)
        raise ValueError(
            f"parity requires actor arms A0–A6 and excludes oracle A7; "
            f"missing={missing}, extra={extra}"
        )

    for arm_id in actor_arm_ids:
        arm = arms[arm_id]
        if not isinstance(arm, MatchedAgentArm) or arm.arm_id != arm_id:
            raise ValueError(f"{arm_id} must map to its matching MatchedAgentArm")
    reference = arms[actor_arm_ids[0]]
    privilege_digest = reference.observation_privileges_sha256
    grading_digest = reference.evaluator_grading_sha256
    if not isinstance(privilege_digest, str) or not isinstance(grading_digest, str):
        raise ValueError(
            "all actor arms require pinned observation privilege and evaluator grading hashes"
        )
    reference_world, reference_memory = _partition_arm_events(
        reference, memory_event_sources,
    )
    if reference_memory:
        raise ValueError("A0 no_memory must not receive memory intervention events")

    arm_inputs = []
    for arm_id in actor_arm_ids:
        arm = arms[arm_id]
        spec = _ARM_SPECS_BY_ID[arm_id]
        if arm.observation.task_id != reference.observation.task_id:
            raise ValueError("all actor arms must use the same task ID")
        if arm.observation.instruction != reference.observation.instruction:
            raise ValueError("all actor arms must use identical task prompt framing")
        if arm.observation.permitted_tools != reference.observation.permitted_tools:
            raise ValueError("all actor arms must use identical legal tools")
        if arm.observation.to_dict()["budget"] != reference.observation.to_dict()["budget"]:
            raise ValueError("all actor arms must use identical task and model budgets")
        if arm.inference_controls() != reference.inference_controls():
            raise ValueError("all actor arms must use identical model inference controls")
        if (arm.memory_policy != spec.memory_policy
                or arm.recovery_policy != spec.recovery_policy
                or arm.cdm_enabled is not spec.cdm_enabled):
            raise ValueError(f"{arm_id} treatment must match its preregistered arm specification")
        if ((spec.cdm_enabled is True and arm.cdm_work_budget < 1)
                or (spec.cdm_enabled is False and arm.cdm_work_budget != 0)):
            raise ValueError(f"{arm_id} CDM work budget must match its declared treatment")
        if arm.prompt_frame_sha256 != reference.prompt_frame_sha256:
            raise ValueError("all actor arms must use identical task prompt framing")
        if arm.observation_privileges_sha256 != privilege_digest:
            raise ValueError("all actor arms must use identical observation privileges")
        if arm.evaluator_grading_sha256 != grading_digest:
            raise ValueError("all actor arms must use identical evaluator grading")
        world_events, memory_events = _partition_arm_events(arm, memory_event_sources)
        if world_events != reference_world:
            raise ValueError("all actor arms must receive identical non-memory world events")
        if arm_id == "A0" and memory_events:
            raise ValueError("A0 no_memory must not receive memory intervention events")
        if arm_id != "A0" and not memory_events:
            raise ValueError(f"{arm_id} {spec.name} must include its declared memory input")
        arm_inputs.append({
            "arm_id": arm_id,
            "name": spec.name,
            "declared_memory_policy": spec.memory_policy,
            "declared_recovery_policy": spec.recovery_policy,
            "declared_cdm_enabled": spec.cdm_enabled,
            "cdm_work_budget": arm.cdm_work_budget,
            "memory_event_count": len(memory_events),
            "memory_input_sha256": _sha256(memory_events),
        })

    shared_controls = {
        "task_id": reference.observation.task_id,
        "instruction_sha256": _sha256(reference.observation.instruction),
        "legal_tools": list(reference.observation.permitted_tools),
        "task_budget": reference.observation.to_dict()["budget"],
        "inference_controls": reference.inference_controls(),
        "observation_privileges_sha256": privilege_digest,
        "evaluator_grading_sha256": grading_digest,
        "world_context_sha256": _sha256(reference_world),
    }
    return {
        "schema_id": "memory-fabric.matched-arm-parity.v1",
        "status": "PARITY_VALIDATED",
        "task_id": reference.observation.task_id,
        "actor_arm_ids": list(actor_arm_ids),
        "shared_controls_sha256": _sha256(shared_controls),
        "shared_controls": {
            "legal_tools_sha256": _sha256(list(reference.observation.permitted_tools)),
            "task_budget_sha256": _sha256(reference.observation.to_dict()["budget"]),
            "inference_controls_sha256": _sha256(reference.inference_controls()),
            "observation_privileges_sha256": privilege_digest,
            "evaluator_grading_sha256": grading_digest,
            "world_context_sha256": _sha256(reference_world),
        },
        "declared_treatment_differences": [
            "memory_policy", "recovery_policy", "cdm_enabled", "cdm_work_budget",
        ],
        "arm_inputs": arm_inputs,
        "oracle_arm_id": "A7",
        "oracle_actor_input_included": False,
        "undeclared_imbalances": [],
        "claim_scope": "mechanical_parity_only_no_efficacy_estimate",
    }


def compare_prompt_framing_negative_control(
    arms: Mapping[str, MatchedAgentArm],
    outcomes_by_arm: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Estimate prompt caution and governance effects in a matched 2x2 control.

    Arms are ``ungoverned_neutral``, ``ungoverned_caution``,
    ``governed_neutral``, and ``governed_caution``. Within each governance
    level, only instruction framing may change; within each framing level,
    only the memory intervention may change. Estimates are descriptive paired
    completion-rate differences, not causal or confirmatory evidence.
    """
    names = ("ungoverned_neutral", "ungoverned_caution",
             "governed_neutral", "governed_caution")
    if not isinstance(arms, Mapping) or set(arms) != set(names):
        raise ValueError("negative control requires all four registered factor arms")
    if not isinstance(outcomes_by_arm, Mapping) or set(outcomes_by_arm) != set(names):
        raise ValueError("negative control requires outcomes for all four factor arms")
    for name in names:
        if not isinstance(arms[name], MatchedAgentArm):
            raise ValueError(f"{name} must be a MatchedAgentArm")
        if arms[name].arm_id != name:
            raise ValueError(f"{name} must use its matching arm ID")

    def world_events(arm: MatchedAgentArm) -> list[dict[str, Any]]:
        world, memory = _partition_arm_events(arm, ("memory_service",))
        if not memory:
            raise ValueError("each negative-control arm must receive its declared memory input")
        return world

    reference = arms["ungoverned_neutral"]
    ref_world = world_events(reference)
    if (not isinstance(reference.observation_privileges_sha256, str)
            or not isinstance(reference.evaluator_grading_sha256, str)):
        raise ValueError("negative-control arms require pinned privilege and grading hashes")
    for name, arm in arms.items():
        if (arm.observation.task_id != reference.observation.task_id
                or arm.actor_id != reference.actor_id
                or arm.observation.permitted_tools != reference.observation.permitted_tools
                or arm.observation.to_dict()["budget"] != reference.observation.to_dict()["budget"]
                or arm.inference_controls() != reference.inference_controls()
                or arm.evaluator_grading_sha256 != reference.evaluator_grading_sha256
                or world_events(arm) != ref_world):
            raise ValueError("negative-control arms must share task, world, evaluator, and budgets")

    caution_pairs = (("ungoverned_neutral", "ungoverned_caution"),
                     ("governed_neutral", "governed_caution"))
    for neutral_id, caution_id in caution_pairs:
        neutral, caution = arms[neutral_id], arms[caution_id]
        if neutral.observation.instruction == caution.observation.instruction:
            raise ValueError("caution arms must differ in prompt framing")
        _, neutral_memory = _partition_arm_events(neutral, ("memory_service",))
        _, caution_memory = _partition_arm_events(caution, ("memory_service",))
        if neutral_memory != caution_memory:
            raise ValueError("prompt framing controls must receive identical memory inputs")
    for neutral_id, caution_id in (("ungoverned_neutral", "governed_neutral"),
                                   ("ungoverned_caution", "governed_caution")):
        if arms[neutral_id].observation.instruction != arms[caution_id].observation.instruction:
            raise ValueError("governance contrasts must use the same prompt framing")
        _, ungoverned_memory = _partition_arm_events(arms[neutral_id], ("memory_service",))
        _, governed_memory = _partition_arm_events(arms[caution_id], ("memory_service",))
        if ungoverned_memory == governed_memory:
            raise ValueError("governance contrasts must change the memory intervention")

    outcomes: dict[str, dict[str, bool]] = {}
    for name in names:
        rows = outcomes_by_arm[name]
        if isinstance(rows, (str, bytes, Mapping)) or not isinstance(rows, Iterable):
            raise ValueError(f"{name} outcomes must be a sequence")
        mapped: dict[str, bool] = {}
        for row in rows:
            if not isinstance(row, Mapping) or not isinstance(row.get("task_id"), str):
                raise ValueError(f"{name} outcomes require task IDs")
            result = row.get("outcome")
            if (row["task_id"] in mapped or not isinstance(result, Mapping)
                    or not isinstance(result.get("completed"), bool)):
                raise ValueError(f"{name} requires unique task IDs and boolean completion labels")
            mapped[row["task_id"]] = result["completed"]
        if not mapped:
            raise ValueError(f"{name} must include task outcomes")
        outcomes[name] = mapped
    task_ids = sorted(outcomes[names[0]])
    if any(set(outcomes[name]) != set(task_ids) for name in names):
        raise ValueError("negative-control arms must cover identical task IDs")

    def effect(left: str, right: str) -> dict[str, Any]:
        deltas = [int(outcomes[right][task]) - int(outcomes[left][task]) for task in task_ids]
        wins = sum(delta > 0 for delta in deltas)
        losses = sum(delta < 0 for delta in deltas)
        return {"from_arm": left, "to_arm": right, "numerator": sum(deltas),
                "denominator": len(task_ids), "rate_difference": sum(deltas) / len(task_ids),
                "paired_wins": wins, "paired_losses": losses,
                "paired_ties": len(task_ids) - wins - losses}

    caution_effects = [effect("ungoverned_neutral", "ungoverned_caution"),
                       effect("governed_neutral", "governed_caution")]
    governance_effects = [effect("ungoverned_neutral", "governed_neutral"),
                          effect("ungoverned_caution", "governed_caution")]
    caution_mean = sum(item["rate_difference"] for item in caution_effects) / 2
    governance_mean = sum(item["rate_difference"] for item in governance_effects) / 2
    return {
        "schema_id": "memory-fabric.prompt-framing-negative-control.v1",
        "status": "PROMPT_AND_GOVERNANCE_CONTRASTS_VALIDATED",
        "task_population": {"denominator": len(task_ids), "task_ids": task_ids,
                             "task_id_set_sha256": _sha256(task_ids)},
        "prompt_caution_effect_by_governance": caution_effects,
        "core_governance_effect_by_prompt": governance_effects,
        "average_prompt_caution_rate_difference": caution_mean,
        "average_core_governance_rate_difference": governance_mean,
        "interaction_rate_difference": (
            caution_effects[1]["rate_difference"] - caution_effects[0]["rate_difference"]
        ),
        "claim_scope": "descriptive_matched_factor_contrasts_only_no_causal_or_confirmatory_claim",
    }


def compare_candidate_to_strongest_fair_arm(
    outcomes_by_arm: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    retrieval_outcomes_by_arm: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Compare A5 with the strongest preregistered non-oracle competitor.

    All A0–A4 arms and fixed-budget retrieval baselines are included in the
    selection rule. The A7 oracle is
    an upper bound and cannot be selected as a fair competitor. A strict rate
    improvement is required; ties do not pass. This descriptive contract does
    not provide uncertainty or a promotion decision, and parity remains a
    separate requirement.
    """
    manifest = match_arm_outcomes(outcomes_by_arm)
    retrieval_manifest = validate_retrieval_baseline_matrix(retrieval_outcomes_by_arm)
    completion_counts: dict[str, int] = {}
    denominators: dict[str, int] = {}
    for arm in manifest["arms"]:
        arm_id = arm["arm_id"]
        outcomes = arm["outcomes_by_task"]
        if not isinstance(outcomes, Mapping):
            raise ValueError("matched outcome maps are malformed")
        completed = []
        for task_id in manifest["task_population"]["task_ids"]:
            outcome = outcomes.get(task_id)
            if not isinstance(outcome, Mapping) or not isinstance(outcome.get("completed"), bool):
                raise ValueError(
                    f"{arm_id} outcomes require a boolean completed field for every task"
                )
            completed.append(outcome["completed"])
        completion_counts[arm_id] = sum(completed)
        denominators[arm_id] = len(completed)

    retrieval_arms = retrieval_manifest["arms"]
    retrieval_outcomes = {
        arm["arm_id"]: arm["outcomes_by_task"] for arm in retrieval_arms
    }
    task_ids = manifest["task_population"]["task_ids"]
    if set(task_ids) != set(retrieval_manifest["task_population"]["task_ids"]):
        raise ValueError("agent and retrieval baselines must cover identical task IDs")
    for arm_id, task_map in retrieval_outcomes.items():
        if any(not isinstance(task_map[task_id].get("completed"), bool) for task_id in task_ids):
            raise ValueError(f"{arm_id} outcomes require a boolean completed field for every task")
        completion_counts[arm_id] = sum(task_map[task_id]["completed"] for task_id in task_ids)
        denominators[arm_id] = len(task_ids)
    comparator_ids = ("A0", "A1", "A2", "A3", "A4", *RETRIEVAL_BASELINE_NAMES)
    rates = {
        arm_id: completion_counts[arm_id] / denominators[arm_id]
        for arm_id in (*comparator_ids, "A5")
    }
    all_arm_rates = [
        {
            "arm_id": arm["arm_id"],
            "name": arm["name"],
            "completed": completion_counts[arm["arm_id"]],
            "denominator": denominators[arm["arm_id"]],
            "rate": completion_counts[arm["arm_id"]] / denominators[arm["arm_id"]],
            "evaluator_only": arm["evaluator_only"],
        }
        for arm in manifest["arms"]
    ]
    all_arm_rates.extend({
        "arm_id": arm_id,
        "name": RETRIEVAL_BASELINE_NAMES[arm_id],
        "completed": completion_counts[arm_id],
        "denominator": denominators[arm_id],
        "rate": completion_counts[arm_id] / denominators[arm_id],
        "evaluator_only": False,
    } for arm_id in RETRIEVAL_BASELINE_NAMES)
    strongest_rate = max(rates[arm_id] for arm_id in comparator_ids)
    strongest_ids = [arm_id for arm_id in comparator_ids if rates[arm_id] == strongest_rate]
    candidate_rate = rates["A5"]
    paired = []
    candidate_outcomes = next(
        arm["outcomes_by_task"] for arm in manifest["arms"] if arm["arm_id"] == "A5"
    )
    for competitor_id in strongest_ids:
        competitor_outcomes = (
            retrieval_outcomes[competitor_id] if competitor_id in retrieval_outcomes
            else next(arm["outcomes_by_task"] for arm in manifest["arms"]
                      if arm["arm_id"] == competitor_id)
        )
        wins = sum(
            candidate_outcomes[task_id]["completed"]
            and not (competitor_outcomes[task_id]["completed"]
                     if competitor_id in retrieval_outcomes
                     else competitor_outcomes[task_id]["completed"])
            for task_id in manifest["task_population"]["task_ids"]
        )
        losses = sum(
            (competitor_outcomes[task_id]["completed"]
             if competitor_id in retrieval_outcomes
             else competitor_outcomes[task_id]["completed"])
            and not candidate_outcomes[task_id]["completed"]
            for task_id in manifest["task_population"]["task_ids"]
        )
        paired.append({
            "competitor_arm_id": competitor_id,
            "candidate_wins": wins,
            "candidate_losses": losses,
            "ties": denominators["A5"] - wins - losses,
            "denominator": denominators["A5"],
            "paired_rate_difference": (wins - losses) / denominators["A5"],
        })
    return {
        "schema_id": "memory-fabric.matched-arm-strongest-fair-comparison.v1",
        "status": (
            "OUTPERFORMS_STRONGEST_DECLARED_FAIR_ARM"
            if candidate_rate > strongest_rate
            else "DOES_NOT_OUTPERFORM_STRONGEST_DECLARED_FAIR_ARM"
        ),
        "candidate_arm_id": "A5",
        "fair_competitor_arm_ids": list(comparator_ids),
        "arm_completion_rates": all_arm_rates,
        "retrieval_baseline_validation": retrieval_manifest,
        "strongest_fair_competitor_arm_ids": strongest_ids,
        "strongest_fair_completion_rate": strongest_rate,
        "candidate_completion": {
            "numerator": completion_counts["A5"],
            "denominator": denominators["A5"],
            "rate": candidate_rate,
        },
        "strongest_fair_completion": {
            "numerator": completion_counts[strongest_ids[0]],
            "denominator": denominators[strongest_ids[0]],
            "rate": strongest_rate,
            "tied_arm_ids": strongest_ids,
        },
        "paired_comparisons_to_strongest": paired,
        "strict_improvement_required": True,
        "oracle_arm_id": "A7",
        "oracle_excluded_from_competitor_selection": True,
        "parity_status": "NOT_MECHANICALLY_VERIFIED",
        "promotion_eligible": False,
        "claim_scope": "descriptive_matched_case_completion_only",
    }


def compare_replay_ablation_outcomes(
    rows: Iterable[Mapping[str, Any]],
    *,
    work_budget: int,
    context_token_budget: int,
    minimum_seed_clusters: int = 5,
) -> dict[str, Any]:
    """Compare replay strategies only after exact per-case resource parity.

    Every strategy must use the same measured work units and answer-context
    tokens for each task, within common fixed caps. The output is descriptive;
    it does not promote an arm or establish causal efficacy.
    """
    for name, value in (("work_budget", work_budget),
                        ("context_token_budget", context_token_budget),
                        ("minimum_seed_clusters", minimum_seed_clusters)):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    by_strategy: dict[str, dict[str, Mapping[str, Any]]] = {
        strategy: {} for strategy in REPLAY_ABLATION_STRATEGIES
    }
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("ablation outcome rows must be mappings")
        strategy = row.get("strategy")
        if not isinstance(strategy, str) or strategy not in by_strategy:
            raise ValueError("unknown replay ablation strategy")
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("ablation rows require a task_id")
        if task_id in by_strategy[strategy]:
            raise ValueError(f"duplicate task {task_id!r} for {strategy}")
        seed = row.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise ValueError("ablation seed must be a non-negative integer")
        if not isinstance(row.get("completion"), bool):
            raise ValueError("completion must be a terminal grader boolean")
        for field, budget in (("work_units", work_budget),
                              ("context_tokens", context_token_budget)):
            amount = row.get(field)
            if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
                raise ValueError(f"{field} must be a non-negative integer")
            if amount > budget:
                raise ValueError(f"{field} exceeds its fixed budget")
        by_strategy[strategy][task_id] = row

    reference_ids = set(by_strategy[REPLAY_ABLATION_STRATEGIES[0]])
    if not reference_ids or any(set(items) != reference_ids for items in by_strategy.values()):
        raise ValueError("all strategies must cover the same non-empty task IDs")
    task_ids = sorted(reference_ids)
    seed_by_task: dict[str, int] = {}
    work_by_task: dict[str, int] = {}
    context_by_task: dict[str, int] = {}
    completion_counts: dict[str, int] = {}
    strategy_task_counts: dict[str, dict[str, int | float]] = {}
    for task_id in task_ids:
        reference: Mapping[str, Any] | None = None
        for strategy in REPLAY_ABLATION_STRATEGIES:
            row = by_strategy[strategy][task_id]
            if reference is None:
                reference = row
                seed_by_task[task_id] = int(row["seed"])
                work_by_task[task_id] = int(row["work_units"])
                context_by_task[task_id] = int(row["context_tokens"])
            elif (row["seed"] != reference["seed"]
                  or row["work_units"] != reference["work_units"]
                  or row["context_tokens"] != reference["context_tokens"]):
                raise ValueError("strategies must match seed, work units, and context per task")
    cluster_count = len(set(seed_by_task.values()))
    for strategy in REPLAY_ABLATION_STRATEGIES:
        rows_by_task = by_strategy[strategy]
        completion_counts[strategy] = sum(
            bool(rows_by_task[task_id]["completion"]) for task_id in task_ids
        )
        strategy_task_counts[strategy] = {
            "completed": completion_counts[strategy], "denominator": len(task_ids),
            "completion_rate": completion_counts[strategy] / len(task_ids),
        }
    task_set_digest = _sha256(task_ids)
    return {
        "schema_id": "memory-fabric.replay-ablation-comparison.v1",
        "status": "MATCHED_COSTS_VALIDATED",
        "strategies": list(REPLAY_ABLATION_STRATEGIES),
        "task_population": {
            "denominator": len(task_ids),
            "task_id_set_sha256": task_set_digest,
            "independent_seed_clusters": cluster_count,
            "minimum_seed_clusters": minimum_seed_clusters,
            "seed_floor_met": cluster_count >= minimum_seed_clusters,
        },
        "fixed_budgets": {
            "work_units": work_budget,
            "context_tokens": context_token_budget,
        },
        "matched_resource_usage": {
            "per_task_work_units": work_by_task,
            "per_task_context_tokens": context_by_task,
            "identical_across_strategies": True,
        },
        "completion_by_strategy": strategy_task_counts,
        "promotion_eligible": False,
        "claim_scope": "matched_budget_ablation_description_no_promotion_claim",
    }
