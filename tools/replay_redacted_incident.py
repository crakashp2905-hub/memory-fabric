"""Verify and replay a redacted Memory Fabric incident artifact offline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from memory_fabric.observability.incident_export import replay_redacted_incident


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="redacted incident JSON export")
    parser.add_argument("--out", type=Path, help="write deterministic explanation JSON")
    args = parser.parse_args()
    try:
        payload = json.loads(args.artifact.read_text(encoding="utf-8"))
        result = replay_redacted_incident(payload)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
