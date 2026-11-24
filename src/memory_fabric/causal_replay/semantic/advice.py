"""Typed questions and strictly validated answers from a semantic advisor (VEGA S01, S03).

An advisor answers closed, host-defined questions (``choice``, ``boolean``,
``score``, as vegaml's ``decide()`` does) about a packet bundle's state text.
Its output is an :class:`Advice`: answers plus a receipt. Nothing here can
mutate a store, call a tool or approve evidence; a caller gets labels and
probabilities and decides what to do with them through the deterministic code.

Parsing never fills a gap. A missing probability, an option outside the
criteria, a non-finite or unnormalised distribution, or a malformed conformal
set becomes ``INVALID``; an advisor that could not answer is ``UNAVAILABLE``;
``abstain`` is kept as its own status (VEGA-CDM-014, 146).
"""

from __future__ import annotations

__stability__ = "experimental"

import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

KINDS = ("choice", "boolean", "score")
ANSWER_STATUSES = ("OK", "ABSTAIN", "UNAVAILABLE", "INVALID")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
NORMALISATION_TOLERANCE = 1e-3


class AdviceError(ValueError):
    pass


@dataclass(frozen=True)
class Question:
    name: str
    kind: str
    instructions: str
    criteria: Mapping[str, str] | tuple[str, ...]

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name or ""):
            raise AdviceError("question name must be a short lowercase identifier")
        if self.kind not in KINDS:
            raise AdviceError(f"unknown question type {self.kind!r}")
        if not isinstance(self.instructions, str) or not self.instructions.strip():
            raise AdviceError("question needs instructions")
        if self.kind == "score":
            if (not isinstance(self.criteria, tuple) or len(self.criteria) < 2
                    or any(not isinstance(c, str) or not c for c in self.criteria)):
                raise AdviceError("a score question lists at least two levels")
        else:
            if not isinstance(self.criteria, Mapping) or not self.criteria:
                raise AdviceError("choice and boolean questions map labels to criteria")
            if any(not _NAME.fullmatch(k) or not isinstance(v, str) or not v
                   for k, v in self.criteria.items()):
                raise AdviceError("criteria labels must be identifiers with descriptions")
            if self.kind == "boolean" and set(self.criteria) != {"true", "false"}:
                raise AdviceError("boolean criteria are exactly true and false")
            object.__setattr__(self, "criteria", dict(self.criteria))

    @property
    def labels(self) -> tuple[str, ...]:
        if self.kind == "score":
            return tuple(str(i) for i in range(len(self.criteria)))
        return tuple(sorted(self.criteria))

    def to_wire(self) -> dict[str, Any]:
        criteria: Any = list(self.criteria) if isinstance(self.criteria, tuple) else dict(self.criteria)
        return {"type": self.kind, "instructions": self.instructions, "criteria": criteria}


@dataclass(frozen=True)
class Answer:
    question: str
    kind: str
    status: str
    value: Any = None
    probs: Mapping[str, float] = field(default_factory=dict)
    prediction_set: tuple[str, ...] = ()
    abstain: bool | None = None
    unbound: bool | None = None
    readout: str | None = None
    reason: str = ""

    @property
    def decisive(self) -> bool:
        """Usable as a single label: OK, not unbound, and a one-option conformal set."""
        return (self.status == "OK" and not self.unbound
                and (not self.prediction_set or len(self.prediction_set) == 1))


@dataclass(frozen=True)
class Advice:
    answers: Mapping[str, Answer]
    receipt: Mapping[str, Any]

    @property
    def available(self) -> bool:
        return any(a.status in ("OK", "ABSTAIN") for a in self.answers.values())


class Advisor(Protocol):
    def decide(self, state: str, questions: Mapping[str, Question]) -> Advice: ...


def unavailable(questions: Mapping[str, Question], reason: str,
                receipt: Mapping[str, Any]) -> Advice:
    return Advice({n: Answer(n, q.kind, "UNAVAILABLE", reason=reason) for n, q in questions.items()},
                  dict(receipt))


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _invalid(q: Question, reason: str) -> Answer:
    return Answer(q.name, q.kind, "INVALID", reason=reason)


def parse_answer(question: Question, raw: Any) -> Answer:
    """One answer from a vegaml-shaped dictionary, refusing anything it would have to guess."""
    q = question
    if not isinstance(raw, Mapping):
        return _invalid(q, "answer is not an object")
    labels = q.labels
    probs_raw = raw.get("probs")
    probs: dict[str, float] = {}
    if probs_raw is not None:
        if isinstance(probs_raw, Mapping):
            # vegaml 0.19 keys boolean probabilities "True"/"False" (recorded fixture);
            # only those two spellings are folded, nothing else is coerced.
            fold = {"True": "true", "False": "false"} if q.kind == "boolean" else {}
            items = {fold.get(str(k), str(k)): v for k, v in probs_raw.items()}
            if len(items) != len(probs_raw):
                return _invalid(q, "probs repeat an option")
        elif (q.kind == "score" and isinstance(probs_raw, (list, tuple))
              and len(probs_raw) == len(labels)):
            items = dict(zip(labels, probs_raw))  # a score's levels are ordered, so position is safe
        else:
            return _invalid(q, "probs must be an object over the criteria")
        if set(items) != set(labels):
            return _invalid(q, "probs keys differ from the criteria")
        if any(not _finite(v) or not 0 <= v <= 1 for v in items.values()):
            return _invalid(q, "probabilities must be finite and in [0, 1]")
        if abs(math.fsum(items.values()) - 1) > NORMALISATION_TOLERANCE:
            return _invalid(q, "probabilities do not sum to 1")
        probs = {k: float(v) for k, v in items.items()}
    if q.kind == "choice":
        value = raw.get("choice")
        if value not in labels:
            return _invalid(q, "choice is not one of the criteria")
        if not probs:
            return _invalid(q, "a choice answer needs its probabilities")
    elif q.kind == "boolean":
        raw_value: Any = raw.get("boolean")
        if not _finite(raw_value) or not 0 <= raw_value <= 1:
            return _invalid(q, "boolean must be p(true) in [0, 1]")
        value = float(raw_value)
        if not probs:
            probs = {"true": value, "false": 1 - value}
        elif abs(probs["true"] - value) > NORMALISATION_TOLERANCE:
            return _invalid(q, "boolean and probs disagree")
    else:
        value = raw.get("score")
        if type(value) is not int or not 0 <= value < len(q.criteria):
            return _invalid(q, "score must be an integer level of the criteria")
    pset_raw = raw.get("prediction_set")
    pset: tuple[str, ...] = ()
    if pset_raw is not None:
        if not isinstance(pset_raw, (list, tuple)) or not pset_raw:
            return _invalid(q, "prediction_set must be a non-empty list")
        pset = tuple(str(x).lower() if isinstance(x, bool) else str(x) for x in pset_raw)
        if any(x not in labels for x in pset) or len(set(pset)) != len(pset):
            return _invalid(q, "prediction_set names options outside the criteria")
    flags = {}
    for flag in ("abstain", "unbound"):
        if flag in raw and raw[flag] is not None:
            if type(raw[flag]) is not bool:
                return _invalid(q, f"{flag} must be a boolean")
            flags[flag] = raw[flag]
    if "abstain" not in flags:
        return _invalid(q, "abstain is missing; an answer cannot be assumed confident")
    readout = raw.get("readout")
    status = "ABSTAIN" if flags["abstain"] else "OK"
    return Answer(q.name, q.kind, status, value, probs, pset, flags["abstain"],
                  flags.get("unbound"), readout if isinstance(readout, str) else None)


def parse_decision(questions: Mapping[str, Question], payload: Any) -> dict[str, Answer]:
    answers = payload.get("answers") if isinstance(payload, Mapping) else None
    if not isinstance(answers, Mapping):
        return {n: _invalid(q, "response has no answers object") for n, q in questions.items()}
    out = {n: parse_answer(q, answers.get(n)) for n, q in questions.items()}
    extra = set(answers) - set(questions)
    if extra:
        return {n: _invalid(q, f"response answered unasked questions {sorted(extra)}")
                for n, q in questions.items()}
    return out
