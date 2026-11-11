"""Experimental contracts for truth-isolated agent outcome evaluation.

This package is deliberately opt-in. Its observations are agent-facing; oracle
state and grading remain in the benchmark world, outside these contracts.
"""

__stability__ = "experimental"

from .observations import AgentObservation, AgentStep, EpisodeOutcome, FailureCode
from .recovery import (
    RECOVERY_ACTIONS, RecoveryAction, RecoveryEpisode, RecoveryLimits, RecoveryStatus,
)
from .eligibility import (
    DiagnosisSource, EvidenceDiagnosis, EvidenceFailureCode, diagnose_access,
    diagnose_answerability, diagnose_certificate, diagnose_relevance,
)

__all__ = ["AgentObservation", "AgentStep", "EpisodeOutcome", "FailureCode",
           "RECOVERY_ACTIONS", "RecoveryAction", "RecoveryEpisode", "RecoveryLimits",
           "RecoveryStatus", "DiagnosisSource", "EvidenceDiagnosis",
           "EvidenceFailureCode", "diagnose_access", "diagnose_answerability",
           "diagnose_certificate", "diagnose_relevance"]
