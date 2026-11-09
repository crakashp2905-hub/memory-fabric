from __future__ import annotations

import unittest

from tools.r5_07_contamination_audit import audit, audit_dataset


class R507ContaminationAudit(unittest.TestCase):
    def test_fixture_labels_do_not_leak_through_text_ids_or_tool_names(self) -> None:
        report = audit()
        self.assertEqual(report["decision"], "PASS")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["scanned_counts"], {
            "case_ids": 256, "memory_ids": 1024, "memory_texts": 1024, "tool_names": 3,
        })

    def test_deliberately_leaked_label_invalidates_fixture(self) -> None:
        cases = [{"case_id": "case-0001", "options": [
            {"id": "mem-ab12", "text": "record corrected status"},
        ]}]
        report = audit_dataset(cases, ("publish",))
        self.assertEqual(report["decision"], "FAIL")
        self.assertEqual(report["findings"][0]["field"], "text")
        self.assertIn("corrected", report["findings"][0]["labels"])


if __name__ == "__main__":
    unittest.main()
