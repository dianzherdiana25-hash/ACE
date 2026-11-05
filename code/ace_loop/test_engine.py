"""Bounded, crash-safe E1.5 research-loop engineering tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .engine import ResearchEngine, ResearchIntegrityError, HashLedger, Policy, _metrics, digest, canonical
from .operators import OperatorAdapter


class OperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter=OperatorAdapter(sizes=(8,5,5))

    def test_bank_disjoint_and_deterministic(self):
        a=self.adapter.bank_manifest()
        b=OperatorAdapter(sizes=(8,5,5)).bank_manifest()
        self.assertEqual(a,b)
        groups=[set(self.adapter.task_ids(s)) for s in ('train','validation','test')]
        self.assertFalse(groups[0]&groups[1]);self.assertFalse(groups[0]&groups[2]);self.assertFalse(groups[1]&groups[2])

    def test_no_witness_assumed_from_coverage(self):
        v=self.adapter.evaluate(Policy('fixed',1,1),'validation')
        self.assertEqual(v['worlds'],5)
        self.assertEqual(v['accepted_correct']+v['accepted_wrong']+v['abstained'],5)

    def test_controlled_policy_improvement_search_space(self):
        self.assertEqual(len(ResearchEngine.proposals()),12)
        self.assertIn(Policy('active',4,2),ResearchEngine.proposals())
        self.assertNotIn(Policy('fixed',1,1),ResearchEngine.proposals())

    def test_reject_untyped_configuration(self):
        for kwargs in ({'selector':'oracle','label_cap':1,'min_evidence':1},
                       {'selector':'active','label_cap':True,'min_evidence':1},
                       {'selector':'fixed','label_cap':2,'min_evidence':3}):
            with self.assertRaises(ResearchIntegrityError):Policy(**kwargs)

    def test_cost_conservation_and_penalties(self):
        row={'accepted_correct':1,'accepted_wrong':0,'abstained':0,'logical_labels':2,'probe_errors':0}
        self.assertEqual(_metrics([row])['utility_units'],18)
        other=dict(row,accepted_correct=0,accepted_wrong=1,probe_errors=6)
        self.assertLess(_metrics([other])['utility_units'],0)

    def test_invalid_metrics_rejected(self):
        bad={'accepted_correct':1,'accepted_wrong':1,'abstained':0,'logical_labels':2,'probe_errors':0}
        with self.assertRaises(ResearchIntegrityError):_metrics([bad])


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_fsync_append_replay(self):
        l=HashLedger(self.root/'x.jsonl');l.append('a',{'n':0});l.append('b',{'n':1})
        self.assertEqual(len(HashLedger(self.root/'x.jsonl').events),2)
        self.assertEqual(l.events[1]['prev'],l.events[0]['sha256'])

    def test_tamper_digest_rejected(self):
        p=self.root/'x.jsonl';HashLedger(p).append('a',{'n':0})
        p.write_bytes(p.read_bytes().replace(b'"n":0',b'"n":1'))
        with self.assertRaisesRegex(ResearchIntegrityError,'digest'):HashLedger(p)

    def test_tamper_sequence_rejected(self):
        p=self.root/'x.jsonl';HashLedger(p).append('a',{'n':0})
        row=json.loads(p.read_text());row['seq']=True
        p.write_bytes(canonical(row)+b'\n')
        with self.assertRaises(ResearchIntegrityError):HashLedger(p)

    def test_truncated_line_blocks_resume(self):
        p=self.root/'x.jsonl';HashLedger(p).append('a',{'n':0})
        with p.open('ab') as f:f.write(b'{bad')
        with self.assertRaisesRegex(ResearchIntegrityError,'truncated'):HashLedger(p)

    def test_symlink_journal_blocked(self):
        p=self.root/'x.jsonl';other=self.root/'other';other.write_text('secret')
        p.symlink_to(other)
        with self.assertRaisesRegex(ResearchIntegrityError,'symlink'):HashLedger(p)
        self.assertEqual(other.read_text(),'secret')


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.adapter=OperatorAdapter(sizes=(8,5,5))

    def new(self,**opts):
        return ResearchEngine(self.root/'one',self.adapter,max_cycles=6,patience=5,**opts)

    def test_full_run_one_holdout(self):
        e=self.new();r=e.run()
        self.assertEqual(r['status'],'COMPLETE_PUBLIC_DEVELOPMENT')
        self.assertEqual(r['scientific_decision'],'NOT_ASSESSED')
        self.assertEqual(r['holdout']['worlds'],5)
        self.assertEqual(sum(x['kind']=='completed' for x in e.ledger.events),1)

    def test_repeat_idempotent(self):
        a=self.new().run();before=(self.root/'one'/'events.jsonl').read_bytes()
        b=self.new().run()
        self.assertEqual(a,b)
        self.assertEqual(before,(self.root/'one'/'events.jsonl').read_bytes())

    def test_checkpoint_resume_matches_uninterrupted(self):
        a=self.new().run(stop_after_trials=2)
        self.assertEqual(a['status'],'PAUSED_CHECKPOINT')
        first=self.new().run()
        uninterrupted=ResearchEngine(self.root/'other',OperatorAdapter(sizes=(8,5,5)),max_cycles=6,patience=5).run()
        self.assertEqual(first,uninterrupted)
        self.assertEqual((self.root/'one'/'events.jsonl').read_bytes(),
                         (self.root/'other'/'events.jsonl').read_bytes())

    def test_config_change_fails_before_evaluation(self):
        self.new().run(stop_after_trials=1)
        with self.assertRaisesRegex(ResearchIntegrityError,'config'):
            ResearchEngine(self.root/'one',self.adapter,max_cycles=7,patience=5)

    def test_bank_change_fails_before_evaluation(self):
        self.new().run(stop_after_trials=1)
        with self.assertRaisesRegex(ResearchIntegrityError,'config'):
            ResearchEngine(self.root/'one',OperatorAdapter(seed=8,sizes=(8,5,5)),max_cycles=6,patience=5)

    def test_no_unaccepted_candidate_promoted(self):
        r=self.new().run();ev=HashLedger(self.root/'one'/'events.jsonl').events
        for x in ev:
            if x['kind']=='decision':
                self.assertEqual(x['payload']['adopted'],x['payload']['reason']=='validated_improvement')
        self.assertTrue(len(ev)>1)

    def test_forged_decision_digest_cannot_change_gate(self):
        self.new().run()
        f=self.root/'one'/'events.jsonl';rows=[json.loads(x) for x in f.read_text().splitlines()]
        # Reconstruct even a fully recomputed hash chain with an illegal adoption.
        for row in rows:
            if row['kind']=='decision':row['payload']['adopted']=not row['payload']['adopted'];break
        prev='0'*64
        for i,row in enumerate(rows):
            row['prev']=prev;row['sha256']=digest({k:row[k] for k in ('seq','prev','kind','payload')});prev=row['sha256']
        f.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))
        with self.assertRaises(ResearchIntegrityError):self.new()

    def test_unfinished_trial_resume_no_double_trial(self):
        engine=self.new();engine.ledger.append('trial',{'ordinal':0,
            'candidate':engine.proposals()[0].json(),
            'previous':Policy('fixed',1,1).json(),
            'train':self.adapter.evaluate(engine.proposals()[0],'train'),
            'validation':self.adapter.evaluate(engine.proposals()[0],'validation')})
        result=self.new().run()
        self.assertEqual(result['status'],'COMPLETE_PUBLIC_DEVELOPMENT')
        self.assertEqual(sum(x['kind']=='trial' for x in self.new().ledger.events),result['trials'])

    def test_completion_blocks_silent_second_test(self):
        self.new().run();p=self.root/'one'/'events.jsonl';old=p.read_bytes()
        self.new().run();self.assertEqual(p.read_bytes(),old)


if __name__=='__main__':unittest.main()

class IntegrityRegression(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.adapter=OperatorAdapter(sizes=(8,5,5))

    def _engine(self):
        return ResearchEngine(self.root/'session',self.adapter,max_cycles=6,patience=5)

    def _rewrite_chain(self,rows):
        prev='0'*64
        for row in rows:
            row['prev']=prev
            row['sha256']=digest({k:row[k] for k in ('seq','prev','kind','payload')})
            prev=row['sha256']
        path=self.root/'session'/'events.jsonl'
        path.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))

    def test_forged_completed_metrics_rejected_even_if_rehashed(self):
        self._engine().run()
        f=self.root/'session'/'events.jsonl'
        rows=[json.loads(line) for line in f.read_text().splitlines()]
        rows[-1]['payload']['champion_validation']['accepted_correct']=999
        self._rewrite_chain(rows)
        with self.assertRaisesRegex(ResearchIntegrityError,'completed evidence'):
            self._engine()

    def test_forged_completed_status_rejected_even_if_rehashed(self):
        self._engine().run()
        f=self.root/'session'/'events.jsonl'
        rows=[json.loads(line) for line in f.read_text().splitlines()]
        rows[-1]['payload']['status']='APPROVED_OAIE'
        self._rewrite_chain(rows)
        with self.assertRaises(ResearchIntegrityError):self._engine()

    def test_two_concurrent_snapshots_cannot_append_conflicting_events(self):
        p=self.root/'journal.jsonl'
        first=HashLedger(p);second=HashLedger(p)
        first.append('event',{'ok':True})
        with self.assertRaisesRegex(ResearchIntegrityError,'concurrent'):
            second.append('event',{'ok':False})
        self.assertEqual(len(HashLedger(p).events),1)

    def test_no_test_split_on_incomplete_session(self):
        class CountingAdapter(OperatorAdapter):
            def __init__(self):
                super().__init__(sizes=(8,5,5));self.test_reads=0
            def evaluate(self,policy,split):
                if split=='test':self.test_reads+=1
                return super().evaluate(policy,split)
        adapter=CountingAdapter()
        run=ResearchEngine(self.root/'session',adapter,max_cycles=6,patience=6)
        run.run(stop_after_trials=2)
        self.assertEqual(adapter.test_reads,0)
        run.run()
        self.assertEqual(adapter.test_reads,2)

    def test_in_family_witness_can_improve(self):
        adapter=OperatorAdapter(sizes=(8,5,5),outsiders_per_split=0)
        baseline=adapter.evaluate(Policy('fixed',1,1),'validation')
        enriched=adapter.evaluate(Policy('fixed',4,1),'validation')
        self.assertGreaterEqual(enriched['accepted_correct'],baseline['accepted_correct'])
        self.assertEqual(enriched['accepted_wrong'],0)

    def test_outside_family_stress_present_in_each_split(self):
        adapter=OperatorAdapter(sizes=(8,5,5),outsiders_per_split=2)
        for split in ('train','validation','test'):
            worlds=adapter.bank_manifest()['split_worlds'][split]
            self.assertEqual(sum(x['family']=='unrepresented' for x in worlds),2)

    def test_reject_invalid_outside_fraction(self):
        for value in (True,-1,3,0.0):
            with self.assertRaises(ResearchIntegrityError):
                OperatorAdapter(sizes=(8,5,5),outsiders_per_split=value)
