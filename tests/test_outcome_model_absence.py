from __future__ import annotations

from benchmarks.outcome_agents import OllamaOutcomePlanner
from benchmarks.outcome_model_status import run_local_model_trial
from memory_fabric.agent_outcomes.observations import AgentObservation


class MissingServer:
    def available(self):
        raise OSError("loopback Ollama is not running")

    def chat(self, *_args, **_kwargs):  # pragma: no cover - absence must prevent inference
        raise AssertionError("no inference is allowed when the server is absent")


class MissingModel:
    def __init__(self) -> None:
        self.chat_calls = 0

    def available(self):
        return ["other-model:latest"]

    def chat(self, *_args, **_kwargs):  # pragma: no cover - absence must prevent inference
        self.chat_calls += 1
        raise AssertionError("no inference is allowed when the pinned model is absent")


def test_missing_server_is_real_agent_not_run_without_fallback() -> None:
    planner = OllamaOutcomePlanner("pinned-model:latest", MissingServer())
    report = run_local_model_trial(planner)
    assert report["model_status"] == "REAL_AGENT_NOT_RUN"
    assert report["gate_status"] == "NOT_RUN"
    assert report["inference_completed"] is False
    assert report["fallback_used"] is False
    assert report["model_calls"] == 0


def test_missing_model_is_not_replaced_or_marked_pass() -> None:
    client = MissingModel()
    planner = OllamaOutcomePlanner("pinned-model", client)
    report = run_local_model_trial(planner)
    assert report["model_status"] == "REAL_AGENT_NOT_RUN"
    assert report["gate_status"] == "NOT_RUN"
    assert report["reason"] == "PINNED_MODEL_NOT_INSTALLED"
    assert report["fallback_used"] is False
    assert client.chat_calls == 0


def test_model_presence_without_explicit_task_does_not_infer() -> None:
    client = MissingModel()
    client.available = lambda: ["pinned-model:latest"]
    planner = OllamaOutcomePlanner("pinned-model", client)
    report = run_local_model_trial(planner)
    assert report["model_status"] == "REAL_AGENT_NOT_RUN"
    assert report["gate_status"] == "NOT_RUN"
    assert report["reason"] == "NO_TASK_OBSERVATION_SUPPLIED"
    assert client.chat_calls == 0


def test_model_presence_without_digest_pin_does_not_infer() -> None:
    client = MissingModel()
    client.available = lambda: ["pinned-model:latest"]
    planner = OllamaOutcomePlanner("pinned-model", client)
    observation = AgentObservation("task-1", "Do the task.", (), ("publish",), {})
    report = run_local_model_trial(planner, observation=observation)
    assert report["model_status"] == "REAL_AGENT_NOT_RUN"
    assert report["reason"] == "MODEL_DIGEST_NOT_PINNED"
    assert report["fallback_used"] is False
    assert client.chat_calls == 0


def test_pinned_model_digest_and_inference_settings_are_reported() -> None:
    class PinnedClient:
        def __init__(self) -> None:
            self.chat_calls = 0

        def available(self):
            return ["pinned-model:latest"]

        def inventory(self):
            return [{"name": "pinned-model:latest", "digest": "a" * 64,
                     "details": {"quantization_level": "Q4_K_M"}}]

        def usage(self):
            return {"calls": float(self.chat_calls), "tokens": 12.0 * self.chat_calls}

        def chat(self, _model, _messages, **_kwargs):
            self.chat_calls += 1
            return {"message": {"content": (
                '{"intent":"abstain","tool":null,"arguments":{},'
                '"evidence_versions":[]}'
            )}}

    client = PinnedClient()
    planner = OllamaOutcomePlanner(
        "pinned-model", client, model_digest="a" * 64, quantization="Q4_K_M",
        temperature=0.2, top_p=0.8, seed=7, num_ctx=2048, num_predict=96,
    )
    observation = AgentObservation("task-1", "Do the task.", (), ("publish",), {})
    report = run_local_model_trial(planner, observation=observation)
    assert report["model_status"] == "LOCAL_MODEL_INFERENCE_COMPLETED"
    assert report["gate_status"] == "PENDING_INDEPENDENT_EVALUATION"
    assert report["model_digest"] == "a" * 64
    assert report["quantization"] == "Q4_K_M"
    assert report["model_tokens"] == 12.0
    assert report["inference_settings"]["prompt_version"] == "outcome_planner_v1"
    assert report["inference_settings"]["temperature"] == 0.2
    assert report["inference_settings"]["top_p"] == 0.8
    assert report["inference_settings"]["seed"] == 7
    assert report["inference_settings"]["num_ctx"] == 2048
    assert report["inference_settings"]["num_predict"] == 96
    assert len(report["inference_settings"]["prompt_sha256"]) == 64
    assert report["inference_settings"]["constrained_json"] is True
    assert len(report["inference_settings"]["output_schema_sha256"]) == 64
    assert "step" not in report
    assert report["fallback_used"] is False


def test_invalid_model_step_reports_adapter_failure_counters_without_raw_output() -> None:
    class InvalidReplyClient:
        def available(self):
            return ["pinned-model:latest"]

        def inventory(self):
            return [{"name": "pinned-model:latest", "digest": "a" * 64,
                     "details": {"quantization_level": "Q4_K_M"}}]

        def chat(self, _model, _messages, **_kwargs):
            return {"message": {"content": '{"intent": [], "tool": null,'
                    '"arguments": {}, "evidence_versions": []}'}}

    planner = OllamaOutcomePlanner(
        "pinned-model", InvalidReplyClient(), model_digest="a" * 64,
        quantization="Q4_K_M",
    )
    observation = AgentObservation("task-1", "Do the task.", (), ("publish",), {})
    report = run_local_model_trial(planner, observation=observation)

    assert report["model_status"] == "LOCAL_MODEL_INFERENCE_FAILED"
    assert report["reason"] == (
        "INVALID_MODEL_STEP:model intent is outside the supported next-step vocabulary"
    )
    assert report["adapter_errors"] == {
        "invalid_json": 1, "tool_misuse": 0,
        "hallucinated_evidence": 0, "retries": 0,
    }
    assert "[]" not in report["reason"]
