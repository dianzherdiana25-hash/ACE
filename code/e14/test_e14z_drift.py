"""Prescore tests for deterministic distance-selected semantic drift controls."""
import copy
import tempfile
import unittest
from pathlib import Path
from e14.e14_shared_budget import BudgetContractError
from e14.e14y_bank import build as old_build,digest
from e14.e14y_induction import grammar
from e14.e14z_drift import (bank,mismatches,source_row,target_row,study,
                              TARGET_PAIRS,MODES)

class DriftBankTests(unittest.TestCase):
    def test_repeatability_and_nonreuse_of_original_truths(self):
        self.assertEqual(bank(),bank())
        old={r['program_id'] for r in old_build()['rows'] if r['program_id'] is not None}
        self.assertTrue(all(r['source_program_id'] not in old for r in bank()['rows']))

    def test_near_vs_far_semantically_different(self):
        for entry in bank()['rows']:
            self.assertLess(entry['near_disagreements'],entry['far_disagreements'])
            self.assertEqual(entry['near_disagreements'],mismatches(
                entry['source_program_id'],entry['near_target_program_id']))
            self.assertEqual(entry['far_disagreements'],mismatches(
                entry['source_program_id'],entry['far_target_program_id']))

    def test_exact_prescore_expected_arms(self):
        b=bank();self.assertEqual(b['expected_arms'],400)
        self.assertEqual((len(b['rows']),len(TARGET_PAIRS),len(MODES)),(20,2,5))

    def test_distinct_lineage_and_target_ids(self):
        ids=set()
        for entry in bank()['rows']:
            ids.add(source_row(entry)['id'])
            a=target_row(entry,'near');c=target_row(entry,'far')
            self.assertNotEqual(a['id'],c['id'])
            self.assertNotEqual(a['program_id'],c['program_id'])
        self.assertEqual(len(ids),20)

    def test_invalid_drift_name_rejected(self):
        self.assertRaises(BudgetContractError,target_row,bank()['rows'][0],'novel')

    def test_mutated_bank_refuses_to_score(self):
        b=bank();b['rows'][0]['near_target_program_id']+=1
        self.assertRaises(BudgetContractError,study,b,indices=(0,))

    def test_one_source_reused_across_four_target_worlds(self):
        r=study(bank(),indices=(0,))
        self.assertEqual((r['source_operator_count'],r['target_worlds'],r['arm_count']),
                         (1,4,20))
        self.assertEqual(r['source_labels'],r['source_replayed'])
        self.assertEqual(len(r['sources']),1)
        for arm in r['rows']:
            self.assertLessEqual(arm['target_labels'],4)
            self.assertEqual(arm['target_labels'],arm['target_replayed'])

    def test_near_drift_is_not_universal_certification(self):
        r=study(bank(),indices=(0,))
        self.assertEqual(r['summary']['near']['transfer-direct']['wrong_accepted'],2)
        self.assertEqual(r['summary']['far']['transfer-verify2']['abstain'],2)

    def test_target_predictions_not_credited_when_abstaining(self):
        r=study(bank(),indices=(0,))
        for row in r['rows']:
            if row['abstain']:
                self.assertEqual(row['accepted_probes'],0)
                self.assertEqual(row['probe_errors'],0)

    def test_source_and_target_grounded_in_same_frozen_candidate_vocabulary(self):
        for row in bank()['rows']:
            for key in ('source_program_id','near_target_program_id','far_target_program_id'):
                self.assertLess(row[key],len(grammar()))
                self.assertGreaterEqual(row[key],0)

if __name__=='__main__':unittest.main()
