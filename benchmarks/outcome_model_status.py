"""Fail-closed status for optional, explicit Ollama outcome trials."""

from __future__ import annotations

from typing import Any

from benchmarks.outcome_agents import InvalidModelStep, OllamaOutcomePlanner


def run_local_model_trial(
    planner: OllamaOutcomePlanner,
    *,
    observation: Any | None = None,
    actor_id: str = "planner-1",
    step_id: str = "model-step-1",
) -> dict[str, Any]:
    """Check the existing local server and run one inference only when requested.

    No package installation or model pull is attempted. Model absence cannot be
    replaced by the scripted adapter, and one inference is not a qualification.
    """
    try:
        available = planner.client.available()
    except Exception as exc:  # transport adapters report backend-specific errors
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "REAL_AGENT_NOT_RUN",
            "gate_status": "NOT_RUN",
            "reason": f"LOCAL_OLLAMA_UNAVAILABLE:{type(exc).__name__}",
            "model": planner.model,
            "inference_completed": False,
            "model_calls": 0,
            "model_tokens": None,
            "fallback_used": False,
        }
    if planner.model not in available and f"{planner.model}:latest" not in available:
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "REAL_AGENT_NOT_RUN",
            "gate_status": "NOT_RUN",
            "reason": "PINNED_MODEL_NOT_INSTALLED",
            "model": planner.model,
            "inference_completed": False,
            "model_calls": 0,
            "model_tokens": None,
            "fallback_used": False,
        }
    if observation is None:
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "REAL_AGENT_NOT_RUN",
            "gate_status": "NOT_RUN",
            "reason": "NO_TASK_OBSERVATION_SUPPLIED",
            "model": planner.model,
            "inference_completed": False,
            "model_calls": 0,
            "model_tokens": None,
            "fallback_used": False,
        }
    try:
        step = planner.decide(observation, actor_id=actor_id, step_id=step_id)
    except InvalidModelStep as exc:
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "LOCAL_MODEL_INFERENCE_FAILED",
            "gate_status": "NOT_RUN",
            "reason": f"INVALID_MODEL_STEP:{type(exc).__name__}",
            "model": planner.model,
            "inference_completed": True,
            "model_calls": 1,
            "model_tokens": None,
            "fallback_used": False,
        }
    return {
        "schema_id": "memory-fabric.outcome-model-trial.v1",
        "model_status": "LOCAL_MODEL_INFERENCE_COMPLETED",
        "gate_status": "PENDING_INDEPENDENT_EVALUATION",
        "reason": None,
        "model": planner.model,
        "inference_completed": True,
        "model_calls": 1,
        "model_tokens": None,
        "fallback_used": False,
        "step": step.to_dict(),
        "adapter_errors": {
            "invalid_json": planner.invalid_json,
            "tool_misuse": planner.tool_misuse,
            "hallucinated_evidence": planner.hallucinated_evidence,
            "retries": planner.retries,
        },
    }
