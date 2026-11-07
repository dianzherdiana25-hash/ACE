"""Unit and regression tests for ACE Autonomous Self-Development Loop V0.1."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from ace_self_dev import (
    AuthorType,
    CandidateDecision,
    ConfirmationTask,
    SelfDevelopmentCoordinator,
    create_confirmation_suite,
)


class TestSelfDevelopmentLoop(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ckpt_dir = Path(self.temp_dir) / "checkpoints"
        self.evidence_dir = Path(self.temp_dir) / "evidence"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_cycle_execution(self):
        """Execute a complete 8-step autonomous self-development cycle."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        res = coord.run_cycle(
            cycle_id=1,
            task_seed=42,
            mutation_ordinal=1,
            author_type=AuthorType.ACE_AUTONOMOUS_V01,
        )

        self.assertEqual(res["cycle_id"], 1)
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["phase"], "REPORTED")
        self.assertIn("G0_self_dev_root_c1", res["active_head_id"])
        self.assertIn(res["decision"], ("ACCEPTED", "REJECTED"))
        self.assertEqual(res["author_type"], "ACE_AUTONOMOUS_V01")
        self.assertTrue(Path(res["evidence_path"]).exists())

        # Verify evidence artifact payload and decompression
        with gzip.open(res["evidence_path"], "rt", encoding="utf-8") as f:
            evidence = json.load(f)

        self.assertEqual(evidence["benchmark_id"], "ACE_AUTONOMOUS_SELF_DEV_LOOP_V01")
        self.assertEqual(evidence["governance_result"]["release_gate"], "BLOCK_RELEASE")
        self.assertEqual(evidence["governance_result"]["scientific_status"], "NOT_ASSESSED")
        self.assertFalse(evidence["governance_result"]["oaie_established"])

    def test_rejection_of_failing_candidate_and_baseline_retention(self):
        """Candidates with gain < 0.1500 MUST be rejected; active head must remain baseline."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        res = coord.run_cycle(
            cycle_id=2,
            task_seed=42,
            mutation_ordinal=2,
            author_type=AuthorType.ACE_AUTONOMOUS_V01,
        )

        # If gain < 0.1500, verify rejection and active head retention
        if res["gain_over_parent"] < 0.1500:
            self.assertEqual(res["decision"], "REJECTED")
            self.assertFalse(res["is_promoted"])
            self.assertNotIn("CAND_", res["active_head_id"])
            self.assertIn("G0_", res["active_head_id"])

    def test_author_provenance_tracking(self):
        """Explicitly tracks and records whether candidate was created by ACE, Gemini, Codex, or Human."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        for author in (AuthorType.GEMINI, AuthorType.CODEX, AuthorType.HUMAN, AuthorType.ACE_AUTONOMOUS_V01):
            with self.subTest(author=author):
                cand = coord.generator.generate_candidate(
                    hypothesis=coord.hypothesizer.select_hypothesis(
                        coord.diagnoser.diagnose_weakness(lambda w: False, "root", create_confirmation_suite(42)),
                        cycle_id=99,
                    ),
                    author_type=author,
                )
                self.assertEqual(cand.author_type, author)

    def test_durable_checkpoint_persistence_and_loading(self):
        """State is persisted atomically and can be reloaded for resumption."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        coord.run_cycle(cycle_id=3, task_seed=42, mutation_ordinal=3)

        ckpt = coord.checkpointer.load_checkpoint(3)
        self.assertIsNotNone(ckpt)
        self.assertEqual(ckpt.cycle_id, 3)
        self.assertEqual(ckpt.phase, "REPORTED")
        self.assertIn("G0_self_dev_root_c3", ckpt.active_head_id)


if __name__ == "__main__":
    unittest.main()
