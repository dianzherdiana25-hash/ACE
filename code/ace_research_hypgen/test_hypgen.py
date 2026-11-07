"""Unit, comparative benchmark, and runtime integration tests for F10 hypothesis synthesis."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from .evaluator import EVALUATION_GAPS, evaluate_arm, execute_hypothesis_in_runtime, run_full_comparative_benchmark
from .generator import (
    ExtraComputeGenerator,
    FixedCatalogGenerator,
    NoveltyOnlyGenerator,
    RandomGrammarGenerator,
    StructuralHypothesisGenerator,
)
from .grammar import FalsificationMetric, HypothesisDomain, PropertyKind, TypedHypothesis
from .verify import verify_hypgen_artifact


class F10HypothesisSynthesisTests(unittest.TestCase):
    def test_grammar_typing_and_canonical_hash(self) -> None:
        goal = {
            "schema": "ace.goal.v1",
            "name": "g1",
            "objective": {"kind": "test", "tasks": [{"name": "t1", "train": ["a"], "validation": ["b"]}]},
            "policy": {"authorized_tools": ["ace_enqueue_task"]},
            "budget": {"max_steps": 1},
        }
        h = TypedHypothesis(
            hyp_id="TEST_01",
            domain=HypothesisDomain.REGULAR_LANGUAGE,
            property_kind=PropertyKind.EXPRESSIBILITY_BOUNDARY,
            gap_reference="GAP_01",
            statement="Test statement",
            metric=FalsificationMetric.ACCURACY_MIN,
            threshold=0.80,
            comparator="<",
            goal_spec=goal,
            epistemic_context={"test": True},
        )
        self.assertEqual(len(h.sha256()), 64)
        self.assertTrue(h.is_falsified(0.75))
        self.assertFalse(h.is_falsified(0.85))

    def test_invalid_grammar_types_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TypedHypothesis(
                hyp_id="BAD_01",
                domain="INVALID_DOMAIN",
                property_kind=PropertyKind.EXPRESSIBILITY_BOUNDARY,
                gap_reference="GAP_01",
                statement="Bad",
                metric=FalsificationMetric.ACCURACY_MIN,
                threshold=0.80,
                comparator="<",
                goal_spec={},
                epistemic_context={},
            )

    def test_structural_generator_synthesizes_grounded_hypotheses(self) -> None:
        gen = StructuralHypothesisGenerator(seed=42)
        hyps = gen.generate(EVALUATION_GAPS, gen.rng)
        self.assertEqual(len(hyps), len(EVALUATION_GAPS))
        domains = set(h.domain for h in hyps)
        self.assertIn(HypothesisDomain.CONTEXT_FREE_MIRROR, domains)
        self.assertIn(HypothesisDomain.REPRESENTATION_OCCUPANCY, domains)
        for h in hyps:
            self.assertTrue(h.metric in FalsificationMetric.ALL)
            self.assertTrue(h.threshold is not None)
            self.assertEqual(h.goal_spec["schema"], "ace.goal.v1")

    def test_baseline_arms_generate_falsifiable_hypotheses(self) -> None:
        arms = [
            FixedCatalogGenerator(),
            RandomGrammarGenerator(seed=1),
            NoveltyOnlyGenerator(),
            ExtraComputeGenerator(),
        ]
        import random
        rng = random.Random(42)
        for gen in arms:
            hyps = gen.generate(EVALUATION_GAPS, rng)
            self.assertGreater(len(hyps), 0)
            self.assertTrue(all(h.metric in FalsificationMetric.ALL for h in hyps))

    def test_real_ace_runtime_execution_integration(self) -> None:
        gen = StructuralHypothesisGenerator(seed=123)
        hyps = gen.generate(EVALUATION_GAPS[:1], gen.rng)
        with tempfile.TemporaryDirectory() as tmp_str:
            rt_dir = Path(tmp_str)
            rec = execute_hypothesis_in_runtime(hyps[0], rt_dir)
            self.assertIn("task_id", rec)
            self.assertTrue(rec["completed"])
            self.assertEqual(len(rec["receipt_sha256"]), 64)

    def test_full_comparative_benchmark_and_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            ws = Path(tmp_str)
            report = run_full_comparative_benchmark(workspace=ws, seed=2026)
            self.assertEqual(report["schema"], "ace.f10.hypgen.v1")
            self.assertIn("M5_f10_structural", report["arms"])
            self.assertIn("M1_fixed_catalog", report["arms"])
            self.assertEqual(report["scientific_status"], "SCIENTIFIC_NOT_ASSESSED")
            self.assertEqual(report["release_gate"], "BLOCK_RELEASE")

            # Write and verify artifact
            art_path = ws / "test_artifact.json.gz"
            import gzip
            with gzip.open(art_path, "wb") as f:
                f.write(json.dumps(report).encode("utf-8"))

            v_res = verify_hypgen_artifact(art_path)
            self.assertEqual(v_res["status"], "PASS")
            self.assertEqual(v_res["schema"], "ace.f10.hypgen.v1")


if __name__ == "__main__":
    unittest.main()
