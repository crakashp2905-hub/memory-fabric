"""Ranking, evidence validity, and readiness are separate API contracts."""

from __future__ import annotations

import unittest

from memory_fabric import (
    DecisionReadiness,
    EvidenceValidity,
    MemoryFabric,
    RetrievalAssessment,
    RetrievalRanking,
)


class EvidenceStatusContract(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(auto_activate=True, hold_suspicious=False)
        self.addCleanup(self.fabric.close)

    def test_api_returns_three_non_interchangeable_fields(self) -> None:
        self.fabric.remember(
            "ag_writer", "Compressor K-31 relief pressure is 14 bar.", scope="team"
        )
        question = "What is the relief pressure of compressor K-31?"
        assessment = self.fabric.retrieve("ag_reader", question).assessment(question)

        self.assertIsInstance(assessment.ranking, RetrievalRanking)
        self.assertIs(assessment.evidence_validity, EvidenceValidity.VALID)
        self.assertIs(assessment.decision_readiness, DecisionReadiness.READY)
        self.assertNotEqual(assessment.ranking, assessment.evidence_validity)
        self.assertNotEqual(assessment.evidence_validity, assessment.decision_readiness)

    def test_high_ranking_does_not_make_contested_evidence_valid_or_ready(self) -> None:
        memory_id = self.fabric.remember(
            "ag_writer", "Pump P-9 trip pressure is 80 bar.", scope="team"
        )
        self.fabric.challenge([memory_id], evidence="conflicting inspection")
        question = "What is the trip pressure of pump P-9?"
        result = self.fabric.retrieve(
            "ag_reader", question, include_contested=True, min_relevance=0.0
        )
        assessment = result.assessment(question)

        self.assertIsNotNone(assessment.ranking.top_score)
        self.assertIs(assessment.evidence_validity, EvidenceValidity.INVALID)
        self.assertIs(assessment.decision_readiness, DecisionReadiness.REVIEW)

    def test_valid_neighbours_can_still_require_abstention(self) -> None:
        self.fabric.remember(
            "ag_writer", "Compressor K-31 relief pressure is 14 bar.", scope="team"
        )
        question = "What is the coolant flow of compressor K-31?"
        assessment = self.fabric.retrieve("ag_reader", question).assessment(question)

        self.assertIs(assessment.evidence_validity, EvidenceValidity.VALID)
        self.assertIs(assessment.decision_readiness, DecisionReadiness.ABSTAIN)

    def test_constructor_rejects_interchanged_contract_types(self) -> None:
        with self.assertRaises(TypeError):
            RetrievalAssessment(  # type: ignore[arg-type]
                EvidenceValidity.VALID,
                EvidenceValidity.VALID,
                DecisionReadiness.READY,
            )
        with self.assertRaises(TypeError):
            RetrievalRanking(True)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
