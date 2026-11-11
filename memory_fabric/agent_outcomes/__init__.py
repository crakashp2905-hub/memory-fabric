"""Experimental contracts for truth-isolated agent outcome evaluation.

This package is deliberately opt-in. Its observations are agent-facing; oracle
state and grading remain in the benchmark world, outside these contracts.
"""

__stability__ = "experimental"

from .observations import AgentObservation, AgentStep, EpisodeOutcome, FailureCode
from .recovery import RecoveryEpisode, RecoveryLimits, RecoveryStatus

__all__ = ["AgentObservation", "AgentStep", "EpisodeOutcome", "FailureCode", "RecoveryEpisode",
           "RecoveryLimits", "RecoveryStatus"]
