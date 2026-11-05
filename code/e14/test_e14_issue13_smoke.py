"""Deterministic engineering-only smoke checks with explicit negative control."""
import unittest
from tools.ace_issue13_smoke import MODES, TRUTHS, matrix

class Issue13Smoke(unittest.TestCase):
    def test_replay_matrix_is_deterministic(self):
        left, a = matrix()
        right, b = matrix()
        self.assertEqual(left, right)
        self.assertEqual(a, b)
        self.assertEqual(left["arms"], 18)
        self.assertEqual(set(left["summary"]), set(MODES))

    def test_qualifier_rejects_known_aliases(self):
        report, _ = matrix()
        active = report["summary"]["active"]
        self.assertEqual(active["wrong_accepted"], 0)
        self.assertEqual(active["correct_accepted"], 3)
        self.assertEqual(active["abstain"], 3)
        self.assertGreater(report["summary"]["receipt"]["wrong_accepted"], 0)

    def test_every_arm_uses_one_shared_budget_and_independent_replay(self):
        report, _ = matrix()
        self.assertEqual(len(report["rows"]), len(TRUTHS) * len(MODES))
        for row in report["rows"]:
            self.assertLessEqual(row["labels"], 4)
            self.assertEqual(row["labels"], row["replay_calls"])
            self.assertEqual(row["correct_accepted"] + row["wrong_accepted"] + row["abstain"],1)

if __name__ == "__main__":
    unittest.main()
