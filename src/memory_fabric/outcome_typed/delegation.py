"""Task delegation receipts that never broaden a principal's permissions (W10-07).

A delegation hands part of a task to another role. The receipt names the task,
both roles, the tools delegated and when; it is digested so it cannot be edited.
It carries no credential, grant or certificate. A role can delegate only tools
it may call itself, and never a protected tool: protected effects run only on a
grant the host issues to the executor.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

from .episode import ROLES, ToolRegistry


class DelegationRefused(ValueError):
    pass


@dataclass(frozen=True)
class DelegationReceipt:
    task_id: str
    from_role: str
    to_role: str
    tools: tuple[str, ...]
    issued_at: int
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "from_role": self.from_role, "to_role": self.to_role,
                "tools": list(self.tools), "issued_at": self.issued_at, "digest": self.digest}

    def verify(self) -> bool:
        return self.digest == _digest(self.task_id, self.from_role, self.to_role, self.tools,
                                      self.issued_at)


def _digest(task_id: str, from_role: str, to_role: str, tools: tuple[str, ...], at: int) -> str:
    body = {"task_id": task_id, "from": from_role, "to": to_role, "tools": list(tools), "at": at}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def delegate(registry: ToolRegistry, task_id: str, from_role: str, to_role: str,
             tools: Iterable[str], issued_at: int) -> DelegationReceipt:
    if from_role not in ROLES or to_role not in ROLES or from_role == to_role:
        raise DelegationRefused("delegation needs two distinct episode roles")
    wanted = tuple(sorted(set(tools)))
    if not wanted:
        raise DelegationRefused("nothing to delegate")
    for name in wanted:
        spec = registry.spec(name)
        if spec is None:
            raise DelegationRefused(f"unknown tool {name!r}")
        if from_role not in spec.roles:
            raise DelegationRefused(f"{from_role} cannot delegate {name!r}: it may not call it")
        if spec.protected:
            raise DelegationRefused(f"{name!r} is protected; effects run only on the executor's grant")
    return DelegationReceipt(task_id, from_role, to_role, wanted, issued_at,
                             _digest(task_id, from_role, to_role, wanted, issued_at))
