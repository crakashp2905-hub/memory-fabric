"""Repeatable local complexity and duplicate-validation metrics for E5-09."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "memory_fabric" / "agent_api.py"


def local_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Walk one function body without counting nested functions/classes."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield child
        yield from local_nodes(child)


def complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    nodes = list(local_nodes(node))
    branches = sum(isinstance(item, (ast.If, ast.For, ast.AsyncFor, ast.While,
                                     ast.ExceptHandler, ast.IfExp, ast.Assert))
                   for item in nodes)
    branches += sum(max(0, len(item.values) - 1)
                    for item in nodes if isinstance(item, ast.BoolOp))
    branches += sum(max(0, len(item.cases) - 1)
                    for item in nodes if isinstance(item, ast.Match))
    return branches + 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    posts = [node for node in functions if node.name == "do_POST"]
    memory_id_extractors = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "_string" and len(node.args) == 2
        and isinstance(node.args[1], ast.Constant) and node.args[1].value == "memory_id"
    ]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    result = {
        "schema": "memory-fabric-e5-09-agent-api-metrics/1", "phase": args.phase,
        "source_commit": commit,
        "method": "AST cyclomatic estimate: decision nodes plus one; duplicated memory-id input-validation call sites",
        "metrics": {
            "post_handler_cyclomatic": complexity(posts[0]),
            "duplicate_memory_id_validators": max(0, len(memory_id_extractors) - 1),
            "memory_id_validator_call_sites": len(memory_id_extractors),
        },
    }
    target = args.out if args.out.is_absolute() else ROOT / args.out
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
