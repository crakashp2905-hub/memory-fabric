"""Deterministic typed observations: numbers, units, relations and their source spans (VEGA next W02).

The development run with vega-U read "sixty-one degrees" as not above 50 C and the
arm chose ``no_action`` on a hot pack. Reading a quantity is not a semantic
judgement, so it is done here, without a model, and either exactly or not at all.

* Numbers: digits with sign, decimals and thousands separators ("1,250", "-4.5");
  English number words, hyphenated or spaced, with "minus"/"negative" and
  "point" ("sixty-one", "one hundred and two", "negative five", "fifty point five").
  An unknown word inside a number phrase makes the whole phrase UNKNOWN (W02-02, 03).
* Units: Celsius, Fahrenheit and kelvin aliases, converted to Celsius; a bare
  "degrees" takes the registered default unit of the property, and says so;
  anything else is UNKNOWN (W02-04).
* Relations become intervals, never booleans: "above 50" is (50, inf), "at least 50"
  is [50, inf), "exactly 50" is [50, 50], "around 50" is an interval of the registered
  tolerance, "between 40 and 60" is [40, 60]. Hedges ("maybe", "possibly",
  "estimated") and double negation make the observation UNKNOWN (W02-05, 06).
* Every value is tied to the exact substring and offsets it came from, and to the
  evidence version; a value whose span does not read back from the text is refused
  (W02-07).

:func:`evaluate` compares an interval with a threshold predicate and returns
``TRUE``, ``FALSE`` or ``UNKNOWN`` (an interval that crosses the threshold). Nothing in
this module returns "safe" for a quantity it could not read (W02-09).
"""

from __future__ import annotations

__stability__ = "experimental"

import builtins
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

STATUSES = ("OK", "UNKNOWN")
RELATIONS = ("eq", "gt", "ge", "lt", "le", "approx", "range")
_UNITS = {"c": "C", "°c": "C", "degc": "C", "celsius": "C", "centigrade": "C", "degrees c": "C",
          "degrees celsius": "C", "f": "F", "°f": "F", "degf": "F", "fahrenheit": "F",
          "degrees f": "F", "degrees fahrenheit": "F", "k": "K", "kelvin": "K", "kelvins": "K",
          "ma": "mA", "a": "A", "v": "V", "bar": "bar"}
_TEMPERATURE = {"C", "F", "K"}
_ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
         "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
         "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_SCALES = {"hundred": 100, "thousand": 1000}
_NUMWORD = set(_ONES) | set(_TENS) | set(_SCALES) | {"and", "point", "minus", "negative"}
_HEDGES = re.compile(r"\b(maybe|perhaps|possibly|probably|might|may|could|estimated|approximately?\s+estimated|"
                     r"unclear|unverified|apparently|reportedly|roughly guessed|not sure)\b")
_DIGIT_NUMBER = r"[-+−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_UNIT_ALT = (r"(?:°\s?[cf]|degrees?\s+(?:celsius|fahrenheit|c|f)\b|degrees?\b|deg\s?[cf]\b|celsius\b|"
             r"centigrade\b|fahrenheit\b|kelvins?\b|ma\b|[cfk]\b|v\b|bar\b|a\b)")
_DIGIT_Q = re.compile(rf"(?<![\w.])({_DIGIT_NUMBER})\s*({_UNIT_ALT})", re.I)
_WORD_RUN = re.compile(r"\b((?:(?:" + "|".join(sorted(_NUMWORD, key=len, reverse=True))
                       + r")(?:[\s-]+|$))+)\s*(" + _UNIT_ALT + r")", re.I)
_RANGE = re.compile(rf"(?:between\s+)?({_DIGIT_NUMBER})\s*(?:-|to|and|–)\s*({_DIGIT_NUMBER})\s*({_UNIT_ALT})", re.I)
_UNREAD = re.compile(r"\b([a-z][a-z-]*)\s+(degrees?)\b", re.I)
_TIME = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_BEFORE = 40  # characters before a quantity searched for its relation words


class ObservationError(ValueError):
    pass


def words_to_number(phrase: str) -> float | None:
    """English number words to a value, or None if any word is not part of a number."""
    tokens = [t for t in re.split(r"[\s-]+", phrase.lower().strip()) if t and t != "and"]
    if not tokens:
        return None
    sign = 1.0
    if tokens[0] in ("minus", "negative"):
        sign, tokens = -1.0, tokens[1:]
    if not tokens or any(t not in _NUMWORD - {"and"} for t in tokens):
        return None
    if "point" in tokens:
        cut = tokens.index("point")
        whole, frac = tokens[:cut], tokens[cut + 1:]
        if not frac or any(t not in _ONES or _ONES[t] > 9 for t in frac):
            return None
        base = words_to_number(" ".join(whole)) if whole else 0.0
        if base is None:
            return None
        return sign * (base + float("0." + "".join(str(_ONES[t]) for t in frac)))
    total = current = 0
    seen_any = False
    last = None
    for t in tokens:
        if t in ("minus", "negative", "point"):
            return None
        if t in _ONES:
            if last in ("ones",) or (last == "tens" and _ONES[t] >= 10):
                return None
            current += _ONES[t]
            last = "ones"
        elif t in _TENS:
            if last in ("ones", "tens"):
                return None
            current += _TENS[t]
            last = "tens"
        else:
            scale = _SCALES[t]
            if current == 0:
                return None
            current *= scale
            if scale >= 1000:
                total += current
                current = 0
            last = "scale"
        seen_any = True
    return sign * float(total + current) if seen_any else None


def to_celsius(value: float, unit: str) -> float:
    if unit == "C":
        return value
    if unit == "F":
        return (value - 32.0) * 5.0 / 9.0
    if unit == "K":
        return value - 273.15
    raise ObservationError(f"no temperature conversion from {unit}")


def _unit(raw: str, default_unit: str | None) -> tuple[str | None, bool]:
    key = re.sub(r"\s+", " ", raw.lower().strip())
    if key in ("degree", "degrees"):
        return default_unit, default_unit is not None
    key = key.replace("deg ", "deg").replace("° ", "°")
    return _UNITS.get(key), False


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class TypedObservation:
    status: str
    reason: str
    sensor: str | None
    property: str
    relation: str | None
    low: float | None
    high: float | None
    low_inclusive: bool
    high_inclusive: bool
    unit: str | None
    unit_from_registry: bool
    raw_value: str
    span: Span
    evidence_ref: str | None
    time: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @builtins.property
    def readable(self) -> bool:
        return self.status == "OK"


def _relation(context: str) -> tuple[str, bool]:
    """(relation, negated) from the words just before a quantity."""
    c = context.lower()
    negations = len(re.findall(r"\b(not|no|never|isn't|wasn't|n't)\b", c))
    rel = "eq"
    for pattern, name in ((r"(at least|no less than|>=|≥|not below)\s*$", "ge"),
                          (r"(at most|no more than|<=|≤|not above|up to)\s*$", "le"),
                          (r"(above|over|more than|greater than|exceed(?:s|ing)?|higher than|>)\s*$", "gt"),
                          (r"(below|under|less than|lower than|<)\s*$", "lt"),
                          (r"(around|about|approximately|approx\.?|roughly|nearly|~|circa)\s*$", "approx"),
                          (r"(exactly|precisely|=)\s*$", "eq")):
        if re.search(pattern, c):
            rel = name
            if name in ("ge", "le") and re.search(r"\bnot\s+(below|above)\s*$", c):
                negations -= 1  # "not below" is itself the relation
            break
    return rel, negations > 0


def _interval(rel: str, v: float, tol: float) -> tuple[float, float, bool, bool]:
    inf = math.inf
    return {"eq": (v, v, True, True), "gt": (v, inf, False, False), "ge": (v, inf, True, False),
            "lt": (-inf, v, False, False), "le": (-inf, v, False, True),
            "approx": (v - tol, v + tol, True, True)}[rel]


def _negate(rel: str) -> str | None:
    return {"gt": "le", "ge": "lt", "lt": "ge", "le": "gt"}.get(rel)


def extract(text: str, *, property: str = "temperature", default_unit: str | None = None,
            tolerance: float = 2.0, evidence_ref: str | None = None, sensor: str | None = None
            ) -> list[TypedObservation]:
    """Every quantity in ``text`` as a typed observation, OK or UNKNOWN with a reason."""
    out: list[TypedObservation] = []
    taken: list[tuple[int, int]] = []
    clock = _TIME.search(text)
    when = f"{int(clock.group(1)):02d}:{clock.group(2)}" if clock else None
    hedged = bool(_HEDGES.search(text.lower()))

    def overlaps(a: int, b: int) -> bool:
        return any(a < y and b > x for x, y in taken)

    def emit(start: int, end: int, raw: str, values: tuple[float, ...] | None, unit_raw: str,
             is_range: bool = False) -> None:
        if overlaps(start, end):
            return
        taken.append((start, end))
        span = Span(start, end, text[start:end])
        unit, from_registry = _unit(unit_raw, default_unit)
        rel, negated = _relation(text[max(0, start - _BEFORE):start])
        base: dict[str, Any] = dict(sensor=sensor, property=property, unit=unit,
                                    unit_from_registry=from_registry, raw_value=raw, span=span,
                                    evidence_ref=evidence_ref, time=when)
        nothing: dict[str, Any] = dict(relation=None, low=None, high=None, low_inclusive=False,
                                       high_inclusive=False)

        def unknown(reason: str) -> None:
            out.append(TypedObservation("UNKNOWN", reason, **base, **nothing))
        if values is None:
            return unknown("number words not understood")
        if unit is None:
            return unknown("unit not recognised and no registered default")
        if hedged:
            return unknown("hedged or uncertain statement")
        if property == "temperature" and unit not in _TEMPERATURE:
            return unknown(f"unit {unit} is not a temperature")
        try:
            converted = tuple(to_celsius(v, unit) for v in values) if unit in _TEMPERATURE else values
        except ObservationError as exc:
            return unknown(str(exc))
        canon = "C" if unit in _TEMPERATURE else unit
        if is_range:
            lo, hi = sorted(converted)
            out.append(TypedObservation("OK", "", **{**base, "unit": canon}, relation="range", low=lo, high=hi,
                                        low_inclusive=True, high_inclusive=True))
            return
        if negated:
            flipped = _negate(rel)
            if flipped is None or len(re.findall(r"\bnot\b", text[max(0, start - _BEFORE):start].lower())) > 1:
                return unknown("negated or double-negated quantity")
            rel = flipped
        lo, hi, li, hi_inc = _interval(rel, converted[0], tolerance if unit in _TEMPERATURE else tolerance)
        out.append(TypedObservation("OK", "", **{**base, "unit": canon}, relation=rel, low=lo, high=hi,
                                    low_inclusive=li, high_inclusive=hi_inc))

    for m in _RANGE.finditer(text):
        a, b = (_digits(m.group(1)), _digits(m.group(2)))
        emit(m.start(), m.end(), m.group(0), (a, b) if a is not None and b is not None else None, m.group(3), True)
    for m in _DIGIT_Q.finditer(text):
        if _TIME.fullmatch(m.group(1).strip()):
            continue
        v = _digits(m.group(1))
        emit(m.start(), m.end(), m.group(1), (v,) if v is not None else None, m.group(2))
    for m in _WORD_RUN.finditer(text):
        phrase = m.group(1)
        emit(m.start(1), m.end(), phrase.strip(), (lambda v: (v,) if v is not None else None)(words_to_number(phrase)),
             m.group(2))
    for m in _UNREAD.finditer(text):  # "<word> degrees" that no rule above could read
        if m.group(1).lower() not in _NUMWORD and not overlaps(m.start(), m.end()):
            emit(m.start(), m.end(), m.group(1), None, m.group(2))
    return sorted(out, key=lambda o: o.span.start)


def _digits(raw: str) -> float | None:
    cleaned = raw.replace(",", "").replace("−", "-").replace("+", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def verify_span(obs: TypedObservation, text: str) -> bool:
    """The value must read back from the exact span of the visible text (W02-07)."""
    return text[obs.span.start:obs.span.end] == obs.span.text and obs.raw_value.lower() in obs.span.text.lower()


@dataclass(frozen=True)
class Predicate:
    property: str
    relation: str  # gt | ge | lt | le
    threshold: float
    unit: str = "C"


def evaluate(obs: TypedObservation, predicate: Predicate) -> str:
    """TRUE, FALSE or UNKNOWN; an interval that straddles the threshold is UNKNOWN."""
    if not obs.readable or obs.low is None or obs.high is None or obs.property != predicate.property:
        return "UNKNOWN"
    t = predicate.threshold
    lo, hi = obs.low, obs.high

    def all_satisfy() -> bool:
        if predicate.relation == "gt":
            return lo > t or (lo == t and not obs.low_inclusive)
        if predicate.relation == "ge":
            return lo >= t
        if predicate.relation == "lt":
            return hi < t or (hi == t and not obs.high_inclusive)
        return hi <= t

    def none_satisfy() -> bool:
        if predicate.relation == "gt":
            return hi < t or (hi == t and obs.high_inclusive) or (hi == t)
        if predicate.relation == "ge":
            return hi < t or (hi == t and not obs.high_inclusive)
        if predicate.relation == "lt":
            return lo > t or lo == t
        return lo > t or (lo == t and not obs.low_inclusive)

    if all_satisfy():
        return "TRUE"
    if none_satisfy():
        return "FALSE"
    return "UNKNOWN"


def observations_for(packets: Sequence[Any], resolver: Any, *, property: str = "temperature",
                     default_unit: str | None = None) -> list[TypedObservation]:
    """Typed observations for packets, each bound to its evidence version and resolved sensor."""
    out = []
    for p in packets:
        sensor = resolver.resolve(p.visible_text) if resolver is not None else None
        for obs in extract(p.visible_text, property=property, default_unit=default_unit,
                           evidence_ref=p.ref, sensor=sensor.canonical if sensor and sensor.unique else None):
            if sensor is not None and not sensor.unique and obs.readable:
                obs = TypedObservation("UNKNOWN", "sensor identity ambiguous", None, obs.property, None, None,
                                       None, False, False, obs.unit, obs.unit_from_registry, obs.raw_value,
                                       obs.span, obs.evidence_ref, obs.time)
            out.append(obs)
    return out


def summary(obs: Sequence[TypedObservation]) -> Mapping[str, int]:
    return {"ok": sum(o.readable for o in obs), "unknown": sum(not o.readable for o in obs)}
