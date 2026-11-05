"""Negative controls for exact public, per-case semantic audit of ACE search."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from .candidate_case_replay import (replay, interpret_ast, ast_id, verify_original_source,
                                    HOLDOUT_PAIRS)

ROOT=Path(__file__).parent

class CaseReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ast=json.loads((ROOT/'candidate_selected_asts.json').read_text())
        cls.scores=json.loads((ROOT/'candidate_search_snapshot.json').read_text())

    def test_all_192_public_predictions_reproduced(self):
        a=replay(self.ast,self.scores)
        self.assertTrue(a['all_claimed_aggregates_match'])
        self.assertEqual((a['runs_replayed'],a['case_predictions_replayed'],a['replayed_correct_cases']),
                         (64,192,47))
        self.assertEqual(a['scientific_claim'],'NOT_CONFIRMED')

    def test_only_three_distinct_holdout_coordinates(self):
        a=replay(self.ast,self.scores)
        self.assertEqual(len({(r['x'],r['y']) for r in a['cases']}),3)
        self.assertEqual(a['distinct_holdout_input_pairs'],3)
        self.assertEqual(len(HOLDOUT_PAIRS),3)

    def test_negative_linear_pair_concrete_counterexample(self):
        a=replay(self.ast,self.scores)
        b=[r for r in a['cases'] if r['budget']=='standard' and r['task']=='negative_linear']
        enum=[r for r in b if r['mode']=='enumerate']
        beam=[r for r in b if r['mode']=='beam']
        self.assertEqual([r['predicted'] for r in enum],[19,-15,18])
        self.assertEqual([r['expected'] for r in beam],[26,-21,15])
        self.assertTrue(all(r['correct'] for r in beam))

    def test_ast_digest_matches_committed_selector_ids(self):
        self.assertEqual(len(self.ast['asts']),19)
        for tree,ident in zip(self.ast['asts'],self.ast['ids']):
            self.assertEqual(ast_id(tree),ident)

    def test_changed_ast_without_matching_identity_rejected(self):
        a=deepcopy(self.ast)
        a['asts'][0][0]='sub'
        with self.assertRaisesRegex(ValueError,'AST identity mismatch'):
            replay(a,self.scores)

    def test_changed_ast_and_self_claimed_id_still_fails_scores(self):
        a=deepcopy(self.ast)
        a['asts'][0][0]='mul'
        a['ids'][0]=ast_id(a['asts'][0])
        with self.assertRaisesRegex(ValueError,'semantic replay mismatch'):
            replay(a,self.scores)

    def test_work_budget_forgery_rejected_before_replay(self):
        s=deepcopy(self.scores)
        s['arms']['tight']['beam']['total_work'][0]=301
        with self.assertRaisesRegex(ValueError,'bound|budget'):
            replay(self.ast,s)

    def test_manipulated_correctness_detected(self):
        s=deepcopy(self.scores)
        s['arms']['standard']['beam']['correct'][1]=2
        with self.assertRaisesRegex(ValueError,'semantic replay mismatch|contradictory'):
            replay(self.ast,s)

    def test_manipulated_absolute_error_detected(self):
        s=deepcopy(self.scores)
        s['arms']['tight']['enumerate']['absolute_error'][0]+=1
        with self.assertRaisesRegex(ValueError,'semantic replay mismatch|contradictory'):
            replay(self.ast,s)

    def test_ast_index_boolean_rejected(self):
        a=deepcopy(self.ast)
        a['by_budget']['tight']['beam'][0]=False
        with self.assertRaisesRegex(ValueError,'invalid AST index'):
            replay(a,self.scores)

    def test_rejected_arbitrary_code_and_invalid_arity(self):
        with self.assertRaisesRegex(ValueError,'forbidden AST'):
            interpret_ast(['call','os.system',[]],1,2)
        with self.assertRaisesRegex(ValueError,'forbidden AST'):
            interpret_ast(['add',None,[['var','x',[]]]],1,2)

    def test_rejected_boolean_constants(self):
        with self.assertRaisesRegex(ValueError,'invalid constant'):
            interpret_ast(['const',True,[]],1,2)

    def test_overdepth_and_overoperations_rejected(self):
        expr=['var','x',[]]
        for _ in range(5):
            expr=['add',None,[expr,['var','y',[]]]]
        with self.assertRaisesRegex(ValueError,'deep AST'):
            interpret_ast(expr,1,2)

    def test_untrusted_modified_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'pinned'):
            verify_original_source(b'{}',self.ast,self.scores)

    def test_forged_source_commit_rejected(self):
        a=deepcopy(self.ast)
        a['source_commit']='0'*40
        with self.assertRaisesRegex(ValueError,'source mismatch'):
            replay(a,self.scores)

    def test_mismatched_task_order_rejected(self):
        a=deepcopy(self.ast)
        a['task_order'].reverse()
        with self.assertRaisesRegex(ValueError,'task order'):
            replay(a,self.scores)

if __name__=='__main__': unittest.main()
