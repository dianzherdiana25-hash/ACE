"""Unit tests for ACE F14 Autonomous Mechanism Discovery."""
from __future__ import annotations

import unittest

from ace_host_controller import (
    ExecutionBudget,
    HostController,
    HostSandboxGate,
    SealedHoldoutEvaluator,
)
from ace_research_f12.tasks import create_f12_task_suite
from ace_research_f14.discovery_engine import (
    AutonomousGenerationalDiscovery,
    ErrorDiagnoser,
    GrammarSearchEngine,
)
from ace_research_f14.grammar import (
    CountOp,
    DyckBalanceOp,
    HalfSplitOp,
    InputString,
    ModEqPred,
    RelationalEqPred,
    SliceOp,
    compile_ast_to_callable,
)


class TestF14Discovery(unittest.TestCase):
    def test_ast_evaluation_and_compilation(self):
        inp = InputString()
        slice_op = SliceOp(src=inp, offset=0, stride=2)
        count_op = CountOp(src=slice_op, char="a")
        pred = ModEqPred(src=count_op, mod=2, target=0)

        # In "ababa": slice[0::2] is "aaa", count('a')=3, 3%2=1 != 0 -> False
        self.assertFalse(pred.evaluate("ababa"))
        # In "ababb": slice[0::2] is "aab", count('a')=2, 2%2=0 == 0 -> True
        self.assertTrue(pred.evaluate("ababb"))

        fn, code = compile_ast_to_callable(pred)
        self.assertFalse(fn("ababa"))
        self.assertTrue(fn("ababb"))
        self.assertIn("candidate_fn", code)

    def test_dyck_balance_ast(self):
        inp = InputString()
        dyck = DyckBalanceOp(src=inp, max_depth=4)
        self.assertTrue(dyck.evaluate("aabb"))
        self.assertTrue(dyck.evaluate("abab"))
        self.assertFalse(dyck.evaluate("baab"))
        self.assertFalse(dyck.evaluate("a"))

        fn, code = compile_ast_to_callable(dyck)
        self.assertTrue(fn("aabb"))
        self.assertFalse(fn("baab"))

    def test_relational_split_ast(self):
        inp = InputString()
        left = CountOp(src=HalfSplitOp(src=inp, half="left"), char="a")
        right = CountOp(src=HalfSplitOp(src=inp, half="right"), char="a")
        rel = RelationalEqPred(left=left, right=right)

        # "abba": len 4, mid 2. left="ab" (1 'a'), right="ba" (1 'a') -> True
        self.assertTrue(rel.evaluate("abba"))
        # "aaba": left="aa" (2 'a'), right="ba" (1 'a') -> False
        self.assertFalse(rel.evaluate("aaba"))

    def test_error_diagnoser(self):
        diagnoser = ErrorDiagnoser()
        # Create failure cases with strong strided parity signal
        failures = [
            ("abab", True),  # w[0::2] = "aa" (count 2 % 2 == 0) -> True
            ("aaaa", True),  # w[0::2] = "aa" -> True
            ("baba", False), # w[0::2] = "ba" (count 1 % 2 == 1) -> False
        ]
        # Baseline predicts wrong on all
        diag = diagnoser.analyze(lambda w: False, failures)
        self.assertGreater(diag.stride_signal, 0.5)

    def test_generational_discovery_progression(self):
        suite = create_f12_task_suite()
        holdout_banks = {t.task_id: list(t.holdout_pool) for t in suite.values()}
        evaluator = SealedHoldoutEvaluator(
            manifest_id="f14_test_manifest",
            holdout_banks=holdout_banks,
        )
        host = HostController(
            evaluator=evaluator,
            budget=ExecutionBudget(max_execution_seconds=60.0, max_queries=500, max_candidates=20),
            sandbox_gate=HostSandboxGate(enforce_os_containment=False),
            root_candidate_id="G0_test_root",
            root_source_sha="test_sha",
            min_gain=0.15,
            max_regression=0.02,
        )
        discovery = AutonomousGenerationalDiscovery(seed=42)
        res = discovery.execute_generational_discovery(suite, host)

        self.assertGreater(res["g0_empirical_accuracy"], 0.0)
        self.assertTrue(res["g1_accepted"])
        self.assertGreaterEqual(res["g1_gain"], 0.15)
        self.assertTrue(res["g2_accepted"])
        self.assertGreaterEqual(res["g2_gain"], 0.15)
        self.assertLessEqual(res["g2_regression"], 0.02)


if __name__ == "__main__":
    unittest.main()
