"""Experimental contracts for truth-isolated agent outcome evaluation.

This package is deliberately opt-in. Its observations are agent-facing; oracle
state and grading remain in the benchmark world, outside these contracts.
"""

__stability__ = "experimental"

from .observations import AgentObservation, AgentStep, EpisodeOutcome
from .recovery import (READ_ONLY_RECOVERY_CATALOG, ReadOnlyRecoveryCatalog, RecoveryAction,
                       RecoveryActionSpec, RecoveryEpisode, RecoveryLimits, RecoveryStatus)
from .eligibility import (AlternateEvidence, EvidenceFailure, EvidenceFailureKind,
                          classify_evidence_failure, search_alternate_sources)

__all__ = ["AgentObservation", "AgentStep", "EpisodeOutcome", "RecoveryEpisode",
           "RecoveryLimits", "RecoveryStatus", "EvidenceFailure", "EvidenceFailureKind",
           "classify_evidence_failure", "RecoveryAction", "RecoveryActionSpec",
           "ReadOnlyRecoveryCatalog", "READ_ONLY_RECOVERY_CATALOG", "AlternateEvidence",
           "search_alternate_sources"]
