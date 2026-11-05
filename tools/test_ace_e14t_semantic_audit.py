"""Adversarial edits against postscore exact-word and probe semantic audit."""
import copy
import unittest
from pathlib import Path

from tools.ace_e14t_semantic_audit import inspect,load

ROOT=Path(__file__).resolve().parents[1]


class SemanticReceiptAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank,cls.report=load(ROOT/'evidence/e14/e14t_public_bank_v1.json.gz',
                                 ROOT/'WORK/e14t-score.json.gz')
        cls.ledger=ROOT/'WORK/e14t-score.sqlite'

    def test_all_240_arms_and_exact_false_accept(self):
        result=inspect(self.bank,self.report,self.ledger)
        self.assertEqual(result['status'],'SEMANTIC_AUDIT_PASS')
        self.assertEqual(result['arms'],240)
        self.assertEqual(result['wrong_exact_total'],1)
        self.assertEqual(result['probe_indistinguishable_wrong_exact'],1)
        self.assertEqual(result['accepted_wrong_exact_cases'][0]['arm'],'rare:10:integrated')

    def test_postscore_witness_falsifies_the_wrong_exact_motif(self):
        audit=inspect(self.bank,self.report,self.ledger)
        case=audit['accepted_wrong_exact_cases'][0]
        self.assertEqual(case['probe_errors'],0)
        witness=case['postscore_distinguishing_witness']
        self.assertIsNone(witness['truth_label'])
        self.assertEqual(witness['hypothesis_label'],8)
        self.assertEqual(witness['postscore_counterfactual_oracle_calls'],2)
        self.assertEqual(len(witness['query_sha256']),64)

    def test_no_other_exact_motif_errors(self):
        audit=inspect(self.bank,self.report,self.ledger)
        self.assertEqual(sum(v['wrong_exact'] for cell in audit['cells'].values()
                             for v in cell.values()),1)

    def test_score_and_replay_identical_semantic_alias(self):
        replay=load(ROOT/'evidence/e14/e14t_public_bank_v1.json.gz',
                    ROOT/'WORK/e14t-replay.json.gz')[1]
        result=inspect(self.bank,replay,ROOT/'WORK/e14t-replay.sqlite')
        self.assertEqual(result['wrong_exact_total'],1)
        self.assertEqual(result['accepted_wrong_exact_cases'][0]['arm'],'rare:10:integrated')

    def tamper(self,change):
        data=copy.deepcopy(self.report)
        change(data)
        with self.assertRaises(ValueError):
            inspect(self.bank,data,self.ledger)

    def test_bad_exact_label_fails(self):
        def corrupt(data):
            r=next(r for r in data['rows'] if r['arm']=='rare:10:integrated')
            r['word_correct']=1
        self.tamper(corrupt)

    def test_bad_probe_tally_fails(self):
        def corrupt(data):
            r=next(r for r in data['rows'] if r['arm']=='reachable:00:integrated')
            r['errors']+=1
        self.tamper(corrupt)

    def test_false_terminal_motif_fails(self):
        def corrupt(data):
            r=next(r for r in data['rows'] if r['arm']=='reachable:00:integrated')
            r['trace'][-1]['metadata']['word']=[1]*8
        self.tamper(corrupt)

    def test_invalid_receipt_id_fails(self):
        def corrupt(data):
            r=next(r for r in data['rows'] if r['arm']=='reachable:00:integrated')
            r['trace'][0]['receipt_id']='q9999'
        self.tamper(corrupt)

    def test_forged_query_label_fails(self):
        def corrupt(data):
            r=next(r for r in data['rows'] if r['arm']=='reachable:00:integrated')
            r['trace'][0]['label']=12345
        self.tamper(corrupt)

    def test_crediting_abstention_fails(self):
        def corrupt(data):
            r=next(r for r in data['rows'] if r['arm']=='natural:00:integrated')
            r['correct']=6
        self.tamper(corrupt)

    def test_missing_arm_fails(self):
        self.tamper(lambda data:data['rows'].pop())


if __name__=='__main__':
    unittest.main()
