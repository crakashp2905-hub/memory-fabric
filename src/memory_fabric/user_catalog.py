"""User-managed model selection and portable, declarative agent manifests.

The catalog deliberately stores no provider credentials and imports no code.
Agent uploads are JSON descriptions that a host may inspect before constructing
its own runtime agent.
"""

from __future__ import annotations

__stability__ = "beta"

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .models import ModelSpec

ENV_CATALOG = "MEMORY_FABRIC_CATALOG"
MAX_MANIFEST_BYTES = 256 * 1024
MAX_PROMPT_CHARS = 100_000
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def catalog_path() -> Path:
    configured = os.environ.get(ENV_CATALOG)
    return Path(configured).expanduser() if configured else Path.home() / ".memory-fabric" / "catalog.json"


@dataclass(frozen=True)
class AgentManifest:
    id: str
    name: str
    description: str = ""
    model: str | None = None
    system_prompt: str = ""
    tools: tuple[str, ...] = ()
    version: int = 1

    @staticmethod
    def from_mapping(value: Mapping[str, Any]) -> "AgentManifest":
        allowed = {"schema", "version", "id", "name", "description", "model", "system_prompt", "tools"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError("unknown agent fields: " + ", ".join(unknown))
        if value.get("schema", "memory-fabric-agent-v1") != "memory-fabric-agent-v1":
            raise ValueError("agent schema must be memory-fabric-agent-v1")
        agent_id = value.get("id")
        name = value.get("name")
        if not isinstance(agent_id, str) or not _ID.fullmatch(agent_id):
            raise ValueError("agent id must be 1-128 letters, numbers, dots, dashes or underscores")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("agent name must be a non-empty string of at most 200 characters")
        description = value.get("description", "")
        prompt = value.get("system_prompt", "")
        model = value.get("model")
        tools = value.get("tools", [])
        version = value.get("version", 1)
        if not isinstance(description, str) or len(description) > 2_000:
            raise ValueError("agent description must be at most 2000 characters")
        if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
            raise ValueError(f"agent system_prompt must be at most {MAX_PROMPT_CHARS} characters")
        if model is not None:
            if not isinstance(model, str):
                raise ValueError("agent model must be a model spec string")
            ModelSpec.parse(model)
        if (not isinstance(tools, list) or len(tools) > 100
                or any(not isinstance(tool, str) or not _ID.fullmatch(tool) for tool in tools)):
            raise ValueError("agent tools must be a list of at most 100 tool ids")
        if version != 1:
            raise ValueError("agent manifest version must be 1")
        return AgentManifest(agent_id, name.strip(), description, model, prompt, tuple(tools), version)


class UserCatalog:
    """A small atomic JSON catalog. It contains preferences, never secrets."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else catalog_path()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": "memory-fabric-catalog-v1", "selected_model": None, "agents": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"cannot read catalog {self.path}: {exc}") from exc
        if not isinstance(data, dict) or data.get("schema") != "memory-fabric-catalog-v1":
            raise ValueError(f"{self.path}: unsupported catalog schema")
        if not isinstance(data.get("agents", {}), dict):
            raise ValueError(f"{self.path}: agents must be an object")
        return data

    def _write(self, data: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def selected_model(self) -> str | None:
        value = self._read().get("selected_model")
        return value if isinstance(value, str) else None

    def select_model(self, spec: str) -> str:
        parsed = str(ModelSpec.parse(spec))
        data = self._read()
        data["selected_model"] = parsed
        self._write(data)
        return parsed

    def import_agent(self, source: str | Path, *, replace: bool = False) -> AgentManifest:
        path = Path(source)
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError(f"agent manifest exceeds {MAX_MANIFEST_BYTES} bytes")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"cannot read agent manifest {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("agent manifest must be a JSON object")
        manifest = AgentManifest.from_mapping(raw)
        data = self._read()
        agents = data.setdefault("agents", {})
        if manifest.id in agents and not replace:
            raise ValueError(f"agent {manifest.id!r} already exists; pass --replace to update it")
        agents[manifest.id] = asdict(manifest)
        agents[manifest.id]["tools"] = list(manifest.tools)
        self._write(data)
        return manifest

    def agents(self) -> list[AgentManifest]:
        return [AgentManifest.from_mapping(value) for _, value in
                sorted(self._read().get("agents", {}).items())]

    def public_view(self) -> dict[str, Any]:
        """Catalog metadata safe for the local read-only operator dashboard.

        System prompts are intentionally omitted: the dashboard needs enough
        to explain configuration, not another surface that displays prompts.
        """
        return {
            "selected_model": self.selected_model(),
            "path": str(self.path),
            "agents": [{
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "model": agent.model,
                "tools": list(agent.tools),
                "version": agent.version,
                "system_prompt_chars": len(agent.system_prompt),
            } for agent in self.agents()],
        }
