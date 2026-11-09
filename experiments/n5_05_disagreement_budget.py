"""Contract evidence for context assembly under an explicit disagreement budget."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.context_receipt import build_context  # noqa: E402

RESULT_PATH = ROOT / "research" / "results" / "n5-05-disagreement-budget.json"
MARKDOWN_PATH = ROOT / "research" / "results" / "n5-05-disagreement-budget.md"
TEST_PATH = ROOT / "research" / "results" / "n5-05-disagreement-tests.xml"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _open_set(fabric: MemoryFabric, first: str, second: str) -> str:
    left = fabric.remember("ops", first, scope="team")
    right = fabric.remember("inspector", second, scope="team")
    return fabric.challenge([left, right], evidence="unresolved contradictory reports")


def run() -> dict[str, Any]:
    junit = ET.parse(TEST_PATH).getroot()
    cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if cases < 9 or failures or errors or skipped:
        raise RuntimeError("N5-05 focused tests must pass with no skips")

    fixtures: dict[str, Any] = {}
    fabric = MemoryFabric(auto_activate=True, hold_suspicious=False)
    try:
        relevant_id = _open_set(
            fabric, "Pump P9 restart pressure is 6 bar.",
            "Pump P9 restart pressure is 9 bar.",
        )
        relevant = build_context(
            fabric, "reader", "Pump P9 restart pressure", mode="exact",
            budget=300, disagreement_budget=200,
        )
        fixtures["relevant_complete_set"] = {
            "hypothesis_set": relevant_id,
            "selected_kind": relevant.plan.items[0].kind,
            "status": relevant.plan.uncertainty[0]["status"],
            "alternatives_rendered": relevant.text.count("[DISPUTED"),
            "both_values_present": "6 bar" in relevant.text and "9 bar" in relevant.text,
            "budget_used": relevant.plan.disagreement_tokens,
            "budget": relevant.plan.disagreement_budget,
        }

        suffix = " calibrated by the night shift with repeated instrument verification" * 18
        large_id = _open_set(
            fabric, "Pump P10 restart pressure is 6 bar." + suffix,
            "Pump P10 restart pressure is 9 bar." + suffix,
        )
        large = build_context(
            fabric, "reader", "Pump P10 restart pressure", mode="exact",
            budget=300, disagreement_budget=50,
        )
        fixtures["over_budget_set"] = {
            "hypothesis_set": large_id,
            "selected_kind": large.plan.items[0].kind,
            "status": large.plan.uncertainty[0]["status"],
            "marker_rendered": "INSUFFICIENT" in large.text,
            "partial_values_rendered": "6 bar" in large.text or "9 bar" in large.text,
            "budget_used": large.plan.disagreement_tokens,
            "budget": large.plan.disagreement_budget,
        }

        private = fabric.remember(
            "ops", "Pump P11 restart pressure is 6 bar.", scope="team"
        )
        hidden = fabric.remember(
            "ops", "Pump P11 restart pressure is 9 bar.", scope="private"
        )
        private_id = fabric.challenge([private, hidden], evidence="restricted alternative")
        restricted = build_context(
            fabric, "reader", "Pump P11 restart pressure", mode="exact",
            budget=300, disagreement_budget=200,
        )
        fixtures["inaccessible_alternative"] = {
            "hypothesis_set": private_id,
            "selected_kind": restricted.plan.items[0].kind,
            "status": restricted.plan.uncertainty[0]["status"],
            "marker_rendered": "INSUFFICIENT" in restricted.text,
            "private_content_leaked": "9 bar" in restricted.text,
        }

        unrelated = build_context(
            fabric, "reader", "Valve V2 opening range", mode="exact", budget=300
        )
        fixtures["unrelated_set"] = {
            "uncertainty_count": len(unrelated.plan.uncertainty),
            "disagreement_items": sum(
                item.kind in {"disagreement", "insufficiency"}
                for item in unrelated.plan.items
            ),
        }

        no_room = build_context(
            fabric, "reader", "Pump P9 restart pressure", mode="exact",
            budget=20, disagreement_budget=0,
        )
        fixtures["marker_cannot_fit"] = {
            "selected_count": len(no_room.plan.items),
            "status": no_room.receipt["uncertainty"][0]["status"],
            "alternatives_selected": any(
                item.kind == "disagreement" for item in no_room.plan.items
            ),
        }
    finally:
        fabric.close()

    checks = (
        fixtures["relevant_complete_set"]["selected_kind"] == "disagreement"
        and fixtures["relevant_complete_set"]["status"] == "PRESERVED"
        and fixtures["relevant_complete_set"]["alternatives_rendered"] == 2
        and fixtures["relevant_complete_set"]["both_values_present"]
        and fixtures["over_budget_set"]["selected_kind"] == "insufficiency"
        and fixtures["over_budget_set"]["status"] == "INSUFFICIENT_DISAGREEMENT_BUDGET"
        and fixtures["over_budget_set"]["marker_rendered"]
        and not fixtures["over_budget_set"]["partial_values_rendered"]
        and fixtures["inaccessible_alternative"]["status"] == "INSUFFICIENT"
        and fixtures["inaccessible_alternative"]["marker_rendered"]
        and not fixtures["inaccessible_alternative"]["private_content_leaked"]
        and fixtures["unrelated_set"]["uncertainty_count"] == 0
        and fixtures["marker_cannot_fit"]["status"] == "INSUFFICIENT_MARKER_NOT_FIT"
        and not fixtures["marker_cannot_fit"]["alternatives_selected"]
    )
    if not checks:
        raise RuntimeError("N5-05 disagreement-budget acceptance oracle failed")

    result = {
        "schema": "memory-fabric-n5-05-disagreement-budget/1",
        "task_id": "N5-05",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "fixtures": fixtures,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "Query-identifier and content-token matching is a relevance heuristic; it is not an action classifier.",
            "One representative is rendered per normalized alternative; independent provenance remains linked in the receipt only for selected representatives.",
            "Context assembly reports uncertainty but does not resolve a hypothesis or authorize an action.",
        ],
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_PATH.write_text(
        "# N5-05 disagreement-budget contract evidence\n\n"
        "The fixture covers complete relevant alternatives, a set over the configured "
        "disagreement-token cap, an inaccessible alternative, an unrelated set, and a "
        "marker too large for the total context budget. Complete sets are atomic; the "
        "selector emits no single alternative when it cannot preserve all recognized "
        "alternatives. The focused test report and exact statuses are recorded in JSON. "
        "Query relevance is a heuristic, and neither the context nor its receipt grants "
        "action authority.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    print(json.dumps(run()["fixtures"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
