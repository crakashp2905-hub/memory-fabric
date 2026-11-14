"""Experimental contracts for truth-isolated agent outcome evaluation.

This package is deliberately opt-in. Its observations are agent-facing; oracle
state and grading remain in the benchmark world, outside these contracts.
"""

__stability__ = "experimental"

from .observations import AgentObservation, AgentStep, EpisodeOutcome, FailureCode
from .runtime import (
    AuthorizedReplayContract, CounterfactualReplayDispatch,
    CounterfactualReplayReason, CounterfactualReplayStatus,
    ReplayBudget, ReplayContractBuild, ReplayContractStatus, ReplayLimits,
    RuntimeResult, RuntimeStatus,
    RuntimeTool, ToolCallRecord, build_authorized_replay_contract,
    dispatch_counterfactual_replay, run_agent_json_loop, run_agent_loop,
)
from .recovery import (
    RECOVERY_ACTIONS, RECOVERY_CHECKPOINT_SCHEMA_ID, RecoveryAction, RecoveryCause,
    RecoveryEpisode, RecoveryGuidance,
    RecoveryFailureClass, RecoveryFeatureFlag, RecoveryLimits, RecoveryNextAction,
    RecoveryResolution, RecoveryStatus,
)
from .eligibility import (
    DiagnosisSource, EvidenceDiagnosis, EvidenceFailureCode, ReportedTaskStatus,
    diagnose_access,
    diagnose_answerability, diagnose_certificate, diagnose_relevance,
    explain_task_failure, find_alternate_sources,
)
from .outcomes import (
    EffectRecord, EpisodeAudit, GradeReason, GradeStatus, OutcomeAuditEvent,
    OutcomeAuditKind, OutcomeBenefitLabel, OutcomeStage, PolicyFlipLabel,
    ReplayFidelityLabel, TerminalGrade, TerminalObjective, TerminalSnapshot,
    canonical_step_id, canonical_task_id, grade_terminal,
    label_counterfactual_evidence, targeted_correction_reevaluation_receipts,
    summarize_audit_memory_links,
)

__all__ = ["AgentObservation", "AgentStep", "EpisodeOutcome", "FailureCode",
           "RuntimeResult", "RuntimeStatus", "RuntimeTool", "ToolCallRecord",
           "run_agent_json_loop", "run_agent_loop", "CounterfactualReplayDispatch",
           "CounterfactualReplayReason", "CounterfactualReplayStatus",
           "dispatch_counterfactual_replay",
           "AuthorizedReplayContract", "ReplayContractBuild", "ReplayContractStatus",
           "ReplayLimits", "ReplayBudget",
           "build_authorized_replay_contract",
           "RECOVERY_ACTIONS", "RECOVERY_CHECKPOINT_SCHEMA_ID", "RecoveryAction",
           "RecoveryEpisode", "RecoveryLimits",
           "RecoveryCause", "RecoveryGuidance", "RecoveryNextAction",
           "RecoveryFailureClass", "RecoveryFeatureFlag", "RecoveryResolution",
           "RecoveryStatus",
           "DiagnosisSource", "EvidenceDiagnosis",
           "EvidenceFailureCode", "ReportedTaskStatus", "explain_task_failure",
           "diagnose_access", "diagnose_answerability",
           "diagnose_certificate", "diagnose_relevance", "find_alternate_sources",
           "EffectRecord", "EpisodeAudit", "GradeReason", "GradeStatus",
           "OutcomeAuditEvent", "OutcomeAuditKind", "OutcomeBenefitLabel",
           "OutcomeStage", "PolicyFlipLabel", "ReplayFidelityLabel", "TerminalGrade",
           "TerminalObjective", "TerminalSnapshot", "canonical_step_id",
           "canonical_task_id", "grade_terminal",
           "label_counterfactual_evidence", "targeted_correction_reevaluation_receipts",
           "summarize_audit_memory_links"]
