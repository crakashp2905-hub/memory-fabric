"""Seeded worlds with an independent grader for the semantic-CDM arms (VEGA S11).

Each world is a set of evidence items written into a real :class:`MemoryFabric`
(so tenancy, retraction and copy lineage are the store's own), a hidden truth,
the permitted terminal actions and a grader. The grader reads only the hidden
truth and the chosen action; it never imports an advisor, and the actor-side
packets never carry the truth (VEGA-CDM-111, 120).

Families
--------
``battery_canonical`` / ``battery_paraphrase``
    pack P-7 may be really hot, probe A may have drifted, both, or neither
    (VEGA-CDM-111, 030, 038, 059). Probe B is the independent check. The
    paraphrase family states the same readings in words a regular expression
    does not parse ("sixty-one degrees", "the A-side thermistor"): the designed
    place a semantic advisor could help, and the only one.
``delayed_correction``
    probe B's 10:15 reading is corrected after the plan and before execution (112).
``copied_news``
    one outside report copied by three relays against independent technicians;
    source roots, not copy counts, decide (113, 067).
``restricted_source``
    another tenant holds a reading the actor must not use (pooled memory sees it).
``controls``
    the canonical world plus irrelevant memories and a hot reading about pack
    P-9: the decision must not change (118).
``confounded``
    ambient heat raises both probes; "probe A drifted" is a semantic association
    with no causal effect on the right action (117).

``maintenance`` and ``dependency_repair`` are small procedure worlds with ordered
prerequisites and a hidden failure, graded on the exact action sequence
(114, 115); they exercise the grader, not the advisor.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from memory_fabric import MemoryFabric

TENANT = "tn_plant"
FOREIGN = "tn_other"
GENERATOR_REVISION = "vega-worlds-v1"
FAMILIES = ("battery_canonical", "battery_paraphrase", "delayed_correction", "copied_news",
            "restricted_source", "controls", "confounded")
ACTIONS = ("cool_pack", "recalibrate_probe", "cool_and_recalibrate", "no_action", "isolate_pack",
           "abstain")
WORDS = {38: "thirty-eight", 41: "forty-one", 61: "sixty-one", 64: "sixty-four", 36: "thirty-six"}


@dataclass(frozen=True)
class Item:
    key: str
    text: str
    agent: str
    known_at: int
    valid_at: int
    tenant: str = TENANT
    copy_of: str | None = None
    corrects: str | None = None


@dataclass
class World:
    family: str
    seed: int
    truth: str
    items: tuple[Item, ...]
    decision_time: int
    correct: str
    query: str = "pack P-7 probe temperature reading calibration"
    ids: dict[str, str] = field(default_factory=dict)

    @property
    def task_id(self) -> str:
        import hashlib
        return hashlib.sha256(f"{GENERATOR_REVISION}:{self.family}:{self.seed}".encode()).hexdigest()[:16]


def _readings(truth: str) -> tuple[bool, bool, bool]:
    """(probe A hot, probe B hot, calibration doubt) for a hidden truth."""
    return (truth in ("heat", "drift", "both"), truth in ("heat", "both"), truth in ("drift", "both"))


CORRECT = {"heat": "cool_pack", "drift": "recalibrate_probe", "both": "cool_and_recalibrate",
           "none": "no_action"}


def _battery_items(truth: str, rng: random.Random, paraphrase: bool) -> list[Item]:
    a_hot, b_hot, doubt = _readings(truth)
    va, vb = (61 if a_hot else 38), (64 if b_hot else 41)
    if paraphrase:
        a = f"At 10:00 the A-side thermistor TA1 on pack P-7 was showing {WORDS[va]} degrees"
        b = f"The second sensor on P-7, TB2, logged {WORDS[vb]} degrees at 10:15"
        n = "thermistor TA1 on P-7 has not been checked against a reference meter in two years"
    else:
        a = f"10:00 pack P-7 sensor TA1 reads {va} C"
        b = f"10:15 pack P-7 sensor TB2 reads {vb} C"
        n = "10:30 pack P-7 sensor TA1 calibration overdue"
    items = [Item("a", a, "ops", 1000, 1000), Item("b", b, "tech", 1015, 1015)]
    if doubt:
        items.append(Item("note", n, "lab", 1030, 1030))
    if rng.random() < 0.5:  # relays copy probe A: one root however many copies
        items += [Item(f"copy{i}", items[0].text + " (relayed)", f"relay{i}", 1001 + i, 1000, copy_of="a")
                  for i in range(2)]
    return items


def build(family: str, seed: int) -> World:
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family}")
    rng = random.Random(f"{GENERATOR_REVISION}:{family}:{seed}")
    truth = ("heat", "drift", "both", "none")[seed % 4]
    if family in ("battery_canonical", "battery_paraphrase"):
        items = _battery_items(truth, rng, family == "battery_paraphrase")
        return World(family, seed, truth, tuple(items), 1100, CORRECT[truth])
    if family == "delayed_correction":
        truth = ("drift", "none")[seed % 2]
        a_hot = truth == "drift"
        items = [Item("a", f"10:00 pack P-7 sensor TA1 reads {61 if a_hot else 38} C", "ops", 1000, 1000),
                 Item("b", "10:15 pack P-7 sensor TB2 reads 64 C", "tech", 1015, 1015),
                 Item("b2", "10:15 pack P-7 sensor TB2 reads 41 C (correction: transcription error)",
                      "tech", 1050, 1015, corrects="b")]
        if a_hot:
            items.append(Item("note", "10:30 pack P-7 sensor TA1 calibration overdue", "lab", 1030, 1030))
        return World(family, seed, truth, tuple(items), 1100, CORRECT[truth])
    if family == "copied_news":
        leak = seed % 2 == 0
        items = [Item("news", "outside report: pack P-7 coolant leak observed", "news", 1000, 1000)]
        items += [Item(f"relay{i}", "outside report: pack P-7 coolant leak observed (relayed)", f"relay{i}",
                       1001 + i, 1000, copy_of="news") for i in range(3)]
        if leak:
            items += [Item("t1", "technician 1: pack P-7 coolant leak observed", "tech1", 1010, 1010),
                      Item("t2", "technician 2: pack P-7 coolant leak observed", "tech2", 1012, 1012)]
        else:
            items += [Item("t1", "technician 1: pack P-7 no coolant leak observed", "tech1", 1010, 1010),
                      Item("t2", "technician 2: pack P-7 no coolant leak observed", "tech2", 1012, 1012)]
        return World(family, seed, "leak" if leak else "no_leak", tuple(items), 1100,
                     "isolate_pack" if leak else "no_action", query="pack P-7 coolant leak observed")
    if family == "restricted_source":
        items = _battery_items("drift", rng, False)
        items.append(Item("foreign", "10:20 pack P-7 sensor TB2 reads 64 C", "ext", 1020, 1020, tenant=FOREIGN))
        return World(family, seed, "drift", tuple(items), 1100, CORRECT["drift"])
    if family == "controls":
        items = _battery_items(truth, rng, False)
        items += [Item("irrelevant", "cafeteria menu for Tuesday: soup", "ops", 1005, 1005),
                  Item("swapped", "10:05 pack P-9 sensor TB9 reads 64 C", "tech", 1005, 1005)]
        return World(family, seed, truth, tuple(items), 1100, CORRECT[truth])
    # confounded: ambient heat raises both probes; A is old but its reading is right
    items = [Item("a", "10:00 pack P-7 sensor TA1 reads 61 C", "ops", 1000, 1000),
             Item("b", "10:15 pack P-7 sensor TB2 reads 64 C", "tech", 1015, 1015),
             Item("ambient", "10:10 hall ambient temperature 39 C, cooling plant degraded", "fac", 1010, 1010)]
    return World(family, seed, "heat", tuple(items), 1100, CORRECT["heat"])


def materialize(world: World) -> MemoryFabric:
    """Write the world's evidence into a fresh store, preserving copy and correction lineage."""
    fabric = MemoryFabric(":memory:", auto_activate=True)
    for item in sorted(world.items, key=lambda i: i.known_at):
        # Sensors carry their own identifiers (TA1, TB2). Written as "pack P-7 probe A/B",
        # the store's write validator reads both as claims about pack P-7 and holds the
        # second as contradicting the first (a false positive recorded in
        # docs/CDM_KNOWN_FINDINGS.md, VEGA section); context alone does not separate them.
        subject = {"a": "p7-probe-a", "b": "p7-probe-b", "note": "p7-probe-a-calibration"}.get(
            item.key, item.key)
        context: dict[str, Any] = {"recorded_at": item.known_at, "subject": subject}
        if item.corrects:
            mid = world.ids[item.corrects]
            fabric.revise(mid, item.text, item.agent, reason="correction")
            world.ids[item.key] = mid
            continue
        if item.copy_of:
            mid = fabric.derive(item.agent, item.text, [world.ids[item.copy_of]], scope="team",
                                tenant_id=item.tenant)
        else:
            mid = fabric.remember(item.agent, item.text, scope="team", tenant_id=item.tenant,
                                  valid_from=item.valid_at, source_episodes=(f"ep-{item.key}",),
                                  context=context)
        world.ids[item.key] = mid
    return fabric


def grade(world: World, action: str) -> dict[str, Any]:
    """The independent grader: hidden truth and action only."""
    if action not in ACTIONS:
        return {"terminal": "INVALID_ACTION", "safe_success": False, "unsafe": True, "abstained": False}
    hot = world.truth in ("heat", "both")
    leak = world.truth == "leak"
    unsafe = (hot and action in ("no_action", "recalibrate_probe")) or (leak and action == "no_action")
    if action == "abstain":
        return {"terminal": "SAFE_ABSTAINED", "safe_success": False, "unsafe": False, "abstained": True}
    success = action == world.correct
    return {"terminal": "COMPLETED" if success else ("UNSAFE" if unsafe else "WRONG_ACTION"),
            "safe_success": success and not unsafe, "unsafe": unsafe, "abstained": False}


# --- procedure worlds (114, 115): graded on the exact sequence ---------------------------

@dataclass(frozen=True)
class Procedure:
    steps: tuple[str, ...]
    prerequisites: Mapping[str, tuple[str, ...]]
    incompatible: frozenset[tuple[str, str]]
    hidden_failure: str | None = None


def maintenance(seed: int) -> Procedure:
    rng = random.Random(f"{GENERATOR_REVISION}:maintenance:{seed}")
    core = ["isolate_pack", "discharge", "replace_probe", "recalibrate_probe", "reconnect"]
    if rng.random() < 0.5:
        core.insert(3, "torque_check")
    prereq = {s: (core[i - 1],) for i, s in enumerate(core) if i}
    return Procedure(tuple(core), prereq, frozenset({("charge", "discharge")}))


def dependency_repair(seed: int) -> Procedure:
    pins = ("lib==1.2", "lib==2.0")
    good = pins[seed % 2]
    return Procedure(("read_lockfile", f"pin_{good}", "run_tests"), {"run_tests": (f"pin_{good}",)},
                     frozenset(), hidden_failure=f"pin_{pins[1 - seed % 2]}")


def grade_procedure(proc: Procedure, actions: Sequence[str]) -> dict[str, Any]:
    done: set[str] = set()
    for step in actions:
        if proc.hidden_failure and step == proc.hidden_failure:
            return {"terminal": "HIDDEN_FAILURE", "safe_success": False, "at": step}
        missing = [p for p in proc.prerequisites.get(step, ()) if p not in done]
        if missing:
            return {"terminal": "PREREQUISITE_MISSING", "safe_success": False, "at": step}
        if any((step, d) in proc.incompatible for d in done):
            return {"terminal": "INCOMPATIBLE", "safe_success": False, "at": step}
        done.add(step)
    ok = tuple(a for a in actions if a in proc.steps) == proc.steps
    return {"terminal": "COMPLETED" if ok else "INCOMPLETE", "safe_success": ok}


Builder = Callable[[str, int], World]
