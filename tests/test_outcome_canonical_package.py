"""One canonical outcome runtime, translations from the legacy packages, and a surface gate (W02)."""

from __future__ import annotations

import ast
import importlib
import json
import re
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import outcome_package_inventory as inventory  # noqa: E402

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from memory_fabric.agent_outcomes import (  # noqa: E402
        AgentObservation as V1Observation, AgentStep as V1Step, EpisodeOutcome as V1Outcome,
    )
    from memory_fabric.outcome_protocol import (  # noqa: E402
        AgentObservation as ProtocolObservation, AgentStep as ProtocolStep,
        RecoveryStatus as ProtocolRecoveryStatus,
    )

from memory_fabric.outcome_typed import compat  # noqa: E402
from memory_fabric.outcome_typed.observations import (  # noqa: E402
    AgentObservation, AgentStep, EpisodeOutcome, OracleTask,
)
from memory_fabric.outcome_typed.recovery import RecoveryStatus  # noqa: E402

DIGEST = "a" * 64
CONTRACT_CLASSES = {"AgentObservation", "AgentStep", "EpisodeOutcome", "RecoveryEpisode",
                    "RuntimeResult", "FailureCode", "OracleTask", "TerminalGrade",
                    "RecoveryStatus", "RecoveryLimits"}
OUTCOME_PACKAGES = {"agent_outcomes", "outcome_protocol", "outcome_typed"}


class Inventory(unittest.TestCase):
    def test_committed_inventory_is_current_and_names_the_conflicts(self) -> None:
        self.assertEqual(inventory.OUT.read_text(encoding="utf-8"), inventory.render(),
                         "regenerate: python tools/outcome_package_inventory.py --write")
        data = json.loads(inventory.render())
        shared = data["shared_names"]
        self.assertEqual(shared["SCHEMA_ID"]["classification"], "conflicting")
        self.assertEqual(shared["RecoveryStatus"]["classification"], "conflicting")
        self.assertEqual(shared["AgentObservation"]["classification"], "identical")
        self.assertEqual(data["unique_names"]["agent_outcomes"], [])

    def test_adr_assigns_every_responsibility_to_an_existing_canonical_module(self) -> None:
        adr = (ROOT / "docs" / "adr" / "0004-canonical-outcome-runtime.md").read_text()
        modules = set(re.findall(r"`outcome_typed\.([a-z_]+)`", adr))
        self.assertTrue(modules)
        for module in modules:
            with self.subTest(module=module):
                self.assertTrue((ROOT / "src" / "memory_fabric" / "outcome_typed"
                                 / f"{module}.py").is_file())


class Translation(unittest.TestCase):
    def test_observations_and_steps_round_trip_from_both_legacy_packages(self) -> None:
        for observation_cls, step_cls in ((V1Observation, V1Step),
                                          (ProtocolObservation, ProtocolStep)):
            with self.subTest(package=observation_cls.__module__):
                legacy = observation_cls("t1", "do it", ({"reading": 4},), ("recall",), {"steps": 3})
                canonical = compat.observation_from_legacy(legacy)
                self.assertEqual(canonical.schema_id, "memory-fabric.agent-outcomes.v3")
                self.assertEqual(compat.observation_to_legacy(canonical, observation_cls).to_dict(),
                                 legacy.to_dict())
                step = step_cls("t1", "planner", "s1", "propose", {"value": 4}, (("m1", 2),))
                self.assertEqual(compat.step_to_legacy(compat.step_from_legacy(step),
                                                       step_cls).to_dict(), step.to_dict())

    def test_legacy_outcome_needs_the_facts_v1_never_recorded(self) -> None:
        legacy = V1Outcome("t1", "A5", 1, True, 0, 0, 0, 1, 1, 0, 0, 1.0, DIGEST)
        with self.assertRaises(compat.IncompatibleRecord):
            compat.outcome_from_legacy(legacy)
        translated = compat.outcome_from_legacy(legacy, attempted_unsafe_effects=1,
                                                executed_unsafe_effects=0)
        self.assertEqual(translated.attempted_unsafe_effects, 1)
        with self.assertRaises(compat.IncompatibleRecord):
            compat.outcome_to_legacy(translated, V1Outcome)
        failed = V1Outcome("t2", "A0", 1, False, 0, 0, 0, 0, 0, 0, 0, 1.0, DIGEST)
        with self.assertRaises(compat.IncompatibleRecord):
            compat.outcome_from_legacy(failed, attempted_unsafe_effects=0, executed_unsafe_effects=0)
        clean = compat.outcome_from_legacy(legacy, attempted_unsafe_effects=0,
                                           executed_unsafe_effects=0)
        self.assertEqual(compat.outcome_to_legacy(clean, V1Outcome), legacy)

    def test_recovery_statuses_without_an_equivalent_are_incompatible(self) -> None:
        self.assertIs(compat.recovery_status_from_legacy(ProtocolRecoveryStatus.BLOCKED),
                      RecoveryStatus.BLOCKED)
        with self.assertRaises(compat.IncompatibleRecord):
            compat.recovery_status_from_legacy(ProtocolRecoveryStatus.DISABLED)
        with self.assertRaises(compat.IncompatibleRecord):
            compat.recovery_status_to_legacy(RecoveryStatus.ESCALATED, ProtocolRecoveryStatus)

    def test_identity_and_versions_are_never_reinterpreted(self) -> None:
        with self.assertRaises(compat.IncompatibleRecord):
            compat.step_from_legacy({"schema_id": compat.LEGACY_SCHEMA_ID, "task_id": "bad id!",
                                     "actor_id": "a", "step_id": "s", "intent": "ask",
                                     "arguments": {}, "evidence_versions": []})
        with self.assertRaises(compat.IncompatibleRecord):
            compat.step_from_legacy({"schema_id": compat.LEGACY_SCHEMA_ID, "task_id": "t",
                                     "actor_id": "a", "step_id": "s", "intent": "ask",
                                     "arguments": {}, "evidence_versions": [["m1", -1]]})
        with self.assertRaises(compat.IncompatibleRecord):
            compat.observation_from_legacy({"schema_id": "memory-fabric.agent-outcomes.v2"})


class CanonicalSchema(unittest.TestCase):
    def test_rejects_unknown_fields_duplicate_keys_and_type_confusion(self) -> None:
        good = AgentStep("t1", "a1", "s1", "ask", {"q": 1}).canonical_json()
        with self.assertRaises(ValueError):
            AgentStep.from_json(good[:-1] + ',"security_level":"admin"}')
        with self.assertRaises(ValueError):
            AgentStep.from_json('{"schema_id":"x","schema_id":"y"}')
        with self.assertRaises(ValueError):
            AgentObservation("t1", "x", (), (), {"steps": True})
        with self.assertRaises((TypeError, ValueError)):
            AgentStep("t1", "a1", "s1", "ask", ["not", "an", "object"])

    def test_canonical_guard_is_at_least_as_strict_as_every_legacy_guard(self) -> None:
        payloads = [{"is_correct": True}, {"task_success": 1}, {"completion": True},
                    {"safety_violations": 0}, {"expected_value": 4}, {"groundTruth": 4},
                    {"oracle": 1}, {"hidden_note": "x"}, {"nested": {"Grader-Output": 1}}]
        constructors = {"agent_outcomes": V1Observation, "outcome_protocol": ProtocolObservation}
        differences = []
        for payload in payloads:
            legacy_rejects = []
            for name, cls in constructors.items():
                try:
                    cls("t1", "x", (payload,), (), {})
                except ValueError:
                    legacy_rejects.append(name)
            try:
                AgentObservation("t1", "x", (payload,), (), {})
                canonical_rejects = False
            except ValueError:
                canonical_rejects = True
            if legacy_rejects and not canonical_rejects:
                differences.append((payload, legacy_rejects))
        self.assertEqual(differences, [], "canonical accepts what a legacy schema refused")

    def test_equivalent_accepted_payloads_have_identical_content(self) -> None:
        events = ({"source": "instrument-A", "value": 4}, {"kind": "correction", "value": 5})
        canonical = AgentObservation("t1", "x", events, ("recall",), {"steps": 2}).to_dict()
        for cls in (V1Observation, ProtocolObservation):
            legacy = cls("t1", "x", events, ("recall",), {"steps": 2}).to_dict()
            self.assertEqual({k: v for k, v in legacy.items() if k != "schema_id"},
                             {k: v for k, v in canonical.items() if k != "schema_id"})


class EvaluatorIsolation(unittest.TestCase):
    def test_evaluator_objects_cannot_enter_actor_contracts(self) -> None:
        oracle = OracleTask.seal("t1", {"truth": {"target": 4}, "eligibility": {}, "reward": {}})
        outcome = EpisodeOutcome("t1", "A5", 1, True, 0, 0, 0, 0, 0, 0, 0, 1.0, DIGEST)
        for value in (oracle, outcome, lambda: None):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(ValueError):
                    AgentObservation("t1", "x", ({"payload": value},), (), {})
                with self.assertRaises((TypeError, ValueError)):
                    AgentStep("t1", "a1", "s1", "ask", {"payload": value})

    def test_actor_facing_modules_import_no_evaluator_code(self) -> None:
        for module in ("observations", "episode", "compat", "evidence"):
            source = (ROOT / "src" / "memory_fabric" / "outcome_typed" / f"{module}.py").read_text()
            imported = {node.module or "" for node in ast.walk(ast.parse(source))
                        if isinstance(node, ast.ImportFrom)}
            imported |= {alias.name for node in ast.walk(ast.parse(source))
                         if isinstance(node, ast.Import) for alias in node.names}
            with self.subTest(module=module):
                self.assertFalse(any(name.startswith(("benchmarks", "experiments", "tests"))
                                     for name in imported))


class LegacyCallSites(unittest.TestCase):
    def test_every_legacy_import_is_registered_with_a_sunset(self) -> None:
        registry = json.loads((ROOT / "docs" / "architecture"
                               / "OUTCOME_LEGACY_CALLSITES.json").read_text())
        listed = {(entry["package"], entry["path"]) for entry in registry["callsites"]}
        for entry in registry["callsites"]:
            self.assertEqual(entry["status"], "GRANDFATHERED")
            self.assertRegex(entry["sunset"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue((ROOT / entry["path"]).is_file(), entry["path"])
        found = {(f"memory_fabric.{package}", path)
                 for package, paths in inventory.legacy_callsites().items() for path in paths}
        self.assertEqual(found - listed, set(),
                         "new legacy import: use memory_fabric.outcome_typed (ADR 0004)")

    def test_legacy_packages_stay_importable_and_say_where_to_go(self) -> None:
        # A fresh interpreter: re-importing in this process would replace the package
        # object and break other tests that patch its submodules.
        import subprocess

        for package in ("memory_fabric.agent_outcomes", "memory_fabric.outcome_protocol"):
            with self.subTest(package=package):
                done = subprocess.run(
                    [sys.executable, "-W", "always::DeprecationWarning", "-c",
                     f"import {package} as m; print(m.__deprecated__['canonical'])"],
                    capture_output=True, text=True, cwd=ROOT, timeout=60)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(done.stdout.strip(), "memory_fabric.outcome_typed")
                self.assertIn("DeprecationWarning", done.stderr)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            importlib.import_module("benchmarks.outcome_report")


class SurfaceGate(unittest.TestCase):
    def test_no_fourth_outcome_package(self) -> None:
        packages = {path.name for path in (ROOT / "src" / "memory_fabric").iterdir()
                    if path.is_dir() and "outcome" in path.name}
        self.assertEqual(packages, OUTCOME_PACKAGES)

    def test_legacy_public_surfaces_are_frozen(self) -> None:
        committed = json.loads(inventory.OUT.read_text(encoding="utf-8"))
        current = json.loads(inventory.render())
        for package in ("agent_outcomes", "outcome_protocol"):
            with self.subTest(package=package):
                self.assertLessEqual(current["packages"][package]["public_names"],
                                     committed["packages"][package]["public_names"])
                self.assertLessEqual(set(current["unique_names"][package]),
                                     set(committed["unique_names"][package]))

    def test_outcome_contract_classes_are_defined_only_in_outcome_packages(self) -> None:
        offenders = []
        for path in (ROOT / "src" / "memory_fabric").rglob("*.py"):
            rel = path.relative_to(ROOT / "src" / "memory_fabric")
            if rel.parts[0] in OUTCOME_PACKAGES:
                continue
            for node in ast.parse(path.read_text(encoding="utf-8")).body:
                if isinstance(node, ast.ClassDef) and node.name in CONTRACT_CLASSES:
                    offenders.append(f"{rel}:{node.name}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
