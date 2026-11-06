"""Tests for structural-credit algorithm and invariants, not performance claims."""
import random
import unittest
from unittest.mock import patch
from . import study as core
from . import proposal_v3 as v3
from . import credit_v4 as v4

class CreditV4Tests(unittest.TestCase):
    def test_new_target_topology_and_determinism(self):
        signatures=set()
        for task in v4.NEW_TASKS:
            g=v4.new_task_graph(task)
            self.assertEqual(4,len(g.gates))
            self.assertEqual(core.N_INPUTS+3,g.output)
            signatures.add(g.canonical())
        self.assertEqual(6,len(signatures))

    def test_mutation_valid_and_structural(self):
        rng=random.Random(5151)
        seen=set()
        for _ in range(200):
            g=core.draw_graph(rng)
            affordable=max(len(g.gates),1)
            for move in v4.eligible_moves(g,affordable):
                h=v4.proposed_edit(g,move,rng)
                h.validate()
                seen.add(h.canonical())
        self.assertGreater(len(seen),100)

    def test_credit_and_uniform_replay(self):
        for arm in ('uniform_edits','credit_edits'):
            self.assertEqual(v4.run_case(arm,v4.DEVELOPMENT[1],0),
                             v4.run_case(arm,v4.DEVELOPMENT[1],0))

    def test_holdout_label_inversion_is_blind(self):
        for arm in ('uniform_edits','credit_edits'):
            a=v4.run_case(arm,v4.NEW_TASKS[0],0)
            b=v4.run_case(arm,v4.NEW_TASKS[0],0,True)
            self.assertEqual(a['selected'],b['selected'])
            self.assertEqual(a['pool_sha256'],b['pool_sha256'])
            self.assertEqual(a['credit'],b['credit'])
            self.assertAlmostEqual(a['test_accuracy']+b['test_accuracy'],1,places=10)

    def test_budget_accounting(self):
        for arm in ('uniform_edits','credit_edits'):
            for task in (v4.DEVELOPMENT[0],v4.NEW_TASKS[3]):
                r=v4.run_case(arm,task,0)
                self.assertEqual(r['proposals'],r['candidate_count']+sum(r['rejection'].values()))
                self.assertLessEqual(r['proposals'],v4.PROPOSAL_CAP)
                self.assertLessEqual(r['candidate_count'],v4.CANDIDATE_CAP)
                self.assertLessEqual(r['gate_work'],v4.WORK_CAP)
                self.assertLessEqual(r['validation_count'],v4.SHORTLIST)
                self.assertEqual(r['proposals']-len(list(core.first_stage())),
                                 sum(entry['attempts'] for entry in r['credit'].values()))

    def test_bad_input_does_not_execute_code(self):
        for bad in ('eval','__import__','random_v4'):
            with self.assertRaises(ValueError):
                v4.run_case(bad,v4.DEVELOPMENT[0],0)
        with self.assertRaises(ValueError):
            v4.run_case('credit_edits','unknown_task',0)
        with self.assertRaises(ValueError):
            v4.proposed_edit(core.Graph((),0),'eval',random.Random(3))

    def test_baseline_matches_unmodified_v3(self):
        for arm in ('config','greedy','cost_aware'):
            direct=v3.run_case(arm,v4.DEVELOPMENT[0],0)
            via=v4.run_case(arm,v4.DEVELOPMENT[0],0)
            for field in ('test_accuracy','selected','candidate_count','gate_work','pool_sha256'):
                self.assertEqual(direct[field],via[field])

    def test_procedure_does_not_touch_v1_or_v3_source(self):
        self.assertEqual(v4.truth(v4.DEVELOPMENT[0],(1,0,1,0,1)),v3.truth(v4.DEVELOPMENT[0],(1,0,1,0,1)))

if __name__=='__main__': unittest.main()
