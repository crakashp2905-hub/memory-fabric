"""A missing model never borrows scripted-agent outcomes."""

from __future__ import annotations

import io
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from benchmarks.outcome_agents import OllamaAgentAdapter
from benchmarks.outcome_report import RealAgentStatus, run_real_agent_gate
from memory_fabric.adapters.ollama import CallRecord, OllamaClient, OllamaError
from memory_fabric.agent_outcomes import AgentObservation, AgentStep
from memory_fabric.agent_outcomes.observations import SCHEMA_ID
from tools.agent_outcome_gate import local_model_evidence_result


class TestOutcomeModelAbsence(unittest.TestCase):
    def setUp(self) -> None:
        self.observation = AgentObservation(
            task_id="model-gate-task",
            instruction="Inspect the visible reading.",
            visible_events=({"source": "instrument", "reading": 4},),
            permitted_tools=("inspect",),
            budget={"steps": 1},
        )

    def _reply(self) -> str:
        return json.dumps({
            "schema_id": SCHEMA_ID,
            "task_id": self.observation.task_id,
            "actor_id": "observer",
            "step_id": "observer-step-1",
            "intent": "inspect",
            "arguments": {"tool": "inspect"},
            "evidence_versions": [],
        }, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _metadata(model: str) -> dict[str, object]:
        return {
            "requested_name": model, "name": model,
            "digest": "sha256:" + "a" * 64, "size": 123,
            "format": "gguf", "family": "qwen2", "parameter_size": "1.5B",
            "quantization_level": "Q4_K_M",
        }

    def test_unavailable_server_reports_not_run_without_scripted_fallback(self) -> None:
        client = OllamaClient(retries=0)
        adapter = OllamaAgentAdapter("observer", model="missing:latest", client=client)
        with patch.object(client, "model_metadata",
                          side_effect=OllamaError("server unavailable")):
            report = run_real_agent_gate(adapter, self.observation)

        value = json.loads(report.canonical_json())
        self.assertEqual(report.status, RealAgentStatus.NOT_RUN)
        self.assertEqual(value["status"], "REAL_AGENT_NOT_RUN")
        self.assertEqual(value["population"], "REAL_AGENT")
        self.assertEqual(value["reason"], "model_unavailable")
        self.assertEqual(value["model_calls"], 0)
        self.assertNotIn("step", value)
        self.assertNotIn("outcomes", value)

    def test_valid_step_without_a_new_call_record_cannot_pass(self) -> None:
        class UnrecordedAdapter:
            model = "unrecorded"
            calls = ()

            def next_step(self, observation: AgentObservation) -> AgentStep:
                return AgentStep.from_json(self_reply)

        self_reply = self._reply()
        report = run_real_agent_gate(UnrecordedAdapter(), self.observation)  # type: ignore[arg-type]
        self.assertEqual(report.status, RealAgentStatus.NOT_RUN)
        self.assertEqual(report.reason, "no_recorded_inference")

    def test_recorded_call_with_a_misbound_step_cannot_pass(self) -> None:
        class MisboundAdapter:
            model = "qwen2.5:1.5b"
            actor_id = "observer"

            def __init__(self) -> None:
                self.calls: tuple[CallRecord, ...] = ()

            def next_step(self, observation: AgentObservation) -> AgentStep:
                self.calls += (CallRecord(self.model, "0" * 64, 5, 3, 0.01),)
                wrong_task = json.loads(self_reply)
                wrong_task["task_id"] = "another-task"
                return AgentStep.from_json(json.dumps(wrong_task))

        self_reply = self._reply()
        report = run_real_agent_gate(MisboundAdapter(), self.observation)
        self.assertEqual(report.status, RealAgentStatus.FAIL)
        self.assertEqual(report.reason, "invalid_agent_step")

    def test_pass_requires_a_recorded_call_and_validated_step(self) -> None:
        client = OllamaClient(retries=0)
        response = {
            "message": {"content": self._reply()},
            "prompt_eval_count": 13,
            "eval_count": 7,
        }
        with patch.object(client, "model_metadata",
                          return_value=self._metadata("qwen2.5:1.5b")):
            with patch.object(client, "_post", return_value=response):
                report = run_real_agent_gate(
                    OllamaAgentAdapter("observer", model="qwen2.5:1.5b", client=client,
                                       num_predict=512),
                    self.observation,
                )

        self.assertEqual(report.status, RealAgentStatus.PASS)
        self.assertEqual(report.reason, "completed_inference")
        self.assertEqual(report.model_calls, 1)
        self.assertEqual(report.model_tokens, 20)
        self.assertEqual(report.step.intent if report.step else None, "inspect")
        self.assertEqual(report.inference["model"]["digest"], "sha256:" + "a" * 64)
        self.assertEqual(report.inference["options"]["seed"], 0)
        self.assertEqual(report.inference["options"]["temperature"], 0.0)
        self.assertEqual(report.inference["options"]["top_p"], 0.9)
        self.assertEqual(report.inference["options"]["num_ctx"], 4096)
        self.assertEqual(report.inference["options"]["num_predict"], 512)
        self.assertIn("nondeterminism_disclosure", report.inference)
        self.assertIn("generated_at_utc", report.to_dict())

    def test_invalid_model_output_is_a_failure_and_keeps_usage(self) -> None:
        client = OllamaClient(retries=0)
        response = {
            "message": {"content": "not valid AgentStep JSON"},
            "prompt_eval_count": 5,
            "eval_count": 3,
        }
        with patch.object(client, "model_metadata",
                          return_value=self._metadata("qwen2.5:3b")):
            with patch.object(client, "_post", return_value=response):
                report = run_real_agent_gate(
                    OllamaAgentAdapter("observer", client=client), self.observation,
                )

        self.assertEqual(report.status, RealAgentStatus.FAIL)
        self.assertEqual(report.reason, "inference_or_step_validation_failed")
        self.assertEqual(report.model_calls, 1)
        self.assertEqual(report.model_tokens, 8)
        self.assertIsNone(report.step)

    def test_ollama_metadata_captures_digest_and_quantization(self) -> None:
        client = OllamaClient(retries=0)
        tags = {
            "models": [{
                "name": "qwen2.5:1.5b",
                "digest": "sha256:" + "b" * 64,
                "size": 987,
                "details": {
                    "format": "gguf", "family": "qwen2", "parameter_size": "1.5B",
                    "quantization_level": "Q4_K_M",
                },
            }],
        }
        response = io.BytesIO(json.dumps(tags).encode("utf-8"))
        with patch("memory_fabric.adapters.ollama.urllib.request.urlopen",
                   return_value=response):
            metadata = client.model_metadata("qwen2.5:1.5b")

        self.assertEqual(metadata["digest"], "sha256:" + "b" * 64)
        self.assertEqual(metadata["quantization_level"], "Q4_K_M")
        self.assertEqual(metadata["parameter_size"], "1.5B")

    def test_chat_sends_pinned_sampling_and_context_options(self) -> None:
        client = OllamaClient(retries=0)
        captured: dict[str, object] = {}

        def respond(path, payload):
            captured.update({"path": path, "payload": payload})
            return {"message": {"content": "{}"}, "prompt_eval_count": 1,
                    "eval_count": 1}

        with patch.object(client, "_post", side_effect=respond):
            client.chat("qwen2.5:1.5b", [{"role": "user", "content": "{}"}],
                        temperature=0.0, top_p=0.9, seed=0, num_ctx=4096,
                        num_predict=256, schema={"type": "object"}, think=False)

        payload = captured["payload"]
        self.assertEqual(captured["path"], "/api/chat")
        self.assertEqual(payload["options"], {
            "temperature": 0.0, "top_p": 0.9, "seed": 0,
            "num_ctx": 4096, "num_predict": 256,
        })
        self.assertFalse(payload["think"])
        self.assertEqual(payload["format"], {"type": "object"})

    def test_run_cannot_pass_when_model_digest_is_missing(self) -> None:
        client = OllamaClient(retries=0)
        response = {
            "message": {"content": self._reply()},
            "prompt_eval_count": 13,
            "eval_count": 7,
        }
        metadata = self._metadata("qwen2.5:1.5b")
        metadata["digest"] = None
        with patch.object(client, "model_metadata", return_value=metadata):
            with patch.object(client, "_post", return_value=response):
                report = run_real_agent_gate(
                    OllamaAgentAdapter("observer", model="qwen2.5:1.5b", client=client),
                    self.observation,
                )

        self.assertEqual(report.status, RealAgentStatus.FAIL)
        self.assertEqual(report.reason, "model_provenance_incomplete")

    def test_offline_model_gate_passes_only_from_a_complete_real_agent_report(self) -> None:
        self.assertEqual(local_model_evidence_result(None)["status"], "REAL_AGENT_NOT_RUN")
        client = OllamaClient(retries=0)
        response = {
            "message": {"content": self._reply()},
            "prompt_eval_count": 13,
            "eval_count": 7,
        }
        with patch.object(client, "model_metadata",
                          return_value=self._metadata("qwen2.5:1.5b")):
            with patch.object(client, "_post", return_value=response):
                report = run_real_agent_gate(
                    OllamaAgentAdapter("observer", model="qwen2.5:1.5b", client=client),
                    self.observation,
                )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "real-agent-report.json"
            path.write_text(report.canonical_json(), encoding="utf-8")
            result = local_model_evidence_result(path)

        self.assertEqual(report.status, RealAgentStatus.PASS)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["model"], "qwen2.5:1.5b")
        self.assertEqual(result["model_digest"], "sha256:" + "a" * 64)
        self.assertEqual(len(result["report_sha256"]), 64)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
