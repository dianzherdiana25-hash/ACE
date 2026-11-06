"""R1 H3 regression and adversarial evidence-tamper tests."""
from __future__ import annotations
import copy
import json
import unittest

try:
    from . import hard_dfa_study as h3
    from . import audit_h3 as audit
    from . import primitive_discovery as d
except ImportError:
    import hard_dfa_study as h3
    import audit_h3 as audit
    import primitive_discovery as d


class H3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(json.dumps(h3.run_h3()))

    def test_bank_has_48_distinct_and_reproducible_training_signatures(self):
        bank = h3.make_targets()
        self.assertEqual(len(bank), 48)
        self.assertEqual([n for n, _, _ in bank], [6]*12 + [8]*12 + [10]*12 + [12]*12)
        self.assertEqual(bank, h3.make_targets())
        self.assertEqual(len({r["train_label_sha256"] for r in self.report["cases"]}), 48)

    def test_holdout_is_reproducible_and_length_disjoint(self):
        for i in range(48):
            h = h3.make_holdout(i)
            self.assertEqual(len(h), 256)
            self.assertEqual(h, h3.make_holdout(i))
            self.assertTrue(all(14 <= len(s) <= 20 for s in h))
            self.assertFalse(set(h) & set(d.training_words() + d.validation_words()))

    def test_prespecified_h3_gates_fail_and_negative_is_retained(self):
        g = self.report["predeclared"]
        self.assertFalse(g["h3a_clean_scaling_pass"])
        self.assertFalse(g["h3b_noise_robustness_pass"])
        self.assertFalse(g["combined_h3_go"])
        self.assertEqual(self.report["modes"]["clean"]["induced_correct"], 9985)
        self.assertEqual(self.report["modes"]["noisy"]["induced_correct"], 9497)
        self.assertEqual(self.report["modes"]["clean"]["high_accuracy_tasks"], 16)
        self.assertEqual(self.report["modes"]["noisy"]["high_accuracy_tasks"], 11)

    def test_independent_evaluator_replays_every_split(self):
        receipt = audit.verify(self.report)
        self.assertEqual(receipt["oracle_labels_verified"], 24528)
        self.assertEqual(receipt["scored_arm_splits"], 1152)

    def test_independent_auditor_detects_tampered_world_source(self):
        corrupted = copy.deepcopy(self.report)
        corrupted["cases"][0]["target_transitions"][0][0] ^= 1
        with self.assertRaises(AssertionError):
            audit.verify(corrupted)

    def test_independent_auditor_detects_tampered_scores(self):
        corrupted = copy.deepcopy(self.report)
        corrupted["cases"][0]["clean"]["scores"]["induced"]["holdout"]["correct"] -= 1
        with self.assertRaises(AssertionError):
            audit.verify(corrupted)

    def test_independent_auditor_detects_tampered_state_machine(self):
        corrupted = copy.deepcopy(self.report)
        original = corrupted["cases"][0]["clean"]["automaton"][0][0]
        corrupted["cases"][0]["clean"]["automaton"][0][0] = not original
        with self.assertRaises(AssertionError):
            audit.verify(corrupted)

    def test_noisy_label_is_one_flip_and_attempts_bounded(self):
        self.assertEqual(self.report["true_oracle_calls"], 24528)
        for case in self.report["cases"]:
            self.assertTrue(0 <= case["single_flip_index"] < 63)
            self.assertLess(case["clean"]["attempts"], 10000)
            self.assertLess(case["noisy"]["attempts"], 10000)
            self.assertEqual(case["clean"]["scores"]["induced"]["train"]["correct"], 63)
            self.assertEqual(case["noisy"]["scores"]["induced"]["train"]["correct"], 63)


if __name__ == "__main__":
    unittest.main()
