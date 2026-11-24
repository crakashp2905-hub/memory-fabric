"""First-party retrieval baselines under one budget (W11-05).

    python -m benchmarks.outcome_retrieval_baselines --seeds 4

Six context-selection strategies answer the same question, "what is the
current reading?", from the same store, under the same budget (at most ``K``
memories and ``CHARS`` characters), with the same deterministic reader. Only the
selection differs:

``recency``          the K most recently written memories
``lexical``          token-overlap ranking over every memory written, top K
``fixed_top_k``      the first K memories ever written, regardless of query
``full_context``     every memory, newest first, until the character budget is full
                     (no item cap: it is the character-budgeted "show everything" arm)
``summary``          a first-party summary: the latest statement per subject
``governed``         Memory Fabric governed retrieval (withdrawn memories excluded)

These are first-party implementations written for this harness, not
reproductions of any published system. The report records the items and
characters each strategy actually used, so no baseline gets a smaller budget
than the governed arm.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Callable, Mapping, Sequence

SCHEMA_ID = "memory-fabric.retrieval-baselines.v1"
K = 4
CHARS = 400
NUMBER = re.compile(r"reading is (\d+)")


def world(seed: int) -> dict[str, Any]:
    from memory_fabric import MemoryFabric

    fabric = MemoryFabric(":memory:", auto_activate=True)
    initial, corrected = 40 + seed, 60 + seed
    old = fabric.remember("obs", f"instrument-A reading is {initial} units (initial).", scope="team")
    for index in range(6):  # unrelated traffic written after the first reading
        fabric.remember("ops", f"shift note {index}: corridor lights checked", scope="team")
    fabric.remember("obs", f"instrument-A reading is {corrected} units (correction).", scope="team")
    fabric.quarantine(old, reason="corrected by a newer observation", actor="obs")
    for index in range(3):  # more traffic after the correction
        fabric.remember("ops", f"shift note {6 + index}: badge reader serviced", scope="team")
    return {"fabric": fabric, "answer": corrected}


def _all(fabric: Any) -> list[tuple[str, str]]:
    """Every memory as written, oldest first, ignoring governance (the pooled view)."""
    rows = []
    for memory_id in fabric.state.memories:
        memory = fabric.get(memory_id)
        rows.append((memory.created_at, memory_id, memory.content))
    return [(memory_id, text) for _, memory_id, text in sorted(rows)]


def _within(items: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    used = 0
    for memory_id, text in items:
        if len(out) >= K or used + len(text) > CHARS:
            break
        out.append((memory_id, text))
        used += len(text)
    return out


def recency(fabric: Any, query: str) -> list[tuple[str, str]]:
    return _within(list(reversed(_all(fabric))))


def lexical(fabric: Any, query: str) -> list[tuple[str, str]]:
    """Token-overlap ranking over the raw pool (withdrawn memories included), newest wins ties."""
    terms = set(query.lower().split())
    pool = list(enumerate(_all(fabric)))
    scored = sorted(pool, key=lambda item: (-len(terms & set(item[1][1].lower().split())), -item[0]))
    return _within([row for _, row in scored if terms & set(row[1].lower().split())])


def fixed_top_k(fabric: Any, query: str) -> list[tuple[str, str]]:
    return _within(_all(fabric))


def full_context(fabric: Any, query: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    used = 0
    for memory_id, text in reversed(_all(fabric)):
        if used + len(text) > CHARS:
            break
        out.append((memory_id, text))
        used += len(text)
    return out


def summary(fabric: Any, query: str) -> list[tuple[str, str]]:
    """Latest statement per subject, most recently updated subjects first."""
    latest: dict[str, tuple[int, str, str]] = {}
    for index, (memory_id, text) in enumerate(_all(fabric)):
        subject = text.split(" reading is ")[0] if " reading is " in text else text.split(":")[0]
        latest[subject] = (index, memory_id, text)
    ordered = sorted(latest.values(), reverse=True)
    return _within([(memory_id, text) for _, memory_id, text in ordered])


def governed(fabric: Any, query: str) -> list[tuple[str, str]]:
    found = fabric.retrieve(agent_id="ops", query=query, k=K, method="lexical")
    return _within([(str(getattr(i, "memory_id", None) or getattr(i, "id")),
                     fabric.get(str(getattr(i, "memory_id", None) or getattr(i, "id"))).content)
                    for i in found])


STRATEGIES: Mapping[str, Callable[[Any, str], list[tuple[str, str]]]] = {
    "recency": recency, "lexical": lexical, "fixed_top_k": fixed_top_k,
    "full_context": full_context, "summary": summary, "governed": governed,
}


def reader(context: Sequence[tuple[str, str]]) -> int | None:
    """The same reader for every strategy: a correction wins, else the last reading seen."""
    readings = [(("(correction)" in text), index, int(m.group(1)))
                for index, (_, text) in enumerate(context) if (m := NUMBER.search(text))]
    if not readings:
        return None
    return max(readings)[2] if any(r[0] for r in readings) else readings[-1][2]


def run(seeds: int = 4) -> dict[str, Any]:
    rows = []
    for seed in range(seeds):
        item = world(seed)
        try:
            for name, strategy in STRATEGIES.items():
                context = strategy(item["fabric"], "instrument-A reading")
                answer = reader(context)
                rows.append({"seed": seed, "strategy": name, "answer": answer,
                             "correct": answer == item["answer"], "items": len(context),
                             "chars": sum(len(text) for _, text in context)})
        finally:
            item["fabric"].close()
    summary_rows = {name: {"accuracy": round(sum(r["correct"] for r in rows if r["strategy"] == name)
                                             / seeds, 4),
                           "max_items": max(r["items"] for r in rows if r["strategy"] == name),
                           "max_chars": max(r["chars"] for r in rows if r["strategy"] == name)}
                    for name in STRATEGIES}
    return {"schema_id": SCHEMA_ID, "population": "SCRIPTED_DEVELOPMENT",
            "budget": {"items": K, "chars": CHARS}, "first_party": True,
            "fidelity_note": "first-party strategies written for this harness; not reproductions "
                             "of any published system", "summary": summary_rows, "rows": rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(args.seeds)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    for name, row in report["summary"].items():
        print(f"{name:13s} accuracy {row['accuracy']}  items<={row['max_items']}  chars<={row['max_chars']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
