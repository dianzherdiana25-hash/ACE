"""Stress tests for generalization across *input values*, not mechanisms."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from .candidate_input_stress import run_stress, STRESS_PAIRS, ORIGINAL_PAIRS

P=Path(__file__).parent

class StressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ast=json.loads((P/'candidate_selected_asts.json').read_text())
        cls.score=json.loads((P/'candidate_search_snapshot.json').read_text())
        cls.report=run_stress(cls.ast,cls.score)

    def test_1024_new_value_predictions(self):
        self.assertEqual(self.report['prediction_rows'],1024)
        self.assertEqual(self.report['original_holdout_unique_input_pairs'],3)
        self.assertEqual(self.report['claim_scope'],'KNOWN_MECHANISMS_NEW_PUBLIC_INPUTS')

    def test_values_disjoint_from_original(self):
        self.assertEqual(len(STRESS_PAIRS),16)
        self.assertFalse(set(STRESS_PAIRS)&set(ORIGINAL_PAIRS))
        self.assertEqual(len(set(STRESS_PAIRS)),16)

    def test_standard_solved_task_counts(self):
        b=self.report['by_budget']['standard']
        self.assertEqual([b[mode]['fully_solved_tasks'] for mode in ('fixed','fixed-list','enumerate','beam')],[0,1,5,6])
        self.assertEqual([b[mode]['total_correct'] for mode in ('fixed','fixed-list','enumerate','beam')],[17,32,87,104])

    def test_tight_solved_task_counts(self):
        b=self.report['by_budget']['tight']
        self.assertEqual([b[mode]['fully_solved_tasks'] for mode in ('fixed','fixed-list','enumerate','beam')],[0,1,0,0])
        self.assertEqual([b[mode]['total_correct'] for mode in ('fixed','fixed-list','enumerate','beam')],[17,32,21,21])

    def test_unseen_family_claim_not_emitted(self):
        self.assertEqual(self.report['scientific_claim'],'NOT_CONFIRMED')
        self.assertNotIn('UNSEEN_FAMILY',self.report['claim_scope'])

    def test_bank_leakage_rejected(self):
        with self.assertRaisesRegex(ValueError,'leaked original'):
            run_stress(self.ast,self.score,pairs=STRESS_PAIRS[:-1]+(ORIGINAL_PAIRS[0],))

    def test_duplicate_new_input_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            run_stress(self.ast,self.score,pairs=STRESS_PAIRS[:-1]+(STRESS_PAIRS[0],))

    def test_float_and_boolean_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError,'invalid stress coordinate'):
            run_stress(self.ast,self.score,pairs=STRESS_PAIRS[:-1]+((True,2),))
        with self.assertRaisesRegex(ValueError,'invalid stress coordinate'):
            run_stress(self.ast,self.score,pairs=STRESS_PAIRS[:-1]+((1.5,2),))

    def test_changed_frozen_ast_rejected_before_stress(self):
        a=deepcopy(self.ast)
        a['asts'][0][0]='sub'
        with self.assertRaisesRegex(ValueError,'AST identity mismatch'):
            run_stress(a,self.score)

    def test_modified_source_score_rejected_before_stress(self):
        s=deepcopy(self.score)
        s['arms']['standard']['beam']['correct'][1]=2
        with self.assertRaisesRegex(ValueError,'semantic replay mismatch|contradictory'):
            run_stress(self.ast,s)

if __name__=='__main__':unittest.main()
