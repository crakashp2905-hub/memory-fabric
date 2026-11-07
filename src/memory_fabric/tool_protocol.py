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
import ipaddress
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

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
_UTCP_MANUAL_FIELDS = frozenset({"utcp_version", "manual_version", "name", "description", "tools"})
_JSON_SCHEMA_FIELDS = frozenset({
    "$schema", "type", "properties", "required", "additionalProperties", "items",
    "enum", "const", "description", "title", "default", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "pattern",
    "format", "minItems", "maxItems", "uniqueItems", "minProperties", "maxProperties",
})
_JSON_SCHEMA_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})
_TOOL_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")


def _validate_input_schema(schema: Mapping[str, Any]) -> None:
    """Validate a bounded JSON Schema subset; unsupported keywords fail closed."""
    if schema.get("type") != "object":
        raise ToolProtocolError("tool input schema root type must be object")
    nodes = 0

    def visit(node: Mapping[str, Any], depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if depth > 32 or nodes > 1000:
            raise ToolProtocolError("tool input schema exceeds validation limits")
        _reject_unknown_fields(node, _JSON_SCHEMA_FIELDS, "JSON Schema")
        schema_type = node.get("type")
        if schema_type is not None:
            types = schema_type if isinstance(schema_type, list) else [schema_type]
            if not types or any(not isinstance(item, str) or item not in _JSON_SCHEMA_TYPES
                                for item in types):
                raise ToolProtocolError("JSON Schema type is invalid")
        properties = node.get("properties", {})
        if not isinstance(properties, Mapping) or any(not isinstance(key, str) for key in properties):
            raise ToolProtocolError("JSON Schema properties must be an object with string keys")
        for child in properties.values():
            if not isinstance(child, Mapping):
                raise ToolProtocolError("each JSON Schema property must be an object")
            visit(child, depth + 1)
        required = node.get("required", [])
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise ToolProtocolError("JSON Schema required must be an array of strings")
        if len(required) != len(set(required)):
            raise ToolProtocolError("JSON Schema required contains duplicates")
        additional = node.get("additionalProperties", True)
        if isinstance(additional, Mapping):
            visit(additional, depth + 1)
        elif not isinstance(additional, bool):
            raise ToolProtocolError("JSON Schema additionalProperties must be a boolean or schema")
        if "items" in node:
            if not isinstance(node["items"], Mapping):
                raise ToolProtocolError("JSON Schema items must be an object")
            visit(node["items"], depth + 1)
        if "enum" in node and not isinstance(node["enum"], list):
            raise ToolProtocolError("JSON Schema enum must be an array")
        for key in ("description", "title", "pattern", "format", "$schema"):
            if key in node and not isinstance(node[key], str):
                raise ToolProtocolError(f"JSON Schema {key} must be a string")
        if "pattern" in node:
            try:
                re.compile(node["pattern"])
            except re.error as exc:
                raise ToolProtocolError("JSON Schema pattern is malformed") from exc
        for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
            value = node.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(value)):
                raise ToolProtocolError(f"JSON Schema {key} must be a finite number")
        for key in ("minLength", "maxLength", "minItems", "maxItems",
                    "minProperties", "maxProperties"):
            value = node.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)
                                      or value < 0):
                raise ToolProtocolError(f"JSON Schema {key} must be a non-negative integer")
        if "uniqueItems" in node and not isinstance(node["uniqueItems"], bool):
            raise ToolProtocolError("JSON Schema uniqueItems must be a boolean")

    visit(schema, 0)


def _validate_transport(transport: Mapping[str, Any]) -> None:
    if not transport:
        return
    supported = frozenset({"call_template_type", "url", "http_method"})
    _reject_unknown_fields(transport, supported, "UTCP transport")
    if transport.get("call_template_type") != "http":
        raise ToolProtocolError("unsupported or dangerous UTCP transport type")
    url = transport.get("url")
    if not isinstance(url, str):
        raise ToolProtocolError("UTCP HTTP transport requires a URL")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ToolProtocolError("malformed UTCP transport URL") from exc
    if (parsed.scheme.lower() != "https" or not host or parsed.username is not None
            or parsed.password is not None or parsed.fragment or port not in (None, 443)):
        raise ToolProtocolError("UTCP transport must use a public HTTPS origin")
    normalized_host = host.rstrip(".").lower()
    if (not normalized_host or normalized_host.endswith(
            (".localhost", ".local", ".internal", ".test", ".example", ".invalid"))
            or normalized_host in {"localhost", "localhost.localdomain"}
            or "." not in normalized_host):
        raise ToolProtocolError("UTCP transport host is local or not a public DNS name")
    if (len(normalized_host) > 253 or any(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
            for label in normalized_host.split("."))):
        raise ToolProtocolError("UTCP transport host is not a valid ASCII DNS name")
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ToolProtocolError("UTCP transport host is a non-public IP address")
    if address is None and not re.fullmatch(r"(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})",
                                            normalized_host.rsplit(".", 1)[-1]):
        raise ToolProtocolError("UTCP transport hostname has an invalid or numeric suffix")
    method = transport.get("http_method", "POST")
    if not isinstance(method, str) or method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ToolProtocolError("unsupported UTCP HTTP method")


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
    if not isinstance(raw.get("name"), str) or _TOOL_NAME.fullmatch(raw["name"]) is None:
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
    if "inputs" not in raw:
        raise ToolProtocolError("UTCP tool requires an inputs schema")
    input_schema = _object_mapping(raw["inputs"], "UTCP inputs")
    _validate_input_schema(input_schema)
    transport_mapping = _object_mapping(transport, "UTCP transport")
    _validate_transport(transport_mapping)
    return ToolDescriptor(
        name=raw["name"], description=description,
        input_schema=input_schema,
        consequential=consequential, protocol=f"utcp-{version}",
        transport=transport_mapping,
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
    if not isinstance(raw.get("name"), str) or _TOOL_NAME.fullmatch(raw["name"]) is None:
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
    _validate_input_schema(schema)
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

    _reject_unknown_fields(document, _UTCP_MANUAL_FIELDS, "UTCP manual")
    version = document.get("utcp_version", "")
    manual_version = document.get("manual_version")
    if (not isinstance(version, str) or re.fullmatch(r"1\.0\.\d+", version) is None
            or manual_version != "1.0.0"):
        raise ToolProtocolError(f"unsupported UTCP version: {version or 'missing'}")
    for label in ("name", "description"):
        if label in document and not isinstance(document[label], str):
            raise ToolProtocolError(f"UTCP manual {label} must be a string")
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
        if _TOOL_NAME.fullmatch(name) is None:
            raise ToolProtocolError("UTCP tool name has invalid characters or length")
        if name.casefold() in names:
            raise ToolProtocolError(f"duplicate tool: {name}")
        names.add(name.casefold())
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
