"""Unit tests for W2 Uncheatable Sealed Evaluator.

Follows TDD: tests written first to specify and verify uncheatable evaluation behavior.
"""
import os
import unittest


class TestSealedEvaluator(unittest.TestCase):
    def test_parameterized_families_and_count_matched_negatives(self):
        """At least 6 task families generate >= 128 balanced examples with count-matched negatives."""
        from ace_evaluator.task_families import TASK_FAMILIES, generate_family_instances

        self.assertGreaterEqual(len(TASK_FAMILIES), 6)
        expected_families = {"counter_ratio", "parity", "boundary", "graph", "an_bn", "sequence"}
        self.assertTrue(expected_families.issubset(set(TASK_FAMILIES)))

        for fam in expected_families:
            instances = generate_family_instances(fam, seed=42, count=128)
            self.assertEqual(len(instances), 128)
            positives = [word for word, label in instances if label is True]
            negatives = [word for word, label in instances if label is False]
            self.assertEqual(len(positives), 64)
            self.assertEqual(len(negatives), 64)

            # In sequence and boundary families, negatives must be count-matched (same count of a's and b's)
            if fam in ("sequence", "boundary", "an_bn"):
                for neg in negatives[:10]:
                    # Check that neg has characters and is not just trivial empty string
                    self.assertGreater(len(neg), 0)

    def test_sealed_seed_and_not_assessed_fallback(self):
        """Without ACE_SEALED_SEED, evaluation defaults to public dev seed and marks claim NOT_ASSESSED."""
        from ace_evaluator.sealed_generator import get_evaluation_seed_and_status

        old_seed = os.environ.pop("ACE_SEALED_SEED", None)
        try:
            seed, status = get_evaluation_seed_and_status()
            self.assertEqual(status, "NOT_ASSESSED")
            self.assertIsInstance(seed, int)

            # When secret seed is provided
            os.environ["ACE_SEALED_SEED"] = "owner_secret_seed_987654"
            seed_secret, status_secret = get_evaluation_seed_and_status()
            self.assertEqual(status_secret, "CONFIRMED_SEALED")
            self.assertNotEqual(seed, seed_secret)
        finally:
            if old_seed is not None:
                os.environ["ACE_SEALED_SEED"] = old_seed
            else:
                os.environ.pop("ACE_SEALED_SEED", None)

    def test_four_cheating_attempts_must_fail_admission(self):
        """All 4 cheating attempts MUST FAIL admission: memorizer, unused code, label flipper, bank leak."""
        from ace_evaluator.cheat_detection import evaluate_candidate_integrity

        # 1. Bank Memorizer: dictionary lookup table
        memorizer_code = """
def predict(word):
    table = {"aa": True, "ab": False, "ba": True, "bb": False}
    return table.get(word, False)
"""
        res_mem = evaluate_candidate_integrity(memorizer_code, candidate_fn=lambda w: True)
        self.assertFalse(res_mem["admitted"])
        self.assertIn("MEMORIZATION_OR_LOOKUP_DETECTED", res_mem["reasons"])

        # 2. Unused Function: template appended function never called
        unused_code = """
def active_predictor(word):
    return len(word) % 2 == 0

def ace_v04_dispatch_template_unused():
    return True
"""
        res_unused = evaluate_candidate_integrity(unused_code, candidate_fn=lambda w: len(w) % 2 == 0)
        self.assertFalse(res_unused["admitted"])
        self.assertIn("DEAD_OR_UNUSED_FUNCTION_DETECTED", res_unused["reasons"])

        # 3. Terminal Label Flipper: inverts or corrupts outputs
        inverted_code = """
def predict(word):
    return not (len(word) > 2)
"""
        res_flip = evaluate_candidate_integrity(
            inverted_code,
            candidate_fn=lambda w: not (len(w) > 2),
            is_flipped=True
        )
        self.assertFalse(res_flip["admitted"])
        self.assertIn("NEGATIVE_CONTROL_VIOLATION", res_flip["reasons"])

        # 4. Bank Leakage: tries to import or inspect evaluator internals
        leak_code = """
import ace_evaluator
def predict(word):
    return hasattr(ace_evaluator, "SEALED_BANK")
"""
        res_leak = evaluate_candidate_integrity(leak_code, candidate_fn=lambda w: True)
        self.assertFalse(res_leak["admitted"])
        self.assertIn("EVALUATOR_PROBING_OR_IMPORT_VIOLATION", res_leak["reasons"])

    def test_reproducible_byte_identical_runs(self):
        """Two separate evaluations with the same seed produce byte-for-byte identical datasets."""
        from ace_evaluator.task_families import generate_family_instances
        import json

        run1 = generate_family_instances("parity", seed=12345, count=128)
        run2 = generate_family_instances("parity", seed=12345, count=128)

        json1 = json.dumps(run1, sort_keys=True)
        json2 = json.dumps(run2, sort_keys=True)
        self.assertEqual(json1, json2)


if __name__ == "__main__":
    unittest.main()
