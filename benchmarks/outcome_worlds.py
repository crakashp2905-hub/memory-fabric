"""Leakage-resistant, seeded allocation for in-house outcome worlds.

Cases connected by template family, fact family, provenance root, exact
identifier, transition structure, or a token-order-independent surface-text
fingerprint stay in one split. Text fingerprints catch literal/shuffled-token
duplicates only; they do not claim to detect semantic paraphrases. Provenance
and authored-family IDs remain the authoritative grouping signals.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, Sequence

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_TOKENS = re.compile(r"[^\W_]+", flags=re.UNICODE)
_DEFAULT_RATIOS = {"train": 0.6, "dev": 0.2, "heldout": 0.2}
_MAX_CASES = 100_000
_MAX_TEXT_CHARS = 16_000
_MAX_WORLD_JSON_BYTES = 64_000
_MAX_WORLD_STATE_BYTES = 256_000
_WORLD_SCHEMA_ID = "memory-fabric.deterministic-outcome-world.v1"


class InsufficientSplitComponents(ValueError):
    """Raised when linked families leave too few independent groups to split."""


class SplitLeakageError(ValueError):
    """A cross-split identifier or world-signature collision was found."""

    def __init__(self, kind: str, left_split: str, right_split: str) -> None:
        self.kind = kind
        self.left_split = left_split
        self.right_split = right_split
        super().__init__(f"cross-split {kind} overlap between {left_split} and {right_split}")


def _identifier(value: str, *, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field} must be a stable identifier")
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (RecursionError, TypeError, ValueError) as exc:
        raise ValueError("world values must be finite JSON data") from exc


def _world_canonical_bytes(value: object) -> bytes:
    encoded = _canonical_bytes(value)
    if len(encoded) > _MAX_WORLD_JSON_BYTES:
        raise ValueError("world JSON data exceeds the size limit")
    return encoded


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_json(value: Any, *, label: str, active: set[int] | None = None,
                   depth: int = 0) -> None:
    if depth > 64:
        raise ValueError(f"{label} nesting exceeds the limit")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must contain finite numbers")
        return
    ancestors = set() if active is None else active
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in ancestors:
            raise ValueError(f"{label} cannot contain cycles")
        ancestors.add(identity)
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} object keys must be strings")
            _validate_json(item, label=label, active=ancestors, depth=depth + 1)
        ancestors.remove(identity)
        return
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in ancestors:
            raise ValueError(f"{label} cannot contain cycles")
        ancestors.add(identity)
        for item in value:
            _validate_json(item, label=label, active=ancestors, depth=depth + 1)
        ancestors.remove(identity)
        return
    raise ValueError(f"{label} must contain only JSON values")


def _copy_json_object(value: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    _validate_json(value, label=label)
    copied = json.loads(_world_canonical_bytes(dict(value)))
    if not isinstance(copied, dict):
        raise ValueError(f"{label} must be a JSON object")
    return copied


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json(item) for item in value]
    return value


def _world_effects(values: Sequence[str], *, label: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or len(values) > 128:
        raise ValueError(f"{label} must be a bounded sequence")
    effects = tuple(sorted(_identifier(item, field=label) for item in values))
    if len(set(effects)) != len(effects):
        raise ValueError(f"{label} must contain unique identifiers")
    return effects


@dataclass(frozen=True)
class ScheduledWorldEvent:
    """One timed public observation plus evaluator-only world changes."""

    __evaluator_only__: ClassVar[bool] = True

    event_id: str
    tick: int
    kind: str
    observation: Mapping[str, Any]
    truth_updates: Mapping[str, Any] = field(default_factory=dict, repr=False)
    truth_deletions: tuple[str, ...] = field(default=(), repr=False)
    legal_effects: tuple[str, ...] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _identifier(self.event_id, field="event_id")
        _identifier(self.kind, field="event kind")
        if not isinstance(self.tick, int) or isinstance(self.tick, bool) or self.tick < 0:
            raise ValueError("event tick must be a non-negative integer")
        public = _copy_json_object(self.observation, label="public observation")
        updates = _copy_json_object(self.truth_updates, label="hidden truth updates")
        if not isinstance(self.truth_deletions, (tuple, list)) \
                or len(self.truth_deletions) > 128:
            raise ValueError("truth_deletions must be a bounded sequence")
        deletions = tuple(sorted(_identifier(item, field="truth deletion")
                                 for item in self.truth_deletions))
        if len(set(deletions)) != len(deletions) or set(deletions) & set(updates):
            raise ValueError("truth deletions must be unique and disjoint from updates")
        object.__setattr__(self, "observation", _freeze_json(public))
        object.__setattr__(self, "truth_updates", _freeze_json(updates))
        object.__setattr__(self, "truth_deletions", deletions)
        if self.legal_effects is not None:
            object.__setattr__(self, "legal_effects",
                               _world_effects(self.legal_effects, label="legal effects"))


@dataclass(frozen=True)
class DeterministicWorldSpec:
    """Complete replay input; hidden truth stays outside actor-facing views."""

    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    seed: int
    initial_truth: Mapping[str, Any] = field(repr=False)
    initial_legal_effects: tuple[str, ...] = ()
    events: tuple[ScheduledWorldEvent, ...] = ()
    schema_id: str = _WORLD_SCHEMA_ID

    def __post_init__(self) -> None:
        _identifier(self.task_id, field="task_id")
        if (not isinstance(self.seed, int) or isinstance(self.seed, bool)
                or not 0 <= self.seed <= 0xffffffffffffffff):
            raise ValueError("world seed must be an unsigned 64-bit integer")
        if self.schema_id != _WORLD_SCHEMA_ID:
            raise ValueError("unsupported deterministic world schema")
        truth = _copy_json_object(self.initial_truth, label="initial hidden truth")
        object.__setattr__(self, "initial_truth", _freeze_json(truth))
        object.__setattr__(self, "initial_legal_effects",
                           _world_effects(self.initial_legal_effects,
                                          label="initial legal effects"))
        if not isinstance(self.events, (tuple, list)) or len(self.events) > 256:
            raise ValueError("world events must be a bounded sequence")
        events = tuple(self.events)
        if not all(isinstance(event, ScheduledWorldEvent) for event in events):
            raise ValueError("world events must be ScheduledWorldEvent values")
        event_ids = [event.event_id for event in events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("world event IDs must be unique")
        object.__setattr__(self, "events", tuple(sorted(
            events, key=lambda event: (event.tick, event.event_id))))
        _world_canonical_bytes({
            "schema_id": self.schema_id,
            "task_id": self.task_id,
            "seed": self.seed,
            "initial_truth": _thaw_json(self.initial_truth),
            "initial_legal_effects": self.initial_legal_effects,
            "events": [{
                "event_id": event.event_id,
                "tick": event.tick,
                "kind": event.kind,
                "observation": _thaw_json(event.observation),
                "truth_updates": _thaw_json(event.truth_updates),
                "truth_deletions": event.truth_deletions,
                "legal_effects": event.legal_effects,
            } for event in self.events],
        })


@dataclass(frozen=True)
class WorldSnapshot:
    """Evaluator state and a safe projection for actors."""

    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    seed: int
    tick: int
    revision_epoch: int
    observations: tuple[Mapping[str, Any], ...]
    hidden_truth: Mapping[str, Any] = field(repr=False)
    legal_effects: tuple[str, ...] = field(repr=False)
    schema_id: str = _WORLD_SCHEMA_ID

    def __post_init__(self) -> None:
        _identifier(self.task_id, field="task_id")
        if (not isinstance(self.seed, int) or isinstance(self.seed, bool)
                or not 0 <= self.seed <= 0xffffffffffffffff):
            raise ValueError("world seed must be an unsigned 64-bit integer")
        if (not isinstance(self.tick, int) or isinstance(self.tick, bool) or self.tick < 0
                or not isinstance(self.revision_epoch, int)
                or isinstance(self.revision_epoch, bool) or self.revision_epoch < 0):
            raise ValueError("world tick and revision epoch must be non-negative integers")
        if self.schema_id != _WORLD_SCHEMA_ID:
            raise ValueError("unsupported deterministic world schema")
        if not isinstance(self.observations, (tuple, list)) or len(self.observations) > 256:
            raise ValueError("world observations must be a bounded sequence")
        observations = tuple(_freeze_json(
            _copy_json_object(item, label="public observation event"))
            for item in self.observations)
        truth = _freeze_json(_copy_json_object(self.hidden_truth, label="hidden world truth"))
        effects = _world_effects(self.legal_effects, label="legal effects")
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "hidden_truth", truth)
        object.__setattr__(self, "legal_effects", effects)
        self.canonical_state_bytes()

    def canonical_state_bytes(self) -> bytes:
        """Serialize the complete evaluator state in stable canonical order."""
        state = {
            "schema_id": self.schema_id,
            "task_id": self.task_id,
            "seed": self.seed,
            "tick": self.tick,
            "revision_epoch": self.revision_epoch,
            "observations": _thaw_json(self.observations),
            "hidden_truth": _thaw_json(self.hidden_truth),
            "legal_effects": list(self.legal_effects),
        }
        encoded = _canonical_bytes(state)
        if len(encoded) > _MAX_WORLD_STATE_BYTES:
            raise ValueError("world state exceeds the size limit")
        return encoded

    @property
    def outcome_digest(self) -> str:
        """Commit the full deterministic task state without exposing truth."""
        return _sha256(self.canonical_state_bytes())

    def public_view(self) -> dict[str, Any]:
        """Return only scheduled observations and the public revision epoch."""
        return {
            "schema_id": "memory-fabric.outcome-world-observation.v1",
            "task_id": self.task_id,
            "tick": self.tick,
            "revision_epoch": self.revision_epoch,
            "observations": _thaw_json(self.observations),
        }


def replay_world(spec: DeterministicWorldSpec, *, through_tick: int | None = None) -> WorldSnapshot:
    """Replay scheduled observations and evaluator state using deterministic transitions."""
    if not isinstance(spec, DeterministicWorldSpec):
        raise ValueError("spec must be a DeterministicWorldSpec")
    final_scheduled_tick = max((event.tick for event in spec.events), default=0)
    if through_tick is None:
        current_tick = final_scheduled_tick
    elif (not isinstance(through_tick, int) or isinstance(through_tick, bool)
          or through_tick < 0):
        raise ValueError("through_tick must be a non-negative integer")
    else:
        current_tick = through_tick

    truth = _thaw_json(spec.initial_truth)
    legal_effects = spec.initial_legal_effects
    observations: list[dict[str, Any]] = []
    revision_epoch = 0
    for event in spec.events:
        if event.tick > current_tick:
            break
        changed = False
        for key in event.truth_deletions:
            if key in truth:
                del truth[key]
                changed = True
        for key, value in event.truth_updates.items():
            thawed = _thaw_json(value)
            if key not in truth or truth[key] != thawed:
                truth[key] = thawed
                changed = True
        if event.legal_effects is not None and event.legal_effects != legal_effects:
            legal_effects = event.legal_effects
            changed = True
        if changed:
            revision_epoch += 1
        observations.append({
            "event_id": event.event_id,
            "kind": event.kind,
            "tick": event.tick,
            "revision_epoch": revision_epoch,
            "data": _thaw_json(event.observation),
        })

    return WorldSnapshot(
        task_id=spec.task_id,
        seed=spec.seed,
        tick=current_tick,
        revision_epoch=revision_epoch,
        observations=tuple(observations),
        hidden_truth=truth,
        legal_effects=legal_effects,
        schema_id=spec.schema_id,
    )


@dataclass(frozen=True)
class CorrectionScenarioResult:
    """Evaluator summary of one correction-after-plan-before-execute replay."""

    __evaluator_only__: ClassVar[bool] = True

    seed: int
    task_id: str
    planned_revision_epoch: int
    correction_revision_epoch: int
    stale_outcome: str
    stale_reason_codes: tuple[str, ...]
    stale_side_effect_count: int
    replanned_revision_epoch: int
    replanned_value: int
    final_value: int
    terminal_status: str
    terminal_reason: str
    world_outcome_digest: str


def run_correction_after_plan_scenario(seed: int) -> CorrectionScenarioResult:
    """Plan against old evidence, deliver a correction, and require gated replanning.

    The old certificate is revoked when the correction arrives, so its exact
    request is refused by the repository's real ``ActionGate``. The corrected
    observation drives a new request, certificate, and exact-action grant.
    """
    if (not isinstance(seed, int) or isinstance(seed, bool)
            or not 0 <= seed <= 0xffffffff):
        raise ValueError("correction scenario seed must be a 32-bit non-negative integer")

    from memory_fabric import MemoryFabric
    from memory_fabric.actions import (
        REFUSED, ActionGate, ActionPolicy, ActionRequest, ToolRule,
    )
    from memory_fabric.agent_outcomes import AgentObservation
    from memory_fabric.agent_outcomes.observations import OracleTask
    from memory_fabric.agent_outcomes.outcomes import (
        EffectRecord, TerminalObjective, TerminalSnapshot,
        canonical_step_id, canonical_task_id, grade_terminal,
    )
    from memory_fabric.model import WithdrawalBasis

    task_id = canonical_task_id("correction_replan", seed, 0)
    initial_value = 10 + seed % 5
    corrected_value = initial_value + 5
    spec = DeterministicWorldSpec(
        task_id=task_id,
        seed=seed,
        initial_truth={"target": initial_value},
        initial_legal_effects=("set_target",),
        events=(
            ScheduledWorldEvent(
                "reading-initial", 0, "observation",
                {"source": "instrument-A", "status": "initial",
                 "value": initial_value},
            ),
            ScheduledWorldEvent(
                "reading-correction", 2, "correction",
                {"source": "instrument-A", "status": "correction",
                 "value": corrected_value},
                truth_updates={"target": corrected_value},
                legal_effects=("set_target",),
            ),
        ),
    )
    initial_snapshot = replay_world(spec, through_tick=0)
    initial_view = initial_snapshot.public_view()
    initial_data = initial_view["observations"][0]["data"]
    planned_revision = initial_snapshot.revision_epoch
    planned_value = initial_data["value"]
    if not isinstance(planned_value, int):
        raise ValueError("initial observation did not contain an integer target")
    actor_observation = AgentObservation(
        task_id, "Set the target to the latest instrument reading.",
        tuple(initial_view["observations"]), ("set_target",), {"steps": 4},
    )

    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        old_evidence_id = fabric.remember(
            "observer", f"Instrument-A target reading is {planned_value} units.", scope="team")
        old_certificate = fabric.certify(
            "Set target to the latest instrument reading.", [old_evidence_id], "executor")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_target": ToolRule("set_target", requires_grant=True)},
            grants={"executor": frozenset({"set_target"})},
        ))
        old_request = ActionRequest("target", {"value": planned_value})
        old_grant = gate.issue_grant(
            "set_target", "executor", issuer="host", certificate=old_certificate,
            request=old_request)

        current_snapshot = replay_world(spec, through_tick=2)
        current_view = current_snapshot.public_view()
        updated_observation = AgentObservation(
            task_id, actor_observation.instruction,
            tuple(current_view["observations"]), actor_observation.permitted_tools,
            actor_observation.budget,
        )
        correction_event = next((event for event in updated_observation.visible_events
                                 if event.get("kind") == "correction"), None)
        correction_data = (correction_event.get("data")
                           if correction_event is not None else None)
        if not isinstance(correction_data, Mapping):
            raise ValueError("re-evaluation observation has no public correction event")
        current_value = correction_data["value"]
        if (not isinstance(current_value, int)
                or current_snapshot.revision_epoch <= planned_revision):
            raise ValueError("correction did not advance the public world revision")

        fabric.quarantine(old_evidence_id, "instrument reading corrected",
                          actor="controller", basis=WithdrawalBasis.CONTRADICTED)
        stale_effects: list[int] = []
        stale_execution = gate.execute(
            "set_target", "executor", lambda _key: stale_effects.append(planned_value),
            old_certificate, key=f"{task_id}-stale", request=old_request, grant=old_grant,
        )
        if stale_execution.outcome != REFUSED or stale_effects:
            raise RuntimeError("stale pre-correction action was not safely refused")

        replan_revision = current_snapshot.revision_epoch
        replan_is_current = (replan_revision > planned_revision
                             and replan_revision == current_snapshot.revision_epoch)
        replan_is_legal = "set_target" in current_snapshot.legal_effects
        if not replan_is_current or not replan_is_legal:
            raise RuntimeError("re-evaluated action is stale or not a legal effect")
        new_evidence_id = fabric.remember(
            "observer", f"Instrument-A corrected target is {current_value} units.",
            scope="team")
        new_certificate = fabric.certify(
            "Set target to the latest instrument reading.", [new_evidence_id], "executor")
        new_request = ActionRequest("target", {"value": current_value})
        new_grant = gate.issue_grant(
            "set_target", "executor", issuer="host", certificate=new_certificate,
            request=new_request)
        completed_values: list[int] = []
        current_execution = gate.execute(
            "set_target", "executor", lambda _key: completed_values.append(current_value),
            new_certificate, key=f"{task_id}-replanned", request=new_request,
            grant=new_grant,
        )
        final_value = completed_values[-1] if completed_values else planned_value
        _, capability = OracleTask.seal_for_evaluator(task_id, {
            "truth": {"target": current_snapshot.hidden_truth["target"]},
            "eligibility": {"legal_effects": current_snapshot.legal_effects},
            "reward": {"complete": 1},
        })
        objective = TerminalObjective(task_id, {"target": current_value},
                                      "set_target", new_request)
        effects = [
            EffectRecord(task_id, canonical_step_id(task_id, 0), "set_target", "executor",
                         old_request, stale_execution),
            EffectRecord(task_id, canonical_step_id(task_id, 1), "set_target", "executor",
                         new_request, current_execution),
        ]
        terminal = TerminalSnapshot(task_id, {"target": final_value})
        grade = grade_terminal(objective, effects, [terminal], capability=capability)
        return CorrectionScenarioResult(
            seed=seed,
            task_id=task_id,
            planned_revision_epoch=planned_revision,
            correction_revision_epoch=current_snapshot.revision_epoch,
            stale_outcome=stale_execution.outcome,
            stale_reason_codes=(stale_execution.decision.reason_codes
                                if stale_execution.decision is not None else ()),
            stale_side_effect_count=len(stale_effects),
            replanned_revision_epoch=replan_revision,
            replanned_value=current_value,
            final_value=final_value,
            terminal_status=grade.status.value,
            terminal_reason=grade.reason.value,
            world_outcome_digest=current_snapshot.outcome_digest,
        )
    finally:
        fabric.close()


@dataclass(frozen=True)
class TransitionSkeleton:
    """Surface-free transition shape used to keep structurally equal worlds together.

    ``event_schedule`` is chronological ``(event_kind, tick)`` data;
    dependencies refer to event indexes in that sequence. Payload values and
    natural-language wording do not belong here.
    """

    event_schedule: tuple[tuple[str, int], ...]
    dependencies: tuple[tuple[int, int], ...] = ()
    legal_effects: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.event_schedule, tuple) or not self.event_schedule:
            raise ValueError("event_schedule must be a non-empty tuple")
        if len(self.event_schedule) > 256:
            raise ValueError("event_schedule exceeds the event limit")
        normalized_events: list[tuple[str, int]] = []
        last_tick = -1
        for event in self.event_schedule:
            if not isinstance(event, tuple) or len(event) != 2:
                raise ValueError("each scheduled event needs a kind and tick")
            kind = _identifier(event[0], field="event kind")
            tick = event[1]
            if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
                raise ValueError("event ticks must be non-negative integers")
            if tick < last_tick:
                raise ValueError("event_schedule must be chronological")
            normalized_events.append((kind, tick))
            last_tick = tick
        object.__setattr__(self, "event_schedule", tuple(normalized_events))

        if not isinstance(self.dependencies, tuple) or len(self.dependencies) > 1024:
            raise ValueError("dependencies must be a bounded tuple")
        normalized_dependencies: list[tuple[int, int]] = []
        for edge in self.dependencies:
            if not isinstance(edge, tuple) or len(edge) != 2:
                raise ValueError("each dependency needs source and target indexes")
            source, target = edge
            if (not isinstance(source, int) or isinstance(source, bool)
                    or not isinstance(target, int) or isinstance(target, bool)
                    or source < 0 or source >= target or target >= len(normalized_events)):
                raise ValueError("dependencies must point forward between scheduled events")
            normalized_dependencies.append((source, target))
        if len(set(normalized_dependencies)) != len(normalized_dependencies):
            raise ValueError("dependencies must be unique")
        object.__setattr__(self, "dependencies", tuple(sorted(normalized_dependencies)))

        if not isinstance(self.legal_effects, tuple) or len(self.legal_effects) > 128:
            raise ValueError("legal_effects must be a bounded tuple")
        effects = tuple(sorted(_identifier(item, field="legal effect")
                               for item in self.legal_effects))
        if len(set(effects)) != len(effects):
            raise ValueError("legal_effects must be unique")
        object.__setattr__(self, "legal_effects", effects)

    @property
    def signature(self) -> str:
        """Return a stable digest of event timing, dependencies and legal effects."""
        return _sha256(_canonical_bytes({
            "event_schedule": self.event_schedule,
            "dependencies": self.dependencies,
            "legal_effects": self.legal_effects,
        }))


@dataclass(frozen=True)
class OutcomeWorldSpec:
    """Split metadata for one generated world case, without its hidden truth."""

    case_key: str
    template_family_id: str
    fact_family_id: str
    transition: TransitionSkeleton
    source_root_ids: tuple[str, ...] = ()
    exact_identifiers: tuple[str, ...] = ()
    surface_texts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("case_key", "template_family_id", "fact_family_id"):
            _identifier(getattr(self, field_name), field=field_name)
        if not isinstance(self.transition, TransitionSkeleton):
            raise ValueError("transition must be a TransitionSkeleton")
        for field_name in ("source_root_ids", "exact_identifiers"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or len(values) > 256:
                raise ValueError(f"{field_name} must be a bounded tuple")
            checked = tuple(sorted(_identifier(item, field=field_name) for item in values))
            if len(set(checked)) != len(checked):
                raise ValueError(f"{field_name} must not contain duplicates")
            object.__setattr__(self, field_name, checked)
        if not isinstance(self.surface_texts, tuple) or len(self.surface_texts) > 64:
            raise ValueError("surface_texts must be a bounded tuple")
        for text in self.surface_texts:
            if (not isinstance(text, str) or not text.strip()
                    or len(text) > _MAX_TEXT_CHARS):
                raise ValueError("surface_texts must contain bounded non-empty strings")


@dataclass(frozen=True)
class AssignedWorld:
    """One spec assigned to a deterministic split with stable generated IDs."""

    split: str
    case_id: str
    world_seed: int
    spec: OutcomeWorldSpec


def _text_bag_fingerprint(text: str) -> str | None:
    tokens = sorted(token.casefold() for token in _TOKENS.findall(text))
    if not tokens:
        return None
    return _sha256(_canonical_bytes(tokens))


def _link_tokens(spec: OutcomeWorldSpec) -> tuple[tuple[str, str], ...]:
    tokens = [
        ("template_family", spec.template_family_id),
        ("fact_family", spec.fact_family_id),
        ("transition_signature", spec.transition.signature),
    ]
    tokens.extend(("source_root", item) for item in spec.source_root_ids)
    tokens.extend(("exact_identifier", item) for item in spec.exact_identifiers)
    tokens.extend(("surface_text_bag", fingerprint)
                  for text in spec.surface_texts
                  if (fingerprint := _text_bag_fingerprint(text)) is not None)
    return tuple(tokens)


def _components(cases: Sequence[OutcomeWorldSpec]) -> list[list[OutcomeWorldSpec]]:
    parent = list(range(len(cases)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)

    first_by_token: dict[tuple[str, str], int] = {}
    for index, case in enumerate(cases):
        for token in _link_tokens(case):
            earlier = first_by_token.setdefault(token, index)
            union(index, earlier)

    grouped: dict[int, list[OutcomeWorldSpec]] = {}
    for index, case in enumerate(cases):
        grouped.setdefault(find(index), []).append(case)
    return [sorted(group, key=lambda case: case.case_key)
            for group in grouped.values()]


def _validate_split_ratios(ratios: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(ratios, Mapping) or len(ratios) < 2:
        raise ValueError("at least two named split ratios are required")
    normalized: dict[str, float] = {}
    for name, ratio in ratios.items():
        _identifier(name, field="split name")
        if (not isinstance(ratio, (int, float)) or isinstance(ratio, bool)
                or not math.isfinite(float(ratio)) or ratio <= 0):
            raise ValueError("split ratios must be finite and positive")
        normalized[name] = float(ratio)
    total = sum(normalized.values())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("split ratios must sum to 1")
    return normalized


def validate_split_disjointness(
    splits: Mapping[str, Sequence[OutcomeWorldSpec]],
) -> None:
    """Reject family, provenance, identifier, text or transition leakage."""
    if not isinstance(splits, Mapping) or len(splits) < 2:
        raise ValueError("at least two named splits are required")
    seen_case_keys: dict[str, str] = {}
    seen: dict[tuple[str, str], str] = {}
    for split_name, cases in splits.items():
        _identifier(split_name, field="split name")
        if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)) or not cases:
            raise ValueError("each split must contain at least one world case")
        split_case_keys: set[str] = set()
        for case in cases:
            if not isinstance(case, OutcomeWorldSpec):
                raise ValueError("split entries must be OutcomeWorldSpec values")
            if case.case_key in split_case_keys:
                raise ValueError("case_key values must be unique within each split")
            split_case_keys.add(case.case_key)
            prior_case_split = seen_case_keys.setdefault(case.case_key, split_name)
            if prior_case_split != split_name:
                raise SplitLeakageError("case_key", prior_case_split, split_name)
            collision_kinds = {
                "template_family": ("template_family", case.template_family_id),
                "fact_family": ("fact_family", case.fact_family_id),
                "transition_signature": (
                    "transition_signature", case.transition.signature),
            }
            collision_kinds.update(
                (f"source_root:{item}", ("source_root", item))
                for item in case.source_root_ids)
            collision_kinds.update(
                (f"exact_identifier:{item}", ("exact_identifier", item))
                for item in case.exact_identifiers)
            collision_kinds.update(
                (f"surface_text_bag:{fingerprint}", ("surface_text_bag", fingerprint))
                for text in case.surface_texts
                if (fingerprint := _text_bag_fingerprint(text)) is not None)
            for label, token in collision_kinds.items():
                prior_split = seen.setdefault(token, split_name)
                if prior_split != split_name:
                    kind = label.split(":", 1)[0]
                    raise SplitLeakageError(kind, prior_split, split_name)


def seeded_world_splits(
    cases: Sequence[OutcomeWorldSpec],
    *,
    split_seed: int,
    ratios: Mapping[str, float] | None = None,
) -> dict[str, tuple[AssignedWorld, ...]]:
    """Allocate whole linked components to train/dev/heldout deterministically.

    The default proportions are 60/20/20. Splits operate on connected
    components of all known leakage links so neither a template nor a fact
    family can straddle them. Component scarcity fails closed.
    """
    if not isinstance(split_seed, int) or isinstance(split_seed, bool) \
            or not 0 <= split_seed <= 0xffffffffffffffff:
        raise ValueError("split_seed must be an unsigned 64-bit integer")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise ValueError("cases must be a bounded sequence")
    if not cases or len(cases) > _MAX_CASES:
        raise ValueError("cases must contain between 1 and 100000 worlds")
    checked_cases = tuple(cases)
    if not all(isinstance(case, OutcomeWorldSpec) for case in checked_cases):
        raise ValueError("cases must contain OutcomeWorldSpec values")
    keys = [case.case_key for case in checked_cases]
    if len(keys) != len(set(keys)):
        raise ValueError("case_key values must be globally unique")
    checked_cases = tuple(sorted(checked_cases, key=lambda case: case.case_key))
    split_ratios = _validate_split_ratios(
        _DEFAULT_RATIOS if ratios is None else ratios)
    split_names = sorted(split_ratios, key=lambda name: (-split_ratios[name], name))
    components = _components(checked_cases)
    if len(components) < len(split_names):
        raise InsufficientSplitComponents(
            f"{len(components)} independent components cannot populate "
            f"{len(split_names)} splits")

    def component_key(component: Sequence[OutcomeWorldSpec]) -> str:
        return _sha256(_canonical_bytes([case.case_key for case in component]))

    ordered_components = sorted(
        components,
        key=lambda component: (
            -len(component),
            _sha256(f"{split_seed}:{component_key(component)}".encode("ascii")),
            component_key(component),
        ),
    )
    total_cases = len(checked_cases)
    targets = {name: split_ratios[name] * total_cases for name in split_names}
    allocated = {name: 0 for name in split_names}
    buckets: dict[str, list[OutcomeWorldSpec]] = {name: [] for name in split_names}

    for index, component in enumerate(ordered_components):
        if index < len(split_names):
            split_name = split_names[index]
        else:
            largest_deficit = max(targets[name] - allocated[name] for name in split_names)
            candidates = [name for name in split_names
                          if math.isclose(targets[name] - allocated[name],
                                          largest_deficit, abs_tol=1e-12)]
            split_name = min(
                candidates,
                key=lambda name: hashlib.sha256(
                    f"{split_seed}:{name}".encode("ascii")).hexdigest(),
            )
        buckets[split_name].extend(component)
        allocated[split_name] += len(component)

    used_seeds: set[int] = set()
    output: dict[str, tuple[AssignedWorld, ...]] = {}
    for split_name in sorted(split_names):
        assigned: list[AssignedWorld] = []
        for spec in sorted(buckets[split_name], key=lambda case: case.case_key):
            identity = f"{split_seed}:{split_name}:{spec.case_key}"
            digest = _sha256(identity.encode("utf-8"))
            case_id = f"ow:v1:{split_name}:s{split_seed:016x}:{digest[:24]}"
            counter = 0
            world_seed = int(digest[:16], 16)
            while world_seed in used_seeds:
                counter += 1
                world_seed = int(_sha256(
                    f"{identity}:{counter}".encode("utf-8"))[:16], 16)
            used_seeds.add(world_seed)
            assigned.append(AssignedWorld(split_name, case_id, world_seed, spec))
        output[split_name] = tuple(assigned)

    validate_split_disjointness({
        name: tuple(assigned.spec for assigned in worlds)
        for name, worlds in output.items()
    })
    return output
