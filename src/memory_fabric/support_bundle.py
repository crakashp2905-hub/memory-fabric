"""Metadata-only support bundle generation.

Raw memory content, identifiers, tenant names, keys and event payloads are not
included. The export is deliberately limited to aggregate diagnostics.
"""
from __future__ import annotations

import json
import platform
from collections import Counter

__stability__ = "beta"
from pathlib import Path
from typing import Any

from . import __version__
from .model import SCHEMA_VERSION


def build_support_bundle(fabric: Any) -> dict[str, Any]:
    """Return aggregate store diagnostics, excluding user-provided values."""
    state_counts = Counter(memory.lifecycle_state.value for memory in fabric.state.memories.values())
    type_counts = Counter(memory.type.value for memory in fabric.state.memories.values())
    connection = fabric.log._conn
    page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
    page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
    return {
        "schema": "memory-fabric-support-bundle/1",
        "product": {"name": "memory-fabric", "version": __version__,
                    "store_schema_version": SCHEMA_VERSION},
        "runtime": {"python": platform.python_version(), "platform": platform.system()},
        "metrics": {
            "memory_count": len(fabric.state.memories),
            "event_count": len(fabric.log),
            "memory_lifecycle_counts": dict(sorted(state_counts.items())),
            "memory_type_counts": dict(sorted(type_counts.items())),
            "sqlite_page_count": page_count,
            "sqlite_page_size_bytes": page_size,
            "sqlite_allocated_bytes": page_count * page_size,
        },
        "content_included": False,
        "identifier_included": False,
        "tenant_metadata_included": False,
        "key_material_included": False,
        "event_payloads_included": False,
    }


def write_support_bundle(fabric: Any, output: str | Path) -> dict[str, Any]:
    """Write a JSON support bundle and return its content-free manifest."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = build_support_bundle(fabric)
    path.write_text(json.dumps(bundle, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return bundle
