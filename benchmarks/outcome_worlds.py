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
from dataclasses import dataclass
from typing import Mapping, Sequence

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_TOKENS = re.compile(r"[^\W_]+", flags=re.UNICODE)
_DEFAULT_RATIOS = {"train": 0.6, "dev": 0.2, "heldout": 0.2}
_MAX_CASES = 100_000
_MAX_TEXT_CHARS = 16_000


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
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
