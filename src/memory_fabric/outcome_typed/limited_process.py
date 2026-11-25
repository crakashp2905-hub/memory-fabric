"""Run a model or replay subprocess under hard OS limits, or refuse (VEGA next W13-06).

:func:`run_limited` starts a command with ``RLIMIT_CPU``, ``RLIMIT_AS`` and ``RLIMIT_NPROC``
set in the child before it executes, plus a wall-clock timeout. Where the platform has no
``resource`` module (Windows) or refuses a limit, it does **not** run the command: it
returns ``UNSUPPORTED_PLATFORM`` naming the missing limit, so an unbounded process is never
the silent fallback.

The superuser ignores ``RLIMIT_NPROC``, so a child started by root drops to the unprivileged
``nobody`` identity (uid/gid 65534) before exec; if that is refused the command is not run
(freeze plan F09-02: a fork bomb is contained, not merely discouraged).
"""

from __future__ import annotations

__stability__ = "experimental"

import importlib
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence

UNPRIVILEGED = 65534


@dataclass(frozen=True)
class LimitedResult:
    status: str  # OK | NONZERO_EXIT | TIMEOUT | LIMIT_EXCEEDED | UNSUPPORTED_PLATFORM
    returncode: int | None
    stdout: str
    stderr: str
    limits: dict[str, Any]


def _resource() -> Any:
    try:
        return importlib.import_module("resource")
    except ImportError:
        return None


def supported() -> list[str]:
    res = _resource()
    if res is None:
        return []
    return [n for n in ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_NPROC") if hasattr(res, n)]


def run_limited(argv: Sequence[str], *, cpu_seconds: int, memory_bytes: int, max_processes: int = 64,
                timeout_seconds: float = 60.0, stdin: str | None = None) -> LimitedResult:
    limits = {"cpu_seconds": cpu_seconds, "memory_bytes": memory_bytes, "max_processes": max_processes,
              "timeout_seconds": timeout_seconds}
    have = supported()
    missing = [n for n in ("RLIMIT_CPU", "RLIMIT_AS") if n not in have]
    if missing:
        return LimitedResult("UNSUPPORTED_PLATFORM", None, "", f"missing {missing}; not run", limits)
    res = _resource()

    def apply() -> None:  # runs in the child, before exec
        res.setrlimit(res.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        res.setrlimit(res.RLIMIT_AS, (memory_bytes, memory_bytes))
        if "RLIMIT_NPROC" in have:
            soft, hard = res.getrlimit(res.RLIMIT_NPROC)
            cap = max_processes if hard == res.RLIM_INFINITY else min(max_processes, hard)
            res.setrlimit(res.RLIMIT_NPROC, (cap, cap))
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                os.setgroups([]) if hasattr(os, "setgroups") else None
                os.setgid(UNPRIVILEGED)
                os.setuid(UNPRIVILEGED)

    try:
        done = subprocess.run(list(argv), input=stdin, capture_output=True, text=True, timeout=timeout_seconds,
                              preexec_fn=apply)  # noqa: PLW1509 - limits must be set before exec
    except subprocess.TimeoutExpired as exc:
        return LimitedResult("TIMEOUT", None, str(exc.stdout or ""), str(exc.stderr or ""), limits)
    except subprocess.SubprocessError:
        # setrlimit raised in the child before exec (macOS refuses some RLIMIT_AS values):
        # the command never ran, and it is not run without the limit.
        return LimitedResult("UNSUPPORTED_PLATFORM", None, "", "the platform refused a limit; not run", limits)
    if done.returncode < 0 or "MemoryError" in done.stderr:
        return LimitedResult("LIMIT_EXCEEDED", done.returncode, done.stdout, done.stderr, limits)
    return LimitedResult("OK" if done.returncode == 0 else "NONZERO_EXIT", done.returncode, done.stdout,
                         done.stderr, limits)
