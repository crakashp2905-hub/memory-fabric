"""End-to-end backup/restore qualification across an authentic old schema."""

from __future__ import annotations

import gzip
import hashlib
import json
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from memory_fabric import LifecycleState, MemoryFabric
from memory_fabric.actions import (GRANT_REPLAYED, ActionGate, ActionPolicy,
                                   ActionRequest, ToolRule)
from memory_fabric.cli import main
from memory_fabric.events import EventType
from memory_fabric.model import SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "data" / "historical"


class BackupRestoreQualification(unittest.TestCase):
    def test_upgrade_backup_restore_preserves_authorization_and_audit_state(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
            compressed = (FIXTURES / manifest["fixture"]).read_bytes()
            self.assertEqual(hashlib.sha256(compressed).hexdigest(), manifest["compressed_sha256"])
            database = gzip.decompress(compressed)
            self.assertEqual(hashlib.sha256(database).hexdigest(), manifest["database_sha256"])

            source = directory / "upgraded.db"
            source.write_bytes(database)
            with closing(MemoryFabric(source, auto_activate=True)) as fabric:
                historical_id = manifest["memory_id"]
                self.assertEqual(fabric.get(historical_id).content, manifest["memory_content"])

                current_id = fabric.remember("fixture-agent", "Valve V-8 closes at 4 bar.",
                                             scope="team")
                fabric.validate(current_id, actor="reviewer")
                fabric.revise(current_id, "Valve V-8 closes at 5 bar.",
                              agent_id="reviewer", reason="calibration bulletin")
                fabric.validate(current_id, actor="reviewer")
                withdrawn_id = fabric.remember("fixture-agent", "Valve V-9 closes at 2 bar.")
                fabric.validate(withdrawn_id, actor="reviewer")
                fabric.request_retraction(
                    withdrawn_id, reason="incorrect calibration", recipients=["peer-test"],
                    actor="reviewer", basis="contradicted")

                policy = ActionPolicy(
                    tools={"publish": ToolRule("publish", min_authority="untrusted",
                                                requires_grant=True)},
                    grants={"fixture-agent": frozenset({"publish"})},
                    policy_id="backup-restore-qualification")
                gate = ActionGate(fabric, policy)
                certificate = fabric.certify("publish-valve-setting", [current_id], "fixture-agent")
                request = ActionRequest("valve-v8", {"closing_pressure_bar": 5})
                used_grant = gate.issue_grant(
                    "publish", "fixture-agent", "supervisor", certificate=certificate,
                    request=request)
                allowed = gate.authorize("publish", "fixture-agent", certificate,
                                         request=request, grant=used_grant)
                self.assertTrue(allowed.allowed, allowed.reason_codes)
                unused_grant = gate.issue_grant(
                    "publish", "fixture-agent", "supervisor", certificate=certificate,
                    request=request)

                events = list(fabric.log.read())
                chain = fabric.log.chain.verify(events)
                self.assertTrue(chain.ok, chain)
                expected_head = list(fabric.log.chain.head())
                expected_schema_versions = fabric.log.schema_versions()
                self.assertIn("0.11.0", expected_schema_versions)
                self.assertIn(SCHEMA_VERSION, expected_schema_versions)
                expected_versioned = [
                    (event.payload["memory"]["id"], event.payload["memory"]["version"])
                    for event in events if event.type == EventType.MEMORY_VERSIONED]
                self.assertIn((current_id, 2), expected_versioned)
                expected_action_evidence = [
                    row for event in events if event.type == EventType.ACTION_GATED
                    and event.payload.get("allowed")
                    for row in event.payload.get("evidence", [])]
                self.assertIn([current_id, 2], expected_action_evidence)
                expected_retractions = [item.to_json() for item in fabric.retractions_since(0)]
                self.assertEqual(len(expected_retractions), 1)
                self.assertEqual(expected_retractions[0]["origin_memory_version"], 1)
                self.assertEqual(fabric.get(current_id).version, 2)
                self.assertEqual(fabric.get(withdrawn_id).lifecycle_state,
                                 LifecycleState.QUARANTINED)

            backup = directory / "qualified-backup.db"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["--db", str(source), "backup", str(backup)]), 0)
            backup_manifest = json.loads(
                backup.with_name(backup.name + ".manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(backup_manifest["chain_head"],
                             {"seq": expected_head[0], "digest": expected_head[1]})

            restored_directory = directory / "restored"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["restore", str(backup), str(restored_directory)]), 0)
            restored = MemoryFabric(restored_directory / "store.db", auto_activate=True)
            try:
                restored_events = list(restored.log.read())
                self.assertTrue(restored.log.chain.verify(restored_events).ok)
                self.assertEqual(list(restored.log.chain.head()), expected_head)
                self.assertEqual(restored.log.schema_versions(), expected_schema_versions)
                self.assertEqual(restored.get(current_id).content, "Valve V-8 closes at 5 bar.")
                self.assertEqual(restored.get(current_id).version, 2)
                self.assertEqual(restored.get(withdrawn_id).lifecycle_state,
                                 LifecycleState.QUARANTINED)
                self.assertEqual([item.to_json() for item in restored.retractions_since(0)],
                                 expected_retractions)
                restored_versioned = [
                    (event.payload["memory"]["id"], event.payload["memory"]["version"])
                    for event in restored_events if event.type == EventType.MEMORY_VERSIONED]
                self.assertEqual(restored_versioned, expected_versioned)
                restored_action_evidence = [
                    row for event in restored_events if event.type == EventType.ACTION_GATED
                    and event.payload.get("allowed")
                    for row in event.payload.get("evidence", [])]
                self.assertEqual(restored_action_evidence, expected_action_evidence)
                restored_grant_ids = {
                    event.payload["grant_id"] for event in restored_events
                    if event.type == EventType.GRANT_ISSUED and not event.payload.get("revoked")}
                self.assertEqual(restored_grant_ids,
                                 {used_grant.grant_id, unused_grant.grant_id})

                restored_gate = ActionGate(restored, policy)
                replayed = restored_gate.authorize(
                    "publish", "fixture-agent", certificate, request=request,
                    grant=used_grant.grant_id)
                self.assertFalse(replayed.allowed)
                self.assertIn(GRANT_REPLAYED, replayed.reason_codes)
                unused = restored_gate.authorize(
                    "publish", "fixture-agent", certificate, request=request,
                    grant=unused_grant.grant_id)
                self.assertTrue(unused.allowed, unused.reason_codes)
                replayed_unused = restored_gate.authorize(
                    "publish", "fixture-agent", certificate, request=request,
                    grant=unused_grant.grant_id)
                self.assertFalse(replayed_unused.allowed)
                self.assertIn(GRANT_REPLAYED, replayed_unused.reason_codes)
                self.assertTrue(restored.log.chain.verify(restored.log.read()).ok)
            finally:
                restored.close()


if __name__ == "__main__":
    unittest.main()
