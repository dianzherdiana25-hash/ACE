"""Adversarial counterexamples are postscore auditor calls, never free labels."""
import copy
import tempfile
import unittest
from pathlib import Path
from e14.e14_shared_budget import BudgetContractError
from e14.e14y_bank import build
from e14.e14y_study import truth_of,source_learn,study,independent_oracle
from e14.e14y_witness import discover_one
from e14.e14u_primitive import PAIR_SPACE

class CounterexampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank=build()
        cls.row=next(x for x in cls.bank['rows'] if x['id']=='y:040')
        cls.study=study(cls.bank,indices=(cls.bank['rows'].index(cls.row),))
        cls.wrong=next(r for r in cls.study['rows'] if r['wrong_accepted']==1)

    def source(self):
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup)
        return source_learn(self.row,Path(d.name))

    def test_genuine_wrong_acceptance_is_falsifiable(self):
        witness=discover_one(self.wrong,self.source(),truth_of(self.row))
        self.assertNotEqual(witness['hypothesis_cost'],witness['oracle_cost'])
        self.assertEqual(witness['oracle_cost'],independent_oracle(
            witness['witness_graph'],PAIR_SPACE[witness['target_pair']],truth_of(self.row)))

    def test_counterexample_is_not_target_purchase(self):
        witness=discover_one(self.wrong,self.source(),truth_of(self.row))
        self.assertTrue(witness['no_frozen_target_label_was_purchased'])
        self.assertTrue(witness['counterexample_postscore_only'])

    def test_false_acceptance_requires_real_audited_journal(self):
        corrupted=copy.deepcopy(self.wrong)
        corrupted['target_journal']['purchased']+=1
        with self.assertRaises(BudgetContractError):
            discover_one(corrupted,self.source(),truth_of(self.row))

    def test_cannot_construct_witness_for_correct_accept(self):
        inrow=next(r for r in self.study['rows'] if r['wrong_accepted']==0)
        self.assertRaises(BudgetContractError,discover_one,inrow,self.source(),truth_of(self.row))

    def test_idempotent_witness_selection(self):
        s=self.source()
        a=discover_one(self.wrong,s,truth_of(self.row))
        b=discover_one(self.wrong,s,truth_of(self.row))
        self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
