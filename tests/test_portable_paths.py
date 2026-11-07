"""Portable path, encoding, line-ending and case-collision regression fixtures."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.freshness import FreshnessLease, LeaseBook
from memory_fabric.migrate import read_records

ROOT = Path(__file__).resolve().parents[1]


class PortablePaths(unittest.TestCase):
    def test_unicode_paths_and_memory_content_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "Memory Fabric – 東京" / "data store.db"
            fabric = MemoryFabric(database, auto_activate=True, encrypt_content=False)
            memory_id = fabric.remember("agent-東京", "Crème brûlée – café ☕; 東京.")
            fabric.close()
            reopened = MemoryFabric(database, auto_activate=True, encrypt_content=False)
            try:
                self.assertEqual(reopened.get(memory_id).content,
                                 "Crème brûlée – café ☕; 東京.")
                self.assertEqual(reopened.get(memory_id).provenance.created_by, "agent-東京")
            finally:
                reopened.close()

    def test_jsonl_import_handles_utf8_and_lf_crlf_and_cr(self) -> None:
        text = json.dumps({"content": "München / São Paulo / 東京 / 🧵",
                           "agent_id": "importer-東京"}, ensure_ascii=False)
        encoded = text.encode("utf-8")
        for label, separator in (("lf", b"\n"), ("crlf", b"\r\n"), ("cr", b"\r")):
            with self.subTest(line_ending=label), tempfile.TemporaryDirectory() as temp:
                source = Path(temp) / "输入 数据" / f"records-{label}.jsonl"
                source.parent.mkdir(parents=True)
                source.write_bytes(encoded + separator + encoded + separator)
                rows = list(read_records(source))
                self.assertEqual([number for number, _ in rows], [1, 2])
                self.assertEqual([row["content"] for _, row in rows],
                                 ["München / São Paulo / 東京 / 🧵"] * 2)

    def test_freshness_lease_file_uses_explicit_utf8(self) -> None:
        key = b"portable-fixture-key"
        lease = FreshnessLease("origin-東京", "memory-acción", 1, 1000, 9000).signed(key)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state – 租约" / "leases.json"
            path.parent.mkdir(parents=True)
            path.write_bytes((json.dumps([lease.to_json()], ensure_ascii=False) + "\r\n")
                             .encode("utf-8"))
            book = LeaseBook({"origin-東京": {"k1": key}}, clock_ms=lambda: 2000,
                             monotonic_ms=lambda: 10)
            self.assertEqual(book.load(path), 1)
            self.assertEqual(book.get("origin-東京", "memory-acción"), lease)
            book.save(path)
            saved = path.read_bytes()
            self.assertTrue(saved.endswith(b"\n"))
            self.assertNotIn(b"\r\n", saved)
            self.assertEqual(json.loads(saved.decode("utf-8"))[0]["memory_id"],
                             "memory-acción")

    def test_tracked_paths_have_no_casefold_collisions(self) -> None:
        completed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                                   capture_output=True, check=True)
        paths = [raw.decode("utf-8") for raw in completed.stdout.split(b"\0") if raw]
        by_casefold: dict[str, list[str]] = {}
        for path in paths:
            by_casefold.setdefault(path.casefold(), []).append(path)
        collisions = {key: values for key, values in by_casefold.items() if len(values) > 1}
        self.assertEqual(collisions, {}, "tracked paths collide on case-insensitive filesystems")

