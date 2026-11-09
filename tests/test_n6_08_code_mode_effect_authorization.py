from __future__ import annotations

import unittest

from experiments.n6_08_code_mode_effect_authorization import evaluate


class CodeModeEffectAuthorizationTests(unittest.TestCase):
    def test_retry_and_injected_arguments_require_their_own_gate_decision(self) -> None:
        report = evaluate()
        self.assertTrue(report["acceptance_passed"])
        self.assertEqual(report["retry_after_evidence_change"]["effects"], 1)
        self.assertEqual(report["injected_argument_binding"]["effects"],
                         [{"target": "pump-7", "setpoint": 40}])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
