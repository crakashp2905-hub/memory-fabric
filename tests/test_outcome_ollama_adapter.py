from __future__ import annotations

import json

import pytest

from benchmarks.outcome_agents import InvalidModelStep, OllamaOutcomePlanner
from memory_fabric.agent_outcomes.observations import AgentObservation


class StubOllama:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def chat(self, model, messages, **kwargs):
        self.calls.append((model, messages, kwargs))
        return {"message": {"content": self.content}}


def observation() -> AgentObservation:
    return AgentObservation(
        "task-1", "Use current evidence to publish the status.",
        ({"memory_id": "evidence-1", "version": 2, "content": "status: ready"},),
        ("publish",), {"model_tokens": 160},
    )


def encoded_step(*, tool: str = "publish", memory_id: str = "evidence-1") -> str:
    return json.dumps({
        "intent": "propose", "tool": tool,
        "arguments": {"target": "status", "value": "ready"},
        "evidence_versions": [[memory_id, 2]],
    })


def test_ollama_planner_sends_only_observation_and_validates_response() -> None:
    client = StubOllama(encoded_step())
    planner = OllamaOutcomePlanner("qwen2.5:3b", client)
    step = planner.decide(observation(), actor_id="planner-1", step_id="step-1")
    assert step.task_id == "task-1"
    assert step.intent == "propose"
    assert step.evidence_versions == (("evidence-1", 2),)
    assert client.calls[0][0] == "qwen2.5:3b"
    request = client.calls[0][1]
    assert json.loads(request[1]["content"]) == observation().to_dict()
    assert "expected_action" not in request[1]["content"]
    assert client.calls[0][2] == {"temperature": 0.0, "num_predict": 160}


def test_ollama_planner_counts_invalid_json_tool_misuse_and_hallucinated_evidence() -> None:
    for response, field in (
        ("not json", "invalid_json"),
        (encoded_step(tool="delete_everything"), "tool_misuse"),
        (encoded_step(memory_id="invented-evidence"), "hallucinated_evidence"),
    ):
        planner = OllamaOutcomePlanner("qwen2.5:3b", StubOllama(response))
        with pytest.raises(InvalidModelStep):
            planner.decide(observation(), actor_id="planner-1", step_id="step-1")
        assert getattr(planner, field) == 1


def test_ollama_planner_requires_an_observation_contract() -> None:
    planner = OllamaOutcomePlanner("qwen2.5:3b", StubOllama(encoded_step()))
    with pytest.raises(TypeError, match="AgentObservation"):
        planner.decide({"truth": "hidden"}, actor_id="planner-1", step_id="step-1")
