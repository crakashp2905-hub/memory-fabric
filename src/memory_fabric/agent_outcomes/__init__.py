"""Experimental contracts for truth-isolated agent outcome evaluation.

This package is deliberately opt-in. Its observations are agent-facing; oracle
state and grading remain in the benchmark world, outside these contracts.
"""

__stability__ = "experimental"

from .observations import AgentObservation, AgentStep, EpisodeOutcome
from .recovery import RecoveryEpisode, RecoveryLimits, RecoveryStatus

__all__ = ["AgentObservation", "AgentStep", "EpisodeOutcome", "RecoveryEpisode",
           "RecoveryLimits", "RecoveryStatus"]

# Deprecated by ADR 0004 (docs/adr/0004-canonical-outcome-runtime.md): the
# canonical outcome runtime is memory_fabric.outcome_typed. This package stays
# importable so historical research and its recorded results keep working;
# memory_fabric.outcome_typed.compat translates its schema-v1 records.
import warnings as _warnings

__deprecated__ = {"canonical": "memory_fabric.outcome_typed", "sunset": "2027-03-31",
                  "adr": "docs/adr/0004-canonical-outcome-runtime.md",
                  "translate_with": "memory_fabric.outcome_typed.compat"}
_warnings.warn(
    "memory_fabric.agent_outcomes is deprecated (ADR 0004): use memory_fabric.outcome_typed; "
    "translate v1 records with memory_fabric.outcome_typed.compat. Sunset 2027-03-31.",
    DeprecationWarning, stacklevel=2)
