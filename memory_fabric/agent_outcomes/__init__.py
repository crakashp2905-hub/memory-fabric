"""Experimental contracts for truth-isolated agent outcome evaluation.

This package is deliberately opt-in. Its observations are agent-facing; oracle
state and grading remain in the benchmark world, outside these contracts.
"""

__stability__ = "experimental"

from .observations import AgentObservation, AgentStep, EpisodeOutcome, FailureCode
from .runtime import RuntimeResult, RuntimeStatus, RuntimeTool, ToolCallRecord, run_agent_loop
from .recovery import (
    RECOVERY_ACTIONS, RecoveryAction, RecoveryCause, RecoveryEpisode, RecoveryGuidance,
    RecoveryFailureClass, RecoveryFeatureFlag, RecoveryLimits, RecoveryNextAction,
    RecoveryResolution, RecoveryStatus,
)
from .eligibility import (
    DiagnosisSource, EvidenceDiagnosis, EvidenceFailureCode, diagnose_access,
    diagnose_answerability, diagnose_certificate, diagnose_relevance,
    find_alternate_sources,
)

__all__ = ["AgentObservation", "AgentStep", "EpisodeOutcome", "FailureCode",
           "RuntimeResult", "RuntimeStatus", "RuntimeTool", "ToolCallRecord",
           "run_agent_loop",
           "RECOVERY_ACTIONS", "RecoveryAction", "RecoveryEpisode", "RecoveryLimits",
           "RecoveryCause", "RecoveryGuidance", "RecoveryNextAction",
           "RecoveryFailureClass", "RecoveryFeatureFlag", "RecoveryResolution",
           "RecoveryStatus",
           "DiagnosisSource", "EvidenceDiagnosis",
           "EvidenceFailureCode", "diagnose_access", "diagnose_answerability",
           "diagnose_certificate", "diagnose_relevance", "find_alternate_sources"]
