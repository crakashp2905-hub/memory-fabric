"""Fail-closed status for optional, explicit Ollama outcome trials."""

from __future__ import annotations

import hashlib
import json
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
    if planner.model_digest is None:
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "REAL_AGENT_NOT_RUN",
            "gate_status": "NOT_RUN",
            "reason": "MODEL_DIGEST_NOT_PINNED",
            "model": planner.model,
            "inference_completed": False,
            "model_calls": 0,
            "model_tokens": None,
            "fallback_used": False,
        }
    inventory_method = getattr(planner.client, "inventory", None)
    if not callable(inventory_method):
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "REAL_AGENT_NOT_RUN",
            "gate_status": "NOT_RUN",
            "reason": "MODEL_DIGEST_UNAVAILABLE",
            "model": planner.model,
            "inference_completed": False,
            "model_calls": 0,
            "model_tokens": None,
            "fallback_used": False,
        }
    try:
        inventory = inventory_method()
    except Exception as exc:  # noqa: BLE001 - unavailable metadata blocks inference
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "REAL_AGENT_NOT_RUN",
            "gate_status": "NOT_RUN",
            "reason": f"MODEL_DIGEST_UNAVAILABLE:{type(exc).__name__}",
            "model": planner.model,
            "inference_completed": False,
            "model_calls": 0,
            "model_tokens": None,
            "fallback_used": False,
        }
    local_model = next((item for item in inventory
                        if item.get("name") in {planner.model, f"{planner.model}:latest"}), None)
    pinned_digest = planner.model_digest.removeprefix("sha256:")
    if local_model is None or local_model.get("digest") != pinned_digest:
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "REAL_AGENT_NOT_RUN",
            "gate_status": "NOT_RUN",
            "reason": "MODEL_DIGEST_MISMATCH",
            "model": planner.model,
            "expected_digest": pinned_digest,
            "observed_digest": local_model.get("digest") if local_model else None,
            "inference_completed": False,
            "model_calls": 0,
            "model_tokens": None,
            "fallback_used": False,
        }
    observed_quantization = local_model.get("details", {}).get("quantization_level")
    if planner.quantization is None or observed_quantization != planner.quantization:
        return {
            "schema_id": "memory-fabric.outcome-model-trial.v1",
            "model_status": "REAL_AGENT_NOT_RUN",
            "gate_status": "NOT_RUN",
            "reason": "QUANTIZATION_NOT_PINNED_OR_MISMATCHED",
            "model": planner.model,
            "model_digest": pinned_digest,
            "expected_quantization": planner.quantization,
            "observed_quantization": observed_quantization,
            "inference_completed": False,
            "model_calls": 0,
            "model_tokens": None,
            "fallback_used": False,
        }
    before_usage = planner.client.usage() if callable(getattr(planner.client, "usage", None)) else None
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
            "model_digest": pinned_digest,
            "quantization": observed_quantization,
        }
    after_usage = planner.client.usage() if callable(getattr(planner.client, "usage", None)) else None
    usage_delta = None
    if isinstance(before_usage, dict) and isinstance(after_usage, dict):
        usage_delta = {key: after_usage.get(key, 0) - value
                       for key, value in before_usage.items() if isinstance(value, (int, float))}
    step_digest = hashlib.sha256(json.dumps(
        step.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()
    return {
        "schema_id": "memory-fabric.outcome-model-trial.v1",
        "model_status": "LOCAL_MODEL_INFERENCE_COMPLETED",
        "gate_status": "PENDING_INDEPENDENT_EVALUATION",
        "reason": None,
        "model": planner.model,
        "model_digest": pinned_digest,
        "quantization": observed_quantization,
        "inference_settings": {
            "prompt_version": "outcome_planner_v1",
            "temperature": planner.temperature,
            "top_p": planner.top_p,
            "seed": planner.seed,
            "num_ctx": planner.num_ctx,
            "num_predict": planner.num_predict,
            "prompt_sha256": hashlib.sha256(
                planner.SYSTEM_PROMPT.encode("utf-8")
                + observation.canonical_json().encode("utf-8")
            ).hexdigest(),
        },
        "inference_completed": True,
        "model_calls": 1,
        "model_tokens": usage_delta.get("tokens") if usage_delta else None,
        "usage": usage_delta,
        "fallback_used": False,
        "validated_step_sha256": step_digest,
        "adapter_errors": {
            "invalid_json": planner.invalid_json,
            "tool_misuse": planner.tool_misuse,
            "hallucinated_evidence": planner.hallucinated_evidence,
            "retries": planner.retries,
        },
    }
