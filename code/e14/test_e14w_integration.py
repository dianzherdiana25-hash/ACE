"""E1.4w end-to-end audit regression and tamper/falsification probes."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .e14_integrated_graph import DurableGraphBudget,graph_routes
from .e14_shared_budget import BudgetContractError,SharedLabelBudget
from .e14u_primitive import PAIR_SPACE
from .e14w_source import source_truth,learn,offers
from .e14w_study import (source_acquire,world,evaluate_arm,run,
                          IN_FAMILY_EXPRESSIONS,ADV_OUTSIDERS,
                          NOVEL_OUTSIDERS,CANARY,NEIGHBOR)
from .e14w_audit import audit_files,alternate_score,validate_receipts


def write_batch(path,data):
    copied=copy.deepcopy(data)
    copied.pop('sha256',None)
    raw=json.dumps(copied,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    copied['sha256']=hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(copied,sort_keys=True,indent=2))


class LineageAndScoring(unittest.TestCase):
    def test_predecessor_is_learned_separately(self):
        with tempfile.TemporaryDirectory() as t:
            record=source_acquire(0,Path(t)/'source.sqlite')
        self.assertTrue(record['correct'])
        self.assertEqual(record['source_labels'],1)
        self.assertEqual(record['source_replay'],1)
        self.assertEqual(record['pair_learned'],PAIR_SPACE[0])

    def test_one_world_has_shared_source_and_separate_target_caps(self):
        report=run(pair_indices=(0,),kinds=(IN_FAMILY_EXPRESSIONS[0],))
        self.assertEqual((report['worlds'],report['arm_count']), (1,6))
        self.assertEqual(report['source_labels'],1)
        self.assertTrue(all(r['target_labels']<=4 and
                            r['target_replays']==r['target_labels'] for r in report['rows']))

    def test_source_learning_is_independent_of_operator(self):
        with tempfile.TemporaryDirectory() as t:
            record=source_acquire(0,Path(t)/'source.sqlite')
            rows=[evaluate_arm(world(0,k),record,'synthesis-safe',Path(t)/'target.sqlite')
                  for k in IN_FAMILY_EXPRESSIONS[:2]]
        self.assertEqual([r['semantic_exact'] for r in rows],[1,1])
        self.assertEqual(record['source_labels'],1)

    def test_underidentified_motif_pair_causes_abstention(self):
        with tempfile.TemporaryDirectory() as t:
            s=source_acquire(3,Path(t)/'s.sqlite')
            self.assertFalse(s['correct'])
            r=evaluate_arm(world(3,IN_FAMILY_EXPRESSIONS[0]),s,'synthesis-safe',Path(t)/'t.sqlite')
        self.assertEqual((r['accepted'],r['target_labels']),(0,0))

    def test_safe_vs_eager_false_acceptance_is_observable(self):
        with tempfile.TemporaryDirectory() as t:
            s=source_acquire(0,Path(t)/'s.sqlite')
            w=world(0,'gap-parity')
            eager=evaluate_arm(w,s,'synthesis-eager',Path(t)/'t.sqlite')
            safe=evaluate_arm(w,s,'synthesis-safe',Path(t)/'t.sqlite')
        self.assertEqual(eager['wrong_accepted'],1)
        self.assertEqual(safe['wrong_accepted'],1)  # finite grammar is not a certificate

    def test_stress_neighbor_and_canary_show_complementary_failures(self):
        with tempfile.TemporaryDirectory() as t:
            s=source_acquire(0,Path(t)/'s.sqlite')
            w=world(0,'gap-parity')
            distant=evaluate_arm(w,s,CANARY,Path(t)/'t.sqlite')
            neighbor=evaluate_arm(w,s,NEIGHBOR,Path(t)/'t.sqlite')
        self.assertEqual(distant['wrong_accepted'],1)
        self.assertEqual(neighbor['wrong_accepted'],0)

    def test_postscore_unseen_family_breaks_neighbor(self):
        with tempfile.TemporaryDirectory() as t:
            s=source_acquire(0,Path(t)/'s.sqlite')
            w=world(0,'clamped-product')
            r=evaluate_arm(w,s,NEIGHBOR,Path(t)/'t.sqlite')
        self.assertEqual(r['wrong_accepted'],1)

    def test_original_and_expanded_source_query_pools_are_finite(self):
        self.assertEqual(len(offers()),420)
        with tempfile.TemporaryDirectory() as t:
            a=learn(0,Path(t)/'s.sqlite',mode='original')
            b=learn(0,Path(t)/'s.sqlite',mode='expanded')
        self.assertEqual((a['correct'],b['correct']),(True,True))
        self.assertLessEqual(a['labels'],4)

    def test_source_can_fail_under_four_labels_even_with_more_offers(self):
        with tempfile.TemporaryDirectory() as t:
            s=learn(6,Path(t)/'s.sqlite',mode='expanded')
        self.assertFalse(s['correct'])
        self.assertEqual(s['labels'],4)

    def test_independent_dfs_checks_actual_graph_receipts(self):
        r=run(pair_indices=(0,),kinds=(IN_FAMILY_EXPRESSIONS[0],))
        row=r['rows'][0];source=r['sources'][0]
        got=validate_receipts(row['target_journal'],PAIR_SPACE[0],row['formula'])
        self.assertEqual(got,row['target_labels'])
        got_source=validate_receipts(source['source_journal'],PAIR_SPACE[0],'source-max')
        self.assertEqual(got_source,source['source_labels'])

    def test_source_query_predictions_match_real_oracle(self):
        from .e14w_source import offers,source_truth
        for graph,predicted in offers()[::17]:
            for idx,pair in enumerate(PAIR_SPACE):
                self.assertEqual(source_truth(graph,pair),predicted[idx])

    def test_source_expansion_has_no_guaranteed_advantage(self):
        from .e14w_source_run import study as source_study
        r=source_study(indices=(0,1,2,3,4))
        self.assertEqual(r['source_worlds'],5)
        self.assertEqual(r['arms'],10)
        self.assertLessEqual(r['summary']['expanded']['solved'],5)

    def test_repeated_predecessor_queries_have_distinct_cost(self):
        with tempfile.TemporaryDirectory() as t:
            s=source_acquire(0,Path(t)/'s.sqlite')
        self.assertEqual(s['source_journal']['purchased'],len(s['source_journal']['receipts']))
        self.assertGreater(s['source_graph_cost']['edges'],0)


class EvidenceIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/'batch.json'
        r=run(pair_indices=(0,),kinds=(IN_FAMILY_EXPRESSIONS[0],ADV_OUTSIDERS[0]))
        write_batch(cls.path,r)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_complete_two_world_audit(self):
        report=audit_files([self.path])
        self.assertEqual(report['pair_sources'],1)
        self.assertEqual(report['source_oracle_replay'],1)
        self.assertEqual(report['policy_summary']['synthesis-safe:arms'],2)

    def test_modified_report_sha_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'bad.json'
            data=json.loads(self.path.read_text())
            data['rows'][0]['accepted']=1-data['rows'][0]['accepted']
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(BudgetContractError,'SHA-256'):
                audit_files([p])

    def test_attacker_rehashes_report_but_independent_score_catches(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'bad.json'
            data=json.loads(self.path.read_text())
            data['rows'][0]['wrong_accepted']=1-data['rows'][0]['wrong_accepted']
            write_batch(p,data)
            with self.assertRaises(BudgetContractError):audit_files([p])

    def test_corrupt_ledger_digest_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'bad.json'
            data=json.loads(self.path.read_text())
            target=next(r for r in data['rows'] if r['target_labels']>0)
            target['target_journal']['receipts'][0]['label_sha256']='0'*64
            write_batch(p,data)
            with self.assertRaises(BudgetContractError):audit_files([p])

    def test_forged_selfconsistent_receipt_label_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'bad.json';data=json.loads(self.path.read_text())
            target=next(r for r in data['rows'] if r['target_labels']>0)
            original=target['target_journal']
            forged=SharedLabelBudget()
            for n,row in enumerate(original['receipts']):
                rid=forged.reserve(row['stage'],row['query'],cost=row['cost'])
                y=row['label'];y=(y or 0)+1 if n==0 else y
                forged.settle(rid,y)
                for stage in row['reused_in']:forged.reuse(rid,stage)
            target['target_journal']=forged.snapshot()
            write_batch(p,data)
            with self.assertRaisesRegex(BudgetContractError,'oracle mismatch'):
                audit_files([p])

    def test_missing_one_arm_detected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'missing.json';data=json.loads(self.path.read_text())
            data['rows'].pop();data['arm_count']-=1
            write_batch(p,data)
            with self.assertRaisesRegex(BudgetContractError,'incomplete'):
                audit_files([p])

    def test_duplicate_pair_source_across_batches_detected(self):
        with self.assertRaisesRegex(BudgetContractError,'duplicate source'):
            audit_files([self.path,self.path])

    def test_false_claim_of_scientific_go_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'claim.json';data=json.loads(self.path.read_text())
            data['scientific_decision']='GO'
            write_batch(p,data)
            with self.assertRaisesRegex(BudgetContractError,'invalid evidence state'):
                audit_files([p])

if __name__=='__main__':unittest.main()
