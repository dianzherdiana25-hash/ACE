"""Regression and falsification tests for constructive nonidentifiability."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from .e14_integrated_graph import DurableGraphBudget, purchase
from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_SPACE
from .e14w_synthesis import library, render, motif_query, target_for
from .e14w_study import source_acquire, world, evaluate_arm, IN_FAMILY_EXPRESSIONS
from .e14x_identifiability import build_certificate, measured_costs, audit_reports


class CountermodelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.db=Path(cls.temp.name)/'journal.sqlite'
        cls.source=source_acquire(0,cls.db)
        cls.world=world(0,IN_FAMILY_EXPRESSIONS[0])
        cls.row=evaluate_arm(cls.world,cls.source,'synthesis-safe',cls.db)
        assert cls.row['semantic_exact']==1

    def test_counterexample_exists_and_is_legal(self):
        c=build_certificate(self.row,PAIR_SPACE[0])
        self.assertEqual(c['status'] if 'status' in c else c['outcome'],
                         'INDISTINGUISHABLE_WITHIN_PURCHASED_INTERVENTIONS')
        self.assertEqual(c['adversarial_cost']-c['original_cost'],1)
        self.assertGreaterEqual(c['unmeasured_domain_points'],116)

    def test_witness_not_purchased(self):
        c=build_certificate(self.row,PAIR_SPACE[0])
        witnessed=tuple(c['witness_route_costs'])
        self.assertTrue(all(witnessed not in measured_costs(r['query'],PAIR_SPACE[0])
                            for r in self.row['target_journal']['receipts']))

    def test_deterministic_certificate(self):
        self.assertEqual(build_certificate(self.row,PAIR_SPACE[0]),
                         build_certificate(self.row,PAIR_SPACE[0]))

    def test_certificates_require_real_acceptance(self):
        bad=copy.deepcopy(self.row)
        bad['semantic_exact']=0
        with self.assertRaises(BudgetContractError):build_certificate(bad,PAIR_SPACE[0])
        bad=copy.deepcopy(self.row)
        bad['accepted']=False
        with self.assertRaises(BudgetContractError):build_certificate(bad,PAIR_SPACE[0])

    def test_corrupted_journal_cannot_be_certified(self):
        bad=copy.deepcopy(self.row)
        bad['target_journal']['receipts'][0]['label']=111
        with self.assertRaises(BudgetContractError):build_certificate(bad,PAIR_SPACE[0])

    def test_witness_replay_reproduces_same_selected_program(self):
        """The same deterministic policy sees unchanged labels and reaccepts."""
        c=build_certificate(self.row,PAIR_SPACE[0])
        true_ast=next(t for t in library(5) if render(t)==self.row['selected_expr'])
        key=tuple(c['witness_route_costs'])
        pair=PAIR_SPACE[0]
        def patched(g):
            points=measured_costs(g,pair)
            return min((__import__('e14.e14w_synthesis',fromlist=['evaluate']).evaluate(true_ast,*p)
                        +int(p==key) for p in points),default=None)
        w=dict(self.world)
        w['oracle']=patched
        with tempfile.TemporaryDirectory() as tmp:
            replay=evaluate_arm(w,self.source,'synthesis-safe',Path(tmp)/'new.sqlite')
        self.assertEqual([r['label'] for r in replay['target_journal']['receipts']],
                         [r['label'] for r in self.row['target_journal']['receipts']])
        self.assertEqual(replay['selected_expr'],self.row['selected_expr'])
        self.assertEqual(replay['accepted'],1)
        self.assertEqual(replay['semantic_exact'],0)
        self.assertEqual(replay['wrong_accepted'],1)

    def test_pair_wrong_type_not_accepted(self):
        with self.assertRaises(BudgetContractError):build_certificate(self.row,((True,2,1),PAIR_SPACE[0][1]))

    def test_report_digest_must_match(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'bad.json';p.write_text(json.dumps({'sha256':'no','rows':[]}))
            with self.assertRaises(BudgetContractError):audit_reports([p])

    def test_original_question_domain_is_bounded(self):
        for r in self.row['target_journal']['receipts']:
            for lo,hi in measured_costs(r['query'],PAIR_SPACE[0]):
                self.assertTrue(4<=lo<=hi<=18)

if __name__=='__main__':unittest.main()
