"""E4-07: three logical hosts in separate localhost processes and stores.

The origin shares one memory over authenticated federation HTTP, then issues a
correction while host B is offline. The outbox must report B as pending, keep A's
acknowledgement, retry after B restarts, and finish with both recipient stores
quarantined and both acknowledgements accounted for.

This is a local multi-process test, not a physical multi-host or network
partition claim. Run with:

    python -m experiments.e4_three_hosts
"""
from __future__ import annotations

import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ("origin", "recipient-a", "recipient-b")


def _fixture_firewall():
    from memory_fabric.governance.firewall import (
        Firewall, rule_capabilities_must_be_granted, rule_must_be_active,
        rule_restricted_stays_private,
    )
    return Firewall(rules=(rule_restricted_stays_private, rule_must_be_active,
                           rule_capabilities_must_be_granted))


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _env() -> dict[str, str]:
    env = os.environ.copy()
    source = str(ROOT / "src")
    env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _node(path: str, peers_path: str, port: int) -> int:
    from memory_fabric import MemoryFabric
    from memory_fabric.manager import load_peers
    from memory_fabric.transport import build_federation_server

    fabric = MemoryFabric(path, busy_timeout_ms=30_000,
                          firewall=_fixture_firewall())
    server = build_federation_server(fabric, load_peers(peers_path), "127.0.0.1", port)
    print(f"READY {fabric.store_id} {port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        fabric.close()
    return 0


def _start(path: Path, peers: Path, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "experiments.e4_three_hosts", "--node",
         str(path), str(peers), str(port)],
        cwd=ROOT, env=_env(), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _wait_ready(process: subprocess.Popen[str], port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/federation/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output, _ = process.communicate(timeout=1)
            raise RuntimeError(f"federation host exited {process.returncode}: {output[-1200:]}")
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except Exception:  # noqa: BLE001 - polling server startup
            time.sleep(0.1)
    process.terminate()
    raise TimeoutError(f"federation host on port {port} did not become ready")


def _stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run() -> dict[str, Any]:
    from memory_fabric import LifecycleState, MemoryFabric
    from memory_fabric.dispatcher import Dispatcher
    from memory_fabric.federation import prepare_offer
    from memory_fabric.manager import load_peers
    from memory_fabric.protocol import PropagationState
    from memory_fabric.transport import HttpTransport

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        paths = {name: root / f"{name}.db" for name in HOSTS}
        ids: dict[str, str] = {}
        source_memory_id = ""
        for name in HOSTS:
            fabric = MemoryFabric(paths[name], busy_timeout_ms=30_000,
                                  firewall=_fixture_firewall(),
                                  auto_activate=True, recognise_copies=False)
            try:
                ids[name] = fabric.store_id
                if name == "origin":
                    source_memory_id = fabric.remember(
                        "operator", "Pump P-100 relief pressure is 8 bar at site 4.",
                        scope="federated", auto_activate=True,
                    )
            finally:
                fabric.close()

        ports = {name: _port() for name in HOSTS}
        key_hex = secrets.token_hex(32)
        peer_paths: dict[str, Path] = {}
        for name in HOSTS:
            peers = [{"store_id": ids[other],
                      "endpoint": f"http://127.0.0.1:{ports[other]}",
                      "key_hex": key_hex, "key_id": "e4-07"}
                     for other in HOSTS if other != name]
            peer_path = root / f"{name}-peers.json"
            peer_path.write_text(json.dumps(peers), encoding="utf-8")
            peer_paths[name] = peer_path

        processes: dict[str, subprocess.Popen[str]] = {}
        try:
            for name in HOSTS:
                processes[name] = _start(paths[name], peer_paths[name], ports[name])
                _wait_ready(processes[name], ports[name])

            # Send the source memory through the authenticated HTTP offer path.
            origin = MemoryFabric(paths["origin"], busy_timeout_ms=30_000,
                                  firewall=_fixture_firewall())
            try:
                registry = load_peers(peer_paths["origin"])
                transport = HttpTransport(registry, ids["origin"], timeout=10.0)
                imported: dict[str, str] = {}
                for name in HOSTS[1:]:
                    prepared = prepare_offer(origin, source_memory_id, ids[name])
                    if not hasattr(prepared, "to_json"):
                        raise RuntimeError(f"origin refused offer to {name}: {prepared}")
                    reply = transport.send_offer(ids[name], prepared, "reviewer")
                    if not reply.get("accepted") or not reply.get("imported_memory_id"):
                        raise RuntimeError(f"{name} refused offer: {reply}")
                    imported[name] = str(reply["imported_memory_id"])
            finally:
                origin.close()

            for name in HOSTS[1:]:
                recipient = MemoryFabric(paths[name], busy_timeout_ms=30_000,
                                         firewall=_fixture_firewall())
                try:
                    recipient.validate(imported[name], actor="reviewer",
                                       reason="three-host fixture approval")
                finally:
                    recipient.close()

            # Partition B by stopping its independent server process. A remains
            # available and must acknowledge while B remains visibly pending.
            b_pid_before = processes["recipient-b"].pid
            _stop(processes["recipient-b"])
            origin = MemoryFabric(paths["origin"], busy_timeout_ms=30_000,
                                  firewall=_fixture_firewall())
            try:
                recipients = [ids["recipient-a"], ids["recipient-b"]]
                retraction = origin.request_retraction(
                    source_memory_id, reason="source value corrected by inspection",
                    recipients=recipients, actor="operator", basis="contradicted",
                )
                dispatch_offline = Dispatcher(
                    origin, HttpTransport(load_peers(peer_paths["origin"]),
                                          ids["origin"], timeout=5.0)
                ).run_once()
                offline_states = {
                    name: origin.outbox.state_of(retraction.retraction_id, ids[name]).value
                    for name in HOSTS[1:]
                }
                offline_acks = origin.outbox.acknowledgements(retraction.retraction_id)

                processes["recipient-b"] = _start(
                    paths["recipient-b"], peer_paths["recipient-b"], ports["recipient-b"]
                )
                _wait_ready(processes["recipient-b"], ports["recipient-b"])
                b_pid_after = processes["recipient-b"].pid
                origin.outbox._conn.execute(
                    "UPDATE outbox SET next_attempt_ms = 0 WHERE retraction_id = ? "
                    "AND recipient = ?", (retraction.retraction_id, ids["recipient-b"])
                )
                dispatch_after_rejoin = Dispatcher(
                    origin, HttpTransport(load_peers(peer_paths["origin"]),
                                          ids["origin"], timeout=10.0)
                ).run_once()
                acknowledgements = origin.outbox.acknowledgements(retraction.retraction_id)
                pending = origin.outbox.pending()
                origin_cursor_expected = retraction.origin_sequence
            finally:
                origin.close()

            recipient_state: dict[str, str] = {}
            recipient_cursors: dict[str, int] = {}
            for name in HOSTS[1:]:
                recipient = MemoryFabric(paths[name], busy_timeout_ms=30_000,
                                         firewall=_fixture_firewall())
                try:
                    recipient_state[name] = recipient.get(
                        imported[name]
                    ).lifecycle_state.value
                    recipient_cursors[name] = recipient.outbox.cursor_for(ids["origin"])
                finally:
                    recipient.close()

            ack_rows = {
                name: {
                    "state": acknowledgements[ids[name]].state.value,
                    "state_revision": acknowledgements[ids[name]].state_revision,
                }
                for name in HOSTS[1:] if ids[name] in acknowledgements
            }
            expected_ids = {ids[name] for name in HOSTS[1:]}
            passed = (
                len({processes[name].pid for name in HOSTS}) == 3
                and b_pid_before != b_pid_after
                and all(offline_states[name] == (
                    PropagationState.ENFORCED.value if name == "recipient-a"
                    else PropagationState.RETRYING.value
                ) for name in HOSTS[1:])
                and dispatch_offline.enforced == 1 and dispatch_offline.retrying == 1
                and dispatch_after_rejoin.enforced == 1
                and set(acknowledgements) == expected_ids
                and all(row["state"] == PropagationState.ENFORCED.value
                        and row["state_revision"] > 0 for row in ack_rows.values())
                and not pending
                and all(value == LifecycleState.QUARANTINED.value
                        for value in recipient_state.values())
                and all(value == origin_cursor_expected
                        for value in recipient_cursors.values())
            )
            return {
                "schema": "memory-fabric-e4-07-three-logical-hosts/1",
                "machine": f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, Python {platform.python_version()}",
                "host_processes": {name: processes[name].pid for name in HOSTS},
                "stores": {name: {"store_id": ids[name], "database": f"{name}.db",
                                  "endpoint": f"http://127.0.0.1:{ports[name]}"}
                           for name in HOSTS},
                "scenario": {"offered_over_authenticated_http": 2,
                             "retraction_recipients": 2,
                             "partitioned_host": "recipient-b",
                             "recipient_b_restarted_with_same_store": True,
                             "b_pid_before": b_pid_before, "b_pid_after": b_pid_after},
                "offline_delivery": {"report": {"attempted": dispatch_offline.attempted,
                                                 "enforced": dispatch_offline.enforced,
                                                 "retrying": dispatch_offline.retrying},
                                     "states": offline_states,
                                     "acknowledged_recipients": sorted(offline_acks)},
                "after_rejoin": {"report": {"attempted": dispatch_after_rejoin.attempted,
                                              "enforced": dispatch_after_rejoin.enforced,
                                              "retrying": dispatch_after_rejoin.retrying},
                                 "acknowledgements": ack_rows,
                                 "pending_outbox_rows": len(pending),
                                 "recipient_lifecycle": recipient_state,
                                 "recipient_origin_cursors": recipient_cursors,
                                 "expected_origin_sequence": origin_cursor_expected},
                "passed": passed,
                "limitations": ["Three logical hosts are separate localhost processes with distinct SQLite files, all on one physical machine.",
                                "The partition is modeled by stopping recipient B's server process; this does not emulate packet loss, bandwidth limits, or clock skew."],
            }
        finally:
            for process in processes.values():
                _stop(process)


def main() -> int:
    if len(sys.argv) == 5 and sys.argv[1] == "--node":
        return _node(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    result = run()
    result["commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      capture_output=True, text=True, check=True).stdout.strip()
    output = ROOT / "research" / "results" / "e4-07-three-hosts.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
