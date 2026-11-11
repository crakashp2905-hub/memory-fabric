"""The Control Center's graph and agents views, and that its script parses."""

from __future__ import annotations

import re
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.observability.control import agents, graph, knowledge_map
from memory_fabric.observability.server import Api, ApiError, STATIC_ROUTES, STATIC_DIR

HTML = Path(__file__).resolve().parents[1] / "src" / "memory_fabric" / "observability" / "static" / "dashboard.html"


class TestViews(unittest.TestCase):
    def setUp(self):
        self.f = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.f.close)
        self.a = self.f.remember("ag_one", "Pump P-14 relief valve is set to 12 bar.", scope="team")
        self.b = self.f.derive("ag_two", "Restore P-14 relief after seal work.", [self.a])
        self.f.remember("ag_one", "To deploy, export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE now.",
                        scope="team")
        self.f.retrieve("ag_two", "P-14 relief", k=3)

    def test_graph_has_lineage_and_masks_secrets(self):
        g = graph(self.f)
        edge = next(e for e in g["edges"] if e["from"] == self.a and e["to"] == self.b)
        self.assertEqual(edge["kind"], "derived")
        self.assertTrue(edge["event_id"])
        event = Api(self.f).handle(f"/api/events/{edge['event_id']}", {})
        self.assertEqual((event["event_id"], event["seq"]), (edge["event_id"], edge["seq"]))
        self.assertFalse(any("AKIAIOSFODNN7EXAMPLE" in n["label"] for n in g["nodes"]))
        self.assertEqual(g["total"], 3)
        self.assertLessEqual(graph(self.f, limit=1)["shown"], 1)

    def test_agents_counts(self):
        rows = {r["agent_id"]: r for r in agents(self.f)}
        self.assertEqual(rows["ag_one"]["writes"], 2)
        self.assertGreaterEqual(rows["ag_two"]["recalls"], 1)

    def test_routes(self):
        api = Api(self.f)
        self.assertIn("nodes", api.handle("/api/graph", {}))
        self.assertIn("topics", api.handle("/api/map", {"per_topic": ["2"]}))
        self.assertTrue(api.handle("/api/agents", {}))
        catalog = api.handle("/api/user-catalog", {})
        self.assertIn("providers", catalog)
        self.assertNotIn("system_prompt", repr(catalog))

    def test_timeline_and_every_graph_edge_resolve_to_log_events(self):
        api = Api(self.f)
        for edge in graph(self.f)["edges"]:
            event = api.handle(f"/api/events/{edge['event_id']}", {})
            self.assertEqual(event["event_id"], edge["event_id"])
            self.assertEqual(event["seq"], edge["seq"])
        timeline = api.handle(f"/api/memories/{self.b}/timeline", {})
        event_steps = [step for step in timeline["steps"] if step["event_id"]]
        self.assertTrue(event_steps)
        for step in event_steps:
            event = api.handle(f"/api/events/{step['event_id']}", {})
            self.assertEqual((event["seq"], event["event_type"]),
                             (step["seq"], step["event_type"]))
        self.assertTrue(any(step["event_id"] for step in timeline["steps"]))

    def test_knowledge_map_lineage_links_have_resolvable_event_ids(self):
        api = Api(self.f)
        mapping = knowledge_map(self.f, max_topics=8, per_topic=8)
        links = [link for link in mapping["memory_links"]
                 if link["from"] == self.a and link["to"] == self.b]
        self.assertTrue(links)
        for link in links:
            event = api.handle(f"/api/events/{link['event_id']}", {})
            self.assertEqual((event["event_id"], event["seq"]),
                             (link["event_id"], link["seq"]))


class TestKnowledgeMap(unittest.TestCase):
    """Topics a person can read without zooming: few, named, with what matters picked out."""

    def setUp(self):
        self.f = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.f.close)
        self.wrong = self.f.remember("ag_one", "Pump P-14 relief valve opens at 12 bar.", scope="team")
        self.f.remember("ag_two", "Pump P-14 relief valve was replaced in May.", scope="team")
        self.f.remember("ag_two", "Pump P-14 relief valve has a new gasket.", scope="team")
        self.f.remember("ag_one", "Chiller C-2 setpoint is 7 C for the server room.", scope="team")
        self.f.remember("ag_one", "Chiller C-2 alarms page the night shift.", scope="team")
        self.f.remember("ag_one", "To deploy, export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE now.", scope="team")
        self.f.quarantine(self.wrong, reason="it opens at 10 bar", actor="op")

    def test_groups_by_a_shared_word_and_names_the_topic(self):
        m = knowledge_map(self.f)
        pump = next(t for t in m["topics"] if t["label"].startswith(("Pump", "Relief", "Valve")))
        self.assertEqual(pump["size"], 3)
        self.assertTrue(any(t["label"].startswith("Chiller") for t in m["topics"]))
        self.assertEqual(m["total"], 6)

    def test_puts_the_withdrawn_memory_first_and_says_so(self):
        pump = next(t for t in knowledge_map(self.f)["topics"] if t["size"] == 3)
        self.assertEqual(pump["highlights"][0]["id"], self.wrong)
        self.assertEqual(pump["highlights"][0]["why"], "withdrawn")
        self.assertEqual(pump["states"].get("quarantined"), 1)
        self.assertTrue(any("withdrawn" in line for line in knowledge_map(self.f)["summary"]))

    def test_stays_small_and_masks_secrets(self):
        m = knowledge_map(self.f, max_topics=1, per_topic=1)
        self.assertLessEqual(len([t for t in m["topics"] if t["id"] != "_other"]), 1)
        self.assertTrue(all(len(t["highlights"]) <= 1 for t in m["topics"]))
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", repr(knowledge_map(self.f)))

    def test_an_empty_store_has_no_topics(self):
        empty = MemoryFabric(":memory:")
        self.addCleanup(empty.close)
        m = knowledge_map(empty)
        self.assertEqual((m["topics"], m["total"]), ([], 0))


class TestPage(unittest.TestCase):
    def test_every_tab_has_a_section_and_a_loader(self):
        html = HTML.read_text(encoding="utf-8")
        tabs = set(re.findall(r'data-tab="([a-z]+)"', html))
        for t in tabs:
            self.assertIn(f'id="tab-{t}"', html, t)
        listed = re.search(r"const TABS = \[(.*?)\];", html, re.S).group(1)
        self.assertEqual(tabs, set(re.findall(r'"([a-z]+)"', listed)))

    def test_action_detail_view_renders_decision_scope_and_current_evidence(self):
        html = HTML.read_text(encoding="utf-8")
        start = html.index("async function showAction(seq)")
        end = html.index("async function loadCapabilities()", start)
        detail = html[start:end]
        for field in ("identity_scope", "reason_codes", "provenance", "support_now",
                      "authority_now", "usable_now", "state_now"):
            self.assertIn(field, detail)
        self.assertIn("Identity scope:", detail)
        self.assertIn("Support recomputation", detail)
        self.assertIn("Blocked because", detail)
        self.assertIn("truth and intent are not established", html)
        self.assertIn("this claim may still be true", html)

    def test_story_links_open_logged_events_by_stable_id(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("data-event-id", html)
        self.assertIn("async function openEvent(eventId)", html)
        self.assertIn("/api/events/${encodeURIComponent(eventId)}", html)
        self.assertIn("click a memory to read its story or a dashed lineage edge", html)

    def test_action_view_exposes_per_tool_timeline_and_receipt_reconciliation(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("id=\"action-reconciliation\"", html)
        self.assertIn("id=\"action-timeline\"", html)
        self.assertIn("/api/action-reconciliation", html)
        self.assertIn("/api/actions/timeline?tool=", html)
        self.assertIn("external effect requires reconciliation", html)

    def test_selected_action_offers_offline_redacted_incident_export(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("/api/incidents/${encodeURIComponent(seq)}/export", html)
        self.assertIn("Download redacted incident report", html)
        self.assertIn("URL.createObjectURL(blob)", html)
        self.assertIn("memory-fabric-incident-${seq}.json", html)

    def test_large_history_has_bounded_pages_and_generic_error_boundary(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('p.set("limit", String(MEMORY_PAGE_SIZE))', html)
        self.assertIn('p.set("offset", String(MEMORY_OFFSET))', html)
        self.assertIn('id="memory-prev"', html)
        self.assertIn('id="memory-next"', html)
        self.assertIn("No memories match this page or filter.", html)
        server = (HTML.parents[4] / "src/memory_fabric/observability/server.py").read_text(encoding="utf-8")
        self.assertIn('{"error": "internal error"}', server)
        self.assertNotIn('{"error": f"internal error: {exc}"}', server)

    def test_accessibility_contract_has_names_keyboard_paths_and_textual_statuses(self):
        html = HTML.read_text(encoding="utf-8")
        for label in ("Filter memories by content or id", "Filter memories by state",
                      "Filter memories by scope", "Filter memories by type", "Sort memories",
                      "Search memories", "Agent id (optional)", "Agent question (optional)"):
            self.assertIn(f'aria-label="{label}"', html)
        for state in ("in use", "waiting for review", "disputed", "withdrawn", "retired", "deleted"):
            self.assertIn(f'"{state}"', html)
        self.assertIn('aria-describedby="map-keyboard-help"', html)
        self.assertIn('id="map-memory-list"', html)
        self.assertIn('data-map-memory="${esc(m.id)}"', html)
        self.assertIn('ev.key === "Enter" || ev.key === " "', html)
        self.assertIn("function trapFocus(dialog, ev)", html)
        self.assertIn("drawerReturnFocus?.focus?.()", html)
        self.assertIn("paletteReturnFocus?.focus?.()", html)
        self.assertIn("helpReturnFocus?.focus?.()", html)
        self.assertIn(":focus-visible", html)
        self.assertIn('aria-live="polite"', html)

    def test_withholding_scorecard_has_denominator_risk_and_population_labels(self):
        static = STATIC_DIR / "withholding-benchmark.json"
        row = json.loads(static.read_text(encoding="utf-8"))
        source_path = HTML.parents[4] / row["source_report"]
        source = json.loads(source_path.read_text(encoding="utf-8"))
        self.assertIn("/withholding-benchmark.json", STATIC_ROUTES)
        self.assertEqual(hashlib.sha256(source_path.read_bytes()).hexdigest(),
                         row["source_report_sha256"])
        self.assertEqual((row["numerator"], row["denominator"], row["rate"]),
                         (source["memory_fabric_valid_withheld"],
                          source["task_denominator"], source["valid_withholding_rate"]))
        self.assertEqual(row["population"], "synthetic_scripted")
        self.assertEqual(row["risk_class"], "HIGH")
        self.assertEqual(row["live_metric"]["status"], "not_measured")
        html = HTML.read_text(encoding="utf-8")
        for phrase in ("task opportunities", "Risk class", "not a measurement of this store",
                       "This store’s live rate", "source_report_sha256"):
            self.assertIn(phrase, html)
        self.assertIn("Refresh impact preview", html)
        self.assertIn("/correction`)", html)
        self.assertIn("The preview changed since it was shown", html)
        self.assertIn("old digest will be rejected", html)
        self.assertIn("Previously shown", html)
        self.assertIn("Fresh impact", html)


class TestActionReasonGroups(unittest.TestCase):
    def test_api_separates_evidence_gaps_from_policy_restrictions(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        memory_id = fabric.remember("ag_ops", "Pump P-14 relief is set to 12 bar.", scope="team")
        gate = ActionGate(
            fabric,
            ActionPolicy(tools={"set_relief": ToolRule("set_relief"),
                                "restricted_tool": ToolRule("restricted_tool")},
                         grants={"ag_ops": frozenset({"set_relief"})}),
        )
        certificate = fabric.certify("P-14 relief", [memory_id], "ag_ops")
        self.assertTrue(gate.authorize("set_relief", "ag_ops", certificate).allowed)
        denied = gate.authorize("restricted_tool", "ag_ops")
        self.assertIn("tool_not_granted", denied.reason_codes)
        api = Api(fabric)
        row = next(item for item in api.handle("/api/actions", {})
                   if "tool_not_granted" in item["reason_codes"])
        detail = api.handle(f"/api/actions/{row['seq']}", {})
        categories = [group["category"] for group in detail["reason_groups"]]
        self.assertEqual(categories, ["Authorization and policy"])
        self.assertIn("not allowed", detail["reason_groups"][0]["messages"][0])

    def test_uncertainty_labels_never_turn_missing_support_into_false_or_malicious(self):
        from memory_fabric.observability.control import _claim_check_label, _support_label

        labels = [_support_label("unsupported"), _support_label(None),
                  _claim_check_label("suspicious"), _claim_check_label(None)]
        combined = " ".join(labels).lower()
        self.assertIn("may still be true", labels[0])
        self.assertIn("not assessed", labels[1].lower())
        self.assertIn("truth and intent are not established", labels[2])
        self.assertNotIn("false", combined)
        self.assertNotIn("malicious", combined)

    def test_fresh_correction_preview_changes_digest_and_stale_apply_is_refused(self):
        from memory_fabric.correction import StalePreview, apply

        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        root = fabric.remember("ag_ops", "Pump P-14 relief is set to 12 bar.", scope="team")
        first = fabric.derive("ag_ops", "P-14 remains safe at the recorded relief setting.",
                              [root], scope="team")
        api = Api(fabric)
        old = api.handle(f"/api/memories/{root}/correction", {})
        self.assertIn(first, old["would_contest"])
        second = fabric.derive("ag_review", "P-14 needs another relief review.",
                               [root], scope="team")
        fresh = api.handle(f"/api/memories/{root}/correction", {})
        self.assertNotEqual(old["digest"], fresh["digest"])
        self.assertIn(second, fresh["would_contest"])
        with self.assertRaises(StalePreview):
            apply(fabric, root, reason="review", actor="reviewer",
                  preview_digest=old["digest"])
        self.assertEqual(fabric.get(root).lifecycle_state.value, "active")


class TestActionReceiptApi(unittest.TestCase):
    def test_timeline_and_redacted_receipt_states_cover_execute_refuse_and_unknown(self):
        from memory_fabric import events

        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        memory_id = fabric.remember("ag_ops", "Pump P-14 relief is set to 12 bar.", scope="team")
        certificate = fabric.certify("P-14 relief", [memory_id], "ag_ops")
        gate = ActionGate(
            fabric,
            ActionPolicy(tools={"operate": ToolRule("operate")},
                         grants={"ag_ops": frozenset({"operate"})}),
        )
        completed_key = "private-idempotency-key-canary"
        completed = gate.execute("operate", "ag_ops", lambda _key: "ok", certificate,
                                 key=completed_key)
        self.assertEqual(completed.outcome, "executed")
        fabric.quarantine(memory_id, reason="changed", actor="reviewer")
        refused = gate.execute("operate", "ag_ops", lambda _key: self.fail("must not run"),
                               certificate, key="refused-key")
        self.assertEqual(refused.outcome, "refused")
        fabric._emit(events.action_attempted(ts=fabric.now(), agent_id="ag_ops",
                                             key="unknown-key", tool="operate", binding="digest"))

        api = Api(fabric)
        receipts = api.handle("/api/action-reconciliation", {})
        states = {row["status"]: row for row in receipts}
        self.assertEqual(set(states), {"completed", "definitely_unexecuted", "unknown"})
        self.assertTrue(states["completed"]["fenced"])
        self.assertTrue(states["unknown"]["reconciliation_required"])
        self.assertNotIn(completed_key, repr(receipts))
        self.assertTrue(all(len(row["idempotency_ref"]) == 12 for row in receipts))

        timeline = api.handle("/api/actions/timeline", {"tool": ["operate"]})
        self.assertTrue(any(row["event_type"] == "ActionGated" for row in timeline))
        self.assertTrue(any(row["event_type"] == "ActionExecuted" for row in timeline))
        self.assertTrue(all(row["event_id"] for row in timeline))
        self.assertNotIn(completed_key, repr(timeline))


class TestActionDetailApi(unittest.TestCase):
    def test_detail_binds_reason_scope_and_evidence_provenance(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        tenant_id = "tn_decision_detail"
        canary = "SYNTHETIC-SECRET-CANARY-DO-NOT-EXPORT"
        memory_id = fabric.remember("ag_ops", f"{canary} Pump P-14 relief valve is set to 12 bar.",
                                    tenant_id=tenant_id, scope="team")
        gate = ActionGate(
            fabric,
            ActionPolicy(tools={"set_relief": ToolRule("set_relief")},
                         grants={"ag_ops": frozenset({"set_relief"})}),
        )
        certificate = fabric.certify("P-14 relief", [memory_id], "ag_ops",
                                     tenant_id=tenant_id)
        self.assertTrue(gate.authorize("set_relief", "ag_ops", certificate,
                                       tenant_id=tenant_id).allowed)
        fabric.quarantine(memory_id, reason="manual changed", actor="reviewer",
                          basis="contradicted")
        refused = gate.authorize("set_relief", "ag_ops", certificate,
                                 tenant_id=tenant_id)
        self.assertIn("evidence_withdrawn", refused.reason_codes)

        watermark = max(event.seq for event in fabric.log.read())
        api = Api(fabric)
        row = next(item for item in api.handle("/api/actions", {})
                   if "evidence_withdrawn" in item["reason_codes"])
        detail = api.handle(f"/api/actions/{row['seq']}", {})
        self.assertEqual(detail["identity_scope"], {
            "agent_id": "ag_ops", "tenant_id": tenant_id, "claim_id": "P-14 relief"})
        self.assertIn("evidence_withdrawn", detail["decision"]["reason_codes"])
        evidence = detail["evidence"][0]
        self.assertEqual(evidence["memory_id"], memory_id)
        self.assertEqual(evidence["provenance"]["created_by"], "ag_ops")
        self.assertEqual(evidence["authority_now"]["origins"], ["ag_ops"])
        self.assertEqual(evidence["state_now"], "quarantined")
        self.assertFalse(evidence["usable_now"])
        self.assertEqual(evidence["support_now"]["verdict"], "justified")
        self.assertIn("justification survives", evidence["support_label"])
        exported = api.handle(f"/api/incidents/{row['seq']}/export", {})
        self.assertEqual(exported["schema"], "memory-fabric-redacted-incident/1")
        self.assertEqual(exported["integrity"]["algorithm"], "sha256")
        self.assertEqual(exported["integrity"]["report_sha256"],
                         hashlib.sha256(json.dumps(exported["report"], sort_keys=True,
                             separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest())
        self.assertNotIn(canary, json.dumps(exported))
        self.assertNotIn("Pump P-14 relief valve", json.dumps(exported))
        with self.assertRaises(ApiError) as malformed:
            api.handle("/api/incidents/not-a-sequence/export", {})
        self.assertEqual(malformed.exception.status.value, 400)
        with self.assertRaises(ApiError) as missing:
            api.handle("/api/incidents/999999/export", {})
        self.assertEqual(missing.exception.status.value, 404)
        self.assertNotIn("false", evidence["claim_check_label"].lower())
        self.assertNotIn("malicious", evidence["claim_check_label"].lower())
        self.assertEqual([group["category"] for group in detail["reason_groups"]],
                         ["Evidence and support"])
        self.assertTrue(any("withdrawn" in message.lower()
                            for message in detail["reason_groups"][0]["messages"]))
        self.assertEqual(max(event.seq for event in fabric.log.read()), watermark)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_script_parses(self):
        html = HTML.read_text(encoding="utf-8")
        script = html[html.index("<script>") + 8: html.rindex("</script>")]
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(script)
        result = subprocess.run(["node", "--check", fh.name], capture_output=True, text=True)
        Path(fh.name).unlink()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_value_onboarding_studio_quality_and_howto_are_real_views(self):
        html = HTML.read_text(encoding="utf-8")
        for tab in ("value", "studio", "compare", "quality", "howto"):
            self.assertIn(f'data-tab="{tab}"', html)
            self.assertIn(f'id="tab-{tab}"', html)
            self.assertRegex(html, rf"{tab}: load[A-Z]")
        self.assertIn('id="role-select"', html)
        self.assertIn('id="agent-drop"', html)
        self.assertIn("Permission review required", html)
        self.assertIn("Evidence, not marketing", html)


if __name__ == "__main__":
    unittest.main()
