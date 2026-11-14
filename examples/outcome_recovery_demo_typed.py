"""DEMO ONLY: source-tree launcher for the typed outcome incident demo. Scripted roles; no model runs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory_fabric.outcome_typed.demo import main, run_demo

__all__ = ["main", "run_demo"]


if __name__ == "__main__":  # pragma: no cover
    print("DEMO ONLY: scripted roles; no model is run.")
    raise SystemExit(main())
