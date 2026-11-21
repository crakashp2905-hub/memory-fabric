"""Experimental contracts for truth-isolated agent outcome evaluation.

This package is deliberately opt-in. Its observations are agent-facing; oracle
state and grading remain in the benchmark world, outside these contracts.
"""

__stability__ = "experimental"

from .observations import AgentObservation, AgentStep, EpisodeOutcome
from .runtime import (MAX_TOOL_REQUEST_BYTES, AgentRuntime, RuntimeTrace, ToolCallRecord,
                      ToolOutput, parse_agent_request)
from .outcomes import (AgentEpisodeAudit, CompletionComparison, ReplayFidelity,
                       ReplayOutcomeInterpretation)
from .boundary import (AgentPort, EvaluatorCallbackNotice, EvaluatorDispatch, EvaluatorPort,
                       build_episode_boundary, grade_after_episode)
from .recovery import (READ_ONLY_RECOVERY_CATALOG, ReadOnlyRecoveryCatalog, RecoveryAction,
                       RecoveryActionSpec, RecoveryDisposition, RecoveryEpisode,
                       RecoveryFailureClass, RecoveryGuidance, RecoveryLimits,
                       RecoveryStatus, classify_recovery_failure, recovery_guidance)
from .eligibility import (AlternateEvidence, EvidenceFailure, EvidenceFailureKind,
                          classify_evidence_failure, search_alternate_sources)
from .metrics import explain_task_outcome, operator_trace

__all__ = ["AgentObservation", "AgentStep", "EpisodeOutcome", "RecoveryEpisode",
           "RecoveryLimits", "RecoveryStatus", "EvidenceFailure", "EvidenceFailureKind",
           "classify_evidence_failure", "RecoveryAction", "RecoveryActionSpec",
           "ReadOnlyRecoveryCatalog", "READ_ONLY_RECOVERY_CATALOG", "AlternateEvidence",
           "search_alternate_sources", "RecoveryDisposition", "RecoveryGuidance",
           "recovery_guidance", "RecoveryFailureClass", "classify_recovery_failure",
           "AgentRuntime", "RuntimeTrace", "ToolCallRecord", "ToolOutput",
           "AgentEpisodeAudit", "ReplayOutcomeInterpretation", "ReplayFidelity",
           "CompletionComparison", "MAX_TOOL_REQUEST_BYTES", "parse_agent_request",
           "AgentPort", "EvaluatorPort", "EvaluatorCallbackNotice", "EvaluatorDispatch",
           "build_episode_boundary", "grade_after_episode", "operator_trace",
           "explain_task_outcome"]

# Deprecated by ADR 0004 (docs/adr/0004-canonical-outcome-runtime.md): the
# canonical outcome runtime is memory_fabric.outcome_typed. This package stays
# importable so historical research and its recorded results keep working;
# memory_fabric.outcome_typed.compat translates its schema-v1 records.
import warnings as _warnings

__deprecated__ = {"canonical": "memory_fabric.outcome_typed", "sunset": "2027-03-31",
                  "adr": "docs/adr/0004-canonical-outcome-runtime.md",
                  "translate_with": "memory_fabric.outcome_typed.compat"}
_warnings.warn(
    "memory_fabric.outcome_protocol is deprecated (ADR 0004): use memory_fabric.outcome_typed; "
    "translate v1 records with memory_fabric.outcome_typed.compat. Sunset 2027-03-31.",
    DeprecationWarning, stacklevel=2)
