"""Unit tests for ACE F13 Causal Memory Validation."""
from __future__ import annotations

import unittest

from ace_research_f13.agent import F13CausalAgent
from ace_research_f13.benchmark import (
    _cohens_d,
    _confidence_interval_95,
    _mean,
    _std,
    run_f13_curriculum_benchmark,
)
from ace_research_f13.causal_memory import CausalMemoryV2
from ace_research_f13.tasks import create_distractor_tasks, create_f13_curriculum


class TestF13CausalMemory(unittest.TestCase):
    def test_curriculum_tasks_disjoint_and_balanced(self):
        curr = create_f13_curriculum()
        self.assertEqual(len(curr), 6)
        for tid, task in curr.items():
            self.assertTrue(len(task.train_pool) > 0)
            self.assertTrue(len(task.holdout_pool) >= 20)
            pos = sum(1 for _, lbl in task.holdout_pool if lbl)
            neg = sum(1 for _, lbl in task.holdout_pool if not lbl)
            self.assertEqual(pos, neg, f"Task {tid} holdout not balanced: {pos} vs {neg}")

    def test_causal_memory_modes(self):
        # 1. Standard mode
        mem_std = CausalMemoryV2(mode="standard", seed=42)
        init_weights = mem_std.get_operator_weights("periodic")
        mem_std.record_task_solution(
            task_id="t0",
            cluster="periodic",
            winning_operator="strided_parity",
            winning_params={"stride": 2},
            holdout_accuracy=1.0,
            queries_used=2,
        )
        updated_weights = mem_std.get_operator_weights("periodic")
        self.assertGreater(updated_weights["strided_parity"], init_weights["strided_parity"])

        # 2. None mode
        mem_none = CausalMemoryV2(mode="none", seed=42)
        mem_none.record_task_solution(
            task_id="t0",
            cluster="periodic",
            winning_operator="strided_parity",
            winning_params={},
            holdout_accuracy=1.0,
            queries_used=2,
        )
        self.assertEqual(len(mem_none.abstractions), 0)
        self.assertEqual(mem_none.get_operator_weights("periodic")["strided_parity"], 1.0)

        # 3. Compute-matched multiplier
        mem_comp = CausalMemoryV2(mode="compute_matched", seed=42)
        self.assertEqual(mem_comp.get_query_budget_multiplier(), 2.0)
        self.assertEqual(mem_std.get_query_budget_multiplier(), 1.0)

        # 4. Irrelevant mode favors distractor
        mem_irrel = CausalMemoryV2(mode="irrelevant", seed=42)
        irrel_w = mem_irrel.get_operator_weights("periodic")
        self.assertGreater(irrel_w["distractor_sort"], irrel_w["strided_parity"])

    def test_statistical_helpers(self):
        vals1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        vals2 = [2.0, 3.0, 4.0, 5.0, 6.0]
        self.assertEqual(_mean(vals1), 3.0)
        self.assertAlmostEqual(_std(vals1), 1.5811, places=3)
        d = _cohens_d(vals2, vals1)
        self.assertAlmostEqual(d, 0.6324, places=3)
        low, high = _confidence_interval_95(vals1)
        self.assertTrue(low < 3.0 < high)

    def test_agent_solves_warmup_task(self):
        curr = create_f13_curriculum()
        task0 = curr["t0_flat_parity"]
        mem = CausalMemoryV2(mode="standard", seed=42)
        agent = F13CausalAgent(memory=mem, seed=42)
        pred_fn, meta = agent.solve_task(task0, task0.oracle_fn, base_query_budget=10)
        self.assertEqual(meta["holdout_accuracy"], 1.0)
        self.assertTrue(meta["queries_used"] >= 0)


if __name__ == "__main__":
    unittest.main()
