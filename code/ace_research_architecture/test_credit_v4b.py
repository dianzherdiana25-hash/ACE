"""Post-hoc novelty-aware edit credit correction tests; separate chain family."""
import json
from pathlib import Path
import unittest
from . import study as core
from . import credit_v4 as v4

HERE=Path(__file__).parent

class CreditV4BTests(unittest.TestCase):
    def test_previous_v4_records_unchanged(self):
        for name,task,seed in [('credit_v4_dev.json',v4.DEVELOPMENT[0],0),
                               ('credit_v4_fresh.json',v4.NEW_TASKS[2],1)]:
            bank='development' if 'dev' in name else 'fresh'
            previous=json.loads((HERE/name).read_text())[bank]['records']
            for arm in ('config','greedy','cost_aware','uniform_edits','credit_edits'):
                stored=next(r for r in previous if r['task']==task and r['seed']==seed and r['arm']==arm)
                self.assertEqual(stored, v4.run_case(arm,task,seed))

    def test_new_chain_families_are_topologically_distinct(self):
        for task in v4.CHAIN_TASKS:
            graph=v4.new_task_graph(task)
            self.assertEqual(len(graph.gates),4)
            self.assertEqual(graph.gates[1].a,core.N_INPUTS)
            self.assertEqual(graph.gates[2].a,core.N_INPUTS+1)
            self.assertEqual(graph.gates[3].a,core.N_INPUTS+2)
            graph.validate()
            for x in core.samples(task,0)[0]:
                self.assertIn(v4.truth(task,x),(0,1))

    def test_novelty_credit_deterministic_bounded_and_counterfactually_blind(self):
        a=v4.run_case('credit_novelty',v4.CHAIN_TASKS[0],1)
        b=v4.run_case('credit_novelty',v4.CHAIN_TASKS[0],1)
        self.assertEqual(a,b)
        c=v4.run_case('credit_novelty',v4.CHAIN_TASKS[0],1,True)
        self.assertEqual(a['pool_sha256'],c['pool_sha256'])
        self.assertEqual(a['selected'],c['selected'])
        self.assertEqual(a['credit'],c['credit'])
        self.assertAlmostEqual(a['test_accuracy']+c['test_accuracy'],1)
        self.assertEqual(a['proposals'],a['candidate_count']+sum(a['rejection'].values()))
        self.assertLessEqual(a['gate_work'],v4.WORK_CAP)

    def test_credit_penalizes_unproductive_actions(self):
        a=v4.run_case('credit_novelty',v4.CHAIN_TASKS[1],0)
        self.assertGreater(sum(x['attempts'] for x in a['credit'].values()),0)
        self.assertLessEqual(sum(x['accepted'] for x in a['credit'].values()),sum(x['attempts'] for x in a['credit'].values()))
        self.assertLessEqual(a['candidate_count'],v4.CANDIDATE_CAP)

if __name__=='__main__':unittest.main()
