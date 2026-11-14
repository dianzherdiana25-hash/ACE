"""Tests for Epoch A Neuro-Formal Program Genesis (`neuro_formal_genesis.py`)."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_component_synthesis.component_synthesizer import TYPE_INT
from ace_operational.neuro_formal_genesis import (
    FormalSkillSpec,
    InvariantViolationError,
    SpecDrivenProgramSynthesizer,
    SpecInconsistencyError,
    build_default_formal_specs,
    run_neuro_formal_genesis_cycle,
)
from ace_operational.oaie_unlimited import AutopoieticSkillForge
from ace_operational.open_world_planner import CapabilityRegistry
from ace_operational.store import OperationalStore


class NeuroFormalGenesisTests(unittest.TestCase):
    def test_zero_template_synthesis_across_four_domains_and_frontier_promotion(self):
        forge = AutopoieticSkillForge()
        res1 = run_neuro_formal_genesis_cycle(forge)
        res2 = run_neuro_formal_genesis_cycle(AutopoieticSkillForge())

        self.assertTrue(res1["zero_handwritten_templates"])
        self.assertEqual(res1["skills_synthesized"], 4)
        self.assertEqual(res1["forgetting_count"], 0)
        self.assertGreater(res1["avg_egraph_compression_ratio"], 1.2)
        self.assertGreater(res1["total_candidates_pruned_oe"], 0)
        self.assertEqual(res1["genesis_digest"], res2["genesis_digest"])

        # Verify synthesized skills execute accurately on unseen inputs
        self.assertEqual(forge.execute_skill("nf_net_tier_settlement", 1000, 250), 750)
        self.assertEqual(forge.execute_skill("nf_net_tier_settlement", 30, 90), 0)
        self.assertTrue(forge.execute_skill("nf_sla_breach_detector", 350, 300))
        self.assertFalse(forge.execute_skill("nf_sla_breach_detector", 250, 300))
        self.assertTrue(forge.execute_skill("nf_token_envelope_guard", "a_valid_b"))
        self.assertFalse(forge.execute_skill("nf_token_envelope_guard", "b_invalid_a"))
        self.assertEqual(forge.execute_skill("nf_compound_margin", 1000, 300, 50), 750)

        # Verify promotion into OperationalStore Frontier
        with tempfile.TemporaryDirectory(prefix="nf-store-") as d:
            store = OperationalStore(workspace=Path(d))
            self.addCleanup(store.close)
            reg = CapabilityRegistry()
            promoted = forge.register_into_frontier(store, reg)
            self.assertEqual(len(promoted), 4)
            frontier_ids = {c["capability_id"] for c in store.list_frontier()}
            for cap_id in promoted:
                self.assertIn(cap_id, frontier_ids)

    def test_adversarial_contradictory_spec_and_smt_invariant_violation_fail_closed(self):
        forge = AutopoieticSkillForge()
        synth = SpecDrivenProgramSynthesizer()

        # 1. Contradictory I/O specification (same input mapped to two different outputs)
        bad_io_spec = FormalSkillSpec(
            skill_id="bad_contradictory",
            title="Contradictory Spec",
            domain="test",
            entrypoint="fn_bad",
            arg_names=("x",),
            return_type=TYPE_INT,
            shown_io=(((5,), 10), ((5,), 20)),
            holdout_io=(((6,), 12),),
        )
        with self.assertRaises(SpecInconsistencyError):
            forge.synthesize_from_spec(bad_io_spec)

        # 2. SMT lower-bound invariant violation (synthesized x - y produces negative on holdout when min_output_bound=0)
        smt_violating_spec = FormalSkillSpec(
            skill_id="bad_smt_bound",
            title="Violates Non-Negative SMT Bound",
            domain="test",
            entrypoint="fn_sub",
            arg_names=("x", "y"),
            return_type=TYPE_INT,
            shown_io=(((10, 3), 7), ((20, 5), 15), ((8, 2), 6)),
            holdout_io=(((3, 10), -7),),
            min_output_bound=0,
        )
        with self.assertRaises(InvariantViolationError):
            synth.synthesize_from_spec(smt_violating_spec, forge)

        # 3. Craig interpolation violation (A and B share symbol and are mutually SAT)
        bad_craig_spec = FormalSkillSpec(
            skill_id="bad_craig",
            title="Violates Craig Unsat Condition",
            domain="test",
            entrypoint="fn_craig",
            arg_names=("x",),
            return_type=TYPE_INT,
            shown_io=(((1,), 1), ((2,), 2)),
            holdout_io=(((3,), 3),),
            craig_pre_clauses=(("p",),),
            craig_bad_clauses=(("p",),),
        )
        with self.assertRaises(InvariantViolationError):
            synth.synthesize_from_spec(bad_craig_spec, forge)


if __name__ == "__main__":
    unittest.main()
