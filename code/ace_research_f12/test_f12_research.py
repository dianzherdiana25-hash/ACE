"""Comprehensive unit tests for ACE F12 Causal Autonomous Research.

Tests task suite disjointness, causal gap analyzer, zero-leakage active synthesizer,
memory ablations, generational growth, and independent evidence verifier.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_host_controller import ExecutionBudget, HostController, HostSandboxGate, SealedHoldoutEvaluator
from ace_research_f12.benchmark import execute_full_f12_benchmark
from ace_research_f12.causal_agent import (
    ActiveInformationGainSynthesizer,
    CausalGapAnalyzer,
    CausalMemory,
    CausalResearchAgent,
)
from ace_research_f12.generational_growth import GenerationalGrowthEngine
from ace_research_f12.tasks import create_f12_task_suite
from ace_research_f12.verify import verify_f12_evidence


class TestF12TaskSuite(unittest.TestCase):
    def test_task_families_and_disjointness(self):
        suite = create_f12_task_suite()
        self.assertIn("task_a1_even_a_mod2", suite)
        self.assertIn("task_b1_dyck_bal", suite)
        self.assertIn("task_c1_split_eq_mod2", suite)

        for task_id, task in suite.items():
            train_words = {w for w, _ in task.train_pool}
            holdout_words = {w for w, _ in task.holdout_pool}
            # Train and holdout words must be completely disjoint
            self.assertEqual(len(train_words & holdout_words), 0)
            self.assertTrue(len(task.train_pool) > 0)
            self.assertTrue(len(task.holdout_pool) > 0)


class TestCausalGapAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CausalGapAnalyzer()

    def test_strided_parity_gap(self):
        # Target: even 'a' count at stride 2 (offset 0)
        # Baseline: length even
        baseline_fn = lambda w: len(w) % 2 == 0
        training_data = [
            ("a", False),
            ("aa", True),
            ("ab", True),
            ("ba", False),
            ("aaa", False),
            ("aab", False),
            ("aba", True),
        ]
        gap = self.analyzer.diagnose_gap(baseline_fn, training_data)
        self.assertIn(gap.gap_type, ("strided_parity", "generic"))

    def test_dyck_balance_gap(self):
        # Target: balanced parentheses (a = (, b = ))
        baseline_fn = lambda w: False
        training_data = [
            ("ab", True),
            ("aabb", True),
            ("abab", True),
            ("ba", False),
            ("a", False),
            ("b", False),
        ]
        gap = self.analyzer.diagnose_gap(baseline_fn, training_data)
        self.assertEqual(gap.gap_type, "dyck_balance")


class TestActiveSynthesizerZeroLeakage(unittest.TestCase):
    def test_synthesizer_discriminates_without_oracle(self):
        synthesizer = ActiveInformationGainSynthesizer(alphabet=("a", "b"))
        cand_fn = lambda w: w.startswith("a")
        base_fn = lambda w: len(w) % 2 == 0

        # Synthesizer finds strings where cand_fn != base_fn without knowing oracle
        probes = synthesizer.select_informative_queries(cand_fn, base_fn, max_queries=4)
        self.assertTrue(len(probes) > 0)
        for p in probes:
            self.assertNotEqual(cand_fn(p), base_fn(p))


class TestCausalMemoryAblations(unittest.TestCase):
    def test_memory_modes(self):
        # Standard
        mem_std = CausalMemory(mode="standard")
        mem_std.record_finding({"step": 1, "val": "A"})
        mem_std.record_finding({"step": 2, "val": "B"})
        ctx = mem_std.get_context()
        self.assertEqual(len(ctx), 2)
        self.assertEqual(ctx[0]["val"], "A")

        # No-memory ablation
        mem_none = CausalMemory(mode="no_memory")
        mem_none.record_finding({"step": 1, "val": "A"})
        self.assertEqual(len(mem_none.get_context()), 0)

        # Shuffled-memory ablation
        mem_shuf = CausalMemory(mode="shuffled_memory", seed=99)
        for i in range(10):
            mem_shuf.record_finding({"idx": i})
        self.assertEqual(len(mem_shuf.get_context()), 10)


class TestGenerationalGrowthAndVerifier(unittest.TestCase):
    def test_generational_growth_execution(self):
        engine = GenerationalGrowthEngine(seed=42)
        host, decisions, summary = engine.run_generational_progression()

        self.assertTrue(summary["g1_accepted"])
        self.assertTrue(summary["g2_accepted"])
        self.assertGreaterEqual(summary["g1_gain"], 0.15)
        self.assertGreaterEqual(summary["g2_gain"], 0.15)
        self.assertEqual(host.lineage.active_head_id, "G2_relational_successor")

    def test_full_benchmark_and_verification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test_f12_evidence.json.gz"
            report = execute_full_f12_benchmark(out_file)
            self.assertTrue(out_file.is_file())

            # Verify evidence
            passed, msg = verify_f12_evidence(report)
            self.assertTrue(passed, msg)


if __name__ == "__main__":
    unittest.main()
