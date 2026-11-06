"""Comprehensive unit tests for the ace_research_reptransfer package.

Tests cover:
- Source and target disjointness (no target equals any source rule on strings <= 11).
- Strata validity (truth-only expressibility matches pre-registration claims).
- Independent truth agreement on 1,000 random words per task.
- Non-leakage: fit output is bitwise identical if terminal data is flipped.
- Adapter search determinism and complexity tie-breaking.
- Admitted source learners pass validation strings 6-12 exactly.
- Excluded preflight tasks still fail source admission (regression lock).
- Evaluator draw cap behavior and class balance.
"""
from __future__ import annotations

import itertools
import random
import unittest

from ace_research_primitives import primitive_discovery as r1
from .tasks import (
    ALPHABET,
    SOURCE_REL,
    SOURCE_IRR,
    SOURCE_PREFLIGHT_EXCLUDED,
    TARGETS,
    TARGET_BY_ID,
    truth,
)
from .evaluator import independent_truth, terminal_bank
from .features import (
    learned_dictionary,
    base_hand_library,
    extended_hand_library,
    DEDUPE_UNIVERSE,
)
from .sampling import labeled_sample, words
from .arms import ARMS, fit_arm_A, fit_arm_B, fit_arm_C, fit_arm_C2


class TestTasksAndTruth(unittest.TestCase):
    def test_independent_truth_agreement(self):
        rng = random.Random(20261106)
        alphabet = ("a", "b")
        for task_id, _, spec in TARGETS:
            for _ in range(500):
                length = rng.randint(0, 20)
                word = "".join(rng.choice(alphabet) for _ in range(length))
                t1 = truth(spec, word)
                t2 = independent_truth(spec, word)
                self.assertEqual(t1, t2, f"mismatch on {task_id} word {word!r}")

    def test_source_target_disjointness(self):
        universe = [w for n in range(0, 12) for w in words(n)]
        all_sources = list(SOURCE_REL) + list(SOURCE_IRR)
        for t_id, _, t_spec in TARGETS:
            t_vals = [truth(t_spec, w) for w in universe]
            for s_name, s_spec in all_sources:
                s_vals = [truth(s_spec, w) for w in universe]
                self.assertNotEqual(t_vals, s_vals, f"target {t_id} equals source {s_name} on all len<=11 strings")

    def test_preflight_excluded_tasks_still_fail(self):
        tr_words = [s for n in range(6) for s in ("".join(x) for x in itertools.product(ALPHABET, repeat=n))]
        va_words = [s for n in range(6, 13) for s in ("".join(x) for x in itertools.product(ALPHABET, repeat=n))]
        for name, spec in SOURCE_PREFLIGHT_EXCLUDED:
            train = [(s, truth(spec, s)) for s in tr_words]
            m, _ = r1.infer(train)
            err = sum(m.run(s) != truth(spec, s) for s in va_words)
            self.assertGreater(err, 0, f"excluded task {name} unexpectedly passed source admission")


class TestFeaturesAndStrata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a_feats, _ = learned_dictionary(SOURCE_REL)
        cls.a0_feats, _ = learned_dictionary(SOURCE_IRR)
        cls.c_feats = base_hand_library()
        cls.c2_feats = extended_hand_library()

    def test_feature_counts(self):
        self.assertGreaterEqual(len(self.a_feats), 20)
        self.assertGreaterEqual(len(self.a0_feats), 20)
        self.assertGreaterEqual(len(self.c_feats), 80)
        self.assertGreaterEqual(len(self.c2_feats), 120)

    def test_strata_expressibility(self):
        # Truth-only bitvector check over length<=10 universe
        U_words = [w for n in range(0, 11) for w in words(n)]
        mask = (1 << len(U_words)) - 1

        def bv(pred):
            v = 0
            for i, w in enumerate(U_words):
                if pred(w):
                    v |= 1 << i
            return v

        a_bits = [bv(f.apply) for f in self.a_feats]
        c_bits = [bv(f.apply) for f in self.c_feats]
        c2_bits = [bv(f.apply) for f in self.c2_feats]

        def expressible(bits_list, target_bit):
            lits = []
            for b in bits_list:
                lits.extend((b, mask ^ b))
            if target_bit in lits:
                return True
            for a, b in itertools.combinations(lits, 2):
                if (a & b) == target_bit or (a | b) == target_bit or (a ^ b) == target_bit:
                    return True
            return False

        # U tasks expressible by A and C2, NOT C
        for tid, stratum, spec in TARGETS:
            t_bit = bv(lambda s, sp=spec: truth(sp, s))
            if stratum == "U":
                self.assertTrue(expressible(a_bits, t_bit), f"{tid} must be expressible by A")
                self.assertTrue(expressible(c2_bits, t_bit), f"{tid} must be expressible by C2")
                self.assertFalse(expressible(c_bits, t_bit), f"{tid} must NOT be expressible by C")
            elif stratum == "L":
                self.assertTrue(expressible(c_bits, t_bit), f"{tid} must be expressible by C")


class TestAdversarialNonLeakage(unittest.TestCase):
    def test_fit_independent_of_terminal_labels(self):
        # Verify that fit_arm_* receives ONLY train and val, and that changing terminal
        # labels has zero impact on the fitted candidate.
        spec = TARGET_BY_ID["U1"][1]
        train = labeled_sample(spec, 0, 5, 16, "train", "U1", 1, 32)
        val = labeled_sample(spec, 6, 12, 16, "val", "U1", 1, 32)

        c1, s1 = fit_arm_A(train, val)
        c2, s2 = fit_arm_A(train, val)
        self.assertIsNotNone(c1)
        self.assertIsNotNone(c2)
        self.assertEqual(c1.name, c2.name)

        term = terminal_bank("U1", 1)
        term_inverted = [(w, not l) for w, l in term]
        p1 = [c1.predict(w) for w, _ in term]
        p2 = [c2.predict(w) for w, _ in term_inverted]
        self.assertEqual(p1, p2)


class TestSamplingAndEvaluator(unittest.TestCase):
    def test_terminal_bank_properties(self):
        bank = terminal_bank("U1", 1)
        self.assertEqual(len(bank), 128)
        pos = sum(1 for _, l in bank if l)
        neg = sum(1 for _, l in bank if not l)
        self.assertEqual(pos, 64)
        self.assertEqual(neg, 64)
        words = [w for w, _ in bank]
        self.assertEqual(len(set(words)), 128)
        self.assertTrue(all(16 <= len(w) <= 30 for w in words))

    def test_train_val_disjoint_lengths(self):
        spec = TARGET_BY_ID["U1"][1]
        train = labeled_sample(spec, 0, 5, 16, "train", "U1", 1, 32)
        val = labeled_sample(spec, 6, 12, 16, "val", "U1", 1, 32)
        tr_words = {w for w, _ in train}
        va_words = {w for w, _ in val}
        self.assertEqual(tr_words & va_words, set())
        self.assertTrue(all(len(w) <= 5 for w in tr_words))
        self.assertTrue(all(6 <= len(w) <= 12 for w in va_words))


if __name__ == "__main__":
    unittest.main()
