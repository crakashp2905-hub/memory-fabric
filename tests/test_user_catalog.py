"""User-selected models and safe declarative agent uploads."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from memory_fabric.models import ModelClient, ModelError, pull_model
from memory_fabric.user_catalog import AgentManifest, UserCatalog


class TestUserCatalog(unittest.TestCase):
    def test_selected_model_is_used_but_environment_wins(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            catalog = UserCatalog(Path(tmp) / "catalog.json")
            catalog.select_model("ollama:qwen2.5:7b")
            with mock.patch.dict(os.environ, {"MEMORY_FABRIC_CATALOG": str(catalog.path)}, clear=True):
                self.assertEqual(str(ModelClient().spec), "ollama:qwen2.5:7b")
            env = {"MEMORY_FABRIC_CATALOG": str(catalog.path),
                   "MEMORY_FABRIC_MODEL": "openai:gpt-test"}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(str(ModelClient().spec), "openai:gpt-test")

    def test_agent_import_is_declarative_validated_and_replace_is_explicit(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            source = Path(tmp) / "agent.json"
            source.write_text(json.dumps({
                "schema": "memory-fabric-agent-v1", "id": "researcher", "name": "Researcher",
                "model": "ollama:qwen2.5:7b", "system_prompt": "Cite sources.",
                "tools": ["recall", "remember"]}), encoding="utf-8")
            catalog = UserCatalog(Path(tmp) / "catalog.json")
            imported = catalog.import_agent(source)
            self.assertEqual(imported, AgentManifest("researcher", "Researcher", "",
                                                     "ollama:qwen2.5:7b", "Cite sources.",
                                                     ("recall", "remember"), 1))
            with self.assertRaisesRegex(ValueError, "already exists"):
                catalog.import_agent(source)
            self.assertEqual(catalog.import_agent(source, replace=True).id, "researcher")
            public = catalog.public_view()
            self.assertEqual(public["selected_model"], None)
            self.assertEqual(public["agents"][0]["system_prompt_chars"], 13)
            self.assertNotIn("system_prompt", public["agents"][0])

    def test_agent_manifest_rejects_executable_or_unknown_fields(self):
        with self.assertRaisesRegex(ValueError, "unknown agent fields"):
            AgentManifest.from_mapping({"id": "bad", "name": "Bad", "python": "evil()"})
        with self.assertRaises(ValueError):
            AgentManifest.from_mapping({"id": "bad/path", "name": "Bad"})


class TestPull(unittest.TestCase):
    def test_pull_uses_fixed_local_ollama_endpoint(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data)
            return io.BytesIO(b'{"status":"success"}')

        result = pull_model("ollama:qwen2.5:7b", opener=opener)
        self.assertEqual(seen, {"url": "http://127.0.0.1:11434/api/pull",
                                "body": {"name": "qwen2.5:7b", "stream": False}})
        self.assertEqual(result["status"], "success")
        with self.assertRaises(ModelError):
            pull_model("openai:gpt-test", opener=opener)


if __name__ == "__main__":
    unittest.main()
