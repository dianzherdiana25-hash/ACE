import copy
import tempfile
import unittest
from pathlib import Path
from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_SPACE
from .e14w_study import source_acquire,world,evaluate_arm,IN_FAMILY_EXPRESSIONS
from .e14x_assumption_contract import scoped_claim,compare_archived

class ClaimScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        db=Path(cls.tmp.name)/'db.sqlite'
        cls.source=source_acquire(0,db)
        cls.w=world(0,IN_FAMILY_EXPRESSIONS[0])
        cls.row=evaluate_arm(cls.w,cls.source,'synthesis-safe',db)
        cls.pair=PAIR_SPACE[0]

    def test_conditional_acceptance_is_explicit(self):
        result=scoped_claim(self.row['target_journal'],self.pair,self.row['selected_expr'])
        self.assertEqual(result['decision'],'accept_conditional')
        self.assertTrue(result['assumptions']['grammar_complete'])
        self.assertTrue(result['not_a_probability'])

    def test_open_world_requires_abstention(self):
        result=scoped_claim(self.row['target_journal'],self.pair,self.row['selected_expr'],scope='open-world-unrestricted')
        self.assertEqual(result['decision'],'abstain')
        self.assertEqual(result['reason'],'UNRESTRICTED_OPERATOR_NOT_IDENTIFIABLE')
        self.assertEqual(result['unmeasured_domain_points'],117)

    def test_no_spent_label_for_scope_change(self):
        before=copy.deepcopy(self.row['target_journal'])
        scoped_claim(before,self.pair,self.row['selected_expr'],scope='open-world-unrestricted')
        self.assertEqual(before,self.row['target_journal'])

    def test_unknown_scope_fails_closed(self):
        with self.assertRaises(BudgetContractError):
            scoped_claim(self.row['target_journal'],self.pair,self.row['selected_expr'],scope='universal-truth')

    def test_wrong_expression_not_certified(self):
        r=scoped_claim(self.row['target_journal'],self.pair,'forged')
        self.assertEqual(r['decision'],'abstain')

    def test_tampered_journal_not_certified(self):
        data=copy.deepcopy(self.row['target_journal']);data['receipts'][0]['label']=999
        with self.assertRaises(BudgetContractError):
            scoped_claim(data,self.pair,self.row['selected_expr'])

    def test_missing_predecessor_forces_abstain(self):
        row={**self.row,'accepted':0,'selected_expr':None}
        source={**self.source,'pair_learned':None}
        out=compare_archived([row],[source])
        self.assertEqual(out['bounded-dsl-assumed']['abstain'],1)
        self.assertEqual(out['open-world-unrestricted']['abstain'],1)

    def test_boolean_motif_does_not_pass_type_check(self):
        original=self.pair
        bad=((True,*original[0][1:]),original[1])
        with self.assertRaises(BudgetContractError):
            scoped_claim(self.row['target_journal'],bad,self.row['selected_expr'])

    def test_one_case_matrix_has_clear_tradeoff(self):
        cells=compare_archived([self.row],[self.source])
        self.assertEqual(cells['bounded-dsl-assumed']['accepted'],1)
        self.assertEqual(cells['open-world-unrestricted']['accepted'],0)

if __name__=='__main__':unittest.main()
