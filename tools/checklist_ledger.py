#!/usr/bin/env python3
"""The task ledger for the agent-validation checklist (checklist W23-09).

    python tools/checklist_ledger.py --check            # validate the ledger against the spec
    python tools/checklist_ledger.py --check --history  # also verify each commit in git history
    python tools/checklist_ledger.py --check --resolve-tests  # every test reference is collected
    python tools/checklist_ledger.py --write            # regenerate the rendered ledger page
    python tools/checklist_ledger.py --init             # create a ledger with every task TODO

The specification (``docs/checklists/AGENT_VALIDATION_CHECKLIST_2026-11-20.md``)
lists 240 tasks. The ledger (``research/checklist/agent-validation-ledger.json``)
records one status per task and the evidence for it. Statuses are ordered and are
not interchangeable::

    TODO < IMPLEMENTED < TESTED < SCRIPTED_QUALIFIED < LOCAL_MODEL_QUALIFIED < RESEARCH_QUALIFIED

plus ``BLOCKED_EXTERNAL`` for work that needs a third party (an independent
review, a real pilot, an installed model this environment does not have).

The validator refuses a status the evidence cannot carry:

* anything above ``TODO`` names evidence files that exist in the tree;
* ``TESTED`` and above also name tests that exist, and the 40-hex commit that
  verified them (a committed file cannot name its own commit, so it is an earlier
  one; ``--history`` checks that it is an ancestor of HEAD and contains the evidence);
* ``SCRIPTED_QUALIFIED`` and above also name a gate report under ``research/``;
* ``LOCAL_MODEL_QUALIFIED`` names a result that records a model digest and real
  inference; ``RESEARCH_QUALIFIED`` names a frozen registration;
* ``BLOCKED_EXTERNAL`` says what it is blocked on.

No task is passed because code exists or a unit test passes: those are
``IMPLEMENTED`` and ``TESTED``, and the qualifying statuses need their own evidence.
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
SPEC = ROOT / "docs" / "checklists" / "AGENT_VALIDATION_CHECKLIST_2026-11-20.md"
LEDGER = ROOT / "research" / "checklist" / "agent-validation-ledger.json"
PAGE = ROOT / "research" / "checklist" / "AGENT_VALIDATION_LEDGER.md"
SCHEMA_ID = "memory-fabric.checklist-ledger.v1"

ORDER = ("TODO", "IMPLEMENTED", "TESTED", "SCRIPTED_QUALIFIED", "LOCAL_MODEL_QUALIFIED",
         "RESEARCH_QUALIFIED")
STATUSES = frozenset(ORDER) | {"BLOCKED_EXTERNAL"}
_TASK = re.compile(r"^- \[ \] \*\*(W(\d{2})-(\d{2})) \[(P[01])\]\*\* (.+?)\s*$")
_ACCEPT = re.compile(r"^\s*\*\*Acceptance:\*\* (.+?)\s*$")
_WORKSTREAM = re.compile(r"^### (\d{2})\. (.+?) — (W\d{2}) \((.+)\)\s*$")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_TEST_REF = re.compile(r"^tests/test_[A-Za-z0-9_]+\.py(::[A-Za-z0-9_]+){0,2}$")
TASK_FIELDS = {"status", "evidence", "tests", "verified_sha", "note", "blocked_on"}


def _rank(status: str) -> int:
    return ORDER.index(status) if status in ORDER else -1


def parse_spec(path: Path = SPEC) -> dict[str, Any]:
    tasks: dict[str, dict[str, Any]] = {}
    workstreams: dict[str, str] = {}
    current: str | None = None
    workstream: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = _WORKSTREAM.match(line)
        if heading:
            workstream = heading.group(3)
            workstreams[workstream] = heading.group(2)
            continue
        match = _TASK.match(line)
        if match:
            task_id = match.group(1)
            if task_id in tasks:
                raise ValueError(f"duplicate task {task_id} in the specification")
            tasks[task_id] = {"workstream": workstream, "priority": match.group(4),
                              "title": match.group(5), "acceptance": None}
            current = task_id
            continue
        accept = _ACCEPT.match(line)
        if accept and current is not None and tasks[current]["acceptance"] is None:
            tasks[current]["acceptance"] = accept.group(1)
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "tasks": tasks,
            "workstreams": workstreams}


def _git(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def validate(ledger: dict[str, Any], spec: dict[str, Any], root: Path = ROOT,
             history: bool = False) -> list[str]:
    problems: list[str] = []
    if ledger.get("schema_id") != SCHEMA_ID:
        problems.append("ledger schema_id is not " + SCHEMA_ID)
    if ledger.get("spec_sha256") != spec["sha256"]:
        problems.append("ledger is for a different revision of the specification")
    tasks = ledger.get("tasks", {})
    missing = sorted(set(spec["tasks"]) - set(tasks))
    extra = sorted(set(tasks) - set(spec["tasks"]))
    if missing:
        problems.append(f"{len(missing)} specification tasks missing from the ledger: {missing[:5]}")
    if extra:
        problems.append(f"ledger has tasks the specification does not: {extra[:5]}")
    for task_id in sorted(set(tasks) & set(spec["tasks"])):
        entry = tasks[task_id]
        unknown = set(entry) - TASK_FIELDS
        if unknown:
            problems.append(f"{task_id}: unknown fields {sorted(unknown)}")
        status = entry.get("status")
        if status not in STATUSES:
            problems.append(f"{task_id}: unknown status {status!r}")
            continue
        evidence = entry.get("evidence") or []
        tests = entry.get("tests") or []
        if status == "BLOCKED_EXTERNAL":
            if not (entry.get("blocked_on") or "").strip():
                problems.append(f"{task_id}: BLOCKED_EXTERNAL must say what it is blocked on")
            continue
        if status == "TODO":
            continue
        if not evidence:
            problems.append(f"{task_id}: {status} needs evidence files")
        for path in evidence:
            if not (root / path).exists():
                problems.append(f"{task_id}: evidence {path} does not exist")
        if _rank(status) >= _rank("TESTED"):
            if not tests:
                problems.append(f"{task_id}: {status} needs the tests that verify it")
            for ref in tests:
                if not _TEST_REF.fullmatch(ref):
                    problems.append(f"{task_id}: test reference {ref!r} is not tests/test_x.py[::Class[::test]]")
                elif not (root / ref.split("::")[0]).is_file():
                    problems.append(f"{task_id}: test file {ref.split('::')[0]} does not exist")
            sha = entry.get("verified_sha")
            if not (isinstance(sha, str) and _SHA40.fullmatch(sha)):
                problems.append(f"{task_id}: {status} needs the 40-hex commit that verified it")
            elif history:
                if _git("merge-base", "--is-ancestor", sha, "HEAD", root=root).returncode != 0:
                    problems.append(f"{task_id}: verified_sha {sha[:12]} is not an ancestor of HEAD")
                else:
                    for path in [*evidence, *(ref.split("::")[0] for ref in tests)]:
                        if _git("cat-file", "-e", f"{sha}:{path}", root=root).returncode != 0:
                            problems.append(f"{task_id}: {path} is not in verified commit {sha[:12]}")
        if _rank(status) >= _rank("SCRIPTED_QUALIFIED") and not any(
                path.startswith("research/") and "gate" in path for path in evidence):
            problems.append(f"{task_id}: {status} needs a gate report under research/")
        if status == "LOCAL_MODEL_QUALIFIED":
            ok = False
            for path in evidence:
                target = root / path
                if target.suffix == ".json" and target.is_file():
                    text = target.read_text(encoding="utf-8")
                    ok |= '"model_digest"' in text and '"inference_completed": true' in text
            if not ok:
                problems.append(f"{task_id}: LOCAL_MODEL_QUALIFIED needs a result with a model "
                                "digest and completed inference")
        if status == "RESEARCH_QUALIFIED" and not any(
                path.startswith("research/prereg/") for path in evidence):
            problems.append(f"{task_id}: RESEARCH_QUALIFIED needs a frozen registration")
    return problems


def unresolved_tests(ledger: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Test references that pytest does not collect (a guessed class or test name)."""
    refs = sorted({ref for entry in ledger.get("tasks", {}).values()
                   for ref in entry.get("tests") or [] if _TEST_REF.fullmatch(ref)})
    files = sorted({ref.split("::")[0] for ref in refs if (root / ref.split("::")[0]).is_file()})
    if not files:
        return []
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                           "-p", "no:cacheprovider", *files],
                          cwd=root, capture_output=True, text=True)
    nodes = [line.strip() for line in done.stdout.splitlines() if "::" in line]
    collected_files = {node.split("::")[0] for node in nodes}
    return [ref for ref in refs
            if not (ref in collected_files
                    or any(node == ref or node.startswith(ref + "::") for node in nodes))]


def summary(ledger: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    by_status: dict[str, int] = {status: 0 for status in (*ORDER, "BLOCKED_EXTERNAL")}
    by_workstream: dict[str, dict[str, int]] = {}
    for task_id, meta in spec["tasks"].items():
        status = ledger["tasks"].get(task_id, {}).get("status", "TODO")
        by_status[status] = by_status.get(status, 0) + 1
        bucket = by_workstream.setdefault(meta["workstream"], {})
        bucket[status] = bucket.get(status, 0) + 1
    return {"total": len(spec["tasks"]), "by_status": by_status, "by_workstream": by_workstream}


def render(ledger: dict[str, Any], spec: dict[str, Any]) -> str:
    totals = summary(ledger, spec)
    lines = ["# Agent-validation checklist ledger", "",
             "Generated by `tools/checklist_ledger.py --write` from "
             "`research/checklist/agent-validation-ledger.json`; do not edit by hand. "
             "Specification: [`AGENT_VALIDATION_CHECKLIST_2026-11-20.md`]"
             "(../../docs/checklists/AGENT_VALIDATION_CHECKLIST_2026-11-20.md).", "",
             "Statuses are ordered and not interchangeable: `TODO < IMPLEMENTED < TESTED < "
             "SCRIPTED_QUALIFIED < LOCAL_MODEL_QUALIFIED < RESEARCH_QUALIFIED`, plus "
             "`BLOCKED_EXTERNAL`. `TESTED` means a test exists and passed at the named commit; "
             "it is not a qualification, and none of these statuses is a production qualification.",
             "", "## Totals", "", "| status | tasks |", "|---|---:|"]
    lines += [f"| `{status}` | {count} |" for status, count in totals["by_status"].items()]
    lines += ["", f"Total: {totals['total']} tasks.", "", "## By workstream", "",
              "| workstream | title | " + " | ".join(f"`{s}`" for s in (*ORDER, "BLOCKED_EXTERNAL"))
              + " |", "|---|---|" + "---:|" * (len(ORDER) + 1)]
    for workstream, title in spec["workstreams"].items():
        counts = totals["by_workstream"].get(workstream, {})
        lines.append(f"| {workstream} | {title} | " + " | ".join(
            str(counts.get(status, 0)) for status in (*ORDER, "BLOCKED_EXTERNAL")) + " |")
    lines += ["", "## Tasks", "", "| task | P | status | evidence | note |", "|---|---|---|---|---|"]
    for task_id, meta in spec["tasks"].items():
        entry = ledger["tasks"].get(task_id, {})
        evidence = "<br>".join(f"`{path}`" for path in (entry.get("evidence") or [])[:4])
        note = (entry.get("note") or entry.get("blocked_on") or "").replace("|", "\\|")
        lines.append(f"| {task_id} | {meta['priority']} | `{entry.get('status', 'TODO')}` | "
                     f"{evidence} | {note} |")
    return "\n".join(lines) + "\n"


def initial(spec: dict[str, Any]) -> dict[str, Any]:
    return {"schema_id": SCHEMA_ID,
            "spec": SPEC.relative_to(ROOT).as_posix(), "spec_sha256": spec["sha256"],
            "tasks": {task_id: {"status": "TODO"} for task_id in spec["tasks"]}}


def load(path: Path = LEDGER) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(ledger: dict[str, Any], path: Path = LEDGER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=1, sort_keys=False) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    spec = parse_spec()
    if "--init" in argv:
        if LEDGER.exists():
            print(f"{LEDGER.relative_to(ROOT)} exists; refusing to overwrite it")
            return 1
        dump(initial(spec))
        print(f"wrote {LEDGER.relative_to(ROOT)}")
        return 0
    ledger = load()
    if "--write" in argv:
        PAGE.write_text(render(ledger, spec), encoding="utf-8")
        print(f"wrote {PAGE.relative_to(ROOT)}")
        return 0
    if "--check" in argv:
        problems = validate(ledger, spec, history="--history" in argv)
        if "--resolve-tests" in argv:
            problems.extend(f"test reference not collected by pytest: {ref}"
                            for ref in unresolved_tests(ledger))
        if not PAGE.is_file() or PAGE.read_text(encoding="utf-8") != render(ledger, spec):
            problems.append("AGENT_VALIDATION_LEDGER.md is stale; run tools/checklist_ledger.py --write")
        print("\n".join(problems) if problems else "PASS")
        return 1 if problems else 0
    print(json.dumps(summary(ledger, spec), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
