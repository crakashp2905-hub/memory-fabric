"""Opt-in, bounded per-request stage timings for local qualification."""

from __future__ import annotations

__stability__ = "beta"

import threading
import time
from dataclasses import dataclass, field
from typing import Callable


STAGES = (
    "body_decode",
    "auth",
    "event_append",
    "projection",
    "copy_lookup",
    "serialization",
    "transport",
    "dispatch_other",
)


class ProfileRecorder:
    """Thread-safe aggregate counters for one benchmark interval."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._totals: dict[str, int] = {}
        self._counts: dict[str, int] = {}

    def add(self, name: str, value: int) -> None:
        with self._lock:
            self._totals[name] = self._totals.get(name, 0) + int(value)
            self._counts[name] = self._counts.get(name, 0) + 1

    def reset(self) -> None:
        with self._lock:
            self._totals.clear()
            self._counts.clear()

    def snapshot(self) -> dict[str, dict[str, int]]:
        with self._lock:
            return {name: {"total": total, "count": self._counts[name]}
                    for name, total in self._totals.items()}


@dataclass(frozen=True)
class StageTrace:
    request_id: str
    operation: str
    stages_ns: dict[str, int]
    total_ns: int

    def validate(self) -> tuple[str, ...]:
        issues: list[str] = []
        if set(self.stages_ns) != set(STAGES):
            issues.append("stage set is incomplete or contains unknown stages")
        if any(type(value) is not int or value < 0 for value in self.stages_ns.values()):
            issues.append("stage durations must be non-negative integers")
        if type(self.total_ns) is not int or self.total_ns < 0:
            issues.append("total duration must be a non-negative integer")
        elif sum(self.stages_ns.values()) > self.total_ns + 2_000_000:
            issues.append("stage durations do not reconcile to total within 2 ms")
        return tuple(issues)

    def to_json(self) -> dict[str, object]:
        return {"request_id": self.request_id, "operation": self.operation,
                "stages_ns": dict(self.stages_ns), "total_ns": self.total_ns,
                "reconciliation_error_ns": sum(self.stages_ns.values()) - self.total_ns,
                "valid": not self.validate(), "issues": list(self.validate())}


@dataclass
class StageTraceRecorder:
    """Thread-safe ring buffer. Traces contain timing metadata only."""

    capacity: int = 10_000
    clock_ns: Callable[[], int] = time.perf_counter_ns
    _rows: list[StageTrace] = field(default_factory=list, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError("capacity must be positive")

    def add(self, trace: StageTrace) -> None:
        with self._lock:
            self._rows.append(trace)
            if len(self._rows) > self.capacity:
                del self._rows[:len(self._rows) - self.capacity]

    def snapshot(self) -> tuple[StageTrace, ...]:
        with self._lock:
            return tuple(self._rows)


class RequestStages:
    def __init__(self, recorder: StageTraceRecorder, request_id: str,
                 operation: str) -> None:
        self.recorder = recorder
        self.request_id = request_id
        self.operation = operation
        self.started = recorder.clock_ns()
        self.last = self.started
        self.values = {name: 0 for name in STAGES}

    def mark(self, stage: str) -> None:
        now = self.recorder.clock_ns()
        if stage not in self.values:
            stage = "dispatch_other"
        self.values[stage] += max(0, now - self.last)
        self.last = now

    def finish_elapsed(self, elapsed_ns: int) -> StageTrace:
        elapsed_ns = max(0, int(elapsed_ns))
        remainder = elapsed_ns - sum(self.values.values())
        self.values["dispatch_other"] = max(0, self.values["dispatch_other"] + remainder)
        trace = StageTrace(self.request_id, self.operation, dict(self.values), elapsed_ns)
        self.recorder.add(trace)
        return trace

    def finish(self) -> StageTrace:
        now = self.recorder.clock_ns()
        self.mark("transport")
        return self.finish_elapsed(now - self.started)
