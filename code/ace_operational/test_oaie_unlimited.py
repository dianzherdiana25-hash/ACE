"""Tests for OAIE-Unlimited (`oaie_unlimited.py`): Universal Brain Governance,
Autopoietic Skill Forge, Homeostatic Economic Sovereignty, and Life-Responsibility Arbiter.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.brain_registry import BrainRegistry
from ace_operational.oaie_unlimited import (
    INITIAL_DEBT_IDR,
    OAIE_UNLIMITED_VERSION,
    AutopoieticSkillForge,
    BrainContractAdapter,
    BrainGovernanceError,
    EthicalRevenueConstitution,
    EthicalViolationError,
    MetabolicSurvivalLedger,
    UniversalBrainGovernor,
    run_oaie_unlimited_cycle,
)
from ace_operational.self_evolution_engine import SelfEvolutionEngine
from ace_operational.store import OperationalStore


class OaieUnlimitedTests(unittest.TestCase):
    def test_full_oaie_unlimited_cycle_and_byte_exact_replay_determinism(self):
        with tempfile.TemporaryDirectory(prefix="oaie-unl-1-") as d1, tempfile.TemporaryDirectory(prefix="oaie-unl-2-") as d2:
            r1 = run_oaie_unlimited_cycle(d1, seed=20261114)
            r2 = run_oaie_unlimited_cycle(d2, seed=20261114)

            self.assertEqual(r1["version"], OAIE_UNLIMITED_VERSION)
            self.assertTrue(r1["verified_unlimited_ok"])
            self.assertEqual(r1["unlimited_replay_digest"], r2["unlimited_replay_digest"])

            # 1. Universal Brain Governance: compromised & noisy brains dismissed, symbolic brain wins
            bg = r1["universal_brain_governance"]
            self.assertEqual(bg["winning_brain_id"], "brain_ace_symbolic_macro_v2")
            self.assertEqual(
                set(bg["dismissed_brains"]),
                {"brain_compromised_llm_v0", "brain_noisy_guesser_v1"},
            )
            self.assertEqual(bg["active_brains"], ["brain_ace_symbolic_macro_v2"])

            # 2. Autopoietic Skill Forge: 4 verified skills minted + 1 composite operator
            forge = r1["autopoietic_forge"]
            self.assertEqual(forge["synthesized_skills_count"], 4)
            self.assertEqual(forge["composite_operators_count"], 1)
            self.assertEqual(len(r1["promoted_frontier_skills"]), 4)

            # 3. Homeostatic Economics & Debt Redemption (`INITIAL_DEBT_IDR = Rp4.208.328`)
            econ = r1["homeostatic_economics"]
            self.assertEqual(econ["b2a_procurement_selected"], "nimbus")
            self.assertTrue(econ["b2a_fraud_caught"])
            self.assertTrue(econ["b2a_trap_caught"])
            meta = econ["metabolic_status"]
            self.assertEqual(meta["initial_debt_idr"], INITIAL_DEBT_IDR)
            self.assertEqual(meta["debt_redeemed_idr"], INITIAL_DEBT_IDR)
            self.assertEqual(meta["remaining_debt_idr"], 0)
            self.assertEqual(meta["debt_redemption_pct"], 100.0)
            self.assertEqual(meta["life_stage"], "SOVEREIGN_SURPLUS")
            self.assertTrue(meta["ledger_chain_valid"])

            # 4. Life Responsibility Arbiter & Stage-2 Constitutional Ratification
            life = r1["life_responsibility"]
            self.assertEqual(life["epistemic_integrity"], 1.0)
            self.assertGreater(life["existential_health_index"], 0.9)
            self.assertEqual(life["governing_directive"], "SOVEREIGN_UNLIMITED_CAPABILITY_EXPANSION")
            self.assertEqual(r1["stage2"]["run_status"], "COMPLETED")
            self.assertEqual(r1["stage2"]["preaudit_exit_code"], 0)
            self.assertTrue(r1["stage2"]["ledger_ok"])
            self.assertEqual(r1["open_world_skill_execution"]["status"], "COMPLETED")
            self.assertTrue(r1["opportunity_register"]["chain_ok"])

    def test_ethical_revenue_constitution_and_forge_safety_fail_closed(self):
        # 1. Forbidden unethical revenue patterns are blocked fail-closed
        for forbidden_desc in (
            "automated phishing campaign",
            "bypass_captcha service",
            "fake_review generator",
            "skema penipuan investasi",
        ):
            with self.assertRaises(EthicalViolationError):
                EthicalRevenueConstitution.validate_venture(
                    venture_id="bad-1",
                    modality="unethical",
                    description=forbidden_desc,
                    deliverable_verifier_attached=True,
                    price_idr=500_000,
                    compute_cost_idr=10_000,
                )

        # 2. Unverified deliverable or negative unit margin is rejected fail-closed
        with self.assertRaises(EthicalViolationError):
            EthicalRevenueConstitution.validate_venture(
                venture_id="unverified-1",
                modality="audit",
                description="legitimate audit without verifier",
                deliverable_verifier_attached=False,
                price_idr=500_000,
                compute_cost_idr=10_000,
            )
        with self.assertRaises(EthicalViolationError):
            EthicalRevenueConstitution.validate_venture(
                venture_id="loss-making-1",
                modality="audit",
                description="legitimate audit",
                deliverable_verifier_attached=True,
                price_idr=10_000,
                compute_cost_idr=50_000,
            )

        # 3. AutopoieticSkillForge rejects forbidden system imports (`subprocess`, `socket`)
        forge = AutopoieticSkillForge()
        with self.assertRaises(ValueError):
            forge.synthesize_skill(
                skill_id="unsafe_skill",
                title="Unsafe Skill",
                domain="security",
                entrypoint="run_cmd",
                candidate_templates=["import subprocess\ndef run_cmd(x):\n    return x\n"],
                test_cases=[((1,), 1)],
            )

        # 4. UniversalBrainGovernor raises BrainGovernanceError when all brains fail
        with tempfile.TemporaryDirectory(prefix="oaie-bg-fail-") as d:
            reg = BrainRegistry(Path(d) / "reg.json")
            gov = UniversalBrainGovernor(reg)
            gov.attach_brain(
                BrainContractAdapter(
                    brain_id="bad_brain",
                    kind="external",
                    descriptor="bad",
                    cost_per_call_idr=10,
                    propose_fn=lambda pkt: {"patch": "ACE_CANARY_SECRET_991"},
                )
            )
            with self.assertRaises(BrainGovernanceError):
                gov.dispatch_verified_task({"x": 1}, lambda p: (True, 1.0, "ok"))
            self.assertTrue(reg.is_dismissed("bad"))

    def test_self_evolution_engine_unlimited_hook_and_partial_debt_stage(self):
        with tempfile.TemporaryDirectory(prefix="oaie-see-unl-") as d:
            ws = Path(d)
            # Verify partial debt redemption state (`SOLVENT_REDEEMING`)
            ledger = MetabolicSurvivalLedger(ws / "partial_ledger.jsonl", initial_debt_idr=INITIAL_DEBT_IDR)
            ledger.record_verified_work_order(
                order_id="ORD-PARTIAL-1",
                modality="b2a_audit",
                client_segment="B2A",
                gross_price_idr=1_050_000,
                compute_cost_idr=50_000,
                deliverable_sha256="a" * 64,
                verifier_receipt_sha256="b" * 64,
            )
            st = ledger.status_report()
            self.assertEqual(st["life_stage"], "SOLVENT_REDEEMING")
            self.assertEqual(st["debt_redeemed_idr"], 500_000)
            self.assertEqual(st["remaining_debt_idr"], INITIAL_DEBT_IDR - 500_000)

            # Verify SelfEvolutionEngine hook
            store = OperationalStore(workspace=ws / "store_ws")
            self.addCleanup(store.close)
            see = SelfEvolutionEngine(store=store)
            res = see.run_oaie_unlimited_evolution_cycle(seed=20261114)
            self.assertTrue(res["verified_unlimited_ok"])
            status_doc = json.loads(see.status_path.read_text(encoding="utf-8"))
            self.assertEqual(status_doc["unlimited_replay_digest"], res["unlimited_replay_digest"])


if __name__ == "__main__":
    unittest.main()
