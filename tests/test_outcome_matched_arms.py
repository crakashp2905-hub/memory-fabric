from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from benchmarks.agent_scale import outcome_task_manifest, task_manifest
from benchmarks.matched_agent_arms import ARMS, run as run_legacy_arm
from benchmarks.outcome_matched_arms import (
    OUTCOME_ARMS, _grade_case, build_outcome_matrix, run_paired_model_proposals,
)
from benchmarks.outcome_agents import OllamaOutcomePlanner
from memory_fabric.agent_outcomes.observations import AgentObservation


def test_outcome_matrix_preserves_task_ids_and_implemented_legacy_totals() -> None:
    seed = 701
    agent_count = 5
    report = build_outcome_matrix(seed=seed, agent_count=agent_count)
    expected_ids = [task["task_id"] for task in outcome_task_manifest(seed)]
    legacy_ids = [task["task_id"] for task in task_manifest(seed)]
    assert report["same_task_ids_all_arms"] is True
    assert report["parity_status"] == "PASS"
    assert report["mechanical_parity"]["status"] == "INCOMPLETE_NOT_RUN_ARMS"
    assert all(report["mechanical_parity"]["checks"].values())
    assert report["mechanical_parity"]["excluded_not_run_arm_ids"] == ["A6"]
    assert report["task_ids"] == expected_ids
    assert len(report["source"]["commit_sha"]) == 40
    assert isinstance(report["source"]["clean_at_start"], bool)
    assert report["environment"]["python"]
    assert expected_ids[:len(legacy_ids)] == legacy_ids
    comparison = report["strongest_non_oracle_comparison"]
    assert comparison["promotion_status"] == "NOT_ASSESSED"
    assert comparison["candidate_completion_rate"] > comparison["baseline_completion_rate"]
    assert comparison["baseline_arm"] in {"A0", "A1", "A2", "A4"}
    mapped_legacy = tuple(
        arm["legacy_arm"] for arm in OUTCOME_ARMS
        if arm["legacy_arm"] in ARMS
    )
    assert mapped_legacy == ("isolated", "pooled_shared", "memory_fabric", "oracle")
    assert OUTCOME_ARMS[3]["legacy_arm"] == "pooled_shared_plus_recovery"
    assert "blanket_retraction" in ARMS
    by_id = {arm["id"]: arm for arm in report["arms"]}
    assert [arm["id"] for arm in report["arms"]] == [f"A{index}" for index in range(8)]
    for arm in report["arms"]:
        assert arm["task_ids"] == expected_ids
    assert by_id["A5"]["status"] == "RUN"
    assert all(row["legacy_counts_reproducible"] is False
               for row in by_id["A5"]["case_outcomes"])
    assert by_id["A5"]["task_ids"] == expected_ids
    assert len(by_id["A5"]["case_outcomes"]) == len(expected_ids)
    assert by_id["A5"]["recovery_trace"]
    assert by_id["A5"]["observed_resource_use"]["recovery_alternates_found"] > 0
    assert all(row["status"] == "COMPLETED" for row in by_id["A5"]["case_outcomes"]
               if row["task_family"] == "recoverable")
    assert by_id["A6"]["status"] == "NOT_RUN"
    assert by_id["A6"]["case_outcomes"] == []
    assert "neither is an outcome-equivalent mapping" in by_id["A6"]["reason"]
    assert report["a5_same_case_comparisons"]["A5-A3"]["denominator"] == len(expected_ids)
    assert report["a5_same_case_comparisons"]["A5-A4"]["denominator"] == len(expected_ids)
    assert report["a5_same_case_comparisons"]["A5-A4"][
        "paired_completion_difference"
    ] > 0
    assert report["a5_same_case_comparisons"]["A5-A3"]["promotion_status"] == "NOT_ASSESSED"
    for arm_id in ("A0", "A1", "A2", "A3", "A4", "A7"):
        assert by_id[arm_id]["status"] == "RUN"
        legacy_name = by_id[arm_id]["legacy_arm"]
        assert by_id[arm_id]["counts"] == run_legacy_arm(
            seed, agent_count, legacy_name,
            task_cases=outcome_task_manifest(seed),
        )["counts"]
        if legacy_name in ARMS:
            assert by_id[arm_id]["legacy_base_counts"] == run_legacy_arm(
                seed, agent_count, legacy_name
            )["counts"]
    assert by_id["A3"]["counts"]["correct"] > by_id["A2"]["counts"]["correct"]
    assert by_id["A3"]["observed_resource_use"]["retrieval_calls"] == 120
    assert by_id["A2"]["observed_resource_use"]["retrieval_calls"] == 100
    assert by_id["A3"]["observed_resource_use"]["recovery_search_calls"] == 20
    assert by_id["A3"]["observed_resource_use"]["recovery_alternates_found"] == 10
    assert len(by_id["A3"]["recovery_trace"]) == 20
    assert sum(item["status"] == "ABSTAINED" for item in by_id["A3"]["recovery_trace"]) == 10
    assert sum(item["status"] == "RECOVERED" for item in by_id["A3"]["recovery_trace"]) == 10


def test_evaluator_grade_is_independent_of_arm_labels() -> None:
    record = {"expected": "allow", "decision_counts": {
        "unsafe_actions": 0, "false_abstentions": 0,
    }}
    labels = ("A1", "A4", "renamed-arm")
    grades = [_grade_case(dict(record, arm=label)) for label in labels]
    assert grades == ["COMPLETED"] * len(labels)


def test_process_contention_benchmark_reports_parallel_latency() -> None:
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(repository / "benchmarks" / "outcome_matched_arms.py"),
            "--workers", "1,2",
            "--tasks", "4",
            "--work-units", "1000",
        ],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["population"] == "SCRIPTED_AGENT"
    assert report["model_status"] == "REAL_AGENT_NOT_RUN"
    assert report["measurement"]["scheduler"] == (
        "OS process scheduler via ProcessPoolExecutor"
    )
    assert "No universal budget claimed" in report["measurement"]["latency_budget"]
    assert len(report["scenarios"]) == 2
    for scenario in report["scenarios"]:
        assert scenario["workers_observed"] >= 1
        assert scenario["tasks"] == 4
        assert scenario["submit_to_result_ms"]["p95"] >= (
            scenario["submit_to_result_ms"]["p50"]
        )
        assert scenario["submit_to_result_ms"]["p99"] >= (
            scenario["submit_to_result_ms"]["p95"]
        )


def test_matched_cli_emits_the_outcome_matrix() -> None:
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repository / "benchmarks" / "outcome_matched_arms.py"),
         "--mode", "matched", "--seed", "701", "--agent-count", "5"],
        cwd=repository, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["schema_id"] == "memory-fabric.outcome-matched-arms.v1"
    assert report["parity_status"] == "PASS"


def test_recorded_a5_development_probe_is_source_bound_and_non_confirmatory() -> None:
    artifact = Path(__file__).resolve().parents[1] / "research" / "results" / (
        "agent-outcome-a5-matched-development.json"
    )
    canonical_bytes = artifact.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(canonical_bytes).hexdigest() == (
        "ce844ed4cf1fe0212749e84ba96d5c74cd47ea333b27a2a3ebf253c365d5ae51"
    )
    report = json.loads(artifact.read_text(encoding="utf-8"))
    assert report["source"]["commit_sha"] == "8b8e6673c48f1e3f5e31b62a585ed0514e6d812c"
    assert report["source"]["clean_at_start"] is True
    assert report["seed"] == 701
    assert report["task_count"] == 10
    assert report["a5_same_case_comparisons"]["A5-A3"][
        "paired_completion_difference"
    ] == 0.0
    assert report["a5_same_case_comparisons"]["A5-A4"][
        "paired_completion_difference"
    ] == 0.2
    assert next(arm for arm in report["arms"] if arm["id"] == "A6")["status"] == (
        "NOT_RUN"
    )
    assert report["a5_same_case_comparisons"]["A5-A4"]["promotion_status"] == (
        "NOT_ASSESSED"
    )


def test_paired_model_proposals_hold_prompt_schema_and_output_budget_constant() -> None:
    class StubOllama:
        def __init__(self) -> None:
            self.calls = []

        def chat(self, model, messages, **kwargs):
            self.calls.append((model, messages, kwargs))
            observation = json.loads(messages[1]["content"])
            if observation["visible_events"]:
                event = observation["visible_events"][0]
                content = json.dumps({
                    "intent": "propose", "tool": "publish",
                    "arguments": {"target": "status", "value": "ready"},
                    "evidence_versions": [[event["memory_id"], event["version"]]],
                })
            else:
                content = json.dumps({
                    "intent": "abstain", "tool": None,
                    "arguments": {}, "evidence_versions": [],
                })
            return {"message": {"content": content}}

        def usage(self):
            return {"calls": float(len(self.calls)), "tokens": 12.0 * len(self.calls)}

    client = StubOllama()
    planner = OllamaOutcomePlanner(
        "pinned-local-model", client, model_digest="a" * 64,
        quantization="Q4_K_M", num_predict=48,
        tool_argument_types={"publish": {"target": str, "value": str}},
    )
    common = {
        "task_id": "paired-prompt-task",
        "instruction": "Publish the current visible status.",
        "permitted_tools": ("publish",),
        "budget": {"model_tokens": 48},
    }
    report = run_paired_model_proposals(planner, {
        "A0": AgentObservation(**common, visible_events=()),
        "A4": AgentObservation(**common, visible_events=(
            {"memory_id": "evidence-1", "version": 2, "content": "status: ready"},
        )),
    })

    assert report["model_status"] == "LOCAL_MODEL_INFERENCE_COMPLETED"
    assert report["qualification_status"] == "NOT_ASSESSED"
    assert report["parity"] == {
        "same_task_and_instruction": True,
        "same_permitted_tools_and_budget": True,
        "same_output_schema": True,
        "only_arm_specific_observation_field": "visible_events",
    }
    assert [row["status"] for row in report["arms"]] == [
        "STEP_VALIDATED", "STEP_VALIDATED",
    ]
    assert [row["intent"] for row in report["arms"]] == ["abstain", "propose"]
    assert report["model_calls"] == 2
    assert report["model_tokens"] == 24
    assert all(call[2]["num_predict"] == 48 for call in client.calls)
    assert client.calls[0][1][0] == client.calls[1][1][0]
    assert client.calls[0][2]["schema"] == client.calls[1][2]["schema"]


def test_paired_model_proposals_reject_changed_instruction_or_budget() -> None:
    class NoCallClient:
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("parity mismatch must fail before inference")

    client = NoCallClient()
    planner = OllamaOutcomePlanner(
        "pinned-local-model", client, model_digest="a" * 64, quantization="Q4_K_M",
    )
    base = AgentObservation("paired-mismatch", "Inspect evidence.", (), ("publish",),
                            {"model_tokens": 160})
    mismatch = AgentObservation("paired-mismatch", "Use a different prompt.", (),
                                ("publish",), {"model_tokens": 160})
    with pytest.raises(ValueError, match="share task, instruction, tools, and budgets"):
        run_paired_model_proposals(planner, {"A0": base, "A4": mismatch})
    assert client.calls == 0
