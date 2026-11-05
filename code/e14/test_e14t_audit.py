"""Full score/replay/audit miniature for fresh E1.4t development bank."""
import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from .e14t_bank import SEED, audit_bank, sha
from .e14t_run import freeze,load_locked,run,encoded,MODES
from .e14t_audit import audit,compare_replay,open_report

REPO=Path(__file__).resolve().parents[2]


class E14TAuditIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.folder=Path(cls.tmp.name)
        cls.lock=cls.folder/'locked.json'
        cls.bank=cls.folder/'bank.json.gz'
        cls.score=cls.folder/'score.json.gz'
        cls.replay=cls.folder/'replay.json.gz'
        cls.score_db=cls.folder/'score.sqlite'
        cls.replay_db=cls.folder/'replay.sqlite'
        cls.frozen=freeze(REPO,cls.lock,cls.bank,seed=SEED+17,per_stratum=1)
        cls.scored=run(REPO,cls.lock,cls.bank,cls.score_db,cls.score)
        cls.replayed=run(REPO,cls.lock,cls.bank,cls.replay_db,cls.replay)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_frozen_bank_is_readback_identical(self):
        bank,lock=load_locked(REPO,self.lock,self.bank)
        self.assertEqual(audit_bank(bank)['bank_sha256'],lock['bank_sha256'])
        self.assertEqual(len(bank['worlds']),4)
        self.assertEqual(len(lock['files_sha256']),len(set(lock['files_sha256'])))

    def test_freeze_refuses_overwrite(self):
        with self.assertRaises(FileExistsError):
            freeze(REPO,self.lock,self.bank)

    def test_modified_protocol_hash_rejected(self):
        lock=json.loads(self.lock.read_text())
        lock['files_sha256']['code/e14/e14t_worker.py']='f'*64
        rogue=self.folder/'bad.lock'
        rogue.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError,'changed source after lock'):
            load_locked(REPO,rogue,self.bank)

    def test_bank_tamper_rejected(self):
        bad=self.folder/'bad.bank.gz'
        payload=json.loads(gzip.decompress(self.bank.read_bytes()))
        payload['worlds'][0]['target'][0]=3-payload['worlds'][0]['target'][0]
        bad.write_bytes(gzip.compress(encoded(payload),mtime=0))
        with self.assertRaisesRegex(ValueError,'bank mismatch'):
            load_locked(REPO,self.lock,bad)

    def test_full_score_and_fresh_replay_agree_deterministically(self):
        result=compare_replay(self.score,self.replay)
        self.assertEqual(result['status'],'REPLAY_PASS')
        self.assertEqual(result['matched_arms'],4*len(MODES))

    def test_independent_oracle_audit_score(self):
        result=audit(REPO,self.bank,self.lock,self.score_db,self.score)
        self.assertEqual(result['status'],'AUDIT_PASS')
        self.assertEqual(result['arms'],20)
        self.assertTrue(result['all_resource_costs_valid'])

    def test_independent_oracle_audit_replay(self):
        self.assertEqual(audit(REPO,self.bank,self.lock,self.replay_db,self.replay)['arms'],20)

    def test_bounded_oracle_costs_and_abstentions(self):
        report=open_report(self.score)
        self.assertEqual(report['summary']['scientific_decision'],'NOT_ASSESSED')
        for row in report['rows']:
            self.assertLessEqual(row['purchased'],4)
            if row['final_action']=='abstain':
                self.assertEqual(row['covered'],0)
            self.assertEqual(row['purchased'],row['auditor_calls'])

    def test_corrupt_summary_detected(self):
        report=copy.deepcopy(open_report(self.score))
        report['summary']['total_target_intervention_labels']+=1
        bad=self.folder/'bad.summary.gz'
        bad.write_bytes(gzip.compress(encoded(report),mtime=0))
        with self.assertRaisesRegex(ValueError,'summary mismatches'):
            audit(REPO,self.bank,self.lock,self.score_db,bad)

    def test_replay_corruption_detected(self):
        report=copy.deepcopy(open_report(self.replay))
        report['rows'][0]['purchased']+=1
        bad=self.folder/'bad.replay.gz'
        bad.write_bytes(gzip.compress(encoded(report),mtime=0))
        with self.assertRaisesRegex(ValueError,'deterministic fields mismatch'):
            compare_replay(self.score,bad)

    def test_repeat_run_from_terminal_cache_has_no_label_effect(self):
        again=run(REPO,self.lock,self.bank,self.score_db,self.folder/'cached.json.gz')
        fields=('purchased','word_correct','covered','correct','errors','receipt_sha256')
        a=self.scored['rows'];b=again['rows']
        for x,y in zip(a,b):
            self.assertTrue(all(x[k]==y[k] for k in fields))


if __name__=='__main__':
    unittest.main()
