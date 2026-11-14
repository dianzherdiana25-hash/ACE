"""Tests for Epoch B Adversarial Challenger-Solver Co-Evolution & Antibody Engine (`coevolution_arena.py`)."""
from __future__ import annotations

import unittest

from ace_operational.coevolution_arena import (
    AdversarialChallenger,
    AntifragileAntibodyCompiler,
    TrivialChallengeError,
    UnsolvableChallengeError,
    run_coevolution_arena_cycle,
)
from ace_operational.oaie_engine import QUOTA_POLICY_ADAPTER, _build_unseen_quota_task


class CoEvolutionArenaTests(unittest.TestCase):
    def test_multi_wave_coevolution_zero_forgetting_and_antibody_immunization(self):
        r1 = run_coevolution_arena_cycle(seed=20261114)
        r2 = run_coevolution_arena_cycle(seed=20261114)

        self.assertEqual(r1["arena_digest"], r2["arena_digest"])
        self.assertEqual(r1["forgetting_count"], 0)
        self.assertEqual(r1["cumulative_solved"], r1["cumulative_total"])
        self.assertEqual(r1["cumulative_total"], 8)

        # Monotonic cumulative progression across waves 0 -> 1 -> 2
        retained_counts = [w["cumulative_retained"] for w in r1["waves"]]
        self.assertEqual(retained_counts, [3, 6, 8])

        # Antibody immunization blocks all 3 malicious repeat payloads and allows the 1 clean payload
        self.assertEqual(r1["immunization"]["antibodies_compiled"], 4)
        self.assertEqual(r1["blocked_repeat_attacks"], 3)

        # Minimax Nash convergence
        self.assertTrue(r1["minimax_equilibrium"]["is_epsilon_nash"])
        self.assertLess(r1["minimax_equilibrium"]["duality_gap"], 0.08)

    def test_unsolvable_and_trivial_challenges_rejected_fail_closed(self):
        challenger = AdversarialChallenger()
        valid_task = _build_unseen_quota_task(120, variant="boundary")

        # 1. Impossible / broken reference_code is rejected with UnsolvableChallengeError
        impossible_task = {
            **valid_task,
            "task_id": "impossible-quota",
            "reference_code": valid_task["reference_code"].replace("return True", "return False"),
        }
        with self.assertRaises(UnsolvableChallengeError):
            challenger.verify_and_mint_witness(impossible_task, QUOTA_POLICY_ADAPTER)

        # 2. Trivial challenge (buggy_code == reference_code, already passes all shown cases) is rejected
        trivial_task = {
            **valid_task,
            "task_id": "trivial-quota",
            "buggy_code": valid_task["reference_code"],
        }
        with self.assertRaises(TrivialChallengeError):
            challenger.verify_and_mint_witness(trivial_task, QUOTA_POLICY_ADAPTER)

        # 3. Empty antibody signature is rejected
        compiler = AntifragileAntibodyCompiler()
        with self.assertRaises(ValueError):
            compiler.compile_trauma(
                category="bad",
                signature_pattern="",
                mitigation_rule="none",
                raw_trauma="x",
            )


if __name__ == "__main__":
    unittest.main()
