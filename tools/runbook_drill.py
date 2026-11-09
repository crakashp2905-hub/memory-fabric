"""Run safe local incident drills; no network or external effects are used."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
import importlib.util
from pathlib import Path
from typing import Any

from memory_fabric import LifecycleState, MemoryFabric

ROOT = Path(__file__).resolve().parents[1]
DRILLS = {
    "outage": "tests.test_federation_transport.TestOfflineRecipient.test_an_offline_recipient_stays_pending_and_visible",
    "key-loss": "tests.test_cipher.KeyCustody.test_a_lost_key_store_is_an_error_not_an_erasure",
    "corrupt-db": "tests.test_doctor.DoctorTests.test_the_event_chain_detects_a_tamper",
}


def run_unit_drill(name: str, selector: str) -> dict[str, Any]:
    temp_root = ROOT / ".task-tmp"
    temp_root.mkdir(exist_ok=True)
    tempfile.tempdir = str(temp_root)
    os.environ["TEMP"] = str(temp_root)
    os.environ["TMP"] = str(temp_root)
    module_name, class_name, method_name = selector.rsplit(".", 2)
    test_path = ROOT / (module_name.replace(".", "/") + ".py")
    spec = importlib.util.spec_from_file_location(f"_drill_{name}", test_path)
    if spec is None or spec.loader is None:
        return {"name": name, "selector": selector, "tests": 0, "passed": False,
                "error": f"cannot load test module at {test_path}"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case = getattr(module, class_name)
    suite = unittest.TestSuite([case(method_name)])
    if suite.countTestCases() != 1:
        return {"name": name, "selector": selector, "tests": suite.countTestCases(),
                "passed": False, "error": "drill selector must resolve to one test"}
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
    return {"name": name, "selector": selector, "tests": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors),
            "passed": result.wasSuccessful(), "output": output.getvalue()}


def run_mass_retraction(*, descendants: int = 100) -> dict[str, Any]:
    fabric = MemoryFabric(":memory:", seed=0, auto_activate=True, encrypt_content=False)
    try:
        root = fabric.remember("drill", "Root source is verified for the drill.", scope="team")
        child_ids = [fabric.derive("drill", f"Derived procedure number {index}.",
                                   parents=[root], scope="team")
                     for index in range(descendants)]
        affected = fabric.quarantine(root, reason="runbook mass-retraction drill")
        all_contested = all(fabric.get(memory_id).lifecycle_state is LifecycleState.CONTESTED
                            for memory_id in child_ids)
        if len(affected) != descendants or not all_contested:
            raise AssertionError(f"expected {descendants} contested descendants, observed {len(affected)}")
        return {"name": "mass-retraction", "descendants_created": descendants,
                "descendants_contested": len(affected), "unrelated_effects": 0,
                "passed": True}
    finally:
        fabric.close()


def run_drill(name: str) -> dict[str, Any]:
    if name == "mass-retraction":
        return run_mass_retraction()
    return run_unit_drill(name, DRILLS[name])


def build_report(selected: str = "all") -> dict[str, Any]:
    names = list(DRILLS) + ["mass-retraction"] if selected == "all" else [selected]
    results = [run_drill(name) for name in names]
    return {"schema": "memory-fabric-runbook-drill/1", "scope": "local deterministic drills",
            "results": results, "passed": all(row["passed"] for row in results),
            "limitations": ["Outage uses an in-process simulated offline peer, not a real network partition.",
                            "Database corruption is a local chain-tampering fixture, not arbitrary disk damage.",
                            "Mass retraction uses an in-memory 100-descendant fixture; no remote stores are contacted."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drill", choices=("all", *DRILLS, "mass-retraction"), default="all")
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/p3-10-runbook-drills.json")
    args = parser.parse_args()
    report = build_report(args.drill)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "passed": report["passed"],
                      "drills": {row["name"]: row["passed"] for row in report["results"]}}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
