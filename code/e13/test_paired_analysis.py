"""Check the paired estimand on public synthetic scores."""

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy is required for E1.3 analysis")
class PairedAnalysisTests(unittest.TestCase):
    def rows(self):
        return [
            {"family": family, "regime": "related", "block": block, "episode": episode,
             "seed_slot": seed, "policy": policy, "status": "scored",
             "correct": 6 if policy == "c_extend" and family == "S" else 4, "total": 8}
            for family in ("S", "G") for block in ("first", "second")
            for episode in ("one", "two") for seed in (0, 1, 2) for policy in ("c_extend", "beam")
        ]

    def test_paired_block_aggregation_and_stratification(self):
        from .evaluator.paired_analysis import analyze, block_effects

        effects = block_effects(self.rows(), blocks_per_family=2)
        self.assertEqual(effects, {"S": [0.25, 0.25], "G": [0.0, 0.0]})
        report = analyze(effects)
        self.assertEqual(report["estimate"], 0.125)
        self.assertEqual(report["interval"], [0.125, 0.125])
        self.assertEqual(report["families"]["G"]["interval"], [0.0, 0.0])
        self.assertEqual(report["decision"], "supports_primary_if_other_gates_pass")

    def test_duplicate_missing_or_unresolved_rows_cannot_change_denominator(self):
        from .evaluator.paired_analysis import block_effects

        rows = self.rows()
        invalid = rows[:1] + rows
        with self.assertRaisesRegex(ValueError, "duplicate"):
            block_effects(invalid, blocks_per_family=2)
        with self.assertRaisesRegex(ValueError, "incomplete paired"):
            block_effects(rows[1:], blocks_per_family=2)
        rows[0]["status"] = "infrastructure_error"
        with self.assertRaisesRegex(ValueError, "unresolved"):
            block_effects(rows, blocks_per_family=2)

    def test_candidate_failure_scores_zero_with_full_denominator(self):
        from .evaluator.paired_analysis import block_effects

        rows = self.rows()
        rows[0].update(status="candidate_failure", correct=0)
        effects = block_effects(rows, blocks_per_family=2)
        self.assertEqual(effects["S"], [0.125, 0.25])
        rows[0]["total"] = 0
        with self.assertRaisesRegex(ValueError, "denominator"):
            block_effects(rows, blocks_per_family=2)

    def test_negative_result_remains_distinct_from_inconclusive(self):
        from .evaluator.paired_analysis import analyze

        self.assertEqual(analyze({"S": [0.0, 0.0], "G": [0.0, 0.0]})["decision"],
                         "minimum_effect_not_supported")
        result = analyze({"S": [-0.5, 0.5], "G": [-0.5, 0.5]})
        self.assertEqual(result["decision"], "inconclusive")
        self.assertEqual(result, analyze({"S": [-0.5, 0.5], "G": [-0.5, 0.5]}))
