"""Actor-only local-model decisions for the canonical episode runtime (W12-02, W12-03, W12-06, W12-07).

:class:`ModelActor` is a :data:`~memory_fabric.outcome_typed.episode.DecisionFunction`.
It sees exactly what a scripted actor sees, the ``(role, AgentObservation)`` pair
the runtime builds, and nothing else: no world, no evaluator, no grading API, no
task generator. The observation goes to the model as canonical JSON next to a
fixed system prompt naming the role's own tools.

The model answers with one JSON object, ``{"intent": ..., "arguments": {...}}``,
parsed strictly: anything else is ``model_malformed_output``. The actor adds the
envelope fields (schema, task id, actor id, a host-numbered step id) itself;
those are bookkeeping, not decisions. A failed call is an
:class:`~memory_fabric.outcome_typed.episode.ActorBackendError` with a distinct
code, so the episode ends incomplete with that reason. There is no retry with a
different prompt and no scripted fallback.

Every call is recorded (AGENTS.md: model, prompt hash, token counts, cost) with
the configuration fingerprint that produced it. Token counts a backend does not
report stay ``None`` and are counted as unknown, never as zero.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from .episode import ROLES, ActorBackendError, ToolRegistry, default_tools
from .observations import _INTENTS, AgentObservation, AgentStep

PROMPT_VERSION = "episode-actor-v1"
INTENTS = tuple(sorted(_INTENTS))

SYSTEM_TEMPLATE = """You are the {role} in a three-role team (observer, planner, executor).
You see only the JSON observation below. Answer with ONE JSON object and nothing else:
{{"intent": one of {intents}, "arguments": {{...}}}}
Put the tool you call in arguments["tool"]. Use intent "abstain" to stop without acting.
Tools you may call: {tools}
Role rules:
- observer: intent "inspect", tool "record_observations", one claim per new world event:
  {{"event_id", "text", "corrects": [event ids it corrects], "restricted": bool}}.
- planner: intent "retrieve" with tool "recall" first; then intent "propose" with the protected
  tool, citing only [memory_id, version] pairs recall returned to you; or recall again; or abstain
  if nothing authorizes acting.
- executor: intent "propose", tool "execute_proposal", with the exact commitment the host gave you.
Never invent memory ids, versions, tools or commitments."""

DECISION_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"intent": {"type": "string", "enum": list(INTENTS)},
                   "arguments": {"type": "object"}},
    "required": ["intent", "arguments"],
    "additionalProperties": False,
}


class ChatBackend(Protocol):
    """The subset of :class:`memory_fabric.adapters.ollama.OllamaClient` the actor uses."""

    def chat(self, model: str, messages: Sequence[Mapping[str, Any]], tools: Any = None,
             temperature: float = 0.0, num_predict: int = 256,
             schema: Mapping[str, Any] | None = None, think: bool | None = None,
             top_p: float | None = None, seed: int | None = None,
             num_ctx: int | None = None) -> dict[str, Any]: ...


def _sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     default=str).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ModelConfig:
    """Everything that determines one inference, pinned (W12-02).

    ``digest`` and ``runtime_version`` come from the loopback preflight, never
    from the caller's memory of what is installed.
    """

    model: str
    digest: str
    runtime_version: str
    quantization: str | None = None
    temperature: float = 0.0
    seed: int = 0
    num_ctx: int = 4096
    num_predict: int = 384
    constrained: bool = True
    think: bool | None = False
    calls_per_role: int = 8

    def __post_init__(self) -> None:
        if not self.model or not self.digest or not self.runtime_version:
            raise ValueError("model, digest and runtime_version must all be pinned")
        if self.num_ctx <= 0 or self.num_predict <= 0 or self.calls_per_role <= 0:
            raise ValueError("context, output and per-role call budgets must be positive")

    def fingerprint(self, tools: ToolRegistry) -> str:
        """One hash over the configuration, prompt template, output schema and tool schema."""
        return _sha256({"config": asdict(self), "prompt_version": PROMPT_VERSION,
                        "system_template": SYSTEM_TEMPLATE, "decision_schema": DECISION_SCHEMA,
                        "tools": tool_schema(tools)})


def tool_schema(tools: ToolRegistry, role: str | None = None) -> list[dict[str, Any]]:
    """The declared tools, optionally only those a role may call, in a stable order."""
    rows = []
    for name in sorted(tools._specs):  # noqa: SLF001 - read-only view of the host's registry
        spec = tools._specs[name]  # noqa: SLF001
        if role is not None and role not in spec.roles:
            continue
        rows.append({"name": spec.name, "fields": dict(sorted(spec.fields.items())),
                     "required": sorted(spec.required), "protected": spec.protected})
    return rows


def render_messages(role: str, observation: AgentObservation,
                    tools: ToolRegistry) -> list[dict[str, str]]:
    """The whole model input: a fixed system prompt and the canonical observation."""
    system = SYSTEM_TEMPLATE.format(role=role, intents=json.dumps(list(INTENTS)),
                                    tools=json.dumps(tool_schema(tools, role), sort_keys=True))
    return [{"role": "system", "content": system},
            {"role": "user", "content": observation.canonical_json()}]


def parse_decision(text: Any) -> tuple[str, dict[str, Any]]:
    """Parse one strict decision object or raise ``model_malformed_output``."""
    if not isinstance(text, str):
        raise ActorBackendError("model_malformed_output")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ActorBackendError("model_malformed_output") from exc
    if (not isinstance(raw, dict) or set(raw) != {"intent", "arguments"}
            or raw["intent"] not in INTENTS or not isinstance(raw["arguments"], dict)):
        raise ActorBackendError("model_malformed_output")
    return raw["intent"], raw["arguments"]


def classify_backend_error(exc: BaseException) -> str:
    """Map a backend exception to one distinct incomplete-outcome code."""
    if isinstance(exc, TimeoutError):
        return "model_timeout"
    if isinstance(exc, MemoryError):
        return "model_out_of_memory"
    text = str(exc).lower()
    if "timed out" in text or "timeout" in text:
        return "model_timeout"
    if "out of memory" in text or "requires more system memory" in text or "oom" in text.split():
        return "model_out_of_memory"
    if "context" in text and ("exceed" in text or "too long" in text or "length" in text):
        return "model_context_overflow"
    if ("cannot reach" in text or "connection refused" in text
            or ("model" in text and "not found" in text)):
        return "model_unavailable"
    return "model_error"


class ModelActor:
    """A local-model actor for every role, with per-role call budgets and a call log."""

    def __init__(self, backend: ChatBackend, config: ModelConfig,
                 tools: ToolRegistry | None = None,
                 clock: Callable[[], float] = time.perf_counter) -> None:
        self.backend = backend
        self.config = config
        self.tools = tools or default_tools()
        self.clock = clock
        self.fingerprint = config.fingerprint(self.tools)
        self.calls: list[dict[str, Any]] = []
        self._counts: dict[str, int] = {role: 0 for role in ROLES}

    def __call__(self, role: str, observation: AgentObservation) -> AgentStep:
        if role not in self._counts:
            raise ActorBackendError("model_error")
        if self._counts[role] >= self.config.calls_per_role:
            self._log(role, None, None, None, 0.0, "model_call_budget_exhausted")
            raise ActorBackendError("model_call_budget_exhausted")
        self._counts[role] += 1
        messages = render_messages(role, observation, self.tools)
        prompt_sha256 = _sha256(messages)
        started = self.clock()
        try:
            result = self.backend.chat(
                self.config.model, messages, temperature=self.config.temperature,
                num_predict=self.config.num_predict,
                schema=DECISION_SCHEMA if self.config.constrained else None,
                think=self.config.think, seed=self.config.seed, num_ctx=self.config.num_ctx)
        except ActorBackendError:
            raise
        except Exception as exc:  # noqa: BLE001 - every backend failure is classified
            code = classify_backend_error(exc)
            self._log(role, prompt_sha256, None, None, self.clock() - started, code)
            raise ActorBackendError(code) from exc
        seconds = self.clock() - started
        prompt_tokens = _count(result.get("prompt_eval_count"))
        completion_tokens = _count(result.get("eval_count"))
        code = "ok"
        if prompt_tokens is not None and prompt_tokens >= self.config.num_ctx:
            code = "model_context_overflow"  # the runtime truncated the input to fit
        elif completion_tokens is not None and completion_tokens >= self.config.num_predict:
            code = "model_truncated"
        message = result.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        if code == "ok":
            try:
                intent, arguments = parse_decision(content)
                step = AgentStep(task_id=observation.task_id, actor_id=role,
                                 step_id=f"{role}-m{self._counts[role]}", intent=intent,
                                 arguments=arguments)
            except ActorBackendError as exc:
                code = exc.code
            except (TypeError, ValueError):
                code = "model_malformed_output"
        self._log(role, prompt_sha256, prompt_tokens, completion_tokens, seconds, code)
        if code != "ok":
            raise ActorBackendError(code)
        return step

    def _log(self, role: str, prompt_sha256: str | None, prompt_tokens: int | None,
             completion_tokens: int | None, seconds: float, outcome: str) -> None:
        self.calls.append({"role": role, "model": self.config.model,
                           "config_fingerprint": self.fingerprint,
                           "prompt_sha256": prompt_sha256, "prompt_tokens": prompt_tokens,
                           "completion_tokens": completion_tokens,
                           "seconds": round(seconds, 6), "outcome": outcome})

    def usage(self) -> dict[str, Any]:
        """Per-role calls, known tokens, calls with unknown tokens, time and failures (W12-07)."""
        roles: dict[str, Any] = {}
        for role in ROLES:
            rows = [row for row in self.calls if row["role"] == role]
            roles[role] = {
                "calls": len(rows),
                "budget": self.config.calls_per_role,
                "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows),
                "completion_tokens": sum(r["completion_tokens"] or 0 for r in rows),
                "calls_with_unknown_tokens": sum(
                    1 for r in rows if r["prompt_tokens"] is None or r["completion_tokens"] is None),
                "seconds": round(sum(r["seconds"] for r in rows), 6),
            }
        failures: dict[str, int] = {}
        for row in self.calls:
            if row["outcome"] != "ok":
                failures[row["outcome"]] = failures.get(row["outcome"], 0) + 1
        return {"config_fingerprint": self.fingerprint, "model": self.config.model,
                "digest": self.config.digest, "roles": roles, "failures": failures,
                "retries": 0}


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
