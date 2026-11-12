"""Source-tree launcher for the installed outcome incident demo."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory_fabric.agent_outcomes.demo import main, run_demo

__all__ = ["main", "run_demo"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
