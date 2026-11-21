"""Research report, A6-A5 registration, reproducibility, benefit, rollout and launch docs (W22, W24)."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIERS = {"CONTRACT", "SCRIPTED", "LOCAL_MODEL", "CONFIRMATORY", "INDEPENDENT"}


def _tool(name: str):
    spec = importlib.util.spec_from_file_location(f"_{name}", ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def table_rows(text: str, first_cell: str) -> list[list[str]]:
    return [[c.strip() for c in line.strip("|").split("|")] for line in text.splitlines()
            if re.match(rf"\| {first_cell}", line)]


class ResearchReport(unittest.TestCase):
    text = (ROOT / "docs" / "AGENT_RESEARCH_REPORT.md").read_text()

    def test_every_finding_names_a_tier_and_links_existing_evidence(self) -> None:
        rows = table_rows(self.text, r"[NF]\d")
        self.assertGreaterEqual(len(rows), 12)
        for row in rows:
            tier = row[2].split(" ")[0]
            self.assertIn(tier, TIERS, row[0])
            links = re.findall(r"\]\(([^)]+)\)", row[3]) or re.findall(r"`(tests/[^`]+)`", row[3])
            self.assertTrue(links, row[0])
            for link in links:
                target = (ROOT / "docs" / link).resolve() if not link.startswith("tests/") else ROOT / link
                self.assertTrue(target.exists(), f"{row[0]}: {link}")

    def test_negatives_come_first_and_unrun_tiers_are_said_out_loud(self) -> None:
        self.assertLess(self.text.index("## Null and negative results first"), self.text.index("## Findings"))
        for tier in ("LOCAL_MODEL: NOT_RUN", "CONFIRMATORY: NOT_RUN", "INDEPENDENT: NOT_RUN"):
            self.assertIn(tier, self.text)
        self.assertIn("Phase A was killed", self.text)
        self.assertIn("R5 v3", self.text)

    def test_related_work_records_overlap_and_difference_for_every_mechanism(self) -> None:
        section = self.text.split("## Related work")[1].split("## How to test")[0]
        rows = [r for r in table_rows(section, r"[A-Z][a-z]") if r[0] != "Mechanism"]
        self.assertGreaterEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(len(row), 4)
            self.assertTrue(all(cell for cell in row), row[0])
        self.assertNotRegex(self.text.lower(), r"\bnovel\b")


class CdmRegistration(unittest.TestCase):
    def frozen(self) -> dict:
        from benchmarks.outcome_prereg import cdm_design_digest

        manifest = json.loads((ROOT / "research/prereg/agent-outcome-cdm-a6-v1.json").read_text())
        manifest.update(status="FROZEN", freeze_commit="f" * 40)
        manifest["design_sha256"] = cdm_design_digest(manifest)
        return manifest

    def test_the_committed_draft_is_blocked_and_a_frozen_copy_validates(self) -> None:
        from benchmarks.outcome_prereg import validate_cdm

        draft = json.loads((ROOT / "research/prereg/agent-outcome-cdm-a6-v1.json").read_text())
        self.assertIn("protocol is not frozen; the A6-A5 test is blocked", validate_cdm(draft))
        self.assertEqual(validate_cdm(self.frozen()), [])

    def test_flip_credit_contrast_and_late_edits_are_refused(self) -> None:
        from benchmarks.outcome_prereg import cdm_design_digest, validate_cdm

        for change, message in ((("flip_credit", 1), "policy flips must earn no credit"),
                                (("contrast", ["A6", "A3"]), "the contrast must be A6-A5")):
            manifest = self.frozen()
            manifest[change[0]] = change[1]
            manifest["design_sha256"] = cdm_design_digest(manifest)
            self.assertIn(message, validate_cdm(manifest))
        edited = self.frozen()
        edited["minimum_net_utility"] = 0.001
        self.assertIn("design_sha256 mismatch; registered design changed", validate_cdm(edited))


class Rollout(unittest.TestCase):
    def test_cdm_is_advisory_by_default_and_advances_only_on_evidence(self) -> None:
        from memory_fabric.outcome_typed.rollout import Rollout as R
        from memory_fabric.outcome_typed.rollout import RolloutRefused

        rollout = R()
        self.assertTrue(rollout.advisory("cdm"))
        with self.assertRaises(RolloutRefused):
            rollout.advance("cdm", "canary", set())
        with self.assertRaises(RolloutRefused):
            rollout.advance("cdm", "on", {"a5_promoted", "a6_net_utility_passed", "canary_clean"})
        rollout.advance("cdm", "canary", {"a5_promoted", "a6_net_utility_passed"})
        self.assertFalse(rollout.advisory("cdm"))

    def test_rollback_restores_the_last_qualified_flags_and_leaves_the_log_alone(self) -> None:
        from memory_fabric import MemoryFabric
        from memory_fabric.outcome_typed.rollout import DEFAULTS
        from memory_fabric.outcome_typed.rollout import Rollout as R

        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        fabric.remember("a", "valve 7 safe below 4 bar", scope="team")
        before = len(fabric.log)
        rollout = R()
        rollout.set_unqualified("model_actor", "on")
        self.assertEqual(rollout.rollback("canary failure"), dict(DEFAULTS))
        self.assertEqual(len(fabric.log), before)
        self.assertTrue(fabric.log.chain.verify(fabric.log.read()).ok)

    def test_the_launch_doc_matches_the_flag_defaults(self) -> None:
        from memory_fabric.outcome_typed.rollout import DEFAULTS

        text = (ROOT / "docs" / "AGENT_LAUNCH_READINESS.md").read_text()
        for feature, default in DEFAULTS.items():
            self.assertRegex(text, rf"\| {feature}[^|]*\| {default}")


class Benefit(unittest.TestCase):
    def test_benefit_is_in_operator_units_with_denominators(self) -> None:
        from benchmarks.outcome_arms import run

        benefit = _tool("scenario_benefit").benefit(run(seeds=1))
        self.assertEqual(set(benefit), {"correction_aware_support", "safe_multi_agent_operations",
                                        "audited_decision_repair"})
        a5 = benefit["correction_aware_support"]["A5"]
        for key in ("tasks", "safe_completions_per_100", "steps_per_safe_completion",
                    "unnecessary_escalations", "escalation_denominator"):
            self.assertIn(key, a5)
        self.assertEqual(a5["recovery_wall_time"], "NOT_RECORDED")


class Reproducibility(unittest.TestCase):
    def test_a_capsule_verifies_and_a_tampered_one_does_not(self) -> None:
        capsule_tool = _tool("repro_capsule")
        capsule = capsule_tool.build(seeds=1)
        self.assertEqual(capsule_tool.verify(capsule), [])
        tampered = copy.deepcopy(capsule)
        tampered["outputs"]["arms_rows"] = "0" * 64
        self.assertIn("output differs from the capsule: arms_rows", capsule_tool.verify(tampered))


class OrthogonalAblations(unittest.TestCase):
    def test_each_factor_is_varied_alone_and_model_accuracy_is_not_claimed(self) -> None:
        from benchmarks.outcome_ablation import orthogonal

        report = orthogonal(seeds=2)
        factors = report["factors"]
        self.assertEqual(factors["evidence_quality"]["unmarked_correction"]["A5_minus_A3"], 1.0)
        self.assertEqual(factors["evidence_quality"]["marked_correction"]["A5_minus_A3"], 0.0)
        for rate in ("0.0", "0.25", "0.5"):
            self.assertEqual(factors["planner_error_rate_proxy"][rate]["A5_minus_A3"], 0.0)
        self.assertGreater(factors["correction_timing_tick"]["2"]["A5_minus_A3"], 0)
        self.assertIn("NOT_RUN", report["model_accuracy"])


class LaunchDoc(unittest.TestCase):
    text = (ROOT / "docs" / "AGENT_LAUNCH_READINESS.md").read_text()

    def test_every_threat_has_a_control_an_existing_test_and_a_residual(self) -> None:
        section = self.text.split("## Production deployment threat model")[1].split("## Operational")[0]
        rows = [r for r in table_rows(section, r"[A-Z]") if r[0] != "Threat"]
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(len(row), 4)
            for test in re.findall(r"`(tests/[^`]+)`", row[2]):
                self.assertTrue((ROOT / test).is_file(), test)

    def test_runbook_names_metrics_stop_switch_rollback_and_reconciliation(self) -> None:
        for needle in ("**Stop-switch:**", "**Rollback:**", "**Stale-effect reconciliation:**",
                       "rollback(reason)", "frozen_results.py --check"):
            self.assertIn(needle, self.text)

    def test_the_pilot_stays_blocked_external(self) -> None:
        self.assertIn("`BLOCKED_EXTERNAL` until its evidence exists", self.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
