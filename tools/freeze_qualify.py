"""Run the release qualification on the exact candidate and write ``qualification/`` (freeze plan).

    python tools/freeze_qualify.py --all                   # every gate
    python tools/freeze_qualify.py --gate core --gate cdm  # selected gates
    python tools/freeze_qualify.py --release               # recompute gates/release.json only

Every gate record carries ``source_sha``, the commands with their exit status, environment,
seeds or task set, model identity where a model ran, timestamps, a summary, limitations and the
reviewer. Failures are kept as records, never dropped. The release record combines the gates
under the plan's decision hierarchy: a component is ``CANDIDATE_GO`` only if every requirement
it names passed; otherwise it is ``HOLD``, ``OFF``, ``SHADOW`` or ``ADVISORY_ONLY`` as the plan
says, and the whole product is never GO while any applicable component is not.

This tool runs existing checks; it adds no product behaviour.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "qualification"
LOGS = QUAL / "logs"
PY = sys.executable
# The lint/type step can run under a different interpreter (for example a venv whose mypy
# does not see an incompatible system numpy); the record names the interpreter used.
CHECK_PY = os.environ.get("FREEZE_CHECK_PYTHON", PY)
REVIEWER = "self-review by the implementing agent; not independent (freeze plan F09-08, F14-01)"

CORE_TESTS = ["tests/test_cross_tenant_surface_matrix.py", "tests/test_enforcement_tenant.py",
              "tests/test_effect_transport_parity.py", "tests/test_action_fence_typed.py",
              "tests/test_action_crash_typed.py", "tests/test_action_crash.py", "tests/test_correction.py",
              "tests/test_erasure.py", "tests/test_erasure_residue.py", "tests/test_erasure_key_destroy.py",
              "tests/test_memory_fabric_migration.py", "tests/test_key_migration.py",
              "tests/test_sensor_entity_claims.py", "tests/test_semantic_quantities.py",
              "tests/test_omission_safety.py", "tests/test_semantic_verification.py",
              "tests/test_n6_08_code_mode_effect_authorization.py"]
SECURITY_TESTS = ["tests/test_vega_next_security.py", "tests/test_vega_cdm_security.py",
                  "tests/test_new_module_redaction.py", "tests/test_personal_data_redaction.py",
                  "tests/test_agent_security_fixtures.py"]
OPERATIONS_TESTS = ["tests/test_backup.py", "tests/test_backup_custody.py", "tests/test_backup_restore_qualification.py",
                    "tests/test_restore_erasure_reconciliation.py", "tests/test_multiprocess_crash.py",
                    "tests/test_vega_recovery.py"]
FEDERATION_TESTS = ["tests/test_federation.py", "tests/test_federation_transport.py", "tests/test_privacy_federation.py"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(name: str, argv: list[str], timeout: int = 3600) -> dict[str, Any]:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{name}.log"
    started = time.monotonic()
    try:
        done = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "PYTHONHASHSEED": "0"})
        code, text = done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired as exc:
        code, text = None, f"TIMEOUT after {timeout}s\n{exc.stdout or ''}"
    log.write_text(text[-200_000:], encoding="utf-8")
    tail = [ln for ln in text.splitlines() if ln.strip()][-3:]
    return {"name": name, "command": " ".join("python" if a == PY else a for a in argv), "exit_status": code,
            "seconds": round(time.monotonic() - started, 1), "log": log.relative_to(ROOT).as_posix(),
            "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(), "tail": tail}


def pytest(name: str, targets: list[str]) -> dict[str, Any]:
    return run(name, [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets])


def environment() -> dict[str, Any]:
    return {"python": platform.python_version(), "platform": platform.platform(), "cpus": os.cpu_count(),
            "machine": platform.machine()}


def record(gate: str, steps: list[dict[str, Any]], summary: dict[str, Any], limitations: list[str],
           extra: dict[str, Any] | None = None) -> dict[str, Any]:
    rec = {"schema_id": "memory-fabric.freeze-gate.v1", "gate": gate, "source_sha": git("rev-parse", "HEAD"),
           "source_dirty": bool(git("status", "--porcelain")), "timestamp": now(), "environment": environment(),
           "steps": steps, "all_steps_exited_zero": all(s["exit_status"] == 0 for s in steps),
           "summary": summary, "limitations": limitations, "reviewer": REVIEWER, **(extra or {})}
    (QUAL / "gates").mkdir(parents=True, exist_ok=True)
    (QUAL / "gates" / f"{gate}.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return rec


def _json(rel: str) -> Any:
    path = ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def gate_core() -> dict[str, Any]:
    steps = [pytest("core-governance", CORE_TESTS), pytest("core-federation", FEDERATION_TESTS),
             run("core-check", [CHECK_PY, "tools/check.py"], timeout=1800)]
    ci = _json("qualification/ci-audit.json")
    head = git("rev-parse", "HEAD")
    return record("core", steps, {
        "tenant_effect_correction_erasure_migration_identity": steps[0]["exit_status"] == 0,
        "federation": steps[1]["exit_status"] == 0, "lint_types_docs": steps[2]["exit_status"] == 0,
        "exact_sha_ci": "PASS" if ci and ci.get("head_sha") == head and ci["counts"].get("PASS") == ci.get("total_jobs")
        else "NOT_AT_THIS_SHA"}, [
        "staging-host and physical multi-host gates have not run (no staging host available)",
        "exact-SHA CI is audited after the candidate is pushed; an audit for another SHA does not count"])


def gate_vega() -> dict[str, Any]:
    steps = [run("vega-next-gate", [PY, "tools/vega_next_gate.py", "--vega-url", "http://127.0.0.1:8011",
                                    "--out", "qualification/vega-next"], timeout=3600),
             run("vega-v2-registration", [PY, "-m", "benchmarks.vega_next_confirmatory", "validate",
                                          "research/prereg/vega-cdm-v2.json"]),
             run("freeze-ladder", [PY, "-m", "benchmarks.freeze_ladder", "--check"])]
    matrix = _json("qualification/vega-next/matrix.json") or {}
    calib = _json("research/results/vega-cdm/next/calibration/vega-0.8b.json") or {}
    specificity = _json("research/results/vega-cdm/freeze/specificity/diagnosis.json")
    summary = {"model_smoke": matrix.get("vega_model_smoke"), "numeric_identity_safety": matrix.get(
        "numeric_and_identity_safety"), "governance_parity": matrix.get("governance_parity"),
        "v2_registration_refused": steps[1]["exit_status"] == 2,
        "calibration_modes": {q: (calib.get(q) or {}).get("calibrated_threshold", {}).get("pilot_transfer", {})
                              .get("mode") for q in ("hot", "doubt", "cleared")},
        "specificity_diagnosis": (specificity or {}).get("verdict"),
        "ladder_intact": steps[2]["exit_status"] == 0}
    return record("vega", steps, summary, [
        "the v2 confirmatory study is refused as not specific; no holdout was read",
        "the hot (numeric) question is never used: numbers come from the deterministic extractor",
        "latency and RSS measured on a 4-CPU Linux container only"], {"model": matrix.get("model")})


def gate_cdm() -> dict[str, Any]:
    steps = [run("cdm-offline-gate", [PY, "tools/cdm_offline_gate.py", "--all", "--out", "qualification/cdm-offline"],
                 timeout=3600),
             run("cdm-scripted-value", [PY, "-m", "benchmarks.vega_next_cdm_value", "--seeds", "40", "--out",
                                        "qualification/cdm-scripted.json"]),
             pytest("cdm-contracts", ["tests/test_causal_graph_constraints.py", "tests/test_semantic_pipeline.py",
                                      "tests/test_cdm_correction_utility.py", "tests/test_cdm_correction_comparison.py"])]
    value = _json("qualification/cdm-scripted.json") or {}
    return record("cdm", steps, {"offline_gate": steps[0]["exit_status"] == 0,
                                 "scripted_verdict": value.get("verdict"),
                                 "strongest_fair_comparator": value.get("strongest_fair_comparator")}, [
        "net utility is measured on scripted deterministic worlds only; no learned-agent CDM study",
        "CDM replays recorded deterministic decisions; it does not establish real-world causality"])


def gate_agents(local_model: str | None) -> dict[str, Any]:
    argv = [PY, "tools/agent_outcome_end_to_end_gate.py", "--offline", "--all", "--out", "qualification/agents"]
    if local_model:
        argv += ["--local-model", local_model]
    steps = [run("agent-outcome-gate", argv, timeout=7200)]
    pilot = _json("research/results/vega-cdm/next/agents/model-agents-pilot.json") or {}
    return record("agents", steps, {"end_to_end_gate": steps[0]["exit_status"] == 0,
                                    "planner_pilot_summary": pilot.get("summary")}, [
        "the 1.5B planner proposes no_action on most hot packs; the guard escalates them",
        "no independent safety assessment of the learned-agent workflow"])


def gate_security() -> dict[str, Any]:
    steps = [pytest("security-tests", SECURITY_TESTS),
             run("secret-scan", [PY, "tools/secret_scan.py"]) if (ROOT / "tools/secret_scan.py").is_file()
             else run("model-attack-check", [PY, "tools/model_attack_check.py"])]
    return record("security", steps, {"internal_tests": steps[0]["exit_status"] == 0,
                                      "independent_review": "BLOCKED_EXTERNAL"}, [
        "no independent threat assessment exists; internal self-review cannot close F09-08"])


def gate_performance() -> dict[str, Any]:
    steps = [run("perf", [PY, "tools/vega_next_perf.py", "--out", "qualification/perf.json"], timeout=3600)]
    return record("performance", steps, {"measured_host": environment(), "record": "qualification/perf.json"}, [
        "only this Linux container was measured; no 16 GB Apple Silicon or staging host"])


def gate_operations() -> dict[str, Any]:
    steps = [pytest("operations-tests", OPERATIONS_TESTS),
             run("vega-killswitch", [PY, "tools/vega_killswitch.py", "--verify"])]
    return record("operations", steps, {"backup_restore_crash_recovery": steps[0]["exit_status"] == 0,
                                        "kill_switch_drill": steps[1]["exit_status"] == 0}, [
        "drills ran against disposable local stores, not a production deployment"])


FROZEN_FILES = {"world generator and grader": "benchmarks/vega_next_worlds.py",
                "arms, deterministic rules and metrics": "benchmarks/vega_next_arms.py",
                "planner harness and system prompt": "benchmarks/vega_next_model_agents.py",
                "calibration study": "benchmarks/vega_calibration_study.py",
                "registration validator and analysis": "benchmarks/vega_next_confirmatory.py",
                "CDM value study": "benchmarks/vega_next_cdm_value.py",
                "omission guard": "src/memory_fabric/outcome_typed/omission.py",
                "threshold ladder": "research/prereg/freeze-threshold-ladder.json",
                "v2 registration (refused)": "research/prereg/vega-cdm-v2.json"}


def freeze_inputs() -> dict[str, Any]:
    """Digests of everything a qualification result depends on (F01-08)."""
    sys.path.insert(0, str(ROOT))
    from benchmarks import vega_next_arms, vega_next_model_agents

    ladder = _json("research/prereg/freeze-threshold-ladder.json")
    files = {k: {"path": v, "sha256": hashlib.sha256((ROOT / v).read_bytes()).hexdigest()}
             for k, v in FROZEN_FILES.items()}
    vega = (_json("research/results/vega-cdm/next/development/vega-0.8b-pilot.json") or {}).get("model") or {}
    planner = (_json("research/results/vega-cdm/next/agents/model-agents-pilot.json") or {}).get("agent_model") or {}
    tags = [{"name": t.get("name"), "digest": t.get("digest")} for t in planner.get("tags", [])]
    return {"schema_id": "memory-fabric.freeze-inputs.v1", "source_sha": git("rev-parse", "HEAD"),
            "files": files, "system_prompt_sha256": hashlib.sha256(
                vega_next_model_agents.SYSTEM.encode()).hexdigest(),
            "metrics": list(vega_next_arms.METRICS), "ladder_digest": (ladder or {}).get("digest"),
            "seed_partitions": {m: {s: r["population"] for s, r in spec["stages"].items()}
                                for m, spec in (ladder or {}).get("metrics", {}).items()},
            "models": {"vega": {k: vega.get(k) for k in ("engine_sha256", "reader", "revision", "vegaml")
                                if k in vega} or vega, "planner": tags},
            "holdout_policy": "the holdout split is read only by `benchmarks.vega_next_confirmatory run` on a "
                              "frozen registration; no committed result contains a holdout row "
                              "(tests/test_freeze_release.py::Holdout)"}


def component_verdicts() -> dict[str, Any]:
    g = {name: _json(f"qualification/gates/{name}.json") for name in
         ("core", "vega", "cdm", "agents", "security", "performance", "operations")}
    ok = {k: bool(v and v.get("all_steps_exited_zero")) for k, v in g.items()}
    head = git("rev-parse", "HEAD")
    stale = sorted(k for k, v in g.items() if v and v.get("source_sha") != head)
    external = "BLOCKED_EXTERNAL: no independent security review, staging host or supervised pilot"
    core_ci = (g["core"] or {}).get("summary", {}).get("exact_sha_ci") == "PASS"
    verdicts = {
        "CORE": "HOLD" if not (ok["core"] and ok["security"] and ok["operations"] and core_ci) else
        "HOLD: engineering gates pass; staging and independent review are " + external,
        "VEGA": "SHADOW: advisory serving only; autonomous influence is HOLD (not specific vs placebo)",
        "CDM": "ADVISORY_ONLY: deterministic replay qualified offline; automatic repair is HOLD (no held-out "
               "learned-agent utility)" if ok["cdm"] else "HOLD",
        "MODEL_AGENT": "OFF / supervised only: no independent safety assessment; planner completion is low",
        "FEDERATION": "HOLD: partition and physical multi-host measurements have not run",
        "WHOLE_PRODUCT": "NO_GO for 1.0: " + external}
    return {"schema_id": "memory-fabric.freeze-release.v1", "source_sha": head, "timestamp": now(),
            "gates_passed": ok, "gates_at_other_sha": stale, "components": verdicts,
            "release_label": "bounded beta: core governance with Vega SHADOW and CDM ADVISORY_ONLY",
            "signoff": {"release_manager": None, "security_reviewer": None, "qualification_owner": None}}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--all", action="store_true")
    p.add_argument("--gate", action="append", default=[])
    p.add_argument("--release", action="store_true")
    p.add_argument("--local-model")
    p.add_argument("--freeze-inputs", action="store_true")
    args = p.parse_args(argv)
    if args.freeze_inputs:
        QUAL.mkdir(exist_ok=True)
        (QUAL / "frozen-inputs.json").write_text(json.dumps(freeze_inputs(), indent=1, sort_keys=True) + "\n",
                                                 encoding="utf-8")
    gates = ["core", "vega", "cdm", "agents", "security", "performance", "operations"] if args.all else args.gate
    runners = {"core": gate_core, "vega": gate_vega, "cdm": gate_cdm, "agents": lambda: gate_agents(args.local_model),
               "security": gate_security, "performance": gate_performance, "operations": gate_operations}
    for name in gates:
        rec = runners[name]()
        print(json.dumps({"gate": name, "all_steps_exited_zero": rec["all_steps_exited_zero"],
                          "summary": rec["summary"]}, default=str)[:600])
    head = git("rev-parse", "HEAD")
    candidate = {"schema_id": "memory-fabric.freeze-candidate.v1", "source_sha": head,
                 "tree": git("rev-parse", "HEAD^{tree}"), "dirty": bool(git("status", "--porcelain")),
                 "version": next((ln.split('"')[1] for ln in (ROOT / "pyproject.toml").read_text().splitlines()
                                  if ln.startswith("version")), None), "environment": environment(),
                 "timestamp": now()}
    QUAL.mkdir(exist_ok=True)
    (QUAL / "candidate.json").write_text(json.dumps(candidate, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.release or args.all or gates:
        rel = component_verdicts()
        (QUAL / "gates" / "release.json").write_text(json.dumps(rel, indent=1, sort_keys=True) + "\n",
                                                     encoding="utf-8")
        print(json.dumps(rel["components"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
