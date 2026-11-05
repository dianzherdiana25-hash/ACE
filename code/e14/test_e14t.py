"""E1.4t preregistration, worker isolation and bounded end-to-end controls."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from .e14_integrated_graph import DurableGraphBudget, graph_oracle
from .e14t_bank import SEED, STRATA, audit_bank, build, packed, public_packet, sha
from .e14t_worker import admitted, candidates, make_chain, propose
from .e14t_run import MODES, evaluate_arm, report_from_rows
from .e14t_sandbox import isolation_canary, sandbox_call, IsolationUnavailable


class BankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank=build(seed=SEED+1,per_stratum=2)

    def test_four_strata_and_auditable_immutable_seed(self):
        audit=audit_bank(self.bank)
        self.assertEqual(audit['worlds'],8)
        self.assertEqual(audit['strata'],{s:2 for s in STRATA})
        self.assertEqual(build(seed=SEED+1,per_stratum=2),self.bank)

    def test_global_graph_uniqueness(self):
        seen=set()
        for w in self.bank['worlds']:
            for g in [x['input'] for x in w['demos']]+w['probes']:
                digest=sha(g)
                self.assertNotIn(digest,seen)
                seen.add(digest)

    def test_train_probe_collision_rejected(self):
        bank=json.loads(json.dumps(self.bank))
        bank['worlds'][0]['probes'][0]=bank['worlds'][0]['demos'][0]['input']
        with self.assertRaisesRegex(ValueError,'collision'):
            audit_bank(bank)

    def test_hidden_target_not_passed_to_worker(self):
        for w in self.bank['worlds']:
            for mode in MODES:
                packet=public_packet(w,mode)
                self.assertEqual(set(packet),{'mode','source_word','demos'})
                self.assertNotIn('target',str(packet.keys()))
                self.assertNotIn('probes',str(packet.keys()))

    def test_reachable_negative_samples_eliminate_base(self):
        for w in self.bank['worlds']:
            if w['stratum']!='reachable':
                continue
            p={**public_packet(w,'integrated'),'receipts':[],'remaining':4}
            samples,_,_=admitted(p)
            self.assertFalse(candidates(samples,(5,6,7)))
            self.assertEqual(len(candidates(samples,(8,9))),2)
            self.assertEqual(propose(p)['stage'],'diagnosis')

    def test_outside_grammar_requires_abstention(self):
        for w in self.bank['worlds']:
            if w['stratum']=='out-of-grammar':
                p={**public_packet(w,'integrated'),'receipts':[],'remaining':4}
                self.assertEqual(propose(p)['action'],'abstain')

    def test_cost_oracle_over_both_packed_routes(self):
        graph=packed(((1,1,2,2,1,2,1,1),(1,1,2,2,1,2,2,1)))
        self.assertEqual(graph_oracle(graph,(1,1,2,2,1,2,1,1)),9)
        self.assertEqual(graph_oracle(graph,(1,1,2,2,1,2,2,1)),9)
        self.assertIsNone(graph_oracle(graph,(2,2,2,2,2,2,2,2)))


class WorkerProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worlds=build(seed=SEED+2,per_stratum=1)['worlds']

    def test_reachable_proposes_length_extension_not_supplied_new_word(self):
        w=self.worlds[0]
        a=propose({**public_packet(w,'integrated'),'receipts':[],'remaining':4})
        self.assertTrue(a['trigger'])
        self.assertEqual(a['representation'],'extended')
        self.assertEqual(a['extended_survivors'],2)
        self.assertNotIn('target',a)

    def test_fixed_grammar_abstains_reachable(self):
        w=self.worlds[0]
        a=propose({**public_packet(w,'fixed'),'receipts':[],'remaining':4})
        self.assertTrue(a['trigger'])
        self.assertEqual(a['action'],'abstain')

    def test_input_rejects_untrusted_hidden_labels(self):
        w=self.worlds[0];p={**public_packet(w,'integrated'),'receipts':[], 'remaining':4}
        with self.assertRaises(ValueError):propose({**p,'target':w['target']})
        with self.assertRaises(ValueError):propose({**p,'probe_gold':[3]})

    def test_bad_receipts_fail_closed(self):
        w=self.worlds[0];p={**public_packet(w,'integrated'),'receipts':[], 'remaining':4}
        bad={'id':'q0001','stage':'diagnosis','query':make_chain(w['source_word']),
             'label':None,'status':'pending','reused_in':[]}
        with self.assertRaises(ValueError):propose({**p,'receipts':[bad],'remaining':3})

    def test_worker_packet_must_be_bounded(self):
        w=self.worlds[0];p={**public_packet(w,'integrated'),'receipts':[], 'remaining':4}
        with self.assertRaises(ValueError):propose({**p,'remaining':5})
        with self.assertRaises(ValueError):propose({**p,'demos':p['demos']*17})

    def test_graph_split_can_filter_hypotheses(self):
        w=self.worlds[0];p={**public_packet(w,'integrated'),'receipts':[], 'remaining':4}
        before=propose(p)
        query=before['graph']
        record={'id':'q0001','stage':'diagnosis','query':query,
                'label':graph_oracle(query,w['target']),'status':'settled','reused_in':[]}
        after=propose({**p,'receipts':[record],'remaining':3})
        self.assertEqual(after['action'],'reuse')
        self.assertEqual(after['stage'],'repair')


class IsolationAndEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank=build(seed=SEED+3,per_stratum=1)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'arms.sqlite'

    def test_actual_worker_isolation_canaries(self):
        result=isolation_canary()
        self.assertTrue(result)
        self.assertTrue(all(result.values()))

    def test_sandbox_matches_pure_candidate(self):
        w=self.bank['worlds'][0]
        p={**public_packet(w,'integrated'),'receipts':[], 'remaining':4}
        self.assertEqual(sandbox_call(p),propose(p))

    def test_reachable_integrated_runs_all_stages(self):
        row=evaluate_arm(self.bank['worlds'][0],'integrated',self.path)
        self.assertEqual(row['status'],'COMPLETE')
        self.assertEqual(row['final_action'],'accept')
        self.assertEqual(row['word_correct'],1)
        self.assertEqual(row['errors'],0)
        self.assertLessEqual(row['purchased'],4)
        self.assertEqual(row['auditor_calls'],row['purchased'])
        trace=[a['action'] for a in row['trace']]
        self.assertIn('query',trace);self.assertIn('reuse',trace)
        self.assertEqual(trace[-1],'accept')

    def test_strong_exhaustive_equal_budget_control(self):
        w=self.bank['worlds'][0]
        a=evaluate_arm(w,'integrated',self.path)
        b=evaluate_arm(w,'exhaustive',self.path)
        self.assertEqual(a['word_correct'],b['word_correct'])
        self.assertLessEqual(a['purchased'],4)
        self.assertLessEqual(b['purchased'],4)

    def test_fixed_grammar_fails_without_lying(self):
        row=evaluate_arm(self.bank['worlds'][0],'fixed',self.path)
        self.assertEqual(row['final_action'],'abstain')
        self.assertEqual(row['covered'],0)

    def test_outside_grammar_stays_abstained_with_zero_labels(self):
        w=next(x for x in self.bank['worlds'] if x['stratum']=='out-of-grammar')
        row=evaluate_arm(w,'integrated',self.path)
        self.assertEqual((row['final_action'],row['purchased']),('abstain',0))

    def test_resume_pending_without_second_oracle_attempt(self):
        w=self.bank['worlds'][0]
        book=DurableGraphBudget(self.path,w['id']+':integrated')
        book.reserve('diagnosis',make_chain((1,2,1,1,2,1,1,2)))
        counter=[]
        def invoker(packet):
            counter.append(1)
            raise AssertionError('must not invoke candidate with pending oracle')
        row=evaluate_arm(w,'integrated',self.path,invoker=invoker)
        self.assertEqual(row['status'],'BLOCKED_UNKNOWN_PENDING')
        self.assertEqual(counter,[])
        self.assertEqual(book.snapshot()['remaining'],3)

    def test_worker_leak_or_wrong_action_rejected(self):
        w=self.bank['worlds'][0]
        def bad(packet):return {'action':'accept','word':w['target'],
                 'trigger':True,'base_survivors':0,'extended_survivors':1,
                 'candidate_fits':992,'representation':'extended'}
        with self.assertRaisesRegex(ValueError,'unguarded acceptance'):
            evaluate_arm(w,'integrated',self.path,invoker=bad)

    def test_completed_arm_returns_cached_terminal_without_worker(self):
        w=self.bank['worlds'][0]
        first=evaluate_arm(w,'integrated',self.path)
        def forbidden(_):
            raise AssertionError('a completed arm must not be re-executed')
        second=evaluate_arm(w,'integrated',self.path,invoker=forbidden)
        self.assertEqual(first,second)

    def test_resume_after_committed_step_uses_same_label(self):
        w=self.bank['worlds'][0]
        from .e14t_worker import propose
        calls=[]
        def interrupt(packet):
            if packet['receipts']:
                raise TimeoutError('simulated interruption')
            calls.append(1)
            return propose(packet)
        with self.assertRaises(TimeoutError):
            evaluate_arm(w,'integrated',self.path,invoker=interrupt)
        before=DurableGraphBudget(self.path,w['id']+':integrated').snapshot()
        self.assertEqual(before['purchased'],1)
        resumed=evaluate_arm(w,'integrated',self.path)
        self.assertEqual(resumed['final_action'],'accept')
        self.assertEqual(resumed['purchased'],2)
        self.assertEqual(len([x for x in resumed['trace'] if x['action']=='query']),2)
        self.assertEqual(len(calls),1)

    def test_unlogged_settled_receipt_requires_reconciliation(self):
        w=self.bank['worlds'][0]
        book=DurableGraphBudget(self.path,w['id']+':integrated')
        rid=book.reserve('diagnosis',make_chain((1,2,1,1,2,1,1,2)))
        book.settle(rid,None)
        row=evaluate_arm(w,'integrated',self.path,
                         invoker=lambda p: (_ for _ in ()).throw(AssertionError('no worker')))
        self.assertEqual(row['status'],'BLOCKED_RECONCILE_TRACE')

    def test_report_does_not_treat_abstain_as_correct(self):
        w=self.bank['worlds'][0]
        rows=[evaluate_arm(w,m,self.path) for m in MODES]
        report=report_from_rows(rows)
        self.assertEqual(report['summary'] if 'summary' in report else report['status'],'ENGINEERING_PUBLIC_DEVELOPMENT')
        self.assertEqual(report['scientific_decision'],'NOT_ASSESSED')
        self.assertEqual(report['cells']['reachable']['fixed']['correct'],0)


if __name__=='__main__':
    unittest.main()
