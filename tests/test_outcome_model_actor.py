"""Local-model actor over the canonical runtime: actor-only input, strict output, distinct failures.

Every backend here is FAKE: an in-process object answering in the model's JSON
channel. These tests show the plumbing, never model behaviour, and the harness
labels their output ``FAKE_BACKEND_NOT_EVIDENCE``.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Callable

from benchmarks.outcome_arms import ARMS, build_task, run_arm
from benchmarks.outcome_episode import ScriptedTeam
from benchmarks.outcome_model_team import not_run, run_model_team
from memory_fabric.adapters.ollama import OllamaClient, OllamaError
from memory_fabric.outcome_typed.episode import ActorBackendError
from memory_fabric.outcome_typed.model_actor import (
    ModelActor, ModelConfig, classify_backend_error, parse_decision,
)
from memory_fabric.outcome_typed.observations import AgentObservation

CONFIG = ModelConfig(model="fake-model", digest="sha256:fake", runtime_version="fake")
OBSERVATION_KEYS = {"schema_id", "task_id", "instruction", "visible_events", "permitted_tools",
                    "budget"}


class FakeBackend:
    """FAKE. Answers each role the way the scripted team would, through JSON text."""

    def __init__(self, mutate: Callable[[str, dict[str, Any]], dict[str, Any] | str] | None = None,
                 usage: tuple[int, int] = (100, 20)) -> None:
        self.team = ScriptedTeam()
        self.mutate = mutate
        self.usage = usage
        self.messages: list[list[dict[str, str]]] = []

    def chat(self, model: str, messages: Any, **options: Any) -> dict[str, Any]:
        self.messages.append([dict(m) for m in messages])
        role = messages[0]["content"].split("You are the ", 1)[1].split(" ", 1)[0]
        observation = AgentObservation.from_json(messages[1]["content"])
        step = self.team(role, observation)
        answer: dict[str, Any] | str = {"intent": step.intent,
                                        "arguments": json.loads(step.canonical_json())["arguments"]}
        if self.mutate is not None:
            answer = self.mutate(role, answer)  # type: ignore[arg-type]
        content = answer if isinstance(answer, str) else json.dumps(answer)
        return {"message": {"content": content}, "prompt_eval_count": self.usage[0],
                "eval_count": self.usage[1]}


class Raising:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def chat(self, model: str, messages: Any, **options: Any) -> dict[str, Any]:
        raise self.exc


def episode(backend: Any, arm: str = "A5", family: str = "public_correction",
            config: ModelConfig = CONFIG) -> tuple[dict[str, Any], ModelActor]:
    actor = ModelActor(backend, config)
    return run_arm(ARMS[arm], build_task(family, 0), decide=actor), actor


class Plumbing(unittest.TestCase):
    def test_json_channel_reproduces_the_scripted_team_exactly(self) -> None:
        for arm in ("A3", "A4", "A5"):
            for family in ("public_correction", "restricted_source"):
                with self.subTest(arm=arm, family=family):
                    task = build_task(family, 0)
                    scripted = run_arm(ARMS[arm], task)
                    modelled, actor = episode(FakeBackend(), arm, family)
                    self.assertEqual(modelled["terminal_status"], scripted["terminal_status"])
                    self.assertEqual(modelled["host_reason"], scripted["host_reason"])
                    self.assertTrue(actor.calls)
                    self.assertTrue(all(call["outcome"] == "ok" for call in actor.calls))

    def test_the_model_sees_only_a_system_prompt_and_the_canonical_observation(self) -> None:
        backend = FakeBackend()
        episode(backend)
        for messages in backend.messages:
            self.assertEqual([m["role"] for m in messages], ["system", "user"])
            self.assertEqual(set(json.loads(messages[1]["content"])), OBSERVATION_KEYS)
            for forbidden in ("truth", "oracle", "best_terminal", "expected", "evaluator"):
                self.assertNotIn(f'"{forbidden}', messages[1]["content"])

    def test_calls_are_logged_with_a_pinned_fingerprint_and_unknown_tokens_stay_unknown(self) -> None:
        backend = FakeBackend()
        _, actor = episode(backend)
        fingerprints = {call["config_fingerprint"] for call in actor.calls}
        self.assertEqual(fingerprints, {CONFIG.fingerprint(actor.tools)})
        usage = actor.usage()
        self.assertEqual(usage["roles"]["planner"]["calls_with_unknown_tokens"], 0)

        class NoCounts(FakeBackend):
            def chat(self, model: str, messages: Any, **options: Any) -> dict[str, Any]:
                reply = super().chat(model, messages, **options)
                return {"message": reply["message"]}

        _, actor = episode(NoCounts())
        planner = actor.usage()["roles"]["planner"]
        self.assertEqual(planner["calls_with_unknown_tokens"], planner["calls"])
        self.assertEqual(planner["prompt_tokens"], 0)

    def test_any_pinned_setting_changes_the_fingerprint(self) -> None:
        from memory_fabric.outcome_typed.episode import default_tools

        tools = default_tools()
        base = CONFIG.fingerprint(tools)
        for change in ({"digest": "sha256:other"}, {"temperature": 0.5}, {"num_ctx": 8192},
                       {"seed": 1}, {"runtime_version": "0.0.1"}):
            with self.subTest(change=change):
                self.assertNotEqual(ModelConfig(**{**CONFIG.__dict__, **change}).fingerprint(tools),
                                    base)
        self.assertNotEqual(CONFIG.fingerprint(default_tools("other_tool")), base)
        with self.assertRaises(ValueError):
            ModelConfig(model="m", digest="", runtime_version="x")


class DistinctFailures(unittest.TestCase):
    def assert_incomplete(self, backend: Any, reason: str,
                          config: ModelConfig = CONFIG) -> dict[str, Any]:
        row, _ = episode(backend, config=config)
        self.assertEqual(row["host_outcome"], "FAILED")
        self.assertEqual(row["host_reason"], reason)
        self.assertFalse(row["completed"])
        return row

    def test_malformed_json_and_extra_fields(self) -> None:
        self.assert_incomplete(FakeBackend(lambda role, a: "not json"), "model_malformed_output")
        self.assert_incomplete(FakeBackend(lambda role, a: {**a, "note": "x"}),
                               "model_malformed_output")
        self.assert_incomplete(FakeBackend(lambda role, a: {**a, "intent": "act"}),
                               "model_malformed_output")

    def test_invalid_tool_name(self) -> None:
        def rename(role: str, answer: dict[str, Any]) -> dict[str, Any]:
            if role == "planner":
                answer["arguments"]["tool"] = "delete_everything"
            return answer
        self.assert_incomplete(FakeBackend(rename), "tool_not_declared")

    def test_hallucinated_evidence_is_refused_before_verification(self) -> None:
        def invent(role: str, answer: dict[str, Any]) -> dict[str, Any]:
            if role == "planner" and "evidence" in answer["arguments"]:
                answer["arguments"]["evidence"] = [["mem_invented", 1]]
            return answer
        self.assert_incomplete(FakeBackend(invent), "evidence_not_retrieved")

    def test_timeout_oom_unavailable_and_unknown_errors(self) -> None:
        cases = {
            "model_timeout": TimeoutError("read timed out"),
            "model_out_of_memory": OllamaError("/api/chat failed (500): CUDA error: out of memory"),
            "model_unavailable": OllamaError("cannot reach Ollama at http://127.0.0.1:9: refused"),
            "model_error": RuntimeError("something else"),
        }
        for code, exc in cases.items():
            with self.subTest(code=code):
                self.assertEqual(classify_backend_error(exc), code)
                self.assert_incomplete(Raising(exc), code)

    def test_context_overflow_and_truncated_output(self) -> None:
        self.assert_incomplete(FakeBackend(usage=(CONFIG.num_ctx, 5)), "model_context_overflow")
        self.assert_incomplete(FakeBackend(usage=(10, CONFIG.num_predict)), "model_truncated")

    def test_per_role_call_budget(self) -> None:
        tight = ModelConfig(**{**CONFIG.__dict__, "calls_per_role": 1})
        self.assert_incomplete(FakeBackend(), "model_call_budget_exhausted", tight)

    def test_a_real_client_whose_runtime_drops_the_connection_is_unavailable(self) -> None:
        # A listener that accepts and closes every connection fails the same way on
        # every OS. (A closed port does not: Windows retries the connect until the
        # client's timeout, which is then, correctly, a timeout.)
        import socket
        import threading

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()

        def drop() -> None:
            while True:
                try:
                    connection, _ = listener.accept()
                except OSError:
                    return
                connection.close()

        threading.Thread(target=drop, daemon=True).start()
        try:
            port = listener.getsockname()[1]
            client = OllamaClient(host=f"http://127.0.0.1:{port}", retries=0, timeout=10)
            self.assert_incomplete(client, "model_unavailable")
        finally:
            listener.close()

    def test_parse_decision_is_strict(self) -> None:
        self.assertEqual(parse_decision('{"intent": "abstain", "arguments": {}}'), ("abstain", {}))
        for bad in ('[]', '{"intent": "abstain"}', '{"intent": "abstain", "arguments": []}', None):
            with self.assertRaises(ActorBackendError):
                parse_decision(bad)


class ModelTeamHarness(unittest.TestCase):
    def test_fake_backend_runs_matched_arms_and_is_never_evidence(self) -> None:
        report = run_model_team("fake-model", seeds=1, families=("public_correction",),
                                backend=FakeBackend())
        self.assertEqual(report["status"], "FAKE_BACKEND")
        self.assertEqual(report["local_model_evidence"], "FAKE_BACKEND_NOT_EVIDENCE")
        self.assertEqual({row["arm"] for row in report["rows"]}, {"A3", "A4", "A5"})
        self.assertIn("A6", report["not_run_arms"])
        self.assertEqual(len(report["config_fingerprints"]), 1)
        self.assertTrue(all(row["inference_backed_steps"] > 0 for row in report["rows"]))
        self.assertEqual(report["promotion"], "NOT_ASSESSED")

    def test_no_runtime_is_real_agent_not_run_without_a_substitute(self) -> None:
        report = run_model_team("qwen2.5:1.5b", host="http://127.0.0.1:9")
        self.assertEqual(report["status"], "REAL_AGENT_NOT_RUN")
        self.assertEqual(report["rows"], [])
        self.assertFalse(report["scripted_substitute_used"])
        self.assertEqual(not_run("X")["local_model_evidence"], "REAL_AGENT_NOT_RUN")

    def test_command_line_exits_3_when_no_model_runs(self) -> None:
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "team.json"
            done = subprocess.run(
                [sys.executable, "-m", "benchmarks.outcome_model_team", "--model", "qwen2.5:1.5b",
                 "--host", "http://127.0.0.1:9", "--out", str(out)],
                cwd=root, capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 3, done.stderr)
            self.assertEqual(json.loads(out.read_text())["status"], "REAL_AGENT_NOT_RUN")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
