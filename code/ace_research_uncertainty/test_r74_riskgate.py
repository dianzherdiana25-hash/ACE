"""Pre-final independent unit tests for locked R7.4 e-process design."""
import math
import unittest
from unittest.mock import patch

from . import experiment as e
from . import r74_riskgate as r


class R74ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.prior = (.18, .42, .63, .78, .91, .97)
        self.task = r.new_tasks('test', 1)[0]

    def test_null_e_multiplier_nonincreasing_expectation(self):
        for p in (0.0, .1, .5, .79, .8):
            self.assertLessEqual(r.null_expected_multiplier(p), 1.0 + 1.e-12)
        self.assertAlmostEqual(r.null_expected_multiplier(.8), 1.0)
        self.assertGreater(r.null_expected_multiplier(.9), 1.)

    def test_multiplier_and_certificate_threshold(self):
        self.assertAlmostEqual(r.likelihood_multiplier(1), 1.2)
        self.assertAlmostEqual(r.likelihood_multiplier(0), .2)
        self.assertLess(1.2**12, 10)
        self.assertGreater(1.2**13, 10)
        for x in (2, -1, True, .5):
            with self.assertRaises(ValueError):
                r.likelihood_multiplier(x)

    def test_candidate_from_purchased_diagnostics_only(self):
        observed = ((0,1),(4,0),(5,1),(0,1),(4,0),(5,0))
        self.assertEqual(r.choose_one(observed, self.prior), 0)
        self.assertEqual(r.choose_one(((0,1),(4,1),(5,1),(0,1),(4,1),(5,1)), self.prior), 5)
        for bad in (observed[:-1], ((0,1),(4,0),(5,1),(0,1),(4,True),(5,0))):
            with self.assertRaises(ValueError):
                r.choose_one(bad, self.prior)

    def test_all_world_split_ids_are_unique_and_new(self):
        banks = [r.new_tasks('train',30),r.new_tasks('validation',12),
                 r.new_tasks('test',20),
                 *(r.new_tasks(s,20) for s in ('ood_a','ood_b','ood_c','ood_d'))]
        ids = [task.uid for bank in banks for task in bank]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(':r74:' in uid for uid in ids))
        with self.assertRaises(ValueError):
            r.new_tasks('ood_e',20)
        with self.assertRaises(ValueError):
            r.new_tasks('test',True)

    def test_zero_budget_abstention_and_undefined_rate(self):
        for method in r.METHODS:
            result = r.aggregate((self.task,),self.prior,method,0)
            self.assertEqual(result['purchases'],0)
            self.assertEqual(result['true_accepts']+result['false_accepts'],0)
            self.assertEqual(result['abstentions'],6)
            self.assertIsNone(result['false_acceptance_rate'])

    def test_no_decisions_without_six_diagnostics(self):
        for cap in (0,6):
            rec = r.one(self.task,self.prior,'e_test',cap)
            self.assertFalse(rec.certified)
            self.assertEqual(rec.certificate_count,0)
            self.assertEqual(rec.scored['purchases'],cap)
            self.assertEqual(rec.scored['abstentions'],6)

    def test_fixed_diag_prefix_and_fresh_cert_labels(self):
        groups=[]
        orig = e.Evaluator.query
        def inspect(instance, group):
            groups.append(group)
            return orig(instance,group)
        with patch.object(e.Evaluator,'query',inspect):
            rec=r.one(self.task,self.prior,'e_test',24)
        self.assertEqual(groups[:6],list(r.DIAGNOSTICS))
        self.assertTrue(all(group == rec.chosen_group for group in groups[6:]))
        self.assertEqual(rec.scored['purchases'],6+rec.certificate_count)
        self.assertEqual(rec.diagnostic_count,6)

    def test_matching_acquisition_for_paired_control(self):
        for split in ('test','ood_a','ood_b','ood_c','ood_d'):
            task=r.new_tasks(split,1)[0]
            a=r.one(task,self.prior,'e_test',24)
            b=r.one(task,self.prior,'paired_lcb',24)
            self.assertEqual(a.scored['purchases'],b.scored['purchases'])
            self.assertEqual(a.chosen_group,b.chosen_group)
            self.assertEqual(a.certificate_count,b.certificate_count)
            self.assertEqual(a.e_value,b.e_value)
            self.assertEqual(a.scored['brier_sum'],b.scored['brier_sum'])

    def test_no_oracle_ceiling_used_in_any_learned_method(self):
        with patch.object(e.Evaluator,'oracle_upper_bound', side_effect=AssertionError('leak')):
            for method in r.METHODS:
                r.one(self.task,self.prior,method,24)

    def test_e_process_only_certifies_one_group_per_task(self):
        for split in ('test','ood_a','ood_b','ood_c','ood_d'):
            tasks=r.new_tasks(split,3)
            for task in tasks:
                rec=r.one(task,self.prior,'e_test',24)
                self.assertLessEqual(rec.scored['true_accepts'] + rec.scored['false_accepts'],1)
                self.assertEqual(rec.scored['true_accepts']+rec.scored['false_accepts']+rec.scored['abstentions'],6)
                self.assertEqual(rec.certified,rec.scored['true_accepts']+rec.scored['false_accepts']==1)

    def test_hard_budgets_and_accounting(self):
        tasks = r.new_tasks('ood_b',2)
        for method in r.METHODS:
            for budget in r.BUDGETS:
                row = r.aggregate(tasks,self.prior,method,budget)
                self.assertLessEqual(row['purchases'],budget*len(tasks))
                self.assertEqual(row['abstentions']+row['true_accepts']+row['false_accepts'],12)
                self.assertLessEqual(row['certificate_labels']+row['diagnostic_labels'],row['purchases'])
                self.assertTrue(math.isfinite(row['ece']))
                self.assertTrue(math.isfinite(row['brier']))

    def test_unknown_method_and_nonprotocol_budget_rejected(self):
        for method, budget in (('oracle',24),('e_test',25),('e_test',-1)):
            with self.assertRaises(ValueError):
                r.one(self.task,self.prior,method,budget)

    def test_no_target_world_label_used_to_fit_prior(self):
        train = r.new_tasks('train',2)
        prior,cost=e.fit_prior(train)
        self.assertEqual(cost,2*6*12)
        with self.assertRaises(ValueError):
            e.fit_prior(r.new_tasks('test',2))
        with self.assertRaises(ValueError):
            e.fit_prior(r.new_tasks('ood_c',2))

    def test_repeated_validation_same_output(self):
        self.assertEqual(r.validation_only(),r.validation_only())

    def test_analytic_bound_not_claimed_under_drift(self):
        # A nonstationary process can violate the per-task null at certain times.
        # The bound is deliberately not stated for arbitrary data-generating drift.
        self.assertGreater(r.null_expected_multiplier(.95),1.0)
        self.assertLess(r.null_expected_multiplier(.20),1.0)


if __name__=='__main__':
    unittest.main()
