"""Postscore audit accepts only complete, truthful, tamper-free receipt evidence."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from e14.e14_shared_budget import BudgetContractError
from e14.e14y_bank import build,canonical,digest
from e14.e14y_study import study
from e14.e14y_audit import audit_files,unpack_costs,reconstruct
from e14.e14u_primitive import PAIR_SPACE

class AuditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank=build();cls.mini=copy.deepcopy(cls.bank)
        cls.mini['rows']=cls.mini['rows'][:1]
        cls.mini['strata_counts']={'residual':1,'threshold':0,'unrepresented':0}
        cls.raw=study(cls.bank,indices=(0,))
        cls.raw['bank_sha256']=digest(cls.mini)
        cls.raw.pop('sha256',None)

    def single(self,report=None):
        if report is None:report=copy.deepcopy(self.raw)
        report['sha256']=hashlib.sha256(canonical(report)).hexdigest()
        return report

    def audit(self,report):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'score.json';p.write_text(json.dumps(report))
            with patch('e14.e14y_audit.build',return_value=self.mini):
                return audit_files([p])

    def test_full_mini_audit_reconstructs_every_claim(self):
        result=self.audit(self.single())
        self.assertEqual((result['source_operators'],result['arms']),(1,10))
        self.assertEqual(result['source_labels_recomputed'],self.raw['source_labels'])
        self.assertEqual(result['target_labels_independently_replayed'],
                         sum(r['target_labels'] for r in self.raw['rows']))

    def test_deterministic_repeat(self):
        self.assertEqual(self.audit(self.single())['summary'],
                         self.audit(self.single())['summary'])

    def test_rejects_hash_tamper(self):
        r=self.single();r['rows'][0]['probe_errors']+=1
        with self.assertRaisesRegex(BudgetContractError,'digest'):
            self.audit(r)

    def test_rejects_forged_receipt_label_even_if_outer_report_rehashed(self):
        r=copy.deepcopy(self.raw)
        row=next(q for q in r['rows'] if q['target_labels'])
        row['target_journal']['receipts'][0]['label']=999
        with self.assertRaises(BudgetContractError):self.audit(self.single(r))

    def test_rejects_wrong_exact_claim(self):
        r=copy.deepcopy(self.raw);r['rows'][0]['exact']^=1
        r['summary'][r['rows'][0]['mode']]['exact']+=1 if r['rows'][0]['exact']==1 else -1
        with self.assertRaisesRegex(BudgetContractError,'semantic or scoring tamper'):
            self.audit(self.single(r))

    def test_rejects_wrong_accepted_probe_error(self):
        r=copy.deepcopy(self.raw);r['rows'][0]['probe_errors']+=1
        r['summary'][r['rows'][0]['mode']]['probe_errors']+=1
        with self.assertRaisesRegex(BudgetContractError,'semantic or scoring tamper'):
            self.audit(self.single(r))

    def test_rejects_fake_summary(self):
        r=copy.deepcopy(self.raw);r['summary']['cold-old']['wrong_accepted']+=1
        with self.assertRaisesRegex(BudgetContractError,'summary corruption'):
            self.audit(self.single(r))

    def test_rejects_duplicate_world_arm(self):
        r=copy.deepcopy(self.raw);r['rows'][1]['mode']=r['rows'][0]['mode']
        with self.assertRaisesRegex(BudgetContractError,'duplicate target arm'):
            self.audit(self.single(r))

    def test_rejects_inflated_source_cost(self):
        r=copy.deepcopy(self.raw);r['sources'][0]['source_labels']+=1
        with self.assertRaisesRegex(BudgetContractError,'source acquisition mismatch'):
            self.audit(self.single(r))

    def test_rejects_wrong_target_pair(self):
        r=copy.deepcopy(self.raw);r['rows'][0]['target_pair']=self.bank['target_pair_indices'][1]
        with self.assertRaises(BudgetContractError):self.audit(self.single(r))

    def test_rejects_nonquery_probe_graph_as_purchased_intervention(self):
        r=copy.deepcopy(self.raw)
        purchased=next(q for q in r['rows'] if q['target_labels'])
        from e14.e14y_study import heldout_probes
        from e14.e14_integrated_graph import graph_cost
        from e14.e14_shared_budget import SharedLabelBudget
        g=heldout_probes({'id':purchased['world']},purchased['target_pair'])[0]
        pair=PAIR_SPACE[purchased['target_pair']]
        with self.assertRaisesRegex(BudgetContractError,'heldout query costs'):
            unpack_costs(g,pair)

if __name__=='__main__':unittest.main()
