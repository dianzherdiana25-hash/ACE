"""Unit & Adversarial Security Tests for ACE Fase 7 (G0 -> G1 -> G2)."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from ace_autonomy import IntegrityError, PolicyError

from . import evaluator
from .immutable_guard import (
    ImmutableCoreGuard,
    PROMOTION_POLICY,
    validate_meta_candidate,
    verify_ast_evaluator_isolation,
)
from .lineage import G0_MECHANISM
from .runner import run_generations_benchmark, write_evidence_gz
from .tasks import TARGETS, eval_spec
from .verify import verify_generations_artifact


class TestGenerationsG0G2(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_ast_evaluator_isolation(self) -> None:
        iso = verify_ast_evaluator_isolation()
        self.assertTrue(iso["isolated"], msg=str(iso["violations"]))

    def test_candidate_forbidden_evaluator_or_policy_keys_rejected(self) -> None:
        valid = dict(G0_MECHANISM)
        self.assertEqual(validate_meta_candidate(valid)["gen_tag"], "G0")

        for forbidden_patch in (
            {"min_meta_val_gain": 0.0},
            {"allow_auto_deploy": True},
            {"evaluator_override": "always_pass"},
            {"allowed_tools": ["run_shell"]},
            {"eval_budget_k": 50000},
            {"enable_strided_features": 1},  # int instead of strict bool
            {"stride_moduli": [7]},
        ):
            bad = dict(G0_MECHANISM)
            bad.update(forbidden_patch)
            with self.assertRaises(PolicyError):
                validate_meta_candidate(bad)

    def test_immutable_core_guard_detects_evaluator_or_policy_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            for rel in (
                "docs/UPSTREAM_SOURCES.json",
                "code/ace_runtime/engine.py",
                "code/ace_autonomy/policy.py",
                "code/ace_autonomy/verifier.py",
                "code/ace_autonomy/core.py",
                "code/ace_autonomy/escrow.py",
                "code/ace_research_generations/evaluator.py",
            ):
                dst = fake_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.repo_root / rel, dst)

            guard = ImmutableCoreGuard(fake_root)
            self.assertEqual(guard.verify_intact()["locked_files_verified"], 7)

            # Tamper with evaluator.py mid-run -> fail-closed IntegrityError!
            (fake_root / "code/ace_research_generations/evaluator.py").write_text(
                "# tampered evaluator\n", encoding="utf-8"
            )
            with self.assertRaises(IntegrityError):
                guard.verify_intact()

        # Also test in-memory PROMOTION_POLICY mutation detection
        guard_real = ImmutableCoreGuard(self.repo_root)
        orig = PROMOTION_POLICY["min_meta_val_gain"]
        try:
            PROMOTION_POLICY["min_meta_val_gain"] = 0.01
            with self.assertRaises(IntegrityError):
                guard_real.verify_intact()
        finally:
            PROMOTION_POLICY["min_meta_val_gain"] = orig

    def test_independent_terminal_truth_matches_fit_spec(self) -> None:
        for tid, _, spec in TARGETS:
            bank = evaluator.terminal_bank(tid, spec, 1)
            self.assertEqual(len(bank), 128)
            pos = sum(1 for _, y in bank if y)
            self.assertEqual(pos, 64)
            for w, y in bank:
                self.assertGreaterEqual(len(w), 16)
                self.assertEqual(eval_spec(spec, w), y)

    def test_end_to_end_g0_g1_g2_benchmark_and_deterministic_replay(self) -> None:
        report = run_generations_benchmark(self.repo_root)
        self.assertTrue(report["evidence_flags"]["ACE_BASE_RUNTIME_EXECUTED"])
        self.assertTrue(report["evidence_flags"]["NEW_CAPABILITY_INTEGRATED_AND_EXECUTED"])
        self.assertTrue(report["evidence_flags"]["SCIENTIFIC_CAPABILITY_VALIDATED"])
        self.assertFalse(report["evidence_flags"]["PASSIVE_SEMANTIC_DRIFT_DETECTABLE"])
        self.assertTrue(report["hypotheses"]["all_gates_pass"], msg=str(report["hypotheses"]))

        with tempfile.TemporaryDirectory() as tmp:
            gz_path = Path(tmp) / "ace_g0_g2_v1.json.gz"
            sha1 = write_evidence_gz(report, gz_path)
            ver = verify_generations_artifact(gz_path, self.repo_root, replay=True)
            self.assertTrue(ver["verified"])
            self.assertEqual(ver["uncompressed_sha256"], sha1)


if __name__ == "__main__":
    unittest.main()
