"""Compatibility shim for an early experimental replay module name.

The implementation lives in :mod:`memory_fabric.causal_replay.replay` so there
is one simulator boundary and one set of intervention semantics.
"""

from __future__ import annotations

__stability__ = "experimental"

from .causal_replay.replay import (DeterministicSimulator, ReplayResult,
                                   deterministic_simulator, replay)

__all__ = ["DeterministicSimulator", "ReplayResult", "deterministic_simulator", "replay"]
