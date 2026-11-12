from __future__ import annotations

from benchmarks.outcome_agents import OllamaOutcomePlanner
from benchmarks.outcome_model_status import run_local_model_trial


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
