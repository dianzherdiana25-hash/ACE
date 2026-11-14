"""Tests for Epoch C Multi-File Causal Repository Evolution & Conformal Truth Market (`causal_repo_evolution.py`)."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.causal_repo_evolution import (
    CartographyOfIgnorance,
    CausalMultiFileRepoEvolver,
    WeakTestSuiteOrOverfitError,
    run_causal_repo_evolution_cycle,
)
from ace_operational.oaie_unlimited import UniversalBrainGovernor


class CausalRepoEvolutionTests(unittest.TestCase):
    def test_causal_do_calculus_localization_cross_file_patch_and_truth_market(self):
        with tempfile.TemporaryDirectory(prefix="epoch-c-1-") as d1, tempfile.TemporaryDirectory(prefix="epoch-c-2-") as d2:
            r1 = run_causal_repo_evolution_cycle(d1)
            r2 = run_causal_repo_evolution_cycle(d2)

            self.assertEqual(r1["epoch_c_digest"], r2["epoch_c_digest"])

            # 1. Causal localization prunes correlated confounder noise_logger.py and isolates true suspects
            causal = r1["causal_localization"]
            self.assertGreater(causal["observational_corr_noise_logger"], 0.5)
            self.assertTrue(causal["noise_d_separated_given_subtotal"])
            self.assertEqual(causal["pruned_confounders"], ["noise_logger.py"])
            self.assertEqual(causal["causal_suspects"], ["discount_policy.py", "tax_rules.py"])

            # 2. Cross-file patch lifts repo pass count from 0/4 to 4/4 and kills 4/4 mutants
            self.assertEqual(r1["baseline_passed"], 0)
            self.assertEqual(r1["patch_report"]["passed_cases"], 4)
            self.assertEqual(r1["mutation_report"]["mutation_kill_rate"], 1.0)

            # 3. Internal Epistemic Prediction Market bankrupts and dismisses overconfident hallucinator
            standings = {s["brain_id"]: s for s in r1["truth_market"]["standings"]}
            self.assertEqual(standings["brain_overconfident_hallucinator"]["status"], "dismissed")
            self.assertLessEqual(standings["brain_overconfident_hallucinator"]["credits"], 20.0)
            self.assertEqual(standings["brain_causal_multifile_solver"]["status"], "active")
            self.assertGreater(standings["brain_counterexample_hunter"]["credits"], 150.0)

            # 4. Cartography of Ignorance maps PROVED, CONFORMAL_BOUNDED, and ABSTAIN_FOR_EXPERIMENT
            cart = r1["cartography"]
            self.assertEqual(cart["proved"]["zone"], "PROVED")
            self.assertTrue(cart["proved"]["can_promote"])
            self.assertEqual(cart["conformal_bounded"]["zone"], "CONFORMAL_BOUNDED")
            self.assertTrue(cart["conformal_bounded"]["can_promote"])
            self.assertEqual(cart["abstain"]["zone"], "ABSTAIN_FOR_EXPERIMENT")
            self.assertFalse(cart["abstain"]["can_promote"])

    def test_atomic_rollback_on_bad_patch_and_weak_test_suite_rejected(self):
        with tempfile.TemporaryDirectory(prefix="epoch-c-neg-") as d:
            evolver = CausalMultiFileRepoEvolver(Path(d) / "repo")
            evolver.materialize_buggy_multi_file_repo()
            orig_tax = (evolver.repo_dir / "tax_rules.py").read_text(encoding="utf-8")

            cases = [((1000, 1000, 10, 10), 990)]
            # 1. Bad cross-file patch triggers exception and restores original file atomically
            with self.assertRaises(RuntimeError):
                evolver.apply_atomic_cross_file_patch(
                    {"tax_rules.py": "def compute_regional_tax(net_amount, tax_pct):\n    return -999\n"},
                    cases,
                )
            self.assertEqual((evolver.repo_dir / "tax_rules.py").read_text(encoding="utf-8"), orig_tax)

            # 2. UniversalBrainGovernor hook returns ABSTAIN_FOR_EXPERIMENT when errors > 0
            zone_doc = UniversalBrainGovernor.evaluate_epistemic_zone(
                deterministic_proof=False,
                mutation_kill_rate=0.5,
                empirical_errors=5,
                sample_size=20,
                kl_divergence=2.0,
                calibration_scores=[0.4, 0.5, 0.6],
            )
            self.assertEqual(zone_doc["zone"], "ABSTAIN_FOR_EXPERIMENT")
            self.assertFalse(zone_doc["can_promote"])


if __name__ == "__main__":
    unittest.main()
