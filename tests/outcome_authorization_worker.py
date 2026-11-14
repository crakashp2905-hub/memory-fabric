"""Subprocess helpers for process-level ActionGate race regressions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.certificates import EvidenceCertificate


def _wait_for(path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for {path.name}")
        time.sleep(0.01)


def main() -> int:
    mode, db_path, cert_json, key, effect_path, *barriers = sys.argv[1:]
    cert = EvidenceCertificate.from_json(json.loads(cert_json))
    fabric = MemoryFabric(db_path)
    gate = ActionGate(fabric, ActionPolicy(
        tools={"start": ToolRule("start")},
        grants={"operator": frozenset({"start"})},
    ))

    effect_path = Path(effect_path)

    def effect(idempotency_key: str) -> str:
        if mode == "race":
            entered, release = (Path(value) for value in barriers)
            entered.write_text("entered", encoding="utf-8")
            _wait_for(release)
        try:
            with effect_path.open("x", encoding="utf-8") as handle:
                handle.write(idempotency_key)
        except FileExistsError:
            if effect_path.read_text(encoding="utf-8") != idempotency_key:
                raise RuntimeError("external idempotency key mismatch")
            return "already_applied"
        if mode == "crash_after_effect":
            os._exit(23)
        return "applied"

    retry = mode == "retry"
    result = gate.execute("start", "operator", effect, cert, key=key, retry=retry)
    print(json.dumps({"outcome": result.outcome, "ran": result.ran,
                      "error": result.error}))
    fabric.close()
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    raise SystemExit(main())
