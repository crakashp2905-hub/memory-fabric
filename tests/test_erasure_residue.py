"""After crypto-erasure, nothing derived from the erased text stays in memory.

Invariant 12 says the text goes and the accountability stays. The log only
holds ciphertext, so a *replay* after erasure cannot see the text. A process
that was already running could, in three places, all found while making
cross-process refresh incremental (tests/test_catch_up.py):

1. `state.history` kept every earlier version's plaintext, served by
   `history()` and the dashboard's version list.
2. The copy index kept the erased text's term set; `_unindex` deliberately
   leaves it alone so withdrawn documents stay recognisable, and the erased
   marker is too short to replace it.
3. (2) for a memory erased by *another* process, folded in by `refresh`.

What must not change: a quarantined document is still recognised when it is
re-ingested, because withdrawn is not erased.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.branching import Branches
from memory_fabric.governance.erasure import ERASED_MARKER
from memory_fabric.navigation import _words
from memory_fabric.retrievers import VectorCache

TEXT = "Pump seven bypass valve torque procedure for the coastal depot requires two people"


class ErasureLeavesNoResidue(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "store.db")

    def open(self) -> MemoryFabric:
        fabric = MemoryFabric(self.path, auto_activate=True)
        self.addCleanup(fabric.close)
        return fabric

    def test_every_version_is_erased_in_the_erasing_process(self) -> None:
        fabric = self.open()
        mid = fabric.remember("a", TEXT)
        fabric.revise(mid, TEXT + " and a spotter", agent_id="a", reason="correction")
        fabric.erase_content(mid, reason="request", actor="dpo")
        self.assertEqual({m.content for m in fabric.history(mid)}, {ERASED_MARKER})

    def test_the_copy_index_forgets_the_erased_text(self) -> None:
        fabric = self.open()
        mid = fabric.remember("a", TEXT)
        self.assertIn(mid, fabric.copy_index.terms)
        fabric.erase_content(mid, reason="request", actor="dpo")
        self.assertNotIn(mid, fabric.copy_index.terms)
        for table in (fabric.copy_index.postings, fabric.copy_index.anchors):
            self.assertFalse(any(mid in ids for ids in table.values()))

    def test_an_erasure_by_another_process_is_folded_without_residue(self) -> None:
        live, other = self.open(), self.open()
        mid = live.remember("a", TEXT)
        live.revise(mid, TEXT + " and a spotter", agent_id="a", reason="correction")
        other.refresh()
        other.erase_content(mid, reason="request", actor="dpo")
        live.refresh()
        self.assertEqual({m.content for m in live.history(mid)}, {ERASED_MARKER})
        self.assertNotIn(mid, live.copy_index.terms)
        self.assertNotIn("torque", live.lexical._terms.get(mid, frozenset()))

    def test_a_revision_replaces_its_old_terms(self) -> None:
        fabric = self.open()
        mid = fabric.remember("a", TEXT)
        fabric.revise(mid, "Completely different wording about the inland reservoir gauge",
                      agent_id="a", reason="rewrite")
        self.assertNotIn("torque", fabric.copy_index.terms[mid])
        self.assertFalse(mid in fabric.copy_index.postings.get("torque", set()))

    def test_a_quarantined_document_is_still_recognised(self) -> None:
        fabric = self.open()
        mid = fabric.remember("a", TEXT)
        fabric.quarantine(mid, reason="poisoned", actor="op")
        self.assertIn(mid, fabric.copy_index.terms)
        self.assertIn(mid, fabric.copy_index.candidates(TEXT))

    def test_erasure_clears_cached_topic_terms_for_every_version(self) -> None:
        fabric = self.open()
        mid = fabric.remember("a", TEXT)
        fabric.revise(mid, TEXT + " and a spotter", agent_id="a", reason="correction")
        _words(fabric, [mid])
        self.assertTrue(any(key[0] == mid for key in fabric._topic_terms))
        fabric.erase_content(mid, reason="request", actor="dpo")
        self.assertFalse(any(key[0] == mid for key in fabric._topic_terms))
        self.assertNotIn("torque", fabric._topic_terms)

    def test_erasure_forgets_a_persistent_embedder_document_vector(self) -> None:
        vector_path = str(Path(self.tmp.name) / "vectors.db")

        class CachedEmbedder:
            def __init__(self) -> None:
                self.cache = VectorCache("erasure-probe", vector_path)

            def embed(self, text: str) -> list[float]:
                cached = self.cache.get(text)
                if cached is None:
                    cached = [float(len(text)), 1.0]
                    self.cache.put_many([(text, cached)])
                return cached

            def forget(self, text: str) -> None:
                self.cache.forget(text)

        embedder = CachedEmbedder()
        self.addCleanup(embedder.cache.close)
        fabric = MemoryFabric(self.path, auto_activate=True, retrieval="hybrid", embedder=embedder)
        self.addCleanup(fabric.close)
        mid = fabric.remember("a", TEXT)
        indexed_text = fabric._index_text(fabric.get(mid))
        self.assertIsNotNone(embedder.cache.get(indexed_text))
        fabric.erase_content(mid, reason="request", actor="dpo")
        self.assertIsNone(embedder.cache.get(indexed_text))

    def test_cross_process_refresh_forgets_each_processes_vector_cache(self) -> None:
        cache_left = VectorCache("left-process")
        cache_right = VectorCache("right-process")
        self.addCleanup(cache_left.close)
        self.addCleanup(cache_right.close)

        class CachedEmbedder:
            def __init__(self, cache: VectorCache) -> None:
                self.cache = cache

            def embed(self, text: str) -> list[float]:
                vector = self.cache.get(text)
                if vector is None:
                    vector = [float(len(text)), 1.0]
                    self.cache.put_many([(text, vector)])
                return vector

            def forget(self, text: str) -> None:
                self.cache.forget(text)

        live = MemoryFabric(self.path, auto_activate=True, retrieval="hybrid",
                            embedder=CachedEmbedder(cache_left))
        other = MemoryFabric(self.path, auto_activate=True, retrieval="hybrid",
                             embedder=CachedEmbedder(cache_right))
        self.addCleanup(live.close)
        self.addCleanup(other.close)
        mid = live.remember("a", TEXT)
        other.refresh()
        indexed_text = live._index_text(live.get(mid))
        self.assertIsNotNone(cache_left.get(indexed_text))
        self.assertIsNotNone(cache_right.get(indexed_text))
        live.erase_content(mid, reason="request", actor="dpo")
        other.refresh()
        self.assertIsNone(cache_left.get(indexed_text))
        self.assertIsNone(cache_right.get(indexed_text))

    def test_branch_history_and_pending_retraction_retain_no_erased_content(self) -> None:
        fabric = self.open()
        branch_text = "Branch residue canary: turbine omega at 19 bar"
        origin_text = "Pending queue residue canary: pump delta at 23 bar"
        target = fabric.remember("a", "Base instruction for the branch target", scope="team")
        branches = Branches(fabric)
        branches.create("erasure-probe", owner="a")
        with branches.commit("erasure-probe", "a", "private proposal") as staged:
            candidate = staged.add(branch_text)
        commit_id = branches.history("erasure-probe")[0]["commit_id"]
        fabric.erase_content(candidate, reason="request", actor="dpo")
        branch_views = json.dumps({
            "history": branches.history("erasure-probe"),
            "diff": branches.diff("erasure-probe"),
            "snapshot": branches.snapshot("erasure-probe", commit_id),
        })
        self.assertNotIn(branch_text, branch_views)
        self.assertEqual(fabric.get(candidate).content, ERASED_MARKER)

        pending_id = fabric.remember("a", origin_text, scope="federated")
        fabric.request_retraction(pending_id, "withdrawn", ["st_peer"], actor="dpo")
        fabric.erase_content(pending_id, reason="request", actor="dpo")
        queued = json.dumps([row.retraction.to_json() for row in fabric.outbox.pending()])
        self.assertNotIn(origin_text, queued)
        self.assertNotIn("23 bar", queued)
        self.assertEqual(fabric.get(target).content, "Base instruction for the branch target")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
