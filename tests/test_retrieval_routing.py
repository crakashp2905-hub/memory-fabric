"""Decision-aware query routing never fuses an unqualified vector arm."""

from __future__ import annotations

import unittest
from unittest import mock

from memory_fabric import MemoryFabric
from memory_fabric._fabric import retrieval as retrieval_module
from memory_fabric.retrieval_routing import route


class RoutingRules(unittest.TestCase):
    def test_identifiers_and_time_are_lexical(self) -> None:
        for query in ("pressure for P-14", "what happened before the repair?"):
            self.assertEqual(route(query, trained_embedder=True).method, "lexical")

    def test_hashing_vectors_never_receive_a_fusion_vote(self) -> None:
        for query in ("paraphrase this maintenance advice", "what caused the shutdown?"):
            self.assertEqual(route(query, trained_embedder=False).method, "lexical")

    def test_trained_semantic_and_multi_hop_queries_are_hybrid(self) -> None:
        self.assertEqual(route("advice for unusual vibration", trained_embedder=True).method,
                         "hybrid")
        self.assertEqual(route("what caused the shutdown?", trained_embedder=True).method,
                         "hybrid")

    def test_adaptive_profile_resolves_before_search(self) -> None:
        fabric = MemoryFabric(auto_activate=True)
        self.addCleanup(fabric.close)
        fabric.remember("ag", "Pump P-14 operates at twelve bar.")
        seen: list[str | None] = []
        real = retrieval_module.RetrievalMixin._search

        def spy(self, query, k, eligible, min_relevance, method=None):
            seen.append(method)
            return real(self, query, k, eligible, min_relevance, method=method)

        with mock.patch.object(retrieval_module.RetrievalMixin, "_search", spy):
            fabric.retrieve("ag", "pressure for P-14", profile="adaptive")
        self.assertEqual(seen, ["auto"])


if __name__ == "__main__":
    unittest.main()
