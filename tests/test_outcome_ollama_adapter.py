from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch

import pytest

from benchmarks.outcome_agents import InvalidModelStep, OllamaOutcomePlanner
from memory_fabric.agent_outcomes.observations import AgentObservation
from memory_fabric.adapters.ollama import OllamaClient


class StubOllama:
    host = "http://127.0.0.1:11434"

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
    assert client.calls[0][2] == {
        "schema": planner.response_schema(observation()),
        "temperature": 0.0, "num_predict": 160, "top_p": None,
        "seed": None, "num_ctx": 4096,
    }
    proposal_schema = client.calls[0][2]["schema"]["anyOf"][0]
    tool_schema = proposal_schema["properties"]["tool"]
    assert tool_schema["enum"] == ["publish"]
    abstention_schema = client.calls[0][2]["schema"]["anyOf"][-1]
    assert abstention_schema["properties"]["intent"]["enum"] == ["abstain"]
    assert abstention_schema["properties"]["tool"]["type"] == "null"


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


@pytest.mark.parametrize("temperature", [float("nan"), float("inf"), float("-inf"), True])
def test_ollama_planner_rejects_non_finite_or_boolean_temperature(temperature) -> None:
    with pytest.raises(ValueError, match="temperature"):
        OllamaOutcomePlanner("qwen2.5:3b", StubOllama(encoded_step()), temperature=temperature)


def test_ollama_planner_handles_unhashable_intent_as_invalid_model_step() -> None:
    planner = OllamaOutcomePlanner(
        "qwen2.5:3b",
        StubOllama(json.dumps({
            "intent": [], "tool": None, "arguments": {}, "evidence_versions": [],
        })),
    )
    with pytest.raises(InvalidModelStep, match="intent"):
        planner.decide(observation(), actor_id="planner-1", step_id="step-1")
    assert planner.invalid_json == 1


def test_ollama_planner_rejects_proposal_without_a_tool() -> None:
    response = json.dumps({
        "intent": "propose", "tool": None, "arguments": {}, "evidence_versions": [],
    })
    planner = OllamaOutcomePlanner("qwen2.5:3b", StubOllama(response))

    with pytest.raises(InvalidModelStep, match="outside its observation grant"):
        planner.decide(observation(), actor_id="planner-1", step_id="step-1")
    assert planner.tool_misuse == 1


def test_ollama_planner_constrains_and_validates_registered_tool_arguments() -> None:
    client = StubOllama(encoded_step())
    planner = OllamaOutcomePlanner(
        "qwen2.5:3b", client,
        tool_argument_types={"publish": {"target": str, "value": str}},
    )
    step = planner.decide(observation(), actor_id="planner-1", step_id="step-1")

    proposal_schema = client.calls[0][2]["schema"]["anyOf"][0]
    arguments_schema = proposal_schema["properties"]["arguments"]
    assert arguments_schema["properties"] == {
        "target": {"type": "string"}, "value": {"type": "string"},
    }
    assert arguments_schema["required"] == ["target", "value"]
    assert arguments_schema["additionalProperties"] is False
    assert step.arguments == {"tool": "publish", "target": "status", "value": "ready"}


def test_ollama_planner_rejects_arguments_outside_registered_tool_schema() -> None:
    malformed = json.dumps({
        "intent": "propose", "tool": "publish",
        "arguments": {"memory_id": "evidence-1", "version": 2},
        "evidence_versions": [["evidence-1", 2]],
    })
    planner = OllamaOutcomePlanner(
        "qwen2.5:3b", StubOllama(malformed),
        tool_argument_types={"publish": {"target": str, "value": str}},
    )

    with pytest.raises(InvalidModelStep, match="declared tool schema"):
        planner.decide(observation(), actor_id="planner-1", step_id="step-1")
    assert planner.invalid_json == 1


@pytest.mark.parametrize("payload", [
    {"intent": "retrieve", "tool": None, "arguments": {}, "evidence_versions": []},
    {"intent": "propose", "tool": "publish", "arguments": {"tool": "erase"},
     "evidence_versions": []},
    {"intent": "propose", "tool": "publish", "arguments": {},
     "evidence_versions": [["evidence-1"]]},
])
def test_ollama_planner_rejects_malformed_or_ambiguous_steps(payload) -> None:
    planner = OllamaOutcomePlanner(
        "qwen2.5:3b", StubOllama(json.dumps(payload)),
    )
    with pytest.raises(InvalidModelStep):
        planner.decide(observation(), actor_id="planner-1", step_id="step-1")


def test_ollama_client_records_and_sends_available_decode_settings() -> None:
    client = OllamaClient()
    requests = []

    def post(_path, payload):
        requests.append(payload)
        return {"message": {"content": "{}"}, "prompt_eval_count": 7, "eval_count": 2}

    client._post = post
    schema = {"type": "object", "properties": {"intent": {"enum": ["abstain"]}}}
    client.chat("model:latest", [{"role": "user", "content": "task"}],
                temperature=0.1, top_p=0.9, seed=42, num_ctx=2048, num_predict=160,
                schema=schema)
    assert requests[0]["options"] == {
        "temperature": 0.1, "top_p": 0.9, "seed": 42,
        "num_ctx": 2048, "num_predict": 160,
    }
    assert requests[0]["format"] == schema
    record = client.calls[0]
    assert (record.temperature, record.top_p, record.seed,
            record.num_ctx, record.num_predict) == (0.1, 0.9, 42, 2048, 160)
    assert record.constrained is True


def test_ollama_inventory_exposes_digest_and_quantization() -> None:
    response = BytesIO(json.dumps({"models": [{
        "name": "model:latest", "digest": "a" * 64, "size": 100,
        "modified_at": "2026-11-13T00:00:00Z",
        "details": {"quantization_level": "Q4_K_M"},
    }]}).encode())
    with patch("urllib.request.urlopen", return_value=response):
        inventory = OllamaClient().inventory()
    assert inventory[0]["name"] == "model:latest"
    assert inventory[0]["digest"] == "a" * 64
    assert inventory[0]["details"]["quantization_level"] == "Q4_K_M"


@pytest.mark.parametrize("host", [
    "https://127.0.0.1:11434", "http://192.0.2.10:11434",
    "http://user:secret@localhost:11434", "http://localhost:11434/path",
])
def test_outcome_adapter_rejects_nonlocal_or_credentialed_endpoint(host: str) -> None:
    with pytest.raises(ValueError, match="loopback-only"):
        OllamaOutcomePlanner("qwen2.5:3b", OllamaClient(host=host))


@pytest.mark.parametrize("host", ["http://127.0.0.1:11434", "http://localhost:11434",
                                    "http://[::1]:11434"])
def test_outcome_adapter_allows_loopback_endpoint(host: str) -> None:
    OllamaOutcomePlanner("qwen2.5:3b", OllamaClient(host=host))


def test_outcome_adapter_rejects_client_without_an_explicit_endpoint() -> None:
    class UnscopedClient:
        def chat(self, *_args, **_kwargs):
            return {"message": {"content": encoded_step()}}

    with pytest.raises(ValueError, match="declare a loopback-only HTTP host"):
        OllamaOutcomePlanner("qwen2.5:3b", UnscopedClient())
