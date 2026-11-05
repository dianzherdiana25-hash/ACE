"""Native namespace-worker integration checks; no claim of Bubblewrap certification."""
from __future__ import annotations
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .e14_shared_budget import BudgetContractError
from .e14t_sandbox import IsolationUnavailable,isolation_canary,sandbox_call
from .e14w_worker import decision,library as cold_library,name as cold_name,validate_packet
from .e14w_synthesis import library as host_library,render
from .e14w_isolated import WORKER,worker_arm,run_batch
from .e14w_study import SEED,source_acquire,world,IN_FAMILY_EXPRESSIONS

PAIR=[[1,1,1],[1,1,2]]

def packet(**extra):
    return {'pair':PAIR,'mode':'synthesis-safe','seed':SEED,
            'remaining':4,'observations':[],**extra}

class WorkerBoundaryTests(unittest.TestCase):
    def test_cold_grammar_exactly_matches_reference(self):
        for n in (3,5):
            self.assertEqual(tuple(map(cold_name,cold_library(n))),
                             tuple(map(render,host_library(n))))

    def test_cold_entrypoint_has_no_evaluator_import(self):
        source=inspect.getsource(__import__('e14.e14w_worker',fromlist=['main']))
        self.assertNotIn('from .e14',source)
        self.assertNotIn('import e14',source)

    def test_first_public_action_matches_local_reference(self):
        self.assertEqual(decision(packet()),{'action':'query','tolls':[7,13]})

    def test_rejects_hidden_target_and_probe_fields(self):
        with self.assertRaises(ValueError):decision({**packet(),'target':[1,2]})
        with self.assertRaises(ValueError):decision({**packet(),'probe_gold':[10]})

    def test_rejects_boolean_seed_budget_and_route_symbols(self):
        for changes in ({'seed':True},{'remaining':True},
                        {'pair':[[1,True,1],[1,1,2]]}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):decision({**packet(),**changes})

    def test_negative_none_label_is_not_free_and_forces_abstention(self):
        obs=[{'costs':[4,18],'label':None}]
        result=decision({**packet(),'remaining':3,'observations':obs})
        self.assertEqual(result,{'action':'abstain'})

    def test_worker_accept_cannot_bypass_required_three_labels(self):
        obs=[{'costs':[11,17],'label':28}]
        result=decision({**packet(),'remaining':3,'observations':obs})
        self.assertNotEqual(result['action'],'accept')

    def test_worker_query_never_exceeds_available_budget(self):
        obs=[{'costs':[11,17],'label':28}]*4
        result=decision({**packet(),'remaining':0,'observations':obs})
        self.assertNotEqual(result['action'],'query')

    def test_real_namespace_canaries_report_all_eight(self):
        checks=isolation_canary()
        self.assertEqual(len(checks),8)
        self.assertTrue(all(checks.values()))

    def test_real_sandbox_policy_call_agrees_with_reference(self):
        result=sandbox_call(packet(),worker=WORKER)
        self.assertEqual((result['action'],result['tolls']),('query',[7,13]))
        self.assertIsInstance(result['cpu_us'],int)
        self.assertIsInstance(result['rss_kib'],int)

    def test_isolated_worker_and_reference_match_on_two_worlds(self):
        report=run_batch((0,),kinds=IN_FAMILY_EXPRESSIONS[:2])
        self.assertEqual((report['arms'],report['worlds']),(8,2))
        self.assertTrue(all(report['canaries'].values()))
        self.assertGreater(sum(row['worker_calls'] for row in report['rows']),8)

    def test_runtime_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            source=source_acquire(0,Path(t)/'s.sqlite')
            w=world(0,IN_FAMILY_EXPRESSIONS[0])
            with patch('e14.e14w_isolated.sandbox_call',side_effect=IsolationUnavailable('blocked')):
                with self.assertRaises(IsolationUnavailable):
                    worker_arm(w,source,'synthesis-safe',Path(t)/'j.sqlite')

    def test_missing_predecessor_artifact_spends_zero_target_labels(self):
        with tempfile.TemporaryDirectory() as t:
            source=source_acquire(3,Path(t)/'s.sqlite')
            self.assertFalse(source['correct'])
            result=worker_arm(world(3,IN_FAMILY_EXPRESSIONS[0]),source,
                              'synthesis-safe',Path(t)/'target.sqlite')
        self.assertEqual((result['accepted'],result['target_labels'],result['worker_calls']),(0,0,0))

if __name__=='__main__':unittest.main()
