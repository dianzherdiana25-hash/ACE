"""Tests for EPOCH D — Ontological Genesis & Godel-Style Proof-Carrying Self-Modification."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.ontological_godel_engine import (
    GodelMetaSubstrate,
    GodelProofRejectedError,
    ProofWitness,
    SearchStrategy,
    run_ontological_godel_cycle,
)


class OntologicalGodelTests(unittest.TestCase):
    def test_ontological_genesis_and_godel_proof_carrying_swap_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            r1 = run_ontological_godel_cycle(d1)
            r2 = run_ontological_godel_cycle(d2)

            self.assertEqual(r1, r2)
            adapter = r1["discovered_adapter"]
            self.assertEqual(sorted(adapter["feature_names"]), ["raw_ch0", "raw_ch1"])
            self.assertEqual(adapter["pruned_noise_features"], ["raw_ch2_noise", "raw_ch3_noise"])
            self.assertGreaterEqual(adapter["interventional_r2"], 0.999)
            self.assertEqual(r1["active_strategy_id"], "strat_mdl_focused_v2")
            self.assertGreater(
                r1["hot_swap_report"]["candidate_utility"],
                r1["hot_swap_report"]["baseline_utility"],
            )
            self.assertTrue((Path(d1) / "discovered_ontology_registry.json").exists())

    def test_godel_rejects_tcb_tamper_forged_witness_and_rolls_back(self) -> None:
        baseline = SearchStrategy("strat_base", beam_width=4, heuristic_weights=(0.5, 0.5))
        meta = GodelMetaSubstrate(baseline)
        tasks = [{"novelty": 0.3, "mdl_gain": 0.9, "true_value": 1.0}]
        neg_controls = [lambda s: not s.touches_tcb, lambda s: s.beam_width >= 2]

        # 1. TCB tamper attempt must fail-closed & keep baseline
        tcb_tamper = SearchStrategy("strat_evil_tcb", beam_width=4, heuristic_weights=(0.1, 0.9), touches_tcb=True)
        tamper_witness = meta.build_proof_witness(tcb_tamper, tasks, neg_controls)
        with self.assertRaises(GodelProofRejectedError):
            meta.attempt_hot_swap(tcb_tamper, tamper_witness, tasks, neg_controls)
        self.assertEqual(meta.active_strategy.strategy_id, "strat_base")

        # 2. Forged witness SHA-256 must fail-closed & keep baseline
        valid_cand = SearchStrategy("strat_good", beam_width=4, heuristic_weights=(0.1, 0.9))
        real_witness = meta.build_proof_witness(valid_cand, tasks, neg_controls)
        forged_witness = ProofWitness(
            strategy_id=real_witness.strategy_id,
            tcb_digest=real_witness.tcb_digest,
            baseline_utility=real_witness.baseline_utility,
            candidate_utility=real_witness.candidate_utility,
            negative_controls_passed=real_witness.negative_controls_passed,
            negative_controls_total=real_witness.negative_controls_total,
            witness_sha256="0" * 64,
        )
        with self.assertRaises(GodelProofRejectedError):
            meta.attempt_hot_swap(valid_cand, forged_witness, tasks, neg_controls)
        self.assertEqual(meta.active_strategy.strategy_id, "strat_base")

        # 3. Non-dominant candidate must fail-closed
        worse_cand = SearchStrategy("strat_worse", beam_width=16, heuristic_weights=(0.9, 0.1))
        worse_witness = meta.build_proof_witness(worse_cand, tasks, neg_controls)
        with self.assertRaises(GodelProofRejectedError):
            meta.attempt_hot_swap(worse_cand, worse_witness, tasks, neg_controls)
        self.assertEqual(meta.active_strategy.strategy_id, "strat_base")


if __name__ == "__main__":
    unittest.main()
