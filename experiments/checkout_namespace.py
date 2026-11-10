"""Resolve a historical checkout's actual declared package without import aliases."""
from __future__ import annotations

import importlib
import sys
import tomllib
from functools import lru_cache
from pathlib import Path
from types import ModuleType


def layout_at(checkout: Path) -> tuple[str, Path]:
    data = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8"))
    finder = data["tool"]["setuptools"]["packages"]["find"]
    candidates = [(name.rstrip("*"), (checkout / where).resolve())
                  for name in finder["include"] for where in finder.get("where", ["."])]
    candidates = [(name, root) for name, root in candidates
                  if name.isidentifier() and root.is_relative_to(checkout.resolve())
                  and (root / name).is_dir()]
    if len(candidates) != 1:
        raise ValueError("checkout must declare exactly one implementation package")
    return candidates[0]


def namespace_at(checkout: Path) -> str:
    return layout_at(checkout)[0]


@lru_cache(maxsize=32)
def load_from_checkout(checkout: Path, suffix: str) -> ModuleType:
    checkout = checkout.resolve()
    namespace, source = layout_at(checkout)
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    # The package this process already imported (the current checkout) would
    # satisfy the import from its cache. Move its entries aside for the import
    # and put them back, so the baseline is loaded from its own files.
    def owned(name: str) -> bool:
        return name == namespace or name.startswith(namespace + ".")
    saved = {name: sys.modules.pop(name) for name in list(sys.modules) if owned(name)}
    try:
        module = importlib.import_module(namespace + "." + suffix)
    finally:
        for name in [name for name in sys.modules if owned(name)]:
            del sys.modules[name]
        sys.modules.update(saved)
    if not module.__file__ or not Path(module.__file__).resolve().is_relative_to(checkout):
        raise RuntimeError("historical baseline resolved outside the selected checkout")
    return module
