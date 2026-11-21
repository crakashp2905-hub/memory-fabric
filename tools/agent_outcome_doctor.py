#!/usr/bin/env python3
"""What can this checkout run, and what is missing? (W20-10)

    python tools/agent_outcome_doctor.py [--model qwen2.5:1.5b] [--host URL] [--json]

Read-only and offline. It reports the runtime (Python, package and schema
versions), which outcome runtime is canonical and which are deprecated, what
each role can see and call, whether recovery is on by default, whether a local
model is available (loopback only, nothing downloaded), the task ledger
totals, and whether the newest end-to-end gate record is for this commit. It
never imports a legacy package, so it raises no deprecation warning, and it
always exits 0: it diagnoses, it does not gate.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

SCHEMA_ID = "memory-fabric.agent-outcome-doctor.v1"
LEGACY = ("agent_outcomes", "outcome_protocol")
GATE_RECORDS = ROOT / "research" / "results" / "agent-outcomes" / "candidate-offline"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _head() -> str | None:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def _legacy_status(name: str) -> dict[str, Any]:
    # Read the marker from source; importing would emit the DeprecationWarning.
    path = ROOT / "src" / "memory_fabric" / name / "__init__.py"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {"present": path.is_file(), "deprecated": "__deprecated__" in text}


def diagnose(model: str | None = None, host: str | None = None) -> dict[str, Any]:
    import memory_fabric
    from memory_fabric.outcome_typed.episode import ROLES, EpisodeRunner, default_tools

    tools = default_tools()
    visibility = {role: sorted(name for name in tools._specs  # noqa: SLF001 - read-only
                               if role in tools._specs[name].roles)  # noqa: SLF001
                  for role in ROLES}
    recovery_default = inspect.signature(EpisodeRunner.__init__).parameters[
        "recovery_enabled"].default
    report: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "package_version": memory_fabric.__version__,
                    "schema_version": memory_fabric.SCHEMA_VERSION, "commit": _head()},
        "outcome_runtime": {"canonical": "memory_fabric.outcome_typed",
                            "legacy": {name: _legacy_status(name) for name in LEGACY}},
        "agent_visibility": {"roles": list(ROLES), "tools_by_role": visibility,
                             "observation": "canonical AgentObservation only; evaluator "
                                            "fields are refused"},
        "recovery": {"enabled_by_default": recovery_default},
    }
    if model:
        preflight = _load("_doctor_preflight", ROOT / "tools" / "model_preflight.py")
        kwargs = {"host": host} if host else {}
        try:
            result = preflight.preflight(required=[model], **kwargs)
        except Exception as exc:  # noqa: BLE001 - e.g. a non-loopback host
            result = {"status": "REFUSED", "reason": str(exc)}
        from benchmarks.fake_local_model import is_fake

        models = result.get("models") or []
        report["local_model"] = {
            "requested": model, "status": result.get("status"), "reason": result.get("reason"),
            "runtime_version": result.get("runtime_version"),
            "fake": any(is_fake(result.get("runtime_version"), m.get("digest")) for m in models),
            "download_attempted": False,
        }
    else:
        report["local_model"] = {"requested": None, "status": "NOT_CHECKED",
                                 "reason": "pass --model NAME to run the loopback preflight"}
    ledger_tool = _load("_doctor_ledger", ROOT / "tools" / "checklist_ledger.py")
    try:
        totals = ledger_tool.summary(ledger_tool.load(), ledger_tool.parse_spec())
        report["ledger"] = {"total": totals["total"], "by_status": totals["by_status"]}
    except Exception as exc:  # noqa: BLE001 - a diagnosis never fails on one source
        report["ledger"] = {"error": f"{type(exc).__name__}: {exc}"}
    records = sorted(GATE_RECORDS.glob("*/report.json")) if GATE_RECORDS.is_dir() else []
    gates = []
    for path in records:
        data = json.loads(path.read_text(encoding="utf-8"))
        gates.append({"record": str(path.relative_to(ROOT)).replace("\\", "/"),
                      "commit": data.get("candidate_commit_sha"), "status": data.get("status")})
    head = report["runtime"]["commit"]
    report["end_to_end_gate"] = {
        "records": gates,
        "at_head": any(g["commit"] == head for g in gates),
        "hint": "run python tools/agent_outcome_end_to_end_gate.py --offline --all --out DIR "
                "to qualify this commit",
    }
    return report


def render(report: dict[str, Any]) -> str:
    runtime, model = report["runtime"], report["local_model"]
    legacy = ", ".join(f"{name} ({'deprecated' if info['deprecated'] else 'ACTIVE'})"
                       for name, info in report["outcome_runtime"]["legacy"].items())
    lines = [
        f"runtime   python {runtime['python']} | memory-fabric {runtime['package_version']} "
        f"(schema {runtime['schema_version']}) | commit {runtime['commit']}",
        f"outcomes  canonical {report['outcome_runtime']['canonical']}; legacy: {legacy}",
        "agents    " + "; ".join(f"{role}: {', '.join(tools)}" for role, tools
                                 in report["agent_visibility"]["tools_by_role"].items()),
        f"recovery  enabled by default: {report['recovery']['enabled_by_default']}",
        f"model     {model['status']}" + (f" ({model['reason']})" if model.get("reason") else "")
        + (" [FAKE server: not inference]" if model.get("fake") else ""),
    ]
    ledger = report["ledger"]
    if "by_status" in ledger:
        nonzero = {k: v for k, v in ledger["by_status"].items() if v}
        lines.append(f"ledger    {ledger['total']} tasks: {nonzero}")
    else:
        lines.append(f"ledger    {ledger.get('error')}")
    gate = report["end_to_end_gate"]
    lines.append(f"gate      {len(gate['records'])} record(s); this commit qualified: "
                 f"{gate['at_head']}" + ("" if gate["at_head"] else f" ({gate['hint']})"))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model")
    parser.add_argument("--host")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = diagnose(args.model, args.host)
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n" if args.json
                     else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
