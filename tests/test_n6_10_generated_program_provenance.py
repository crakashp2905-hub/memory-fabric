from __future__ import annotations

import unittest

from experiments.n6_10_generated_program_provenance import evaluate
from memory_fabric.tool_protocol import CodeModePlan


class GeneratedProgramProvenanceTests(unittest.TestCase):
    def test_source_mutation_invalidates_approval_without_changing_first_effect(self) -> None:
        report = evaluate()
        self.assertTrue(report["acceptance_passed"])
        self.assertEqual(report["results"]["approved_outcome"], "executed")
        self.assertEqual(report["results"]["mutations_total"], 10)
        self.assertEqual(report["results"]["mutations_refused"], 10)
        self.assertEqual(report["results"]["mutations_with_approval_invalid"], 10)
        self.assertEqual(report["results"]["simple_policy_baseline_outcome"], "executed")
        self.assertEqual(report["results"]["handler_effects"],
                         [{"target": "pump-7", "setpoint": 40}])
        self.assertEqual(report["results"]["simple_policy_baseline_effects"],
                         [{"target": "pump-7", "setpoint": 40}])
        self.assertNotEqual(
            CodeModePlan.parse('dispatch(target="pump-7", setpoint=40)').source_digest,
            CodeModePlan.parse(
                'dispatch(target="pump-7", setpoint=40)\n'
                'dispatch(target="pump-8", setpoint=40)'
            ).source_digest,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
