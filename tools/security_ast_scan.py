"""AST checks for dangerous primitives in the security boundary modules."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SECURITY_MODULES = (
    "actions.py", "agent_api.py", "eventlog.py", "identity.py", "integrity.py",
    "tool_protocol.py", "transport.py",
)
EXCEPTIONS = ROOT / "tools" / "security_ast_exceptions.json"


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def findings_for(source: str, filename: str) -> list[dict[str, object]]:
    tree = ast.parse(source, filename=filename)
    found: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = call_name(node.func)
            category = None
            if name in {"eval", "exec", "builtins.eval", "builtins.exec"}:
                category = "dynamic-code"
            elif name in {"pickle.load", "pickle.loads", "_pickle.load", "_pickle.loads"}:
                category = "unsafe-deserialization"
            elif name == "yaml.load":
                safe = any(k.arg == "Loader" and "SafeLoader" in ast.unparse(k.value)
                           for k in node.keywords)
                if not safe:
                    category = "unsafe-deserialization"
            elif name in {"os.system", "os.popen"}:
                category = "shell-execution"
            elif name.startswith("subprocess.") and any(
                    k.arg == "shell" and isinstance(k.value, ast.Constant)
                    and k.value.value is True for k in node.keywords):
                category = "shell-execution"
            if category:
                found.append({"file": filename, "line": node.lineno,
                              "category": category, "expression": ast.unparse(node)})
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if call_name(node.left).endswith("Path") and isinstance(node.right, ast.Name) \
                    and any(word in node.right.id.lower() for word in
                            ("user", "request", "input", "supplied", "filename")):
                found.append({"file": filename, "line": node.lineno,
                              "category": "untrusted-path-join",
                              "expression": ast.unparse(node)})
        elif isinstance(node, ast.Call) and call_name(node.func).endswith(".joinpath"):
            if any(isinstance(arg, ast.Name) and any(word in arg.id.lower() for word in
                   ("user", "request", "input", "supplied", "filename")) for arg in node.args):
                found.append({"file": filename, "line": node.lineno,
                              "category": "untrusted-path-join", "expression": ast.unparse(node)})
    return found


def scan(paths: Iterable[Path], exceptions: list[dict[str, str]] | None = None) -> list[dict[str, object]]:
    allow = exceptions or []
    remaining = list(allow)
    result: list[dict[str, object]] = []
    for path in paths:
        rel = path.resolve().relative_to(ROOT).as_posix()
        for finding in findings_for(path.read_text(encoding="utf-8"), rel):
            match = next((entry for entry in remaining
                          if entry.get("file") == rel
                          and entry.get("category") == finding["category"]
                          and entry.get("line") == str(finding["line"])
                          and entry.get("rationale", "").strip()), None)
            if match:
                remaining.remove(match)
            else:
                result.append(finding)
    for entry in remaining:
        result.append({"file": entry.get("file"), "line": entry.get("line"),
                       "category": "stale-or-unjustified-exception",
                       "expression": entry.get("rationale", "")})
    return result


def production_paths() -> list[Path]:
    base = ROOT / "src" / "memory_fabric"
    paths = [base / name for name in SECURITY_MODULES if (base / name).is_file()]
    paths.extend(sorted(p for p in (base / "governance").rglob("*.py") if p.is_file()))
    return paths


def main() -> int:
    exceptions = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    if not isinstance(exceptions, list) or any(not str(x.get("rationale", "")).strip() for x in exceptions):
        print("invalid exception registry: each entry requires a rationale", file=sys.stderr)
        return 2
    findings = scan(production_paths(), exceptions)
    print(json.dumps({"schema": "memory-fabric-security-ast/1",
                      "modules_scanned": len(production_paths()),
                      "finding_count": len(findings), "findings": findings}, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
