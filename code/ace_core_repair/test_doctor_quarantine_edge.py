"""Edge-case unit tests for ace_core_repair (doctor.py and drift_quarantine.py)."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from ace_core_repair.doctor import run_doctor_diagnostics
from ace_core_repair.drift_quarantine import SemanticDriftQuarantine


class TestCoreRepairDoctorAndQuarantineEdgeCases(unittest.TestCase):
    def test_01_doctor_healthy_on_real_repo_when_workspace_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_ws = Path(tmp) / "no_such_ws"
            rep = run_doctor_diagnostics(workspace=missing_ws)
            self.assertEqual(rep["overall_health"], "HEALTHY")
            self.assertTrue(rep["source_integrity_pass"])
            self.assertFalse(rep["checks"]["workspace_exists"]["pass"])

    def test_02_doctor_detects_existing_workspace_and_none_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rep_yes = run_doctor_diagnostics(workspace=Path(tmp))
            self.assertTrue(rep_yes["checks"]["workspace_exists"]["pass"])
        rep_none = run_doctor_diagnostics(workspace=None)  # type: ignore[arg-type]
        self.assertFalse(rep_none["checks"]["workspace_exists"]["pass"])

    def test_03_doctor_sealed_seed_env_var_toggles_status(self) -> None:
        with patch.dict(os.environ, {"ACE_SEALED_SEED": "1"}, clear=False):
            rep = run_doctor_diagnostics()
            self.assertEqual(rep["checks"]["scientific_claim_gate"]["status"], "CONFIRMED_SEALED")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACE_SEALED_SEED", None)
            rep = run_doctor_diagnostics()
            self.assertIn("NOT_ASSESSED", rep["checks"]["scientific_claim_gate"]["status"])

    def test_04_doctor_degrades_when_verify_sources_raises(self) -> None:
        with patch("tools.verify_sources.verify", side_effect=ValueError("hash mismatch")):
            rep = run_doctor_diagnostics()
        self.assertEqual(rep["overall_health"], "DEGRADED")
        self.assertFalse(rep["source_integrity_pass"])
        self.assertFalse(rep["checks"]["source_integrity"]["pass"])
        self.assertIn("hash mismatch", rep["checks"]["source_integrity"]["details"])

    def test_05_doctor_marginal_financial_spend_invariant_present(self) -> None:
        rep = run_doctor_diagnostics()
        self.assertTrue(rep["checks"]["marginal_financial_spend"]["pass"])
        self.assertIn("Rp0", rep["checks"]["marginal_financial_spend"]["cost"])

    def test_06_quarantine_empty_base_and_empty_incoming_is_consistent(self) -> None:
        q = SemanticDriftQuarantine()
        status, meta = q.check_distribution_consistency([], [])
        self.assertEqual(status, "CONSISTENT")
        self.assertFalse(meta["quarantined"])
        self.assertEqual(meta["discrepancy_rate"], 0.0)
        self.assertEqual(meta["false_admission_count"], 0)

    def test_07_quarantine_disjoint_observations_consistent(self) -> None:
        q = SemanticDriftQuarantine()
        status, meta = q.check_distribution_consistency([("a", True)], [("b", False)])
        self.assertEqual(status, "CONSISTENT")
        self.assertFalse(meta["quarantined"])

    def test_08_quarantine_identical_overlapping_observations_consistent(self) -> None:
        q = SemanticDriftQuarantine()
        status, meta = q.check_distribution_consistency([("a", True), ("b", False)], [("a", True), ("b", False)])
        self.assertEqual(status, "CONSISTENT")
        self.assertEqual(meta["discrepancy_rate"], 0.0)

    def test_09_quarantine_single_flip_triggers_fail_closed_abstain(self) -> None:
        q = SemanticDriftQuarantine(consistency_threshold=0.95)
        status, meta = q.check_distribution_consistency([("a", True)], [("a", False)])
        self.assertEqual(status, "ABSTAIN")
        self.assertTrue(meta["quarantined"])
        self.assertEqual(meta["conflicts"], 1)
        self.assertEqual(meta["overlap"], 1)
        self.assertEqual(meta["false_admission_count"], 0)
        self.assertEqual(meta["reason"], "LATE_FLIP_SEMANTIC_MUTATION_DETECTED")

    def test_10_quarantine_threshold_above_allowed_margin_abstains(self) -> None:
        # 2 conflicts out of 20 = 0.10 > 0.05
        q = SemanticDriftQuarantine(consistency_threshold=0.95)
        base = [(f"k{i}", True) for i in range(20)]
        inc = [(f"k{i}", i >= 2) for i in range(20)]
        status, meta = q.check_distribution_consistency(base, inc)
        self.assertEqual(status, "ABSTAIN")
        self.assertEqual(meta["discrepancy_rate"], 0.1)

    def test_11_quarantine_threshold_strictly_below_margin_remains_consistent(self) -> None:
        # 1 conflict out of 40 = 0.025 < 0.05
        q = SemanticDriftQuarantine(consistency_threshold=0.95)
        base = [(f"k{i}", True) for i in range(40)]
        inc = [(f"k{i}", i != 0) for i in range(40)]
        status, meta = q.check_distribution_consistency(base, inc)
        self.assertEqual(status, "CONSISTENT")
        self.assertEqual(meta["discrepancy_rate"], 0.025)

    def test_12_quarantine_threshold_1_point_0_abstains_on_any_conflict(self) -> None:
        q = SemanticDriftQuarantine(consistency_threshold=1.0)
        base = [(f"k{i}", True) for i in range(100)]
        inc = [(f"k{i}", i != 99) for i in range(100)]
        status, _ = q.check_distribution_consistency(base, inc)
        self.assertEqual(status, "ABSTAIN")

    def test_13_quarantine_threshold_0_point_0_permits_total_contradiction(self) -> None:
        q = SemanticDriftQuarantine(consistency_threshold=0.0)
        status, meta = q.check_distribution_consistency([("x", True)], [("x", False)])
        self.assertEqual(status, "CONSISTENT")
        self.assertEqual(meta["discrepancy_rate"], 1.0)

    def test_14_quarantine_duplicate_base_keys_last_value_wins(self) -> None:
        q = SemanticDriftQuarantine()
        status, _ = q.check_distribution_consistency([("x", True), ("x", False)], [("x", False)])
        self.assertEqual(status, "CONSISTENT")

    def test_15_quarantine_duplicate_incoming_keys_weighted_in_overlap(self) -> None:
        q = SemanticDriftQuarantine(consistency_threshold=0.5)
        # 1 conflict in 3 duplicate occurrences => 0.3333 <= 0.5 => CONSISTENT
        status, meta = q.check_distribution_consistency([("x", True)], [("x", True), ("x", True), ("x", False)])
        self.assertEqual(status, "CONSISTENT")
        self.assertEqual(meta["discrepancy_rate"], 0.3333)

    def test_16_quarantine_ignores_extra_non_overlapping_incoming_items(self) -> None:
        q = SemanticDriftQuarantine(consistency_threshold=0.95)
        base = [("shared", True)]
        inc = [("shared", False)] + [(f"new_{i}", True) for i in range(50)]
        status, meta = q.check_distribution_consistency(base, inc)
        self.assertEqual(status, "ABSTAIN")
        self.assertEqual(meta["overlap"], 1)

    def test_17_quarantine_does_not_mutate_input_lists(self) -> None:
        q = SemanticDriftQuarantine()
        base = [("a", True), ("b", False)]
        inc = [("a", False)]
        q.check_distribution_consistency(base, inc)
        self.assertEqual(base, [("a", True), ("b", False)])
        self.assertEqual(inc, [("a", False)])

    def test_18_quarantine_unicode_and_empty_string_keys(self) -> None:
        q = SemanticDriftQuarantine()
        status, meta = q.check_distribution_consistency([("", True), ("αβγ", False)], [("", False), ("αβγ", False)])
        self.assertEqual(status, "ABSTAIN")
        self.assertEqual(meta["conflicts"], 1)
        self.assertEqual(meta["overlap"], 2)

    def test_19_quarantine_exact_boundary_discrepancy_half_with_exact_binary_threshold(self) -> None:
        # 0.5 is exact in IEEE 754: discrepancy_rate == 0.5 is NOT > 0.5 => CONSISTENT
        q = SemanticDriftQuarantine(consistency_threshold=0.5)
        status, meta = q.check_distribution_consistency([("a", True), ("b", True)], [("a", True), ("b", False)])
        self.assertEqual(status, "CONSISTENT")
        self.assertEqual(meta["discrepancy_rate"], 0.5)

    @unittest.expectedFailure
    def test_20_suspected_float_boundary_bug_1_minus_0_95_exact_equal_triggers_abstain(self) -> None:
        # Suspected precision boundary bug in code/ace_core_repair/drift_quarantine.py:
        # `1 - 0.95 == 0.050000000000000044`, whereas with consistency_threshold=0.90,
        # `1.0 - 0.9 == 0.09999999999999998`, so exact 0.10 discrepancy incorrectly exceeds `1 - 0.9`!
        q = SemanticDriftQuarantine(consistency_threshold=0.9)
        base = [(f"k{i}", True) for i in range(10)]
        inc = [(f"k{i}", i != 0) for i in range(10)]
        status, _ = q.check_distribution_consistency(base, inc)
        self.assertEqual(status, "CONSISTENT")

    def test_21_doctor_returns_expected_top_level_keys(self) -> None:
        rep = run_doctor_diagnostics()
        self.assertEqual(set(rep.keys()), {"overall_health", "source_integrity_pass", "checks"})

    def test_22_quarantine_false_admission_count_always_zero(self) -> None:
        q = SemanticDriftQuarantine()
        for inc in ([("a", True)], [("a", False)], []):
            _, meta = q.check_distribution_consistency([("a", True)], inc)
            self.assertEqual(meta["false_admission_count"], 0)


if __name__ == "__main__":
    unittest.main()
