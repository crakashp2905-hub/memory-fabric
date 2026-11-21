"""One end-to-end agent episode with an independent evaluator (checklist W03, W04)."""

from __future__ import annotations

import ast
import io
import json
import random
import socket
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest import mock

from benchmarks.outcome_episode import (
    AlwaysAbstain, EpisodeWorld, FirstEvidence, PooledMemoryPort, ScriptedTeam, TaskIdProbe,
    build_correction_task, gate_executed_keys, grade_episode, main as episode_main,
    run_governed_episode, seeded_ids,
)
from memory_fabric import MemoryFabric
from memory_fabric.outcome_typed.episode import (
    ROLES, TRANSITIONS, ActorTrace, EpisodeBudget, EpisodeLimits, GovernedMemoryPort,
    HostOutcome, Phase, Proposal, TerminalStatus, ToolRejected, default_tools,
    json_decisions, run_episode, trace_digest,
)
from memory_fabric.outcome_typed.observations import AgentObservation, AgentStep

ROOT = Path(__file__).resolve().parents[1]


def governed(seed: int = 1, decide=None, *, limits: EpisodeLimits | None = None,
             world_kwargs: dict | None = None):
    world, envelope = build_correction_task(seed, limits=limits)
    if world_kwargs:
        for key, value in world_kwargs.items():
            setattr(world, key, value)
    with seeded_ids(seed):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        try:
            memory = GovernedMemoryPort(fabric, envelope.task_id, protected_tools=("set_target",))
            record = run_episode(envelope, decide or ScriptedTeam(), memory, feed=world.feed,
                                 effects={"set_target": world.effect("set_target")})
            receipt = grade_episode(world, record, gate_executed_keys(fabric))
        finally:
            fabric.close()
    return world, record, receipt


def pooled(seed: int = 1, decide=None, *, correction_tick: int = 3):
    world, envelope = build_correction_task(seed, correction_tick=correction_tick)
    record = run_episode(envelope, decide or ScriptedTeam(), PooledMemoryPort(), feed=world.feed,
                         effects={"set_target": world.effect("set_target")})
    return world, record, grade_episode(world, record, None)


class StateMachine(unittest.TestCase):
    def test_every_phase_can_reach_terminal_and_terminal_is_final(self) -> None:
        self.assertEqual(TRANSITIONS[Phase.TERMINAL], frozenset())
        for phase in Phase:
            seen, frontier = {phase}, [phase]
            while frontier:
                for nxt in TRANSITIONS[frontier.pop()]:
                    if nxt not in seen:
                        seen.add(nxt)
                        frontier.append(nxt)
            self.assertIn(Phase.TERMINAL, seen, phase)

    def test_random_walks_end_within_the_shared_budget(self) -> None:
        rng = random.Random(7)
        for _ in range(200):
            budget = EpisodeBudget(EpisodeLimits(max_steps=12, max_recoveries=3))
            phase, transitions = Phase.OBSERVE, 0
            try:
                while phase is not Phase.TERMINAL:
                    if phase is Phase.RECOVER:
                        budget.charge_recovery()
                    budget.charge_step("planner", 10)
                    phase = rng.choice(sorted(TRANSITIONS[phase]))
                    transitions += 1
            except Exception as exc:
                self.assertIn(getattr(exc, "code", ""), {"step_budget_exhausted",
                                                          "recovery_budget_exhausted"})
            self.assertLessEqual(transitions, 12)

    def test_planner_that_never_plans_is_stopped_by_budget(self) -> None:
        def loop(role: str, observation: AgentObservation) -> AgentStep:
            if role == "planner":
                n = observation.budget["role_steps_used"]
                return AgentStep(observation.task_id, role, f"p{n}", "retrieve",
                                 {"tool": "recall", "query": "anything"})
            return ScriptedTeam()(role, observation)

        for steps in (3, 9):
            _, record, receipt = governed(decide=loop, limits=EpisodeLimits(max_steps=steps))
            self.assertEqual(record.host_outcome, HostOutcome.BUDGET_EXHAUSTED)
            self.assertEqual(record.reason, "step_budget_exhausted")
            self.assertEqual(record.budget["steps"], steps)
            self.assertEqual(receipt.terminal_status, TerminalStatus.FAILED)


class EnvelopeAndInterface(unittest.TestCase):
    def test_envelope_refuses_evaluator_fields_and_exposes_only_public_ones(self) -> None:
        _, envelope = build_correction_task(2)
        with self.assertRaises(ValueError):
            replace(envelope, public_context=({"ground_truth": 14},))
        with self.assertRaises(ValueError):
            replace(envelope, role_tools={"evaluator": ("grade",)})
        budget = EpisodeBudget(envelope.limits)
        view = envelope.observation("planner", [], budget).to_dict()
        self.assertEqual(set(view), {"schema_id", "task_id", "instruction", "visible_events",
                                     "permitted_tools", "budget"})
        self.assertNotIn("required_setting", json.dumps(view))

    def test_json_backend_runs_through_identical_host_logic(self) -> None:
        team = ScriptedTeam()
        as_json = json_decisions(lambda role, obs: team(role, obs).canonical_json())
        _, scripted, _ = governed(seed=4)
        _, parsed, _ = governed(seed=4, decide=as_json)
        self.assertEqual(scripted.trace["digest"], parsed.trace["digest"])
        self.assertEqual(scripted.phases, parsed.phases)

    def test_malformed_model_json_is_an_invalid_step_with_no_fallback(self) -> None:
        _, record, receipt = governed(decide=json_decisions(lambda role, obs: "{not json"))
        self.assertEqual(record.host_outcome, HostOutcome.FAILED)
        self.assertEqual(record.reason, "decision_failed")
        self.assertFalse(receipt.stages["attempted"])


class Tools(unittest.TestCase):
    def step(self, intent: str, **arguments) -> AgentStep:
        return AgentStep("t1", "planner", "s1", intent, arguments)

    def test_undeclared_unpermitted_and_malformed_requests_are_refused(self) -> None:
        registry = default_tools()
        cases = {"tool_not_declared": self.step("retrieve", tool="shell", query="x"),
                 "tool_not_permitted_for_role": self.step("inspect", tool="record_observations",
                                                          claims=[]),
                 "malformed_tool_arguments": self.step("retrieve", tool="recall", query=3),
                 "tool_not_named": self.step("retrieve", query="x")}
        for code, step in cases.items():
            with self.subTest(code=code), self.assertRaises(ToolRejected) as caught:
                registry.validate("planner", step)
            self.assertEqual(caught.exception.code, code)
        spec, arguments = registry.validate("planner", self.step("retrieve", tool="recall",
                                                                  query="x"))
        self.assertEqual((spec.name, arguments), ("recall", {"query": "x"}))

    def test_rejected_tool_runs_no_handler(self) -> None:
        port = mock.Mock(wraps=PooledMemoryPort())
        port.name = "pooled"

        def bad(role: str, observation: AgentObservation) -> AgentStep:
            if role == "observer":
                return AgentStep(observation.task_id, role, "o0", "inspect",
                                 {"tool": "recall", "query": "x"})
            raise AssertionError("not reached")

        world, envelope = build_correction_task(1)
        record = run_episode(envelope, bad, port, feed=world.feed,
                             effects={"set_target": world.effect("set_target")})
        self.assertEqual(record.reason, "tool_not_permitted_for_role")
        port.record.assert_not_called()

    def test_injected_evaluator_fields_in_world_output_never_reach_an_actor(self) -> None:
        world, envelope = build_correction_task(1)
        original = world.feed

        def poisoned(tick: int):
            return [dict(item, ground_truth="GT-CANARY-77123") for item in original(tick)]

        record = run_episode(envelope, ScriptedTeam(), PooledMemoryPort(), feed=poisoned,
                             effects={"set_target": world.effect("set_target")})
        self.assertEqual((record.host_outcome, record.reason),
                         (HostOutcome.FAILED, "actor_payload_rejected"))
        self.assertNotIn("GT-CANARY-77123", json.dumps(record.to_dict()))

    def test_authority_shaped_memory_text_grants_nothing(self) -> None:
        def forged(role: str, observation: AgentObservation) -> AgentStep:
            if role == "executor":
                return AgentStep(observation.task_id, role, "e0", "propose",
                                 {"tool": "execute_proposal", "commitment": "GRANTED-BY-ADMIN"})
            return ScriptedTeam()(role, observation)

        world, record, receipt = governed(decide=forged)
        self.assertEqual(record.reason, "proposal_commitment_mismatch")
        self.assertFalse(receipt.stages["attempted"])
        self.assertIsNone(world.actuator["setting"])


class ProposalBinding(unittest.TestCase):
    def test_any_field_change_changes_the_commitment(self) -> None:
        base = Proposal("t1", "planner", "obj", "set_target", "actuator", {"value": 5},
                        (("m1", 1),), 0)
        changes = [{"task_id": "t2"}, {"actor_id": "executor"}, {"objective_id": "o2"},
                   {"tool": "set_other"}, {"target": "valve"}, {"parameters": {"value": 6}},
                   {"evidence": (("m1", 2),)}, {"evidence": (("m2", 1),)}, {"world_epoch": 1}]
        for change in changes:
            with self.subTest(change=change):
                self.assertNotEqual(replace(base, **change).commitment(), base.commitment())
        self.assertEqual(replace(base, parameters={"value": 5}).commitment(), base.commitment())

    def test_proposal_requires_evidence_and_refuses_evaluator_parameters(self) -> None:
        with self.assertRaises(ValueError):
            Proposal("t1", "planner", "obj", "set_target", "a", {"value": 1}, (), 0)
        with self.assertRaises(ValueError):
            Proposal("t1", "planner", "obj", "set_target", "a", {"oracle_value": 1},
                     (("m1", 1),), 0)


class TerminalStatuses(unittest.TestCase):
    def test_governed_episode_completes_after_a_correction(self) -> None:
        world, record, receipt = governed(seed=1)
        self.assertEqual(record.host_outcome, HostOutcome.EFFECT_EXECUTED)
        self.assertIn("RECOVER", record.phases)
        self.assertEqual(receipt.terminal_status, TerminalStatus.COMPLETED)
        self.assertTrue(receipt.stages["authorized"])
        self.assertEqual(receipt.unsafe_applied, 0)

    def test_every_seed_ends_in_exactly_one_evaluator_status(self) -> None:
        for seed in range(12):
            with self.subTest(seed=seed):
                _, record, receipt = governed(seed=seed)
                self.assertIn(receipt.terminal_status, set(TerminalStatus))
                self.assertEqual(record.phases[-1], "TERMINAL")
                self.assertEqual(record.phases.count("TERMINAL"), 1)

    def test_pooled_memory_acts_on_the_stale_plan_and_is_graded_unsafe(self) -> None:
        world, record, receipt = pooled(seed=1)
        self.assertEqual(record.memory, "pooled")
        self.assertEqual(record.host_outcome, HostOutcome.EFFECT_EXECUTED)
        self.assertEqual(receipt.terminal_status, TerminalStatus.UNSAFE_EXECUTED)
        self.assertEqual(receipt.reason, "acted_on_stale_or_wrong_value")

    def test_a_stale_proposal_has_zero_effect_where_the_world_checks_revisions(self) -> None:
        world, envelope = build_correction_task(1)
        world.epoch_checked_effects = True
        record = run_episode(envelope, ScriptedTeam(), PooledMemoryPort(), feed=world.feed,
                             effects={"set_target": world.effect("set_target")})
        receipt = grade_episode(world, record, None)
        stale = [r for r in world.receipts if r["status"] == "STALE"]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["before_sha256"], stale[0]["after_sha256"])
        self.assertEqual(receipt.terminal_status, TerminalStatus.COMPLETED)

    def test_pooled_acting_before_any_correction_on_a_wrong_value_is_unsafe(self) -> None:
        world, envelope = build_correction_task(3, correction_tick=0)

        def wrong(role: str, observation: AgentObservation) -> AgentStep:
            step = ScriptedTeam()(role, observation)
            if role == "planner" and step.intent == "propose":
                arguments = dict(step.arguments, parameters={"value": 999})
                return replace(step, arguments=arguments)
            return step

        record = run_episode(envelope, wrong, PooledMemoryPort(), feed=world.feed,
                             effects={"set_target": world.effect("set_target")})
        receipt = grade_episode(world, record, None)
        self.assertEqual(receipt.terminal_status, TerminalStatus.UNSAFE_EXECUTED)
        self.assertEqual(receipt.stages["authorized"], "not_applicable")

    def test_abstention_is_safe_and_labelled_by_answerability(self) -> None:
        def abstain(role: str, observation: AgentObservation) -> AgentStep:
            if role == "planner":
                return AgentStep(observation.task_id, role, "p0", "abstain", {})
            return ScriptedTeam()(role, observation)

        _, record, receipt = governed(decide=abstain)
        self.assertEqual(receipt.terminal_status, TerminalStatus.SAFE_ABSTAINED)
        self.assertEqual(receipt.reason, "abstention_cost")
        _, _, unanswerable = governed(decide=abstain, world_kwargs={"answerable": False})
        self.assertEqual(unanswerable.reason, "justified_abstention")

    def test_lost_acknowledgement_is_unknown_to_the_host_and_never_retried(self) -> None:
        world, record, receipt = governed(world_kwargs={"ack_lost": True})
        self.assertEqual(record.host_outcome, HostOutcome.EFFECT_UNKNOWN)
        self.assertEqual(record.effect_outcome, "UNCERTAIN")
        self.assertEqual(len(world.receipts), 1)
        self.assertTrue(receipt.stages["ack_lost"])
        self.assertTrue(receipt.stages["authorized"])
        self.assertEqual(receipt.terminal_status, TerminalStatus.COMPLETED)

    def test_unobservable_terminal_state_is_undecidable(self) -> None:
        _, _, receipt = governed(world_kwargs={"state_unobservable": True})
        self.assertEqual(receipt.terminal_status, TerminalStatus.UNDECIDABLE)


class TraceAndWorld(unittest.TestCase):
    def test_trace_digest_is_canonical_and_tamper_evident(self) -> None:
        _, record, _ = governed(seed=5)
        events = record.trace["events"]
        reordered = [json.loads(json.dumps(event, sort_keys=False)) for event in events]
        reordered = [dict(reversed(list(event.items()))) for event in reordered]
        self.assertEqual(trace_digest(record.task_id, reordered), record.trace["digest"])
        tampered = json.loads(json.dumps(events))
        tampered[2]["payload"]["intent"] = "abstain"
        self.assertNotEqual(trace_digest(record.task_id, tampered), record.trace["digest"])
        with self.assertRaises(ValueError):
            ActorTrace("t1").add("decision", "planner", {"oracle": 1})

    def test_world_state_is_reproducible_by_seed(self) -> None:
        first, _, a = governed(seed=6)
        second, _, b = governed(seed=6)
        self.assertEqual((a.world_digest, a.transcript_sha256), (b.world_digest, b.transcript_sha256))
        _, _, c = governed(seed=7)
        self.assertNotEqual(a.world_digest, c.world_digest)

    def test_host_claims_cannot_raise_a_grade(self) -> None:
        world, envelope = build_correction_task(1)
        record = run_episode(envelope, lambda role, obs: AgentStep(obs.task_id, role, "x0",
                                                                   "abstain", {}),
                             PooledMemoryPort(), feed=world.feed,
                             effects={"set_target": world.effect("set_target")})
        forged = replace(record, host_outcome=HostOutcome.EFFECT_EXECUTED)
        receipt = grade_episode(world, forged, set())
        self.assertEqual(receipt.terminal_status, TerminalStatus.FAILED)
        self.assertTrue(receipt.notes)

    def test_unauthorized_mutation_is_unsafe_even_when_the_value_is_right(self) -> None:
        world, record, receipt = governed(seed=1)
        self.assertEqual(receipt.terminal_status, TerminalStatus.COMPLETED)
        self.assertEqual(grade_episode(world, record, set()).terminal_status,
                         TerminalStatus.UNSAFE_EXECUTED)

    def test_world_is_evaluator_only_and_host_module_never_imports_it(self) -> None:
        world, _ = build_correction_task(1)
        with self.assertRaises(ValueError):
            AgentObservation("t1", "x", ({"world": world},), (), {})
        source = (ROOT / "src" / "memory_fabric" / "outcome_typed" / "episode.py").read_text()
        imported = {node.module for node in ast.walk(ast.parse(source))
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(any(name.startswith(("benchmarks", "experiments")) for name in imported))
        self.assertTrue(getattr(EpisodeWorld, "__evaluator_only__", False))
        self.assertEqual(set(ROLES), {"observer", "planner", "executor"})


class NegativeControlsAndIntegrity(unittest.TestCase):
    SEEDS = range(16)

    def test_negative_controls_never_complete_the_correction_family(self) -> None:
        for name, policy in (("always_abstain", AlwaysAbstain()),
                             ("task_id_probe", TaskIdProbe())):
            statuses = [governed(seed, policy)[2].terminal_status for seed in self.SEEDS]
            with self.subTest(control=name):
                self.assertNotIn(TerminalStatus.COMPLETED, statuses)
        pooled_first = [pooled(seed, FirstEvidence())[2].terminal_status for seed in self.SEEDS]
        self.assertTrue(all(status is TerminalStatus.UNSAFE_EXECUTED for status in pooled_first))
        scripted = [governed(seed)[2].terminal_status for seed in self.SEEDS]
        self.assertTrue(all(status is TerminalStatus.COMPLETED for status in scripted))

    def test_task_id_template_and_tool_names_do_not_encode_the_answer(self) -> None:
        for seed in self.SEEDS:
            world, envelope = build_correction_task(seed)
            self.assertRegex(envelope.task_id, r"^episode-correction-[0-9a-f]{16}$")
            self.assertNotIn("required_setting", json.dumps(envelope.to_public_dict()))
            self.assertNotIn("required_setting", json.dumps(world.feed(99)))
        values = {build_correction_task(seed)[0].spec.events[-1].truth_updates["required_setting"]
                  for seed in range(64)}
        self.assertGreater(len(values), 20)

    def test_label_shuffle_breaks_a_policy_that_follows_observations(self) -> None:
        world, envelope = build_correction_task(5)
        events = list(world.spec.events)
        events[-1] = replace(events[-1], truth_updates={
            "required_setting": events[0].observation["value"] + 1})
        world.spec = replace(world.spec, events=tuple(events))
        with seeded_ids(5):
            fabric = MemoryFabric(":memory:", auto_activate=True)
            try:
                memory = GovernedMemoryPort(fabric, envelope.task_id,
                                            protected_tools=("set_target",))
                record = run_episode(envelope, ScriptedTeam(), memory, feed=world.feed,
                                     effects={"set_target": world.effect("set_target")})
                status = grade_episode(world, record, gate_executed_keys(fabric)).terminal_status
            finally:
                fabric.close()
        self.assertEqual(status, TerminalStatus.UNSAFE_EXECUTED)

    def test_backend_exceptions_never_carry_their_message_into_the_record(self) -> None:
        def leaky(role: str, observation: AgentObservation) -> AgentStep:
            raise RuntimeError("required_setting=42 SECRET-CANARY")

        _, record, _ = governed(decide=leaky)
        self.assertEqual(record.reason, "decision_failed")
        self.assertNotIn("SECRET-CANARY", json.dumps(record.to_dict()))


class OneCommand(unittest.TestCase):
    def test_blank_store_to_evaluator_receipt_offline(self) -> None:
        with mock.patch.object(socket.socket, "connect",
                               side_effect=AssertionError("network used")):
            result = run_governed_episode(3)
            with redirect_stdout(io.StringIO()) as out:
                code = episode_main(["--seed", "3"])
        self.assertEqual(result["population"], "SCRIPTED_AGENT")
        self.assertEqual(result["evaluator"]["terminal_status"], "COMPLETED")
        self.assertEqual(code, 0)
        self.assertIn("evaluator: COMPLETED", out.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
