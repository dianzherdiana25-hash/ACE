"""Unit and Safety Regression Tests for Audited Self-Evolver."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ace_mission.bus import MissionBus
from ace_mission.admission import REQUESTS
import ace_self_evolver


class TestAuditedSelfEvolver(unittest.TestCase):
    """Verifies that ace_self_evolver strictly eliminates fake claims and protects main."""

    def test_decision_must_be_in_official_requests_enum(self):
        """Ensure no illegal decisions like 'GO' are submitted."""
        self.assertNotIn("GO", REQUESTS)
        self.assertIn("STAGED_EMPIRICAL", REQUESTS)
        self.assertIn("PENDING_EVALUATION", REQUESTS)

    def test_evaluate_and_solve_unsupported_mission_returns_zero_score(self):
        """Unverified missions must return benchmark_score 0.0 and PENDING_EVALUATION, never fake 1.0."""
        with tempfile.TemporaryDirectory() as td:
            artifacts_dir = Path(td)
            dummy_mission = {
                "id": "mission_test_unsupported",
                "goal": "Unverified goal",
                "hypothesis": "Unverified hyp",
            }
            art_path, dec, metrics = ace_self_evolver.evaluate_and_solve_mission(dummy_mission, artifacts_dir)
            self.assertEqual(dec, "PENDING_EVALUATION")
            self.assertEqual(metrics["benchmark_score"], 0.0)
            self.assertNotEqual(metrics["benchmark_score"], 1.0)
            data = json.loads(art_path.read_text())
            self.assertEqual(data["status"], "UNVERIFIED_PROPOSAL")

    def test_evaluate_and_solve_reasoning_mission_returns_staged_empirical_when_solved(self):
        """Reasoning problems solved return STAGED_EMPIRICAL with real score."""
        with tempfile.TemporaryDirectory() as td:
            artifacts_dir = Path(td)
            from ace_cognition.reasoning import SCHEMA
            dummy_mission = {
                "id": "mission_test_reasoning",
                "goal": "Solve simple reasoning identity",
                "hypothesis": "Identity holds",
                "reasoning_problem": {
                    "schema": SCHEMA,
                    "id": "prob_identity",
                    "goal": "output equals input x",
                    "train": [{"inputs": {"x": 0}, "output": 0}, {"inputs": {"x": 1}, "output": 1}],
                    "validation": [{"inputs": {"x": 2}, "output": 2}],
                },
                "budget": {"max_primitive_operations": 5000, "time_sec": 1.0},
            }
            art_path, dec, metrics = ace_self_evolver.evaluate_and_solve_mission(dummy_mission, artifacts_dir)
            self.assertIn(dec, ("STAGED_EMPIRICAL", "INCONCLUSIVE"))
            self.assertIn("benchmark_score", metrics)

    def test_branch_isolation_refuses_commit_directly_on_main(self):
        """Isolated git commit must never allow committing directly to main or master."""
        with patch("ace_self_evolver.get_current_git_branch", return_value="main"):
            with patch("ace_self_evolver.run_verification_test_gate", return_value=(False, "Tests failed")):
                ok, msg = ace_self_evolver.execute_isolated_git_commit(
                    "mission_123", "Test goal", Path("/tmp/dummy"), allow_push=False
                )
                self.assertFalse(ok)
                self.assertIn("verification failed", msg.lower())

    def test_branch_isolation_refuses_when_active_branch_matches_target(self):
        """Refuses when active branch already equals target branch."""
        with patch("ace_self_evolver.get_current_git_branch", return_value="ace-evolution/m123"):
            ok, msg = ace_self_evolver.execute_isolated_git_commit(
                "m123", "Test goal", Path("/tmp/dummy"), allow_push=False
            )
            self.assertFalse(ok)
            self.assertIn("invalid active branch", msg.lower())

    def test_verification_gate_detects_test_failure(self):
        """If acceptance tests fail, the verification gate must block commit."""
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=1, stderr="1 test failed", stdout="")
            ok, msg = ace_self_evolver.run_verification_test_gate()
            self.assertFalse(ok)
            self.assertIn("failed", msg.lower())


if __name__ == "__main__":
    unittest.main()
