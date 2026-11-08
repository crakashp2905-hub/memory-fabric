"""Run deterministic mutation probes against benchmark evaluator invariants."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.evaluator_mutations import run  # noqa: E402

OUT = ROOT / "research" / "results" / "r4-07-evaluator-mutations.json"


def main() -> int:
    result = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["all_killed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
