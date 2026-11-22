import unittest

from ._contracts import identity
from .hypothesis_tester import test_hypothesis as evaluate_hypothesis


def assumptions(*keys):
    return {key: {"declared": True, "source_ref": "fixture:protocol"} for key in keys}


class ExactTestTests(unittest.TestCase):
    def test_fisher_two_tail_and_exact_threshold(self):
        plan = {"schema": "ace.institute.hypothesis-plan.v1", "hypothesis": "Peluang kelompok sama.",
                "method": "fisher", "alternative": "two_sided", "alpha": "0.1",
                "assumptions": assumptions("independent_observations", "fixed_margins"),
                "data": {"a": 3, "b": 0, "c": 0, "d": 3}}
        result = evaluate_hypothesis(plan, identity(plan))
        self.assertEqual(result["p_value_exact"], [1, 10])
        self.assertEqual(result["status"], "reject_null")
        plan["alternative"] = "greater"
        self.assertEqual(evaluate_hypothesis(plan, identity(plan))["p_value_exact"], [1, 20])
        plan["assumptions"]["fixed_margins"]["declared"] = False
        result = evaluate_hypothesis(plan, identity(plan))
        self.assertEqual(result["status"], "held_assumption")
        self.assertIsNone(result["p_value_exact"])

    def test_paired_sign_assignments_calculate_exact_tail(self):
        plan = {"schema": "ace.institute.hypothesis-plan.v1", "hypothesis": "Selisih tidak berubah.",
                "method": "paired_sign_flip", "alternative": "two_sided", "alpha": "0.05",
                "assumptions": assumptions("independent_pairs", "exchangeable_signs"),
                "data": {"pairs": [{"id": key, "before": -1, "after": 2, "source_ref": f"fixture:{key}"} for key in "abc"]}}
        result = evaluate_hypothesis(plan, identity(plan))
        self.assertEqual(result["p_value_exact"], [1, 4])
        self.assertEqual(result["status"], "fail_to_reject")
        self.assertEqual(result["statistics"]["observed_sum"], "9")
