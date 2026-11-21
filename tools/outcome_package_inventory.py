#!/usr/bin/env python3
"""Diff the public surfaces of the three experimental outcome packages (checklist W02-01).

    python tools/outcome_package_inventory.py            # print the mapping
    python tools/outcome_package_inventory.py --write    # rewrite the committed mapping
    python tools/outcome_package_inventory.py --check    # exit 1 if the mapping is stale

Reads source with ``ast`` (nothing is imported or executed) for
``memory_fabric.agent_outcomes``, ``memory_fabric.outcome_protocol`` and
``memory_fabric.outcome_typed``. For every public name it records the kind
(class, enum, dataclass, function, constant), the enum members, the dataclass
fields, the function parameters and any ``schema_id``-style string constants.
Each name is then classified:

* ``identical`` - defined in more than one package with the same shape;
* ``conflicting`` - the same name with a different shape (members, fields or
  parameters differ);
* ``incompatible`` - the same name is a different kind (an enum in one package,
  a class in another);
* ``missing`` - defined in only some packages (reported with where it exists).

The result is the factual basis of ADR 0004 (canonical outcome runtime).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "memory_fabric"
PACKAGES = ("agent_outcomes", "outcome_protocol", "outcome_typed")
OUT = ROOT / "docs" / "architecture" / "OUTCOME_PACKAGE_INVENTORY.json"
CALLSITES = ROOT / "docs" / "architecture" / "OUTCOME_LEGACY_CALLSITES.json"
LEGACY = ("agent_outcomes", "outcome_protocol")
SCAN_DIRS = ("src", "benchmarks", "experiments", "examples", "tools", "tests", "memeval")
SCHEMA_ID = "memory-fabric.outcome-package-inventory.v1"


def _decorator_names(node: ast.ClassDef | ast.FunctionDef) -> set[str]:
    names = set()
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _bases(node: ast.ClassDef) -> list[str]:
    return [ast.unparse(base) for base in node.bases]


def describe_class(node: ast.ClassDef) -> dict[str, Any]:
    bases = _bases(node)
    if any(base.split(".")[-1] in {"Enum", "IntEnum", "StrEnum"} for base in bases):
        members = sorted(target.id for statement in node.body if isinstance(statement, ast.Assign)
                         for target in statement.targets if isinstance(target, ast.Name)
                         and not target.id.startswith("_"))
        return {"kind": "enum", "bases": bases, "members": members}
    if "dataclass" in _decorator_names(node):
        fields = [statement.target.id for statement in node.body
                  if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
                  and not statement.target.id.startswith("_")
                  and "ClassVar" not in ast.unparse(statement.annotation)]
        return {"kind": "dataclass", "bases": bases, "fields": fields}
    methods = sorted(statement.name for statement in node.body
                     if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and not statement.name.startswith("_"))
    return {"kind": "class", "bases": bases, "methods": methods}


def describe_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    arguments = node.args
    names = [arg.arg for arg in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]]
    return {"kind": "function", "parameters": names}


def module_surface(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    surface: dict[str, dict[str, Any]] = {}
    schema_ids: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            surface[node.name] = describe_class(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            surface[node.name] = describe_function(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    if target.id.isupper():
                        value = node.value
                        literal = (value.value if isinstance(value, ast.Constant)
                                   and isinstance(value.value, (str, int, float, bool)) else None)
                        surface.setdefault(target.id, {"kind": "constant", "value": literal})
        for child in ast.walk(node):
            if (isinstance(child, ast.Constant) and isinstance(child.value, str)
                    and child.value.startswith("memory-fabric.") and child.value.count(".") >= 2
                    and " " not in child.value):
                schema_ids.append(child.value)
    return surface, sorted(set(schema_ids))


def package_surface(package: str, root: Path = SRC) -> dict[str, Any]:
    names: dict[str, dict[str, Any]] = {}
    schema_ids: set[str] = set()
    for path in sorted((root / package).glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = f"memory_fabric.{package}.{path.stem}"
        surface, ids = module_surface(path)
        schema_ids.update(ids)
        for name, shape in surface.items():
            names.setdefault(name, {**shape, "module": module})
    return {"names": dict(sorted(names.items())), "schema_ids": sorted(schema_ids),
            "modules": sorted(path.stem for path in (root / package).glob("*.py")
                              if path.name != "__init__.py")}


def _shape(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (entry["kind"], tuple(entry.get("members", ())), tuple(entry.get("fields", ())),
            tuple(entry.get("parameters", ())), tuple(entry.get("methods", ())),
            repr(entry.get("value")))


def build(root: Path = SRC) -> dict[str, Any]:
    surfaces = {package: package_surface(package, root) for package in PACKAGES}
    all_names = sorted({name for surface in surfaces.values() for name in surface["names"]})
    mapping: dict[str, dict[str, Any]] = {}
    counts = {"identical": 0, "conflicting": 0, "incompatible": 0, "missing": 0, "unique": 0}
    for name in all_names:
        present = {package: surfaces[package]["names"][name] for package in PACKAGES
                   if name in surfaces[package]["names"]}
        kinds = {entry["kind"] for entry in present.values()}
        shapes = {_shape(entry) for entry in present.values()}
        if len(present) == 1:
            classification = "unique"
        elif len(kinds) > 1:
            classification = "incompatible"
        elif len(shapes) > 1:
            classification = "conflicting"
        else:
            classification = "identical"
        if classification != "unique" and len(present) < len(PACKAGES):
            # Shared by some packages but absent from at least one.
            counts["missing"] += 1
        counts[classification] += 1
        mapping[name] = {"classification": classification,
                         "present_in": sorted(present),
                         "absent_from": sorted(set(PACKAGES) - set(present)),
                         "shapes": {package: {key: value for key, value in entry.items()
                                              if key != "bases"}
                                    for package, entry in present.items()}}
    shared = {name: entry for name, entry in mapping.items() if entry["classification"] != "unique"}
    return {"schema_id": SCHEMA_ID, "generated_by": "tools/outcome_package_inventory.py",
            "packages": {package: {"modules": surfaces[package]["modules"],
                                   "public_names": len(surfaces[package]["names"]),
                                   "schema_ids": surfaces[package]["schema_ids"]}
                         for package in PACKAGES},
            "counts": counts, "shared_names": shared,
            "unique_names": {package: sorted(name for name, entry in mapping.items()
                                             if entry["classification"] == "unique"
                                             and entry["present_in"] == [package])
                             for package in PACKAGES}}


def legacy_callsites(root: Path = ROOT) -> dict[str, list[str]]:
    """Files outside each legacy package that import it (W02-07)."""
    found: dict[str, set[str]] = {package: set() for package in LEGACY}
    for directory in SCAN_DIRS:
        for path in sorted((root / directory).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if any(f"src/memory_fabric/{package}/" in rel for package in LEGACY):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.append(node.module)
                    modules.extend(f"{node.module}.{alias.name}" for alias in node.names)
                elif isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                for module in modules:
                    for package in LEGACY:
                        if module == f"memory_fabric.{package}" or module.startswith(
                                f"memory_fabric.{package}."):
                            found[package].add(rel)
    return {package: sorted(paths) for package, paths in found.items()}


def render(root: Path = SRC) -> str:
    return json.dumps(build(root), indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0
    if "--check" in argv:
        stale = not OUT.is_file() or OUT.read_text(encoding="utf-8") != text
        print("stale: run tools/outcome_package_inventory.py --write" if stale else "PASS")
        return 1 if stale else 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
