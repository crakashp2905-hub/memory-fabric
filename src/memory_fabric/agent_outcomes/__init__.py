"""Experimental contracts for truth-isolated agent outcome evaluation.

This package is deliberately opt-in. Its observations are agent-facing; oracle
state and grading remain in the benchmark world, outside these contracts.
"""

__stability__ = "experimental"

from .observations import AgentObservation, AgentStep, EpisodeOutcome
from .recovery import (READ_ONLY_RECOVERY_CATALOG, ReadOnlyRecoveryCatalog, RecoveryAction,
                       RecoveryActionSpec, RecoveryDisposition, RecoveryEpisode,
                       RecoveryFailureClass, RecoveryGuidance, RecoveryLimits,
                       RecoveryStatus, classify_recovery_failure, recovery_guidance)
from .eligibility import (AlternateEvidence, EvidenceFailure, EvidenceFailureKind,
                          classify_evidence_failure, search_alternate_sources)

__all__ = ["AgentObservation", "AgentStep", "EpisodeOutcome", "RecoveryEpisode",
           "RecoveryLimits", "RecoveryStatus", "EvidenceFailure", "EvidenceFailureKind",
           "classify_evidence_failure", "RecoveryAction", "RecoveryActionSpec",
           "ReadOnlyRecoveryCatalog", "READ_ONLY_RECOVERY_CATALOG", "AlternateEvidence",
           "search_alternate_sources", "RecoveryDisposition", "RecoveryGuidance",
           "recovery_guidance", "RecoveryFailureClass", "classify_recovery_failure"]
