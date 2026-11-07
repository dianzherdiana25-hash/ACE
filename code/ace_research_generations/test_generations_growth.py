"""Unit & Adversarial Tests for P4 Cross-Generation Capability Growth."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from .growth import (
    GROWTH_TARGETS,
    eval_growth_spec,
    growth_terminal_bank,
    run_generations_growth_benchmark,
    write_growth_evidence_gz,
)
from .immutable_guard import verify_ast_evaluator_isolation
from .verify_growth import verify_generations_growth_artifact


class TestGenerationsGrowth(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_ast_evaluator_isolation(self) -> None:
        iso = verify_ast_evaluator_isolation()
        self.assertTrue(iso["isolated"], msg=str(iso["violations"]))

    def test_independent_truth_consistency(self) -> None:
        """Verify ground truth matches independent terminal bank draws."""
        for tid, _, spec in GROWTH_TARGETS:
            bank = growth_terminal_bank(tid, spec, 1)
            self.assertEqual(len(bank), 128)
            pos_cnt = sum(1 for _, y in bank if y)
            self.assertEqual(pos_cnt, 64)
            for w, y in bank:
                self.assertGreaterEqual(len(w), 16)
                self.assertEqual(eval_growth_spec(spec, w), y)

    def test_run_growth_benchmark_and_hypothesis_evaluation(self) -> None:
        """Run full benchmark and verify all pre-registered gates."""
        report = run_generations_growth_benchmark(self.repo_root)
        self.assertEqual(report["schema"], "ace.generations.growth.v1")
        self.assertEqual(report["scientific_status"], "NOT_ASSESSED")
        self.assertEqual(report["release_status"], "BLOCK_RELEASE")
        self.assertFalse(report["oaie_established"])
        self.assertTrue(report["evidence_flags"]["ACE_BASE_RUNTIME_EXECUTED"])
        self.assertTrue(report["evidence_flags"]["NEW_CAPABILITY_INTEGRATED_AND_EXECUTED"])
        self.assertFalse(report["evidence_flags"]["SCIENTIFIC_CAPABILITY_VALIDATED"])
        self.assertFalse(report["evidence_flags"]["PASSIVE_SEMANTIC_DRIFT_DETECTABLE"])

        hyps = report["hypotheses"]
        self.assertTrue(hyps["H1_growth_advantage"]["passed"], msg=str(hyps))
        self.assertTrue(hyps["H2_compute_amortization"]["passed"], msg=str(hyps))
        self.assertTrue(hyps["H3_semantic_drift_unobservability"]["passed"], msg=str(hyps))
        self.assertTrue(hyps["H4_lineage_and_immutability"]["passed"], msg=str(hyps))
        self.assertTrue(hyps["all_gates_pass"])

        # Test artifact write and replay verification
        with tempfile.TemporaryDirectory() as tmp:
            gz = Path(tmp) / "test_growth.json.gz"
            sha = write_growth_evidence_gz(report, gz)
            res = verify_generations_growth_artifact(gz, self.repo_root, replay=False)
            self.assertTrue(res["verified"])
            self.assertEqual(res["uncompressed_sha256"], sha)


if __name__ == "__main__":
    unittest.main()
