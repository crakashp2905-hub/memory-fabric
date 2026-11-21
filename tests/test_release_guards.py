"""Release guards: source-bound contracts, frozen records, contract mutations,
dependency closure and the CI matrix (W23-03, W23-04, W23-06, W23-07, W23-08, W15-10)."""

from __future__ import annotations

import copy
import dataclasses
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool(name: str):
    spec = importlib.util.spec_from_file_location(f"_{name}", ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


source_bound = _tool("source_bound")
frozen = _tool("frozen_results")


class SourceBound(unittest.TestCase):
    def test_the_recorded_contracts_match_the_code(self) -> None:
        recorded = json.loads(source_bound.FIXTURE.read_text())
        self.assertEqual(source_bound.diff(recorded, source_bound.compute()), [])

    def test_a_contract_change_without_a_fixture_update_is_caught(self) -> None:
        recorded = json.loads(source_bound.FIXTURE.read_text())
        changed = copy.deepcopy(recorded)
        changed["episode_limits"]["max_recoveries"] += 1
        changed["evaluator_only_fields"] = changed["evaluator_only_fields"][1:]
        self.assertEqual(source_bound.diff(changed, source_bound.compute()),
                         ["episode_limits", "evaluator_only_fields"])


class FrozenRecords(unittest.TestCase):
    def test_the_committed_registry_is_intact(self) -> None:
        self.assertEqual(frozen.check(), [])
        paths = [e["path"] for e in frozen.load()["entries"]]
        self.assertTrue(any("candidate-offline" in p for p in paths))

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry = self.root / "FROZEN.json"
        (self.root / "run.json").write_text(json.dumps({"candidate_commit_sha": "a" * 40,
                                                        "status": "FAIL"}))
        frozen.freeze("run.json", "python make", "a" * 40, registry=self.registry, root=self.root)

    def test_a_deleted_failed_run_is_caught(self) -> None:
        (self.root / "run.json").unlink()
        self.assertIn("run.json: frozen record deleted", frozen.check(self.registry, self.root))

    def test_a_silently_replaced_record_is_caught_and_supersede_keeps_history(self) -> None:
        (self.root / "run.json").write_text(json.dumps({"candidate_commit_sha": "b" * 40,
                                                        "status": "PASS"}))
        self.assertTrue(any("changed" in p for p in frozen.check(self.registry, self.root)))
        frozen.supersede("run.json", "rerun after fix", "b" * 40, registry=self.registry,
                         root=self.root)
        self.assertEqual(frozen.check(self.registry, self.root), [])
        history = frozen.load(self.registry)["entries"][0]["history"]
        self.assertEqual(history[0]["superseded_because"], "rerun after fix")

    def test_stale_commit_fields_and_raw_prompts_are_caught(self) -> None:
        (self.root / "bad.json").write_text(json.dumps({"rows": [{"prompt": "system: ..."}]}))
        frozen.freeze("bad.json", "python make", "c" * 40, registry=self.registry, root=self.root)
        problems = frozen.check(self.registry, self.root)
        self.assertTrue(any("no commit field" in p for p in problems))
        self.assertTrue(any("forbidden keys" in p for p in problems))


class ContractMutations(unittest.TestCase):
    """Each manipulation of evidence is rejected by the evaluator or a gate (W23-06)."""

    def test_a_flipped_hidden_outcome_breaks_the_seal(self) -> None:
        from memory_fabric.outcome_typed.observations import OracleTask

        oracle, capability = OracleTask.seal_for_evaluator(
            "task-m1", {"truth": {"value": 4}, "eligibility": {}, "reward": {}})
        self.assertTrue(oracle.verify_seal(capability))
        with self.assertRaisesRegex(ValueError, "does not match its seal"):
            dataclasses.replace(oracle, _sealed_payload=oracle._sealed_payload.replace(b"4", b"9"))

    def test_a_flipped_row_outcome_shows_up_above_the_oracle(self) -> None:
        from benchmarks.outcome_arms import run
        from benchmarks.outcome_scorecard import scorecard

        report = run(seeds=1)
        for row in report["rows"]:
            if row["arm"] == "A2":
                row["safe_success"], row["terminal_status"] = True, "COMPLETED"
        card = scorecard(report, source_sha="d" * 40, evidence_type="scripted")
        self.assertEqual(card["decision"], "FAIL")
        self.assertIn("A2", card["arms_above_oracle"])

    def test_a_removed_source_root_or_stale_version_does_not_verify(self) -> None:
        from memory_fabric import MemoryFabric
        from memory_fabric.certificates import CertificateError, EvidenceCertificate

        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        memory = fabric.remember("a", "valve 7 safe below 4 bar", scope="team")
        fabric.revise(memory, "valve 7 safe below 5 bar", "a", "update")
        body = fabric.certify("c", [memory], "ops").to_json()
        stale = copy.deepcopy(body)
        stale["evidence"][0]["version"] = 1
        codes = fabric.verify_certificate(EvidenceCertificate.from_json(stale), "ops").reason_codes
        self.assertNotEqual(list(codes), ["ok"])
        # Removing a source root: two independent reports are required; replace one
        # with a copy of the other and the evidence has one root, so it is refused.
        first = fabric.remember("inspector-a", "Inspection A: pump 9 relief valve is set to 6 bar.",
                                scope="team", source_episodes=["ep-a"])
        second = fabric.remember("inspector-b",
                                 "Field check B measured the pump 9 relief setting at 6 bar.",
                                 scope="team", source_episodes=["ep-b"])
        two = fabric.certify("p9", [first, second], "ops", min_independent_sources=2)
        self.assertEqual(list(fabric.verify_certificate(two, "ops").reason_codes), ["ok"])
        fabric.retrieve("copier", "pump 9 relief valve", k=5)
        copy_of_first = fabric.remember("copier", "Inspection A: pump 9 relief valve is set to 6 bar.",
                                        scope="team")
        one_root = fabric.certify("p9", [first, copy_of_first], "ops", min_independent_sources=2)
        codes = fabric.verify_certificate(one_root, "ops").reason_codes
        self.assertNotEqual(list(codes), ["ok"])
        # The certificate's own source_roots field is not trusted: verification derives
        # roots from the store, so deleting the field neither helps nor breaks anything.
        rootless = copy.deepcopy(two.to_json())
        rootless.pop("source_roots", None)
        try:
            again = fabric.verify_certificate(EvidenceCertificate.from_json(rootless), "ops")
            self.assertEqual(list(again.reason_codes), ["ok"])
        except (CertificateError, KeyError, TypeError, ValueError):
            pass

    def test_a_changed_model_digest_breaks_the_registration(self) -> None:
        from tests.test_outcome_prereg import frozen as frozen_manifest
        from benchmarks.outcome_prereg import validate

        with tempfile.TemporaryDirectory() as directory:
            manifest = frozen_manifest(Path(directory))
            self.assertEqual(validate(manifest, Path(directory)), [])
            manifest["commitments"]["model_digest"] = "sha256:" + "9" * 64
            self.assertIn("design_sha256 mismatch; preregistered design changed",
                          validate(manifest, Path(directory)))


class DependencyClosure(unittest.TestCase):
    def test_no_mandatory_runtime_dependency(self) -> None:
        import tomllib

        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertEqual(project["dependencies"], [])

    def test_the_agent_outcome_modules_import_only_the_standard_library(self) -> None:
        import ast

        stdlib = set(sys.stdlib_module_names)
        files = sorted((ROOT / "src/memory_fabric/outcome_typed").glob("*.py"))
        files.append(ROOT / "src/memory_fabric/observability/outcomes.py")
        for path in files:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    top = name.split(".")[0]
                    self.assertTrue(top in stdlib or top == "memory_fabric",
                                    f"{path.name} imports {name}")

    def test_the_scripted_demo_runs_with_site_packages_disabled(self) -> None:
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        done = subprocess.run([sys.executable, "-S", "-m", "benchmarks.outcome_episode", "--seed", "1"],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("evaluator: COMPLETED", done.stdout)


class CiMatrix(unittest.TestCase):
    def test_core_tests_run_on_three_pythons_and_three_platforms(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        for platform in ("ubuntu-latest", "macos-latest", "windows-latest"):
            self.assertIn(platform, workflow)
        for version in ('"3.11"', '"3.12"', '"3.13"'):
            self.assertIn(version, workflow)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
