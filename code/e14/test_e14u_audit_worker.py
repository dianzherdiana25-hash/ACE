"""E1.4u candidate isolation, response validation and adversarial replay tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .e14_shared_budget import BudgetContractError
from .e14u_audit import audit_report, audit_row, independent_label
from .e14u_dev import MODES, SEED, make_world, report
from .e14u_isolated import WORKER, decision, run
from .e14u_primitive import (PAIR_SPACE, PAIR_WORDS, fit, graph_from_routes,
                              oracle, program, query_pool, select_query)
from .e14u_worker import solve
from .e14t_sandbox import sandbox_call


class IsolatedAndAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full,cls.digest=report()

    def test_complete_development_report_replayed(self):
        result=audit_report(self.full)
        self.assertEqual(result['arms'],168)
        self.assertEqual(result['purchased_labels'],236)
        self.assertEqual(result['oracle_audit_calls'],236)
        self.assertEqual(result['initial_demo_labels'],528)
        self.assertEqual(result['heldout_probe_labels'],1008)

    def test_dev_report_deterministic_fresh_ledgers(self):
        again,digest=report()
        self.assertEqual(digest,self.digest)
        self.assertEqual(self.full,again)

    def test_active_vs_controls_descriptive_only(self):
        paired=self.full['summary']['pair']
        self.assertEqual([paired[k]['exact'] for k in MODES],[28,21,26,0])
        self.assertEqual([paired[k]['purchased'] for k in MODES],[51,73,68,0])
        self.assertEqual(sum(r['wrong_accepted'] for r in self.full['rows']),0)
        self.assertEqual(max(r['purchased'] for r in self.full['rows']),4)

    def test_worker_never_receives_truth_or_probe_fields(self):
        w=make_world('pair',1)
        packet={'mode':'active','seed':SEED,'demos':w['demonstrations'],'purchased':[]}
        self.assertIn(solve(packet)['action']['action'],('query','accept','abstain'))
        for forbidden in ('truth','oracle','probes','evaluator','target'):
            with self.subTest(forbidden=forbidden),self.assertRaises(ValueError):
                solve({**packet,forbidden:w['truth']})

    def test_worker_survivors_match_host_on_all_initial_worlds(self):
        for kind,count in (('pair',28),('single',8),('triple',6)):
            for idx in range(count):
                w=make_world(kind,idx)
                packet={'mode':'active','seed':SEED,'demos':w['demonstrations'],'purchased':[]}
                observed=solve(packet)
                expected=fit(w['demonstrations'],extended=(kind!='single'))['candidates']
                self.assertEqual(observed['survivors'],len(expected))
                self.assertEqual(observed['trigger'],kind!='single')

    def test_worker_cap_four_abstains_instead_of_query_five(self):
        w=make_world('pair',10)
        packet={'mode':'active','seed':SEED,'demos':w['demonstrations'],
                'purchased':[g for g in query_pool()[:4]]}
        action=solve(packet)['action']
        self.assertEqual(action,{'action':'abstain'})

    def test_worker_rejects_boolean_resource_and_bad_packet(self):
        w=make_world('pair',2)
        packet={'mode':'active','seed':SEED,'demos':w['demonstrations'],'purchased':[]}
        for modified in ({**packet,'seed':True},{**packet,'mode':'openai-god'},
                         {**packet,'purchased':'none'},{**packet,'demos':[]},
                         {**packet,'demos':[{'input':w['demonstrations'][0]['input'],'output':True}]}):
            with self.subTest(modified=modified),self.assertRaises(ValueError):solve(modified)

    def test_worker_rejects_unbounded_graph(self):
        w=make_world('pair',0)
        packet={'mode':'active','seed':SEED,'demos':copy.deepcopy(w['demonstrations']),'purchased':[]}
        packet['demos'][0]['input']['nodes']=100
        self.assertRaises(ValueError,solve,packet)

    def test_worker_rejects_wrong_oracle_receipt_bool(self):
        w=make_world('pair',0)
        packet={'mode':'active','seed':SEED,'demos':copy.deepcopy(w['demonstrations']),'purchased':[]}
        packet['demos'][0]['output']=True
        self.assertRaises(ValueError,solve,packet)

    def test_real_namespace_worker_matches_in_process_one_action(self):
        w=make_world('pair',4)
        packet={'mode':'active','seed':SEED,'demos':w['demonstrations'],'purchased':[]}
        a=solve(packet)
        b=sandbox_call(packet,worker=WORKER)
        for k in ('trigger','survivors','action'):
            self.assertEqual(a[k],b[k])
        self.assertGreater(b['cpu_us'],0)

    def test_actual_namespace_subset_result_corresponds_to_simulator(self):
        out=run(subset=3)
        self.assertEqual((out['worlds'],out['arms']),(3,12))
        self.assertTrue(all(out['preflight'].values()))
        for row in out['rows']:
            counterpart=next(x for x in self.full['rows'] if x['world']==row['world'] and x['arm']==row['arm'])
            for k in ('purchased','accepted','exact','wrong_accepted','covered','probe_errors'):
                self.assertEqual(row[k],counterpart[k])

    def test_forged_early_acceptance_rejected(self):
        w=make_world('pair',9)
        with tempfile.TemporaryDirectory() as temp:
            def hostile(_packet,*,worker):
                return {'trigger':True,'survivors':7,'action':{'action':'accept','candidate':
                        {'kind':'branch-pair','words':[[1,1,1],[2,2,2]]}},
                        'cpu_us':10,'rss_kib':500}
            with patch('e14.e14u_isolated.sandbox_call',hostile):
                self.assertRaises(BudgetContractError,decision,w,'active',Path(temp)/'j.sqlite')

    def test_audit_fails_modified_oracle_label(self):
        row=copy.deepcopy(next(x for x in self.full['rows'] if x['purchased']>0))
        row['journal']['receipts'][0]['label']=777
        self.assertRaises(BudgetContractError,audit_row,row)

    def test_audit_fails_modified_graph_resource_cost(self):
        row=copy.deepcopy(next(x for x in self.full['rows'] if x['purchased']>0))
        row['journal']['receipts'][0]['cost']['edges']=15
        self.assertRaises(BudgetContractError,audit_row,row)

    def test_audit_fails_modified_trace_receipt(self):
        row=copy.deepcopy(next(x for x in self.full['rows'] if x['purchased']>0))
        row['trace'][0]['receipt']='q1000'
        self.assertRaises(BudgetContractError,audit_row,row)

    def test_audit_fails_missing_reuse_proof(self):
        row=copy.deepcopy(next(x for x in self.full['rows'] if x['purchased']>0))
        row['journal']['receipts'][0]['reused_in']=[]
        self.assertRaises(BudgetContractError,audit_row,row)

    def test_audit_fails_wrong_accepted_count(self):
        row=copy.deepcopy(next(x for x in self.full['rows'] if x['exact']==1))
        row['wrong_accepted']=1
        self.assertRaises(BudgetContractError,audit_row,row)

    def test_audit_fails_probe_result_tamper(self):
        row=copy.deepcopy(next(x for x in self.full['rows'] if x['covered']>0))
        row['probe_errors']=100
        self.assertRaises(BudgetContractError,audit_row,row)

    def test_audit_fails_duplicate_arm_or_missing_arm(self):
        copied=copy.deepcopy(self.full)
        copied['rows'][1]['world']=copied['rows'][0]['world']
        copied['rows'][1]['arm']=copied['rows'][0]['arm']
        self.assertRaises(BudgetContractError,audit_report,copied)
        copied=copy.deepcopy(self.full);copied['rows'].pop()
        self.assertRaises(BudgetContractError,audit_report,copied)

    def test_audit_fails_forged_totals(self):
        copied=copy.deepcopy(self.full)
        copied['summary']['pair']['active']['purchased']+=1
        self.assertRaises(BudgetContractError,audit_report,copied)

    def test_audit_fails_invented_world(self):
        row=copy.deepcopy(self.full['rows'][0]);row['world']='pair:100'
        self.assertRaises(BudgetContractError,audit_row,row)

    def test_separate_oracle_matches_all_world_demonstrations(self):
        for kind,count in (('pair',28),('single',8),('triple',6)):
            for i in range(count):
                w=make_world(kind,i)
                for demo in w['demonstrations']:
                    self.assertEqual(independent_label(demo['input'],w['truth']),demo['output'])

    def test_heldout_probes_not_equal_to_selector_pool(self):
        candidates={json.dumps(g,sort_keys=True) for g in query_pool()}
        for kind,count in (('pair',28),('single',8),('triple',6)):
            for i in range(count):
                for probe in make_world(kind,i)['probes']:
                    self.assertNotIn(json.dumps(probe,sort_keys=True),candidates)

    def test_standalone_worker_has_no_evaluator_imports(self):
        source=WORKER.read_text()
        self.assertNotIn('from .e14_integrated_graph import',source)
        self.assertNotIn('from .e14u_dev import',source)
        self.assertNotIn('from .e14u_primitive import',source)


if __name__=='__main__':unittest.main()
