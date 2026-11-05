"""Exact finite-population query-miss analysis is not a new scored learner."""
import unittest
from unittest.mock import patch
from e14.e14_shared_budget import BudgetContractError
from e14.e14z_detection_limits import miss_probability,limits
from e14.e14z_drift import bank,study

class QueryMissTests(unittest.TestCase):
    def test_one_disagreement_and_two_queries(self):
        self.assertAlmostEqual(miss_probability(1,2),64/66)

    def test_no_disagreement_is_never_detected(self):
        self.assertEqual(miss_probability(0,4),1)

    def test_all_disagreement_is_always_detected(self):
        self.assertEqual(miss_probability(66,2),0)

    def test_additional_query_never_increases_miss_probability(self):
        for d in range(1,67):
            self.assertGreaterEqual(miss_probability(d,2),miss_probability(d,4))

    def test_boolean_or_out_of_domain_counts_fail_closed(self):
        for args in ((True,2),(3,True),(67,2),(-1,2),(1,67)):
            self.assertRaises(BudgetContractError,miss_probability,*args)

    def test_one_operator_reconstructs_observed_false_acceptance(self):
        result=study(bank(),indices=(0,));partial=bank()
        partial['rows']=partial['rows'][:1]
        with patch('e14.e14z_detection_limits.read_scores',return_value=(partial,result['rows'],result['sources'],[])):
            output=limits(['unused'])
        self.assertEqual(output['summary']['near']['actual_false_accepts_random_2'],2)
        self.assertEqual(output['summary']['far']['actual_false_accepts_random_2'],0)

if __name__=='__main__':unittest.main()
