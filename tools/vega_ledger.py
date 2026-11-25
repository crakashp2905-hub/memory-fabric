#!/usr/bin/env python3
"""Task-to-evidence ledger for the Vega-CDM checklist (VEGA-CDM-009, 180).

    python tools/vega_ledger.py --check [--history] [--resolve-tests]
    python tools/vega_ledger.py --write          # regenerate the rendered matrix

Spec: ``docs/checklists/VEGA_CAUSAL_MEMORY_CHECKLIST.md`` (180 tasks).
Ledger: ``research/checklist/vega-cdm-ledger.json``. Statuses, in order::

    NOT_STARTED < IMPLEMENTED < VALIDATED < MODEL_VALIDATED

plus ``BLOCKED`` (says what it is blocked on). ``IMPLEMENTED`` names evidence
files that exist; ``VALIDATED`` also names tests that exist and the 40-hex commit
that contains them; ``MODEL_VALIDATED`` also names a result file recording real
inference (``evidence_level`` starting ``VEGA_MODEL``) and a model digest. No
task is completed on documentation or a mock-only test alone (180): a
``VALIDATED`` entry must name at least one test, and a docs-only evidence list
is refused.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLANS = {
    "s00": {"spec": ROOT / "docs" / "checklists" / "VEGA_CAUSAL_MEMORY_CHECKLIST.md",
            "ledger": ROOT / "research" / "checklist" / "vega-cdm-ledger.json",
            "page": ROOT / "research" / "checklist" / "VEGA_CDM_EVIDENCE_MATRIX.md",
            "task": r"^- \[ \] \*\*(VEGA-CDM-(\d{3})) — (.+?)\*\*\s*$", "done": r"^\s*\*\*Done when:\*\* (.+?)\s*$",
            "section": r"^### (S\d{2})\. (.+?)\s*$", "title": "Vega-CDM evidence matrix"},
    "next": {"spec": ROOT / "docs" / "checklists" / "VEGA_NEXT_CORRECTNESS_CHECKLIST_2026-11-25.md",
             "ledger": ROOT / "research" / "checklist" / "vega-next-ledger.json",
             "page": ROOT / "research" / "checklist" / "VEGA_NEXT_EVIDENCE_MATRIX.md",
             "task": r"^- \[ \] \*\*(W(\d{2})-\d{2}) — (.+?)\*\*\s*$", "done": r"^\s*\*\*Acceptance:\*\* (.+?)\s*$",
             "section": r"^### (W\d{2}) — (.+?)\s*$", "title": "Vega next evidence matrix"},
}
PLAN = "s00"
SPEC = PLANS[PLAN]["spec"]
LEDGER = PLANS[PLAN]["ledger"]
PAGE = PLANS[PLAN]["page"]


def use(plan: str) -> None:
    """Point the module at one plan's spec, ledger and rendered page."""
    global PLAN, SPEC, LEDGER, PAGE, _TASK, _DONE, _SECTION
    cfg = PLANS[plan]
    PLAN, SPEC, LEDGER, PAGE = plan, cfg["spec"], cfg["ledger"], cfg["page"]
    _TASK, _DONE, _SECTION = re.compile(cfg["task"]), re.compile(cfg["done"]), re.compile(cfg["section"])
ORDER = ("NOT_STARTED", "IMPLEMENTED", "VALIDATED", "MODEL_VALIDATED")
STATUSES = frozenset(ORDER) | {"BLOCKED"}
_TASK = re.compile(r"^- \[ \] \*\*(VEGA-CDM-(\d{3})) — (.+?)\*\*\s*$")
_DONE = re.compile(r"^\s*\*\*Done when:\*\* (.+?)\s*$")
_SECTION = re.compile(r"^### (S\d{2})\. (.+?)\s*$")
_TEST = re.compile(r"^tests/test_[A-Za-z0-9_]+\.py(::[A-Za-z0-9_]+){0,2}$")
FIELDS = {"status", "evidence", "tests", "verified_sha", "note", "blocked_on", "model_result"}


def parse_spec(path: Path | None = None) -> dict[str, Any]:
    text = (path or SPEC).read_text(encoding="utf-8")
    tasks: dict[str, dict[str, str]] = {}
    section, current = "", None
    for line in text.splitlines():
        if m := _SECTION.match(line):
            section = m.group(1)
        elif m := _TASK.match(line):
            current = m.group(1)
            tasks[current] = {"section": section, "title": m.group(3)}
        elif current and (m := _DONE.match(line)):
            tasks[current]["done_when"] = m.group(1)
            current = None
    return {"sha256": hashlib.sha256(text.encode()).hexdigest(), "tasks": tasks}


def load() -> dict[str, Any]:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def dump(ledger: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def validate(ledger: dict[str, Any], spec: dict[str, Any], history: bool = False) -> list[str]:
    problems: list[str] = []
    if ledger.get("spec_sha256") != spec["sha256"]:
        problems.append("ledger was built from another version of the spec")
    tasks = ledger.get("tasks", {})
    if set(tasks) != set(spec["tasks"]):
        problems.append(f"task ids differ from the spec: {sorted(set(tasks) ^ set(spec['tasks']))[:5]}")
    for tid, entry in sorted(tasks.items()):
        status = entry.get("status")
        if status not in STATUSES:
            problems.append(f"{tid}: unknown status {status!r}")
            continue
        if set(entry) - FIELDS:
            problems.append(f"{tid}: unknown fields {sorted(set(entry) - FIELDS)}")
        if status == "NOT_STARTED":
            continue
        if status == "BLOCKED" and not entry.get("blocked_on"):
            problems.append(f"{tid}: BLOCKED must say what it is blocked on")
        evidence = entry.get("evidence", [])
        if not evidence and status != "BLOCKED":
            problems.append(f"{tid}: {status} needs evidence files")
        for rel in evidence:
            if not (ROOT / rel).exists():
                problems.append(f"{tid}: evidence {rel} does not exist")
        if status in ("VALIDATED", "MODEL_VALIDATED"):
            tests = entry.get("tests", [])
            if not tests:
                problems.append(f"{tid}: {status} needs at least one test")
            if evidence and all(rel.endswith(".md") for rel in evidence):
                problems.append(f"{tid}: documentation alone cannot validate a task")
            for ref in tests:
                if not _TEST.match(ref) or not (ROOT / ref.split("::")[0]).is_file():
                    problems.append(f"{tid}: test {ref} is malformed or missing")
            sha = entry.get("verified_sha", "")
            if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
                problems.append(f"{tid}: {status} needs a 40-hex verified_sha")
            elif history:
                if _git("merge-base", "--is-ancestor", sha, "HEAD").returncode != 0:
                    problems.append(f"{tid}: {sha[:7]} is not an ancestor of HEAD")
                for rel in [*evidence, *{t.split('::')[0] for t in tests}]:
                    if _git("cat-file", "-e", f"{sha}:{rel}").returncode != 0:
                        problems.append(f"{tid}: {rel} is not in {sha[:7]}")
        if status == "MODEL_VALIDATED":
            result = entry.get("model_result", "")
            try:
                data = json.loads((ROOT / result).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                problems.append(f"{tid}: model_result {result!r} is unreadable")
                continue
            level = str(data.get("evidence_level", data.get("status", "")))
            blob = json.dumps(data)
            # The pinned vega-U engine, or a real local model's weight digest; never a declared fake.
            digest = "78f96be7c6a0" in blob or bool(re.search(r'"digest": "sha256:[0-9a-f]{64}"', blob))
            if "sha256:fake" in blob or not (level.startswith("VEGA_MODEL") or level.startswith("LOCAL_MODEL")) \
                    or not digest:
                problems.append(f"{tid}: model_result does not record real inference with the pinned digest")
    return problems


def unresolved_tests(ledger: dict[str, Any]) -> list[str]:
    refs = sorted({t for e in ledger["tasks"].values() for t in e.get("tests", [])})
    if not refs:
        return []
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *refs],
                          cwd=ROOT, capture_output=True, text=True)
    return [] if done.returncode == 0 else [done.stdout[-1500:]]


def summary(ledger: dict[str, Any]) -> dict[str, int]:
    out = {s: 0 for s in (*ORDER, "BLOCKED")}
    for entry in ledger["tasks"].values():
        out[entry["status"]] += 1
    return out


def render(ledger: dict[str, Any], spec: dict[str, Any]) -> str:
    lines = [f"# {PLANS[PLAN]['title']}", "",
             "Generated by `python tools/vega_ledger.py --write` from "
             "[vega-cdm-ledger.json](vega-cdm-ledger.json). One row per checklist task; "
             "no row is complete on documentation or a mock-only test alone.", "",
             "| status | count |", "|---|---:|"]
    lines += [f"| `{k}` | {v} |" for k, v in summary(ledger).items()]
    current = ""
    for tid, task in spec["tasks"].items():
        if task["section"] != current:
            current = task["section"]
            lines += ["", f"## {current}", "", "| task | status | tests | note |", "|---|---|---|---|"]
        e = ledger["tasks"][tid]
        tests = "<br>".join(f"`{t.removeprefix('tests/')}`" for t in e.get("tests", [])[:3])
        note = (e.get("blocked_on") or e.get("note") or "").replace("|", "/")
        lines.append(f"| {tid} | `{e['status']}` | {tests} | {note} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if "--plan" in argv:
        use(argv[argv.index("--plan") + 1])
    spec = parse_spec()
    if "--init" in argv:
        dump({"spec": SPEC.relative_to(ROOT).as_posix(), "spec_sha256": spec["sha256"],
              "tasks": {t: {"status": "NOT_STARTED"} for t in spec["tasks"]}})
        return 0
    ledger = load()
    if "--write" in argv:
        PAGE.write_text(render(ledger, spec), encoding="utf-8")
    problems = validate(ledger, spec, history="--history" in argv)
    if "--resolve-tests" in argv:
        problems += unresolved_tests(ledger)
    if "--check" in argv and PAGE.is_file() and PAGE.read_text(encoding="utf-8") != render(ledger, spec):
        problems.append("the evidence matrix is stale; run --write")
    print("\n".join(problems) if problems else f"PASS {json.dumps(summary(ledger))}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
