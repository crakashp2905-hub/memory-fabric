"""Standalone local verifier for exported CDM certificate JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.causal_replay.certificates import verify  # noqa: E402


def verify_json(data: str) -> bool:
    try:
        value: Any = json.loads(data)
    except (ValueError, TypeError):
        return False
    return verify(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", help="path to local certificate JSON")
    args = parser.parse_args(argv)
    try:
        data = Path(args.certificate).read_text(encoding="utf-8")
    except OSError:
        print("REFUSED")
        return 1
    if verify_json(data):
        print("VERIFIED")
        return 0
    print("REFUSED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
