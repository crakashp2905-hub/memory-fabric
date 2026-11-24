"""Tenant and authorization setup for the agent-outcome stack, on a fresh machine.

    python examples/agent_outcome_tenant_setup.py

No hard-coded credentials and no permissive defaults:

1. the store is a throwaway in-memory one;
2. agent keys are generated on the spot with ``os.urandom`` and never printed;
3. the action policy grants ``open_valve`` to exactly one agent, ``ops``;
4. a second agent, ``intern``, is registered in the same tenant but holds no grant.

It then shows the grant working for ``ops`` and refusing ``intern``.
"""

from __future__ import annotations

import os

from memory_fabric import MemoryFabric
from memory_fabric.actions import EXECUTED, ActionGate, ActionPolicy, ToolRule
from memory_fabric.service import MemoryService

TENANT = "tn_plant_a"


def main() -> int:
    print("DEMO ONLY: in-memory store; ephemeral local keys; no external action is performed.")
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        service = MemoryService(fabric=fabric)
        for agent in ("ops", "intern"):
            service.register_agent(agent, key=os.urandom(32), tenant_id=TENANT)
        gate = ActionGate(fabric, ActionPolicy(tools={"open_valve": ToolRule("open_valve")},
                                               grants={"ops": frozenset({"open_valve"})}))
        memory = fabric.remember("inspector", "valve 7 is safe to open below 4 bar",
                                 scope="team", tenant_id=TENANT)
        for agent in ("ops", "intern"):
            session = service.session(service.issue(agent))
            certificate = fabric.certify("open-7", [memory], agent, tenant_id=TENANT)
            done = gate.execute("open_valve", agent, lambda key: "opened", certificate,
                                key=f"open-7-{agent}", tenant_id=TENANT, session=session)
            verdict = "allowed" if done.outcome == EXECUTED else "refused"
            reasons = ",".join(done.decision.reason_codes) if done.decision else done.outcome
            print(f"{agent}: {verdict} ({reasons})")
    finally:
        fabric.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
