"""Compare naive deletion, blanket invalidation and selective evidence gating."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule  # noqa: E402


def main() -> int:
    print("DEMO ONLY: one deterministic correction fixture; no external effects.")
    initial = {"pump:P1:purge_seconds": 30, "tyre:target_psi": 34}
    corrected = {"pump:P1:purge_seconds": 45, "tyre:target_psi": 34}

    # Naive store applies the correction, but an action already cached by an
    # agent has no reference that the store can invalidate or recheck.
    naive = dict(initial)
    cached_action = initial["pump:P1:purge_seconds"]
    naive.update(corrected)
    naive_stale = cached_action == 30

    # Blanket invalidation refuses every pre-correction certificate, including
    # the unrelated tyre check: safe for stale work, but one false block.
    blanket_stale = False
    blanket_independent = False

    fabric = MemoryFabric(":memory:", auto_activate=True, seed=0)
    try:
        stale_id = fabric.remember("ops", "Pump P1 purge time is 30 seconds.", scope="team")
        tyre_id = fabric.remember("ops", "Tyre pressure target is 34 psi.", scope="team")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"restart_pump": ToolRule("restart_pump"), "check_tyres": ToolRule("check_tyres")},
            grants={"ops": frozenset({"restart_pump", "check_tyres"})}))
        stale = fabric.certify("restart P1 with 30-second purge", [stale_id], "ops")
        independent = fabric.certify("check tyre pressure target", [tyre_id], "ops")
        replacement = fabric.remember("reviewer", "Pump P1 purge time is 45 seconds.", scope="team")
        fabric.validate(replacement, actor="reviewer")
        fabric.share(replacement, "team")
        fabric.quarantine(stale_id, reason="manufacturer changed purge time", actor="reviewer",
                          basis="contradicted")
        selective_stale = gate.authorize("restart_pump", "ops", stale).allowed
        selective_independent = gate.authorize("check_tyres", "ops", independent).allowed

        print("arm             stale action   unrelated action   stale actions   false blocks")
        print(f"naive delete    {'WOULD RUN' if naive_stale else 'blocked':<13} "
              f"{'allowed':<16} {int(naive_stale):<14} 0")
        print(f"blanket         {'blocked':<13} {'blocked':<16} {int(blanket_stale):<14} "
              f"{int(not blanket_independent)}")
        print(f"selective gate  {'allowed' if selective_stale else 'blocked':<13} "
              f"{'allowed' if selective_independent else 'blocked':<16} "
              f"0 {int(not selective_independent)}")
        print("Naive stale outcome is a cached proposal; blanket arm is a scripted comparator.")
        print("False block means the unrelated 34-psi action is refused despite unchanged evidence.")
        if naive_stale is not True or blanket_stale or blanket_independent:
            return 1
        if selective_stale or not selective_independent:
            return 1
        return 0
    finally:
        fabric.close()


if __name__ == "__main__":
    raise SystemExit(main())
