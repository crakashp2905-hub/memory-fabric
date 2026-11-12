"""Source-tree launcher for the installed outcome incident demo."""

from memory_fabric.agent_outcomes.demo import main, run_demo

__all__ = ["main", "run_demo"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
