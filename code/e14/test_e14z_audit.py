"""Tamper-evident replay and adversarial witness tests for semantic drift."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from e14.e14_shared_budget import BudgetContractError
from e14.e14y_bank import canonical,digest
from e14.e14z_drift import bank,study
from e14.e14z_audit import audit,read_scores
from e14.e14z_witness import collect

class DriftAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full=bank();cls.mini=copy.deepcopy(cls.full)
        cls.mini['rows']=cls.mini['rows'][:1]
        cls.mini['expected_arms']=20
        cls.r=study(cls.full,indices=(0,))
        cls.r['bank_sha256']=digest(cls.mini)
        cls.r.pop('sha256',None)

    def emit(self,record=None):
        if record is None:record=copy.deepcopy(self.r)
        record['sha256']=hashlib.sha256(canonical(record)).hexdigest()
        path=Path(tempfile.mkdtemp(prefix='ace-e14z-audit-test-'))/'score.json'
        self.addCleanup(lambda:__import__('shutil').rmtree(path.parent,ignore_errors=True))
        path.write_text(json.dumps(record))
        return path

    def with_audit(self,record=None):
        path=self.emit(record)
        with patch('e14.e14z_audit.bank',return_value=self.mini):
            return audit([path])

    def test_independent_receipt_reconstruction(self):
        r=self.with_audit()
        self.assertEqual((r['arms'],r['source_operators']),(20,1))
        self.assertEqual(r['source_labels_independently_recomputed'],self.r['source_labels'])
        self.assertEqual(r['target_labels_independently_replayed'],
                         sum(x['target_labels'] for x in self.r['rows']))

    def test_replay_is_deterministic(self):
        self.assertEqual(self.with_audit()['summary'],self.with_audit()['summary'])

    def test_detects_modified_score_without_new_digest(self):
        f=self.emit();r=json.loads(f.read_text());r['rows'][0]['exact']^=1;f.write_text(json.dumps(r))
        with patch('e14.e14z_audit.bank',return_value=self.mini):
            with self.assertRaisesRegex(BudgetContractError,'digest'):audit([f])

    def test_rejects_inconsistent_source_transfer_count(self):
        r=copy.deepcopy(self.r);r['sources'][0]['source_labels']+=1
        with self.assertRaisesRegex(BudgetContractError,'source replay mismatch'):
            self.with_audit(r)

    def test_rejects_source_operator_impersonation(self):
        r=copy.deepcopy(self.r);r['rows'][0]['source_program_id']+=1
        with self.assertRaisesRegex(BudgetContractError,'task drift/lineage'):
            self.with_audit(r)

    def test_rejects_target_operator_impersonation(self):
        r=copy.deepcopy(self.r);r['rows'][0]['target_program_id']+=1
        with self.assertRaisesRegex(BudgetContractError,'task drift/lineage'):
            self.with_audit(r)

    def test_detects_rehashed_but_forged_receipt_label(self):
        r=copy.deepcopy(self.r);q=next(a for a in r['rows'] if a['target_labels']>0)
        q['target_journal']['receipts'][0]['label']=123
        with self.assertRaises(BudgetContractError):self.with_audit(r)

    def test_detects_rehashed_but_wrong_reported_exactness(self):
        r=copy.deepcopy(self.r);r['rows'][0]['exact']^=1
        with self.assertRaises(BudgetContractError):self.with_audit(r)

    def test_hindsight_witnesses_are_not_scored_label_purchases(self):
        path=self.emit()
        with patch('e14.e14z_audit.bank',return_value=self.mini),patch(
             'e14.e14z_witness.bank',return_value=self.mini):
            result=collect([path])
        self.assertGreater(result['false_acceptances_proved'],0)
        self.assertEqual(result['additional_purchased_target_labels'],0)
        self.assertEqual(result['additional_auditor_oracle_calls'],result['false_acceptances_proved'])

    def test_invalid_drift_stratum_fails_closed(self):
        r=copy.deepcopy(self.r);r['rows'][0]['drift_type']='mystery'
        with self.assertRaises(BudgetContractError):self.with_audit(r)

if __name__=='__main__':unittest.main()
