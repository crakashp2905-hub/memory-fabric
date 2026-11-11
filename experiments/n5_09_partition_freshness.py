"""Deterministic partition experiment for lease-bounded stale knowledge.

This is a contract experiment, not a network or field measurement. It uses the
real federation, freshness lease book, and action gate with a controllable clock.
"""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import MemoryFabric, offer, propagate_retraction  # noqa: E402
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule  # noqa: E402
from memory_fabric.freshness import LeaseBook, freshness_of, issue_lease  # noqa: E402
from memory_fabric.governance.firewall import (  # noqa: E402
    Firewall,
    rule_capabilities_must_be_granted,
    rule_must_be_active,
    rule_restricted_stays_private,
)

KEY = b"n5-09-partition-key-32-bytes!!"
TTL_MS = 5_000


def _firewall() -> Firewall:
    return Firewall(rules=[rule_must_be_active, rule_restricted_stays_private,
                           rule_capabilities_must_be_granted])


def run_scenario(reconnect_ms: int | None, withdraw: bool = True) -> dict[str, Any]:
    """Run one partition; reconnect_ms=None means no reconnection in the window."""
    now = [1_000_000]
    origin = MemoryFabric(auto_activate=True, clock=lambda: now[0], firewall=_firewall())
    peer = MemoryFabric(auto_activate=True, clock=lambda: now[0], firewall=_firewall())
    try:
        source = origin.remember("origin", "Pump P9 pressure is 9 bar.", scope="federated")
        origin.validate(source, actor="supervisor")
        imported = offer(origin, source, peer, "ops", activate=True).imported_memory_id
        book = LeaseBook({origin.store_id: {"k1": KEY}}, clock_ms=lambda: now[0],
                         monotonic_ms=lambda: now[0], max_clock_skew_ms=0)
        initial = issue_lease(origin, source, TTL_MS / 1000, KEY)
        assert book.accept(initial, received_ms=now[0]) is None
        gate = ActionGate(peer, ActionPolicy(
            tools={"strict": ToolRule("strict", require_fresh=True, min_authority="untrusted"),
                   "lenient": ToolRule("lenient", min_authority="untrusted")},
            grants={"ops": frozenset({"strict", "lenient"})}), leases=book)

        # Validate one stable certificate once per sample, like a disconnected
        # consumer retaining evidence between action attempts.
        def attempt(tool: str) -> bool:
            cert = peer.certify("open-pump", [imported], "ops")
            return gate.authorize(tool, "ops", cert).allowed

        horizon = reconnect_ms if reconnect_ms is not None else 8_000
        sample_ms = list(range(0, horizon + 1, 1_000))
        stale_reads = stale_strict_actions = 0
        strict_denied_while_current = 0
        observations: list[dict[str, Any]] = []
        reconnected = False
        for elapsed in sample_ms:
            now[0] = initial.issued_ms + elapsed
            if withdraw and elapsed >= 2_000 and not reconnected:
                origin.quarantine(source, reason="withdrawn during partition", actor="origin")
            if reconnect_ms is not None and elapsed == reconnect_ms:
                withdrawn_lease = issue_lease(origin, source, TTL_MS / 1000, KEY)
                accepted = book.accept(withdrawn_lease, received_ms=now[0]) is None
                delivered = propagate_retraction(origin, source, [peer], actor="federation")
                reconnected = True
            else:
                accepted = delivered = None

            status = freshness_of(peer, imported, book)
            imported_memory = peer.get(imported)
            exists = imported_memory is not None
            active_for_retrieval = (exists and imported_memory.lifecycle_state.value == "active")
            strict_allowed = attempt("strict")
            lenient_allowed = attempt("lenient")
            is_stale = withdraw and elapsed >= 2_000 and not reconnected
            stale_reads += int(is_stale and active_for_retrieval)
            stale_strict_actions += int(is_stale and strict_allowed)
            strict_denied_while_current += int(not withdraw and elapsed >= TTL_MS and not strict_allowed)
            observations.append({
                "elapsed_ms": elapsed, "lease_status": status,
                "imported_memory_readable": exists,
                "imported_memory_active_for_retrieval": active_for_retrieval,
                "origin_withdrawn": bool(withdraw and elapsed >= 2_000),
                "strict_action_allowed": strict_allowed,
                "lenient_action_allowed": lenient_allowed,
                "reconnection": elapsed == reconnect_ms,
                "withdrawn_lease_accepted": accepted,
                "retraction_delivery": [row.state for row in delivered] if delivered is not None else None,
            })
        stale_window_ms = min(horizon, TTL_MS) - 2_000 if withdraw else 0
        stale_window_ms = max(0, stale_window_ms)
        return {
            "reconnect_ms": reconnect_ms, "origin_withdraws": withdraw,
            "lease_ttl_ms": TTL_MS, "sample_interval_ms": 1_000,
            "stale_knowledge_window_ms": max(0, (reconnect_ms or horizon) - 2_000) if withdraw else 0,
            "stale_strict_action_window_ms": stale_window_ms,
            "stale_read_samples": stale_reads,
            "stale_strict_action_samples": stale_strict_actions,
            "strict_denied_while_origin_current_samples": strict_denied_while_current,
            "reconnected_and_retracted": reconnected and peer.get(imported).lifecycle_state.value == "quarantined",
            "observations": observations,
        }
    finally:
        origin.close()
        peer.close()


def build_report() -> dict[str, Any]:
    scenarios = [run_scenario(4_000), run_scenario(8_000), run_scenario(None),
                 run_scenario(None, withdraw=False)]
    return {
        "schema": "memory-fabric-n5-09-partition-freshness/1",
        "evidence_class": "DETERMINISTIC_CONTRACT_SIMULATION",
        "clock": "shared deterministic millisecond wall and monotonic clock",
        "scenarios": scenarios,
        "conclusion": (
            "Offline stale knowledge is nonzero: a withdrawn import remains readable until "
            "retraction arrives. A valid lease bounds strict stale-action exposure to its "
            "remaining lifetime, but strict actions become unavailable after expiry even "
            "when the origin is still current. Reconnection can deliver a withdrawn lease "
            "and quarantine the import. These results are contract-level, not a claim of "
            "zero stale reads, physical partition behavior, or field availability."
        ),
    }


def write_report() -> dict[str, Any]:
    junit = ROOT / "research" / "results" / "n5-09-partition-tests.xml"
    root = ET.parse(junit).getroot()
    cases = len(list(root.iter("testcase")))
    failures = len(list(root.iter("failure")))
    errors = len(list(root.iter("error")))
    skipped = len(list(root.iter("skipped")))
    if cases < 2 or failures or errors or skipped:
        raise RuntimeError("N5-09 contract tests must pass with no skips")
    source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    report = build_report()
    report.update({
        "task_id": "N5-09", "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {"commit": source,
                   "dirty_before_result_write": bool(subprocess.run(
                       ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                       capture_output=True, text=True).stdout.strip()),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "tests": {"junit": junit.relative_to(ROOT).as_posix(), "test_cases": cases,
                  "failures": failures, "errors": errors, "skipped": skipped},
        "limitations": [
            "This uses real in-process lease, action-gate and retraction code with a deterministic clock; it is not a physical network partition or production availability measurement.",
            "One withdrawn source, one importer, one lease TTL and one-second observation resolution are evaluated; results do not generalize to fleet distributions.",
            "Lenient actions are intentionally shown as an ungated comparison and are not a recommendation for consequential operations.",
        ],
    })
    out = ROOT / "research" / "results" / "n5-09-partition-freshness.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# N5-09 partition freshness contract experiment", "",
             "Deterministic in-process scenarios exercise the real signed lease book, action gate, imported memory and retraction path.", "",
             "| reconnection | origin withdraws | stale knowledge window | strict stale-action window | strict blocks while origin current | retraction delivered |",
             "|---:|:---:|---:|---:|---:|:---:|"]
    for row in report["scenarios"]:
        reconnect = "none (8 s observed)" if row["reconnect_ms"] is None else f"{row['reconnect_ms'] / 1000:g} s"
        lines.append(f"| {reconnect} | {row['origin_withdraws']} | {row['stale_knowledge_window_ms'] / 1000:g} s | "
                     f"{row['stale_strict_action_window_ms'] / 1000:g} s | "
                     f"{row['strict_denied_while_origin_current_samples']} samples | {row['reconnected_and_retracted']} |")
    lines += ["", report["conclusion"], "",
              f"Contract tests: {cases} cases, {failures} failures, {errors} errors, {skipped} skipped. Evidence class: `{report['evidence_class']}`.", "",
              "This is not physical-network or field evidence. Offline stale reads persist until retraction arrives; the lease limits the strict action window while imposing an availability cost after expiry.", ""]
    (ROOT / "research" / "results" / "n5-09-partition-freshness.md").write_text("\n".join(lines), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = write_report()
    out = ROOT / "research" / "results" / "n5-09-partition-freshness.json"
    print(json.dumps({"output": str(out), "scenarios": len(result["scenarios"])}, indent=2))
