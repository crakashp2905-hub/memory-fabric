"""One outcome-evidence vocabulary that cannot overstate its evidence (W01-04, W01-07, W01-08)."""

from __future__ import annotations

import unittest

from memory_fabric.outcome_typed.evidence import (
    EvidenceBoundaryError, EvidenceType, GateEvidence, OutcomeEvidenceStatus, Population,
    RELEASE_MATRIX_GATES, ResultPopulation, UnpairedComparisonError, from_legacy_gate_status,
    release_evidence_matrix, validate_paired_comparison,
)

SHA = "70e34c870d387cb5de8ba0bbdda0320cf3574d6c"
OTHER = "11036e2b9df619ab38e9b82269d5beaf0d7eb5da"
S = OutcomeEvidenceStatus
T = EvidenceType


class Vocabulary(unittest.TestCase):
    def test_exact_status_set(self) -> None:
        self.assertEqual({status.value for status in S}, {
            "NOT_RUN", "BLOCKED", "SCRIPTED_PASS", "LOCAL_MODEL_PASS",
            "CONFIRMATORY_SUPPORTED", "FAILED", "INCONCLUSIVE"})

    def test_green_ci_cannot_be_a_real_agent_pass(self) -> None:
        with self.assertRaises(EvidenceBoundaryError):
            GateEvidence("real_agent", S.SCRIPTED_PASS, T.CI, SHA, "35/35 jobs green")
        with self.assertRaises(EvidenceBoundaryError):
            GateEvidence("real_agent", S.LOCAL_MODEL_PASS, T.SCRIPTED, SHA, "scripted run",
                         model_digest="sha256:abc")

    def test_scripted_pass_cannot_be_rendered_as_local_model(self) -> None:
        with self.assertRaises(EvidenceBoundaryError):
            GateEvidence("x", S.LOCAL_MODEL_PASS, T.SCRIPTED, SHA, "scripted", model_digest="d")

    def test_positive_status_requires_exact_sha(self) -> None:
        with self.assertRaises(EvidenceBoundaryError):
            GateEvidence("synthetic_outcome_gate", S.SCRIPTED_PASS, T.SCRIPTED, None, "ran")
        with self.assertRaises(ValueError):
            GateEvidence("synthetic_outcome_gate", S.SCRIPTED_PASS, T.SCRIPTED, "70e34c8", "ran")

    def test_local_model_pass_requires_model_digest(self) -> None:
        with self.assertRaises(EvidenceBoundaryError):
            GateEvidence("real_agent", S.LOCAL_MODEL_PASS, T.LOCAL_MODEL, SHA, "ran")
        ok = GateEvidence("real_agent", S.LOCAL_MODEL_PASS, T.LOCAL_MODEL, SHA, "ran",
                          model_digest="sha256:" + "a" * 64)
        self.assertEqual(ok.to_dict()["status"], "LOCAL_MODEL_PASS")

    def test_confirmatory_requires_frozen_registration(self) -> None:
        with self.assertRaises(EvidenceBoundaryError):
            GateEvidence("confirmatory", S.CONFIRMATORY_SUPPORTED, T.CONFIRMATORY, SHA, "ran")
        GateEvidence("confirmatory", S.CONFIRMATORY_SUPPORTED, T.CONFIRMATORY, SHA, "ran",
                     registration_sha256="b" * 64)

    def test_every_status_needs_a_reason(self) -> None:
        with self.assertRaises(ValueError):
            GateEvidence("main_ci", S.NOT_RUN, T.CI, None, " ")

    def test_legacy_pass_keeps_its_evidence_type(self) -> None:
        self.assertIs(from_legacy_gate_status("synthetic_outcome_gate", "PASS", T.SCRIPTED,
                                              SHA, "gate").status, S.SCRIPTED_PASS)
        self.assertIs(from_legacy_gate_status("main_ci", "FAIL", T.CI, SHA, "red").status,
                      S.FAILED)
        with self.assertRaises(EvidenceBoundaryError):
            from_legacy_gate_status("real_agent", "PASS", T.CI, SHA, "ci")
        with self.assertRaises(ValueError):
            from_legacy_gate_status("main_ci", "GREEN", T.CI, SHA, "?")


class ReleaseMatrix(unittest.TestCase):
    def test_absent_gates_are_not_run_not_inherited(self) -> None:
        matrix = release_evidence_matrix([
            GateEvidence("main_ci", S.SCRIPTED_PASS, T.CI, SHA, "35/35 ordinary jobs green")])
        rows = {row["gate_id"]: row for row in matrix["rows"]}
        self.assertEqual(set(RELEASE_MATRIX_GATES) - set(rows), set())
        self.assertEqual(rows["main_ci"]["status"], "SCRIPTED_PASS")
        for gate in ("real_agent", "model_attacks", "confirmatory", "independent_review"):
            self.assertEqual(rows[gate]["status"], "NOT_RUN")
            self.assertIsNone(rows[gate]["evidence_type"])
        self.assertFalse(matrix["production_qualified"])

    def test_duplicate_gate_and_mixed_shas_are_visible(self) -> None:
        entry = GateEvidence("main_ci", S.SCRIPTED_PASS, T.CI, SHA, "green")
        with self.assertRaises(ValueError):
            release_evidence_matrix([entry, entry])
        matrix = release_evidence_matrix([
            entry, GateEvidence("synthetic_outcome_gate", S.SCRIPTED_PASS, T.SCRIPTED, OTHER, "g")])
        self.assertFalse(matrix["single_target_sha"])


class Pairing(unittest.TestCase):
    def population(self, **overrides: object) -> ResultPopulation:
        fields: dict[str, object] = dict(
            task_ids=("t1", "t2", "t3"), generator_id="outcome_worlds",
            generator_revision=SHA, outcome_unit="task_case",
            population=Population.SAME_COMMIT, source_sha=SHA)
        fields.update(overrides)
        return ResultPopulation(**fields)  # type: ignore[arg-type]

    def test_matched_populations_pair(self) -> None:
        report = validate_paired_comparison(self.population(),
                                            self.population(task_ids=("t3", "t1", "t2")))
        self.assertTrue(report["paired"])
        self.assertEqual(report["task_count"], 3)

    def test_mismatches_are_refused(self) -> None:
        base = self.population()
        for change in ({"task_ids": ("t1", "t2", "t4")}, {"generator_id": "teamworld"},
                       {"generator_revision": OTHER}, {"outcome_unit": "agent_decision"},
                       {"population": Population.RETROSPECTIVE, "source_sha": None},
                       {"source_sha": OTHER}):
            with self.subTest(change=change), self.assertRaises(UnpairedComparisonError):
                validate_paired_comparison(base, self.population(**change))

    def test_population_shape_is_checked(self) -> None:
        with self.assertRaises(ValueError):
            self.population(task_ids=("t1", "t1"))
        with self.assertRaises(ValueError):
            self.population(task_ids=())
        with self.assertRaises(ValueError):
            self.population(source_sha=None)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
