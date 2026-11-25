"""Equipment and sensor identity without lossy splitting (VEGA next W03).

A registry holds a hierarchy (site -> equipment -> pack/module -> sensor) and each
sensor's approved aliases. Canonical ids keep every level ("pack:p-7/sensor:ta1"),
so probe A and probe B on pack P-7 are two entities, while "TA1", "probe A" and
"the A-side thermistor" can be registered as one.

:meth:`Registry.resolve` maps text to exactly one registered sensor, or reports the
candidates when it is ambiguous, or nothing. Matching is on normalised text
(Unicode NFKC, case-folded, separators unified) and on whole tokens, so
"TA10" never matches "TA1" and "Ｔ Ａ１" matches "TA1" only if registered that way.
Unregistered identifiers are never guessed into a registered sensor (W03-10).
"""

from __future__ import annotations

__stability__ = "experimental"

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Mapping

KINDS = ("site", "equipment", "pack", "module", "sensor")


class EntityError(ValueError):
    pass


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[‐-―−_]", "-", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class Entity:
    canonical: str
    kind: str
    parent: str | None
    aliases: tuple[str, ...]
    property: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise EntityError(f"unknown entity kind {self.kind!r}")


@dataclass(frozen=True)
class Resolution:
    canonical: str | None
    candidates: tuple[str, ...]

    @property
    def unique(self) -> bool:
        return self.canonical is not None


@dataclass
class Registry:
    entities: dict[str, Entity] = field(default_factory=dict)
    _alias: dict[str, set[str]] = field(default_factory=dict)

    def add(self, canonical: str, kind: str, *, parent: str | None = None,
            aliases: Iterable[str] = (), property: str | None = None) -> Entity:
        if parent is not None and parent not in self.entities:
            raise EntityError(f"parent {parent} is not registered")
        if canonical in self.entities:
            raise EntityError(f"{canonical} is already registered")
        names = tuple(normalise(a) for a in aliases)
        entity = Entity(canonical, kind, parent, names, property)
        self.entities[canonical] = entity
        for name in names:
            self._alias.setdefault(name, set()).add(canonical)
        return entity

    def ancestors(self, canonical: str) -> list[str]:
        out, here = [], self.entities[canonical].parent
        while here is not None:
            out.append(here)
            here = self.entities[here].parent
        return out

    def resolve(self, text: str, kind: str = "sensor") -> Resolution:
        norm = normalise(text)
        found: set[str] = set()
        for alias, owners in self._alias.items():
            if re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", norm):
                found |= {o for o in owners if self.entities[o].kind == kind}
        # A sensor named together with its own parent is still that one sensor; two
        # sensors named at once are ambiguous.
        found = {f for f in found if not any(f in self.ancestors(g) for g in found if g != f)}
        if len(found) == 1:
            return Resolution(next(iter(found)), tuple(found))
        return Resolution(None, tuple(sorted(found)))

    def claim_key(self, canonical: str, property: str) -> str:
        """The typed claim identity: entity path and measured property (W03-03)."""
        if canonical not in self.entities:
            raise EntityError(f"{canonical} is not registered")
        return f"{canonical}#{property}"


def battery_registry() -> Registry:
    """The registry the seeded battery worlds use: pack P-7 with sensors TA1 and TB2."""
    r = Registry()
    r.add("site:plant", "site", aliases=())
    r.add("pack:p-7", "pack", parent="site:plant", aliases=("pack p-7", "p-7", "p7"))
    r.add("pack:p-7/sensor:ta1", "sensor", parent="pack:p-7", property="temperature",
          aliases=("ta1", "probe a", "a-side thermistor", "thermistor ta1", "p7-a"))
    r.add("pack:p-7/sensor:tb2", "sensor", parent="pack:p-7", property="temperature",
          aliases=("tb2", "probe b", "second sensor", "p7-b"))
    r.add("pack:p-9", "pack", parent="site:plant", aliases=("pack p-9", "p-9"))
    r.add("pack:p-9/sensor:tb9", "sensor", parent="pack:p-9", property="temperature", aliases=("tb9",))
    return r


def aliases_of(registry: Registry, canonical: str) -> Mapping[str, str]:
    return {a: canonical for a in registry.entities[canonical].aliases}
