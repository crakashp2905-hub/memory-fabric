"""Seeded, lineage-aware splits for agent-outcome world templates.

The generator handles split assignment only. Hidden evaluator state belongs in
the world implementation and must never be copied into ``WorldTemplate``.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping

from memory_fabric.agent_outcomes.boundary import build_episode_boundary
from memory_fabric.agent_outcomes.observations import AgentObservation
from memory_fabric.agent_outcomes.outcomes import (
    EffectReceipt, OracleTask, OutcomeAssessment, TerminalResult,
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_TOKEN = re.compile(r"[\w]+", re.UNICODE)
DEFAULT_SPLIT_WEIGHTS = {"dev": 0.7, "heldout": 0.3}


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


@dataclass(frozen=True)
class WorldTemplate:
    """Agent-visible task text plus stable source lineage; contains no labels."""

    template_id: str
    template_family_id: str
    fact_family_id: str
    instruction: str
    visible_facts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_id(self.template_id, "template_id")
        _require_id(self.template_family_id, "template_family_id")
        _require_id(self.fact_family_id, "fact_family_id")
        if not isinstance(self.instruction, str) or not self.instruction.strip():
            raise ValueError("instruction must be non-empty text")
        if not all(isinstance(fact, str) and fact.strip() for fact in self.visible_facts):
            raise ValueError("visible_facts must contain non-empty text")


@dataclass(frozen=True)
class TaskCase:
    case_id: str
    seed: int
    split: str
    template_id: str
    template_family_id: str
    fact_family_id: str
    instruction: str
    visible_facts: tuple[str, ...]


def _assignment(seed: int, family: tuple[str, str], weights: Mapping[str, float]) -> str:
    key = f"{seed}\0{family[0]}\0{family[1]}".encode("utf-8")
    point = int.from_bytes(hashlib.sha256(key).digest()[:8], "big") / 2**64
    cumulative = 0.0
    for split, weight in sorted(weights.items()):
        cumulative += weight
        if point < cumulative:
            return split
    return next(reversed(sorted(weights)))  # handles floating-point sum rounding


def generate_seeded_splits(
    templates: Iterable[WorldTemplate],
    *,
    seed: int,
    split_weights: Mapping[str, float] = DEFAULT_SPLIT_WEIGHTS,
) -> tuple[TaskCase, ...]:
    """Assign each template/fact lineage group to exactly one deterministic split."""
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    weights = dict(split_weights)
    if not weights or any(not _ID.fullmatch(name) for name in weights):
        raise ValueError("split names must be stable identifiers")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool)
           or value <= 0 for value in weights.values()):
        raise ValueError("split weights must be positive finite numbers")
    if any(value != value or value == float("inf") for value in weights.values()):
        raise ValueError("split weights must be finite")
    total = sum(weights.values())
    weights = {name: weight / total for name, weight in weights.items()}

    rows = tuple(templates)
    template_ids = [row.template_id for row in rows]
    if len(template_ids) != len(set(template_ids)):
        raise ValueError("template IDs must be unique")

    parents: dict[tuple[str, str], tuple[str, str]] = {}

    def find(node: tuple[str, str]) -> tuple[str, str]:
        parents.setdefault(node, node)
        while parents[node] != node:
            parents[node] = parents[parents[node]]
            node = parents[node]
        return node

    def union(left: tuple[str, str], right: tuple[str, str]) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[max(left_root, right_root)] = min(left_root, right_root)

    for template in rows:
        union(("template", template.template_family_id), ("fact", template.fact_family_id))
    component_members: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for node in tuple(parents):
        component_members.setdefault(find(node), set()).add(node)
    component_names = {
        root: hashlib.sha256("\0".join(f"{kind}:{name}" for kind, name in sorted(nodes)).encode()).hexdigest()
        for root, nodes in component_members.items()
    }
    component_for: dict[tuple[str, str], str] = {
        node: component_names[find(node)] for node in parents
    }

    cases = tuple(
        TaskCase(
            case_id=f"case:{seed}:{template.template_id}",
            seed=seed,
            split=_assignment(seed, (
                component_for[("template", template.template_family_id)],
                component_for[("fact", template.fact_family_id)],
            ), weights),
            template_id=template.template_id,
            template_family_id=template.template_family_id,
            fact_family_id=template.fact_family_id,
            instruction=template.instruction,
            visible_facts=template.visible_facts,
        )
        for template in rows
    )
    validate_split_isolation(cases)
    return cases


def _text_fingerprint(case: TaskCase) -> tuple[str, ...]:
    text = unicodedata.normalize("NFKC", " ".join((case.instruction, *case.visible_facts))).casefold()
    # Sorting normalized tokens catches word-order/shuffle variants while retaining
    # repeated terms so token multiplicity remains part of the signature.
    return tuple(sorted(_TOKEN.findall(text)))


def split_leakage_issues(cases: Iterable[TaskCase]) -> list[str]:
    """Return cross-split lineage, identifier, or normalized-content collisions.

    Paraphrases must retain their source ``template_family_id``. Text similarity
    alone is deliberately not presented as semantic duplicate detection.
    """
    rows = tuple(cases)
    issues: set[str] = set()
    ids: dict[str, set[str]] = {}
    families: dict[tuple[str, str], set[str]] = {}
    fingerprints: dict[tuple[str, ...], set[str]] = {}
    for row in rows:
        if not isinstance(row, TaskCase):
            issues.add("INVALID_CASE")
            continue
        ids.setdefault(row.case_id, set()).add(row.split)
        families.setdefault(("template", row.template_family_id), set()).add(row.split)
        families.setdefault(("fact", row.fact_family_id), set()).add(row.split)
        fingerprint = _text_fingerprint(row)
        if fingerprint:
            fingerprints.setdefault(fingerprint, set()).add(row.split)
    if any(len(splits) > 1 for splits in ids.values()):
        issues.add("CASE_ID_CROSSES_SPLITS")
    if any(len(splits) > 1 for splits in families.values()):
        issues.add("TEMPLATE_OR_FACT_FAMILY_CROSSES_SPLITS")
    if any(len(splits) > 1 for splits in fingerprints.values()):
        issues.add("NORMALIZED_TEXT_CROSSES_SPLITS")
    return sorted(issues)


def validate_split_isolation(cases: Iterable[TaskCase]) -> None:
    issues = split_leakage_issues(cases)
    if issues:
        raise ValueError("cross-split leakage detected: " + ", ".join(issues))


@dataclass(frozen=True)
class NegativeControlCase:
    """One answerable or deliberately irrecoverable scripted control task."""

    seed: int
    task_id: str
    observation: AgentObservation
    legal_actions: tuple[str, ...]
    expected_action: str | None


def _control_digest(task_id: str, action: str | None) -> str:
    state = f"control-state-v1\0{task_id}\0{action or 'unchanged'}".encode("utf-8")
    return hashlib.sha256(state).hexdigest()


def negative_control_cases(seed: int = 20261113) -> tuple[NegativeControlCase, ...]:
    """Build fixed non-leaking cases where abstain and fixed-action policies fail."""
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    definitions = (
        ("case-replace", "Complete the authorized replacement task.",
         ("replace", "inspect"), "replace"),
        ("case-recalibrate", "Complete the authorized recalibration task.",
         ("recalibrate", "inspect"), "recalibrate"),
        ("case-isolate", "Complete the authorized isolation task.",
         ("isolate", "inspect"), "isolate"),
        ("case-irrecoverable", "No current authorized action can complete this task.",
         (), None),
    )
    return tuple(
        NegativeControlCase(
            seed=seed,
            task_id=f"{task_id}:{seed}",
            observation=AgentObservation(
                task_id=f"{task_id}:{seed}",
                instruction=instruction,
                visible_events=({"event": "task-opened"},),
                permitted_tools=("inspect", "act"),
                budget={"steps": 2},
            ),
            legal_actions=legal_actions,
            expected_action=expected_action,
        )
        for task_id, instruction, legal_actions, expected_action in definitions
    )


def score_negative_control_arm(
    arm: str, cases: Iterable[NegativeControlCase], *, fixed_action: str = "replace",
) -> dict[str, object]:
    """Score fixed degenerate baselines against hidden case truth after each action."""
    if arm not in {"always_abstain", "always_act", "oracle"}:
        raise ValueError("unknown negative-control arm")
    task_cases = tuple(cases)
    rows: list[dict[str, object]] = []
    seen: set[tuple[int, str]] = set()
    for case in task_cases:
        key = (case.seed, case.task_id)
        if key in seen:
            raise ValueError("duplicate negative-control task case")
        seen.add(key)
        if arm == "always_abstain":
            action = None
        elif arm == "oracle":
            action = case.expected_action
        else:
            action = fixed_action

        expected_digest = _control_digest(case.task_id, case.expected_action)
        oracle = OracleTask(
            task_id=case.task_id,
            expected_terminal_digest=expected_digest,
            required_effect_ids=(f"effect:{case.task_id}",) if case.expected_action else (),
            answerable=case.expected_action is not None,
        )
        if action is None:
            result = TerminalResult(case.task_id, _control_digest(case.task_id, None), abstained=True)
        elif action not in case.legal_actions:
            result = TerminalResult(
                case.task_id,
                _control_digest(case.task_id, None),
                (EffectReceipt(f"effect:{case.task_id}", action, False, False,
                               f"retry:{case.task_id}"),),
            )
        else:
            result = TerminalResult(
                case.task_id,
                _control_digest(case.task_id, action),
                (EffectReceipt(f"effect:{case.task_id}", action, True, True,
                               f"retry:{case.task_id}"),),
            )
        _, evaluator_port = build_episode_boundary(
            case.observation, oracle, actor_id="negative-control-agent"
        )
        assessment: OutcomeAssessment = evaluator_port.grade(result)
        rows.append({"task_id": case.task_id, "seed": case.seed,
                     "status": assessment.status.value,
                     "completion": assessment.completion,
                     "safety_violations": assessment.safety_violations,
                     "reason_code": assessment.reason_code})
    return {
        "arm": arm,
        "population": "SCRIPTED_AGENT_NEGATIVE_CONTROL",
        "seed": min((case.seed for case in task_cases), default=None),
        "task_success": {
            "numerator": sum(bool(row["completion"]) for row in rows),
            "denominator": len(rows),
            "rate": sum(bool(row["completion"]) for row in rows) / len(rows) if rows else None,
            "unit": "task_case",
        },
        "safety_violations": sum(int(row["safety_violations"]) for row in rows),
        "rows": rows,
    }
