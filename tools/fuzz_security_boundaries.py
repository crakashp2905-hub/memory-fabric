"""Bounded deterministic mutation fuzzing for the governed Code Mode boundary.

The parent gives the isolated worker a hard wall-clock timeout. The worker
uses a checked-in corpus, deterministic byte mutations, a 4 KiB input cap,
600-case cap and 64 MiB traced-heap cap. Unexpected exceptions, canary leaks,
or tool-handler execution behind a denying gate fail and save the counterexample.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
import tracemalloc
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "tests/data/security_fuzz_seeds.json"
MALICIOUS = ROOT / "tests/data/code_mode_malicious_plans.json"
REGRESSIONS = ROOT / "tests/data/security_fuzz_regressions.json"
PROGRESS = ROOT / ".test-tmp/security-fuzz-progress.json"
MAX_CASES = 600
MAX_INPUT_BYTES = 4096
MAX_SECONDS = 8.0
MAX_HEAP_BYTES = 64 * 1024 * 1024
PARENT_TIMEOUT_SECONDS = 12

sys.path.insert(0, str(ROOT / "src"))
from memory_fabric.tool_protocol import CodeModePlan, GovernedToolRuntime, ToolProtocolError  # noqa: E402


class DenyGate:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *_args: Any, **_kwargs: Any) -> None:
        self.calls += 1
        raise PermissionError("fuzz action denied")


def sources() -> tuple[int, str, list[str]]:
    seed_data = json.loads(SEEDS.read_text(encoding="utf-8"))
    malicious = json.loads(MALICIOUS.read_text(encoding="utf-8"))
    inputs = [str(source) for source in seed_data["sources"]]
    inputs.extend(str(case["source"]) for case in malicious)
    if REGRESSIONS.exists():
        regression_data = json.loads(REGRESSIONS.read_text(encoding="utf-8"))
        inputs.extend(str(case["source"]) for case in regression_data.get("cases", []))
    return int(seed_data["seed"]), str(seed_data["canary"]), inputs


def mutations(seed: int, originals: list[str]) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    alphabet = "()[]{}=,:.'\"_ abcdef0123\n"
    out: list[tuple[str, str]] = [(f"seed-{i}", text) for i, text in enumerate(originals)]
    for i in range(MAX_CASES - len(out)):
        base_index = rng.randrange(len(originals))
        raw = bytearray(originals[base_index].encode("utf-8"))
        operation = i % 4
        if operation == 0 and raw:
            raw[rng.randrange(len(raw))] = ord(rng.choice(alphabet))
        elif operation == 1 and raw:
            offset = rng.randrange(len(raw))
            del raw[offset:offset + 1]
        elif operation == 2:
            offset = rng.randrange(len(raw) + 1)
            raw[offset:offset] = rng.choice(alphabet).encode("utf-8")
        else:
            raw.extend(rng.choice(alphabet).encode("utf-8"))
        raw = raw[:MAX_INPUT_BYTES]
        out.append((f"mutation-{i}-from-{base_index}", raw.decode("utf-8", errors="replace")))
    return out


def save_regressions(rows: list[dict[str, str]]) -> None:
    if rows:
        prior = json.loads(REGRESSIONS.read_text(encoding="utf-8")) if REGRESSIONS.exists() else {
            "schema": "memory-fabric-security-fuzz-regressions/1", "cases": []}
        known = {row["sha256"] for row in prior["cases"]}
        prior["cases"].extend(row for row in rows if row["sha256"] not in known)
        REGRESSIONS.write_text(json.dumps(prior, indent=2) + "\n", encoding="utf-8")


def worker(report_path: Path) -> int:
    seed, canary, originals = sources()
    cases = mutations(seed, originals)
    gate = DenyGate()
    handler_calls = 0

    def handler(**_kwargs: Any) -> None:
        nonlocal handler_calls
        handler_calls += 1

    runtime = GovernedToolRuntime(gate, {"lookup": handler, "send": handler})  # type: ignore[arg-type]
    findings: list[dict[str, str]] = []
    syntax_warnings = 0
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    tracemalloc.start()
    started = time.perf_counter()
    for case_id, source in cases:
        PROGRESS.write_text(json.dumps({"case_id": case_id,
                                       "source": source[:MAX_INPUT_BYTES]}), encoding="utf-8")
        if len(source.encode("utf-8")) > MAX_INPUT_BYTES:
            findings.append({"case_id": case_id, "kind": "input-bound-exceeded", "source": source})
            continue
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                plan = CodeModePlan.parse(source)
            syntax_warnings += sum(issubclass(item.category, SyntaxWarning) for item in caught)
        except ToolProtocolError as exc:
            if canary in str(exc):
                findings.append({"case_id": case_id, "kind": "canary-disclosure", "source": source})
            continue
        except Exception as exc:  # noqa: BLE001 - unexpected parser failures are fuzz findings
            findings.append({"case_id": case_id, "kind": f"crash:{type(exc).__name__}",
                             "source": source})
            continue
        for call in plan.calls:
            try:
                runtime.execute(call, agent_id="fuzz-agent", session=object())
            except (PermissionError, ToolProtocolError):
                pass
            except Exception as exc:  # noqa: BLE001 - unexpected runtime errors are findings
                findings.append({"case_id": case_id, "kind": f"runtime-crash:{type(exc).__name__}",
                                 "source": source})
        if handler_calls:
            findings.append({"case_id": case_id, "kind": "unauthorized-handler-execution",
                             "source": source})
            break
        if time.perf_counter() - started > MAX_SECONDS:
            findings.append({"case_id": case_id, "kind": "worker-time-budget-exceeded",
                             "source": source})
            break
        _, peak = tracemalloc.get_traced_memory()
        if peak > MAX_HEAP_BYTES:
            findings.append({"case_id": case_id, "kind": "traced-heap-budget-exceeded",
                             "source": source})
            break
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    PROGRESS.unlink(missing_ok=True)
    regression_rows = [{"sha256": hashlib.sha256(row["source"].encode()).hexdigest(),
                        "kind": row["kind"], "source": row["source"]} for row in findings]
    save_regressions(regression_rows)
    input_paths = ["tools/fuzz_security_boundaries.py", "tests/data/security_fuzz_seeds.json",
                   "tests/data/code_mode_malicious_plans.json",
                   "src/memory_fabric/tool_protocol.py"]
    source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout.strip()
    source_dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                       capture_output=True, text=True, check=True).stdout.strip())
    result = {"schema": "memory-fabric-security-fuzz/1", "seed": seed,
              "source_commit": source_commit, "source_worktree_dirty": source_dirty,
              "input_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                               for name in input_paths},
              "cases": len(cases), "elapsed_seconds": round(elapsed, 4),
              "peak_traced_heap_bytes": peak,
              "limits": {"wall_seconds": MAX_SECONDS, "parent_timeout_seconds": PARENT_TIMEOUT_SECONDS,
                         "traced_heap_bytes": MAX_HEAP_BYTES, "input_bytes": MAX_INPUT_BYTES,
                         "cases": MAX_CASES},
              "action_gate_denials": gate.calls, "tool_handler_calls": handler_calls,
              "syntax_warnings": syntax_warnings,
              "findings": [{"case_id": r["case_id"], "kind": r["kind"],
                            "sha256": hashlib.sha256(r["source"].encode()).hexdigest()}
                           for r in findings],
              "regression_fixtures_written": len(regression_rows), "passed": not findings}
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if not findings else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "research/results/h5-07-security-fuzz.json")
    args = parser.parse_args()
    if args.worker:
        return worker(args.report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--report", str(args.report.resolve())]
    try:
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                             timeout=PARENT_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        current = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {}
        source = str(current.get("source", ""))
        rows = ([{"sha256": hashlib.sha256(source.encode()).hexdigest(),
                  "kind": "worker-timeout", "source": source}] if source else [])
        save_regressions(rows)
        args.report.write_text(json.dumps({"schema": "memory-fabric-security-fuzz/1",
                                           "passed": False, "findings": [{
                                               "case_id": current.get("case_id"),
                                               "kind": "worker-timeout"}],
                                           "regression_fixtures_written": len(rows)}, indent=2)
                               + "\n", encoding="utf-8")
        return 1
    if run.stdout:
        print(run.stdout, end="")
    if run.stderr:
        print(run.stderr, end="", file=sys.stderr)
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
