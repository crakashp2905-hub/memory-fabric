"""Copied claims do not gain weight; independent roots can change support."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.consensus import support  # noqa: E402


def main() -> int:
    print("DEMO ONLY: synthetic claims and deterministic agents; source counts do not prove truth.")
    fabric = MemoryFabric(auto_activate=True, hold_suspicious=False, seed=0)
    try:
        origin = fabric.remember("agent-origin",
            "Compressor K-31 relief pressure is 22 bar.", scope="team")
        copies = [fabric.derive(f"agent-copy-{i}",
            "Compressor K-31 relief pressure is 22 bar, copied from the shared report.",
            [origin], scope="team") for i in range(1, 5)]
        independent_a = fabric.remember("field-observer-a",
            "Field check: compressor K-31 relief setting reads 14 bar.", scope="team")
        first = support(fabric, "Compressor K-31 relief pressure setting")
        loud = next(row for row in first.values if row.value == "22")
        quiet = next(row for row in first.values if row.value == "14")
        print(f"Five agents repeat 22 bar, but share {loud.independent_sources} source root.")
        print(f"One independent report supports 14 bar from {quiet.independent_sources} source root.")
        print(f"With one root per side, support is contested: {first.contested}; leading value: {first.leading}.")

        independent_b = fabric.remember("field-observer-b",
            "Night shift independently measured the K-31 relief setting at 14 bar.", scope="team")
        second = support(fabric, "Compressor K-31 relief pressure setting")
        quiet = next(row for row in second.values if row.value == "14")
        print(f"A second independent report raises 14-bar support to {quiet.independent_sources} roots; "
              f"leading value: {second.leading}.")
        print("Origin independence is not truth verification; evidence quality and authority remain separate checks.")
        if (len(copies) != 4 or not first.contested or first.leading is not None
                or quiet.independent_sources != 2 or second.leading != "14"
                or not independent_a or not independent_b):
            raise AssertionError("copied sources were counted as independent")
        return 0
    finally:
        fabric.close()


if __name__ == "__main__":
    raise SystemExit(main())
