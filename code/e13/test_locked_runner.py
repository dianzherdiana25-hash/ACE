"""Test the lock and the failure boundary without a private bank."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .contract import canonical_json
from .evaluator.order_challenge import MODE, PROTOCOL, _fixture, order_certificate, public_run
from .evaluator.locked_runner import digest, make_plan, verify_lock
from .evaluator.reference_arm import evaluate_reference
from .isolation import (
    READY_MARKER, CandidateWallTimeout, InvalidCandidateAST, WorkerError,
    _sandbox_python, fit_isolated,
)


class LockedRunnerTests(unittest.TestCase):
    def test_public_run_covers_nine_policies_and_reuses_terminal_arms(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run.sqlite"
            report = public_run(path)
            self.assertEqual(report["arms"], 54)
            self.assertEqual(report["by_policy"]["structured_oracle"]["G"]["correct"], 24)
            self.assertEqual(report["by_policy"]["structured_oracle"]["S"]["correct"], 24)
            with patch("e13.evaluator.locked_runner._evaluate", side_effect=AssertionError("repeated fit")):
                self.assertEqual(public_run(path), report)

    def test_sealed_mode_requires_full_bank_and_lock_digest_precedes_admission(self):
        episodes = (_fixture("S"), _fixture("G"))
        with self.assertRaisesRegex(ValueError, "prespecified block"):
            make_plan(episodes, b"oracle", PROTOCOL, mode="sealed_evaluation")
        plan = make_plan(episodes, b"oracle", PROTOCOL, mode=MODE)
        with self.assertRaisesRegex(ValueError, "external anchor"):
            verify_lock(b"{}", digest(b"other"), plan, b"{}", mode=MODE)

    def test_hypothesis_order_cannot_supply_the_answer(self):
        item = _fixture("S")
        first = evaluate_reference(item.fixture, item.hypotheses)
        second = evaluate_reference(item.fixture, item.hypotheses[::-1])
        self.assertEqual(first["ast_sha256"], second["ast_sha256"])
        self.assertEqual(first["scores"], second["scores"])
        self.assertEqual(sum(s["correct"] for s in first["scores"].values()), 8)

    def test_timeout_requires_candidate_phase_evidence(self):
        for stderr, expected in ((b"", WorkerError), (READY_MARKER, CandidateWallTimeout)):
            error = subprocess.TimeoutExpired("worker", 3, stderr=stderr)
            with patch("e13.isolation.subprocess.run", side_effect=error):
                with self.assertRaises(expected) as captured:
                    _sandbox_python([], solver=Path("/public-test"))
                self.assertIs(type(captured.exception), expected)

    def test_bad_program_and_bad_transport_have_distinct_failure_classes(self):
        raw = _fixture("S").fixture.fit_request
        reply = {"program": {"family": "S", "ast": {}}, "candidates": 1, "steps": 1,
                 "status": "fit", "cpu_us": 100, "rss_kib": 1024}
        for message, expected in ((canonical_json(reply), InvalidCandidateAST), (b"{", WorkerError)):
            with patch("e13.isolation._sandbox_python", return_value=(message, 500)):
                with self.assertRaises(expected) as captured:
                    fit_isolated(raw, policy="beam")
                self.assertIs(type(captured.exception), expected)

    def test_all_frozen_transition_definitions_collapse_order_witnesses(self):
        for family in ("S", "G"):
            result = order_certificate(_fixture(family))
            self.assertEqual(result["distinguishing_definitions_per_pair"], [0, 0, 0, 0])
            self.assertEqual(result["max_correct_on_balanced_pairs"], 4)
