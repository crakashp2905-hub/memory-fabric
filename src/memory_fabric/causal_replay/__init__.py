"""Experimental counterfactual decision replay.

Importing this package is inert: it does not open stores, files, services,
sockets, models, or mutate Memory Fabric state.
"""

from __future__ import annotations

__stability__ = "experimental"

from .types import (BeliefReference, CaptureResult, DecisionRecord, EventReference,
                    RNGSnapshot,
                    ReplayContext, ReplayStatus, SCHEMA_MAJOR, SCHEMA_MINOR,
                    ToolObservation, canonical_json, digest_json, parse_record,
                    schema_is_compatible, schema_version, serialize_record)
from .capture import (capture, capture_rng_state, record_decision,
                      validate_replay_option, verify_decision_record)
from .intervention import (Intervention, InterventionBatch, ReplacementFixture,
                           SensitivityFixture,
                           apply as apply_intervention, compose as compose_interventions,
                           create as create_intervention)
from .bayes import (BinaryNode, enumerate_posterior, independent_binary_oracle,
                    marginal, sensitivity_sweep)
from .policy import ThresholdPolicy
from .state import (BeliefState, Observation, generated_belief_state_schema,
                    update, validate_belief_state_record)
from .certificates import (Estimand, ExplanationStatus, MinimalityClaim, ReplayCertificate,
                           WorldSemantics, issue as issue_certificate,
                           issue_verified_recorded_replay,
                           masked_export, verify as verify_certificate)
from .replay import ReplayResult, replay, replay_captured, deterministic_simulator
from .environment import (ContinuationResult, DeterministicEnvironment,
                          EnvironmentResult, WorldTransition,
                          battery_sensor_environment, continue_counterfactual)
from .api import CausalReplayAPI
from .checkpoints import (CacheKey, CheckpointCache, ReplayCheckpoint,
                          create as create_checkpoint, restore_rng as restore_checkpoint_rng,
                          verify as verify_checkpoint,
                          verify_exact_ready as verify_checkpoint_exact_ready)
from .visualization import timeline as build_timeline
from .viewer import render as render_local_viewer
from .executor import (ExecutionCheckpoint, ReplayExecution, ReplayStep,
                       create_execution_checkpoint, execute_from_checkpoint,
                       execute_dependency_frontier,
                       execute as execute_replay, execute_recorded, execute_captured,
                       first_divergence)
from .verifier import (AttributionVerification, VerificationResult,
                       verify_execution, verify_small_n_shapley)
from .scheduler import (Candidate, ReplayBudget, check_budget, earliest_affected_index,
                        branch_recall_at_k, dependency_frontier, replay_frontier,
                        select_centrality, select_priority,
                        select_random, select_recency)
from .evaluator import (CalibrationReport, ContributionAssessment, FidelityAssessment,
                        Outcome, OutcomeAssessment, assess_outcome, calibration_report,
                        heuristic_contribution, verify_fidelity)
from .attribution import (DistributionalEstimate, Effect, FederatedEvidenceVersion,
                          FederatedVersionAssessment, PairedEstimate, PruningResult,
                          SourceRootAssessment, assess_fabric_source_roots,
                          assess_federated_versions, assess_source_roots,
                          compare_effect, distributional_effect, exhaustive_shapley,
                          paired_bootstrap_interval, paired_common_random_estimate,
                          pairwise_interaction_screen, prune_candidates_by_lineage,
                          sampled_shapley, total_variation,
                          wilson_interval)

SCHEMA_VERSION = SCHEMA_MAJOR

__all__ = ["SCHEMA_VERSION", "SCHEMA_MAJOR", "SCHEMA_MINOR", "EventReference", "BeliefReference", "DecisionRecord",
           "ReplayContext", "ToolObservation", "CaptureResult", "ReplayStatus",
           "canonical_json", "digest_json"]
__all__ += ["parse_record", "serialize_record"]
__all__ += ["generated_belief_state_schema", "validate_belief_state_record"]
__all__ += ["schema_version", "schema_is_compatible"]
__all__ += ["RNGSnapshot"]
__all__ += ["capture", "capture_rng_state", "record_decision", "verify_decision_record",
            "validate_replay_option", "Intervention", "create_intervention",
            "apply_intervention", "ReplacementFixture", "InterventionBatch",
            "compose_interventions", "SensitivityFixture"]
__all__ += ["BinaryNode", "enumerate_posterior", "independent_binary_oracle", "marginal",
            "sensitivity_sweep", "BeliefState", "Observation", "update", "ThresholdPolicy"]
__all__ += ["ReplayCertificate", "issue_certificate", "verify_certificate", "ReplayResult",
            "replay", "replay_captured", "deterministic_simulator"]
__all__ += ["issue_verified_recorded_replay"]
__all__ += ["DeterministicEnvironment", "EnvironmentResult", "WorldTransition",
            "ContinuationResult", "continue_counterfactual",
            "battery_sensor_environment"]
__all__ += ["ExplanationStatus", "Estimand", "WorldSemantics", "MinimalityClaim"]
__all__ += ["masked_export"]
__all__ += ["CausalReplayAPI"]
__all__ += ["ReplayCheckpoint", "CacheKey", "CheckpointCache", "create_checkpoint",
            "restore_checkpoint_rng", "verify_checkpoint"]
__all__ += ["verify_checkpoint_exact_ready"]
__all__ += ["build_timeline", "render_local_viewer"]
__all__ += ["ReplayExecution", "ReplayStep", "ExecutionCheckpoint",
            "create_execution_checkpoint", "execute_from_checkpoint", "execute_replay",
            "execute_dependency_frontier", "execute_recorded", "first_divergence"]
__all__ += ["execute_captured"]
__all__ += ["VerificationResult", "verify_execution", "AttributionVerification",
            "verify_small_n_shapley"]
__all__ += ["Candidate", "ReplayBudget", "check_budget", "earliest_affected_index",
            "branch_recall_at_k", "dependency_frontier", "replay_frontier", "select_random", "select_recency", "select_centrality",
            "select_priority"]
__all__ += ["Outcome", "OutcomeAssessment", "FidelityAssessment", "CalibrationReport",
            "ContributionAssessment", "assess_outcome", "verify_fidelity",
            "calibration_report", "heuristic_contribution"]
__all__ += ["Effect", "PairedEstimate", "DistributionalEstimate", "PruningResult",
            "SourceRootAssessment", "assess_source_roots", "assess_fabric_source_roots",
            "FederatedEvidenceVersion", "FederatedVersionAssessment",
            "assess_federated_versions", "compare_effect",
            "distributional_effect", "total_variation", "exhaustive_shapley",
            "sampled_shapley", "paired_bootstrap_interval", "wilson_interval",
            "pairwise_interaction_screen", "paired_common_random_estimate",
            "prune_candidates_by_lineage"]
