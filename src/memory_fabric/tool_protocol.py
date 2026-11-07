"""Protocol-neutral discovery plus governed MCP/UTCP/Code Mode execution.

Discovery describes tools; it never grants them.  Every consequential call is
bound to exact arguments, authorized by ``ActionGate``, and protected by an
execution idempotency key.  Generated code can compose registered tools but
cannot import modules, access files, open sockets, or invoke arbitrary Python.
"""

from __future__ import annotations

__stability__ = "experimental"

import ast
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .actions import ActionGate, ActionRequest


class ToolProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    consequential: bool = True
    protocol: str = "native"
    transport: Mapping[str, Any] = field(default_factory=dict)
    annotations: Mapping[str, Any] = field(default_factory=dict)


_UTCP_TOOL_FIELDS = frozenset({
    "name", "description", "inputs", "consequential",
    "tool_call_template", "tool_transport",
})
_MCP_TOOL_FIELDS = frozenset({"name", "description", "inputSchema", "annotations"})
_MCP_ANNOTATION_FIELDS = frozenset({
    "title", "readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint",
})


def _reject_unknown_fields(raw: Mapping[str, Any], supported: frozenset[str],
                           protocol: str) -> None:
    if any(not isinstance(key, str) for key in raw):
        raise ToolProtocolError(f"{protocol} descriptor keys must be strings")
    unknown = sorted(set(raw) - supported)
    if unknown:
        raise ToolProtocolError(
            f"unsupported {protocol} descriptor field(s): {', '.join(unknown)}")


def _object_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ToolProtocolError(f"{label} must be an object")
    return value


def utcp_tool_to_descriptor(raw: Mapping[str, Any], *, version: str = "1.0.0") -> ToolDescriptor:
    """Convert the supported UTCP tool subset without dropping unknown fields."""
    _reject_unknown_fields(raw, _UTCP_TOOL_FIELDS, "UTCP")
    if not isinstance(raw.get("name"), str) or not raw["name"]:
        raise ToolProtocolError("UTCP tool name must be a non-empty string")
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise ToolProtocolError("UTCP description must be a string")
    consequential = raw.get("consequential", True)
    if not isinstance(consequential, bool):
        raise ToolProtocolError("UTCP consequential must be a boolean")
    if "tool_call_template" in raw and "tool_transport" in raw:
        raise ToolProtocolError("UTCP tool cannot specify both transport spellings")
    transport = raw.get("tool_call_template", raw.get("tool_transport", {}))
    return ToolDescriptor(
        name=raw["name"], description=description,
        input_schema=_object_mapping(raw.get("inputs", {}), "UTCP inputs"),
        consequential=consequential, protocol=f"utcp-{version}",
        transport=_object_mapping(transport, "UTCP transport"),
    )


def descriptor_to_utcp_tool(descriptor: ToolDescriptor) -> dict[str, Any]:
    """Serialize the supported canonical fields in the pinned UTCP spelling."""
    if descriptor.annotations:
        raise ToolProtocolError("UTCP cannot represent MCP tool annotations")
    result: dict[str, Any] = {
        "name": descriptor.name, "description": descriptor.description,
        "inputs": dict(descriptor.input_schema),
        "consequential": descriptor.consequential,
    }
    if descriptor.transport:
        result["tool_call_template"] = dict(descriptor.transport)
    return result


def mcp_tool_to_descriptor(raw: Mapping[str, Any]) -> ToolDescriptor:
    """Convert a supported MCP tool definition; reject extensions we cannot retain."""
    _reject_unknown_fields(raw, _MCP_TOOL_FIELDS, "MCP")
    if not isinstance(raw.get("name"), str) or not raw["name"]:
        raise ToolProtocolError("MCP tool name must be a non-empty string")
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise ToolProtocolError("MCP description must be a string")
    annotations = _object_mapping(raw.get("annotations", {}), "MCP annotations")
    _reject_unknown_fields(annotations, _MCP_ANNOTATION_FIELDS, "MCP annotation")
    for key, value in annotations.items():
        if key != "title" and not isinstance(value, bool):
            raise ToolProtocolError(f"MCP annotation {key} must be a boolean")
        if key == "title" and not isinstance(value, str):
            raise ToolProtocolError("MCP annotation title must be a string")
    read_only = annotations.get("readOnlyHint", False)
    destructive = annotations.get("destructiveHint", False)
    if read_only and destructive:
        raise ToolProtocolError("MCP tool cannot be both read-only and destructive")
    schema = _object_mapping(raw.get("inputSchema"), "MCP inputSchema")
    return ToolDescriptor(
        name=raw["name"], description=description, input_schema=schema,
        consequential=not read_only, protocol="mcp", annotations=dict(annotations),
    )


def descriptor_to_mcp_tool(descriptor: ToolDescriptor) -> dict[str, Any]:
    """Serialize canonical fields that MCP can represent without semantic loss."""
    if descriptor.transport:
        raise ToolProtocolError("MCP cannot represent UTCP transport metadata")
    annotations = dict(descriptor.annotations)
    if not annotations:
        annotations = {
            "readOnlyHint": not descriptor.consequential,
            "destructiveHint": descriptor.consequential,
        }
    return {
        "name": descriptor.name, "description": descriptor.description,
        "inputSchema": dict(descriptor.input_schema),
        "annotations": annotations,
    }


def discover_utcp(document: Mapping[str, Any]) -> tuple[ToolDescriptor, ...]:
    """Parse the pinned UTCP discovery subset without performing network I/O."""

    version = str(document.get("utcp_version", ""))
    manual_version = document.get("manual_version")
    if not version.startswith("1.0.") or not isinstance(manual_version, str):
        raise ToolProtocolError(f"unsupported UTCP version: {version or 'missing'}")
    tools = document.get("tools")
    if not isinstance(tools, list):
        raise ToolProtocolError("UTCP document must contain a tools list")
    result: list[ToolDescriptor] = []
    names: set[str] = set()
    for raw in tools:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("name"), str):
            raise ToolProtocolError("every UTCP tool needs a string name")
        descriptor = utcp_tool_to_descriptor(raw, version=version)
        name = descriptor.name
        if name in names:
            raise ToolProtocolError(f"duplicate tool: {name}")
        names.add(name)
        result.append(descriptor)
    return tuple(result)


@dataclass(frozen=True)
class GovernedToolCall:
    tool: str
    arguments: Mapping[str, Any]
    idempotency_key: str


class GovernedToolRuntime:
    """Registry whose calls are individually authorized at execution time."""

    def __init__(self, gate: ActionGate, handlers: Mapping[str, Callable[..., Any]]) -> None:
        self.gate = gate
        self.handlers = dict(handlers)

    def execute(self, call: GovernedToolCall, *, agent_id: str,
                certificate: Any = None, approval: Any = None,
                tenant_id: str | None = None, grant: Any = None,
                retry: bool = False) -> Any:
        handler = self.handlers.get(call.tool)
        if handler is None:
            raise ToolProtocolError(f"no registered handler for {call.tool}")
        request = ActionRequest(target=call.tool, parameters=dict(call.arguments))
        return self.gate.execute(
            call.tool,
            agent_id,
            lambda _key: handler(**dict(call.arguments)),
            key=call.idempotency_key,
            certificate=certificate,
            approval=approval,
            tenant_id=tenant_id,
            request=request,
            grant=grant,
            retry=retry,
        )


class CodeModePlan:
    """Validated sequence of literal tool calls; not an arbitrary code evaluator."""

    def __init__(self, calls: Sequence[GovernedToolCall]) -> None:
        self.calls = tuple(calls)

    @classmethod
    def parse(cls, source: str) -> "CodeModePlan":
        """Accept only ``tool_name(key=value, ...)`` expression statements."""

        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError as exc:
            raise ToolProtocolError(f"invalid code-mode plan: {exc.msg}") from exc
        calls: list[GovernedToolCall] = []
        for index, statement in enumerate(tree.body):
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                raise ToolProtocolError("code mode permits tool-call expressions only")
            node = statement.value
            if not isinstance(node.func, ast.Name) or node.args:
                raise ToolProtocolError("tools require a simple name and keyword arguments")
            arguments: dict[str, Any] = {}
            for keyword in node.keywords:
                if keyword.arg is None:
                    raise ToolProtocolError("expanded arguments are forbidden")
                if keyword.arg in arguments:
                    raise ToolProtocolError(f"duplicate argument: {keyword.arg}")
                try:
                    arguments[keyword.arg] = ast.literal_eval(keyword.value)
                except (ValueError, TypeError) as exc:
                    raise ToolProtocolError("generated arguments must be literals") from exc
            binding = json.dumps({"tool": node.func.id, "arguments": arguments},
                                 sort_keys=True, separators=(",", ":"), default=str)
            digest = hashlib.sha256(binding.encode()).hexdigest()[:20]
            calls.append(GovernedToolCall(node.func.id, arguments,
                                           f"code-mode:{index}:{digest}"))
        return cls(calls)

    def execute(self, runtime: GovernedToolRuntime, **authorization: Any) -> tuple[Any, ...]:
        return tuple(runtime.execute(call, **authorization) for call in self.calls)
