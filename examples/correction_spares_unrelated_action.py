"""A correction blocks its dependent action but leaves an unrelated action usable."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule  # noqa: E402


def main() -> int:
    print("DEMO ONLY: deterministic in-memory fixtures; no external effects.")
    fabric = MemoryFabric(":memory:", auto_activate=True, seed=0)
    effects: list[str] = []
    try:
        stale_id = fabric.remember("ops", "Pump P1 purge setting is 30 seconds.", scope="team")
        independent_id = fabric.remember("ops", "Tyre pressure target is 34 psi.", scope="team")
        policy = ActionPolicy(
            tools={"restart_pump": ToolRule("restart_pump"),
                   "check_tyre": ToolRule("check_tyre")},
            grants={"ops": frozenset({"restart_pump", "check_tyre"})},
        )
        gate = ActionGate(fabric, policy)
        stale_cert = fabric.certify("restart P1", [stale_id], "ops")
        independent_cert = fabric.certify("check tyre pressure", [independent_id], "ops")
        request = ActionRequest("local-demo-target", {})
        first = gate.execute("restart_pump", "ops", lambda _key: effects.append("restart"),
                             stale_cert, key="correction-demo-before", request=request)
        independent_before = gate.execute(
            "check_tyre", "ops", lambda _key: effects.append("tyre-check"),
            independent_cert, key="correction-demo-tyre-before", request=request)
        replacement = fabric.remember("reviewer", "Pump P1 purge setting is 45 seconds.", scope="team")
        fabric.validate(replacement, actor="reviewer")
        fabric.share(replacement, "team")
        fabric.quarantine(stale_id, reason="manufacturer revised the purge setting",
                          actor="reviewer", basis="contradicted")
        after_correction = gate.execute(
            "restart_pump", "ops", lambda _key: effects.append("stale-restart"),
            stale_cert, key="correction-demo-after", request=request)
        independent_after = gate.execute(
            "check_tyre", "ops", lambda _key: effects.append("tyre-check"),
            independent_cert, key="correction-demo-tyre-after", request=request)
        print(f"dependent action: {first.outcome} before correction, "
              f"{after_correction.outcome} after correction")
        print(f"unrelated action: {independent_before.outcome} before, "
              f"{independent_after.outcome} after correction")
        print(f"external effects simulated: {effects}")
        if (first.outcome != "executed" or after_correction.outcome != "refused"
                or independent_before.outcome != "executed"
                or independent_after.outcome != "executed"
                or effects != ["restart", "tyre-check", "tyre-check"]):
            raise AssertionError("correction affected the wrong action set")
        return 0
    finally:
        fabric.close()


if __name__ == "__main__":
    raise SystemExit(main())
