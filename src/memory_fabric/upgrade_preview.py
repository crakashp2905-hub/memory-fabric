"""Read-only schema compatibility preview for SQLite stores."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any

__stability__ = "beta"

from .model import SCHEMA_VERSION

_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def preview_upgrade(path: str | Path) -> dict[str, Any]:
    """Inspect a SQLite event log using mode=ro; no migration is attempted."""
    database = Path(path).resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    before = _file_sha256(database)
    uri = database.as_uri() + "?mode=ro"
    incompatibilities: list[dict[str, str]] = []
    versions: list[str] = []
    event_count = 0
    integrity = "not_run"
    try:
        connection = sqlite3.connect(uri, uri=True)
        try:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if "events" not in tables:
                incompatibilities.append({"code": "missing_events_table",
                                          "detail": "database has no events table"})
            else:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(events)")}
                required = {"seq", "event_id", "schema_version", "payload"}
                if not required <= columns:
                    incompatibilities.append({"code": "missing_event_columns",
                                              "detail": f"missing columns: {sorted(required - columns)}"})
                else:
                    event_count = int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
                    versions = sorted(str(row[0]) for row in connection.execute(
                        "SELECT DISTINCT schema_version FROM events ORDER BY schema_version"))
                    current = tuple(int(part) for part in SCHEMA_VERSION.split("."))
                    for version in versions:
                        if not _VERSION.fullmatch(version):
                            incompatibilities.append({"code": "malformed_schema_version",
                                                      "detail": f"event schema version {version!r} is malformed"})
                            continue
                        parsed = tuple(int(part) for part in version.split("."))
                        if parsed[0] != current[0] or parsed > current:
                            incompatibilities.append({"code": "unsupported_schema_version",
                                                      "detail": f"event schema {version} is outside the supported <= {SCHEMA_VERSION} major-version range"})
                    integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
                    if integrity != "ok":
                        incompatibilities.append({"code": "sqlite_integrity_check_failed",
                                                  "detail": integrity})
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        incompatibilities.append({"code": "unreadable_sqlite", "detail": str(exc)})
    after = _file_sha256(database)
    if before != after:
        incompatibilities.append({"code": "dry_run_mutated_store",
                                  "detail": "database bytes changed during read-only preview"})
    return {
        "schema": "memory-fabric-upgrade-preview/1",
        "database": str(database),
        "mode": "read_only_preview_no_migration",
        "current_schema_version": SCHEMA_VERSION,
        "event_count": event_count,
        "event_schema_versions": versions,
        "sqlite_quick_check": integrity,
        "sha256_before": before,
        "sha256_after": after,
        "store_byte_identical": before == after,
        "incompatibilities": incompatibilities,
        "compatible_for_current_reader": not incompatibilities,
        "limitations": [
            "SQLite only; PostgreSQL connection strings are not inspected by this command.",
            "This checks recorded event schema labels and SQLite integrity; it does not simulate a future migration or prove application-level semantics."
        ],
    }
