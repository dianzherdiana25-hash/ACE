"""Unit tests for ACE F14 Autonomous Mechanism Discovery."""
from __future__ import annotations

import json
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

    def test_generational_discovery_on_terminal_suite(self):
        """Verify empirical G0 initialization, G1 acceptance, and G2 rejection on terminal suite."""
        from ace_research_f14.terminal_tasks import create_f14_terminal_suite

        suite = create_f14_terminal_suite(task_generation_seed=42)
        holdout_banks = {t.task_id: list(t.holdout_pool) for t in suite.values()}
        evaluator = SealedHoldoutEvaluator(
            manifest_id="f14_terminal_test_manifest",
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

        # G0 measured empirically on 192 samples (75 hits -> 0.3906)
        self.assertEqual(res["g0_empirical_accuracy"], 0.3906)
        self.assertEqual(host.lineage.nodes["G0_test_root"].holdout_score, 0.3906)

        # G1 achieves 0.6042 (+0.2136 gain over G0 >= 0.15 -> ACCEPTED)
        self.assertTrue(res["g1_accepted"])
        self.assertEqual(res["g1_accuracy"], 0.6042)
        self.assertEqual(res["g1_gain"], 0.2136)

        # G2 achieves 0.6146 (+0.0104 gain over parent G1 < 0.15 -> REJECTED)
        self.assertFalse(res["g2_accepted"])
        self.assertEqual(res["g2_accuracy"], 0.6146)
        self.assertEqual(res["g2_gain"], 0.0104)

        # Active head remains G1 because G2 was rejected
        self.assertEqual(host.lineage.active_head_id, "G1_autonomous_discovered")
        self.assertEqual(res["active_head_id"], "G1_autonomous_discovered")

    def test_verifier_adversarial_rejection_on_manipulation(self):
        """Verifier must catch any fabricated gains, false acceptances, or lineage manipulations."""
        from ace_research_f14.benchmark import run_single_seed_f14
        from ace_research_f14.verify import verify_f14_evidence

        single_run = run_single_seed_f14(task_seed=42, search_seed=42)
        valid_artifact = {
            "benchmark_id": "ACE_F14_INDEPENDENT_TERMINAL_EVALUATION",
            "governance": {
                "release_gate": "BLOCK_RELEASE",
                "scientific_status": "NOT_ASSESSED",
                "oaie_established": False,
            },
            "primary_discovery_summary": {},
            "baselines_summary": {},
            "per_seed_runs": [single_run] * 5,
        }

        # 1. Authentic artifact passes
        passed, msg = verify_f14_evidence(valid_artifact)
        self.assertTrue(passed, f"Expected pass, got: {msg}")

        # 2. Fraudulent G2 acceptance is caught
        tampered = json.loads(json.dumps(valid_artifact))
        tampered["per_seed_runs"][0]["g2_accepted"] = True
        p, m = verify_f14_evidence(tampered)
        self.assertFalse(p)
        self.assertIn("g2_accepted mismatch", m)

        # 3. Fraudulent G2 gain exaggeration is caught
        tampered = json.loads(json.dumps(valid_artifact))
        tampered["per_seed_runs"][0]["g2_gain"] = 0.20
        p, m = verify_f14_evidence(tampered)
        self.assertFalse(p)
        self.assertIn("g2_gain mismatch", m)

        # 4. Lineage promotion corruption (promoting rejected G2 to active head) is caught
        tampered = json.loads(json.dumps(valid_artifact))
        tampered["per_seed_runs"][0]["active_head_id"] = "G2_autonomous_discovered"
        p, m = verify_f14_evidence(tampered)
        self.assertFalse(p)
        self.assertIn("lineage corruption", m)

        # 5. Governance invariant breach is caught
        tampered = json.loads(json.dumps(valid_artifact))
        tampered["governance"]["release_gate"] = "ALLOW_RELEASE"
        p, m = verify_f14_evidence(tampered)
        self.assertFalse(p)
        self.assertIn("release_gate must be BLOCK_RELEASE", m)


if __name__ == "__main__":
    import json
    unittest.main()

