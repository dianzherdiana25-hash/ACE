"""Offline tests for isolated ACE R1 data-driven state abstraction."""
import hashlib
import json
import random
import unittest

try:
    from . import primitive_discovery as d
except ImportError:
    import primitive_discovery as d


class R1Tests(unittest.TestCase):
    def test_dataset_sizes_and_disjointness(self):
        train, val, hold = d.training_words(), d.validation_words(), d.heldout_regular(0)
        self.assertEqual((len(train), len(val), len(hold)), (63, 192, 256))
        self.assertFalse(set(train) & set(val))
        self.assertFalse(set(train) & set(hold))
        self.assertFalse(set(val) & set(hold))

    def test_deterministic_holdout(self):
        self.assertEqual(d.heldout_regular(3), d.heldout_regular(3))
        self.assertNotEqual(d.heldout_regular(3), d.heldout_regular(4))

    def test_stressor_is_stratified(self):
        for i, (_, judge) in enumerate(d.stress_tasks()):
            hold = d.heldout_stress(i, judge)
            self.assertEqual(len(hold), 256)
            self.assertEqual(sum(judge(x) for x in hold), 128)
            self.assertTrue(all(10 <= len(x) <= 14 for x in hold))
            self.assertFalse(set(hold) & set(d.training_words() + d.validation_words()))

    def test_prefix_tree_memorizes_not_generalizes(self):
        examples = [(s, bool(s.count("a") % 2 == 0)) for s in d.training_words()]
        m = d.prefix_tree(examples)
        self.assertEqual(len(m.labels), 63)
        self.assertTrue(all(m.run(s) == v for s, v in examples))
        self.assertFalse(m.run("a" * 8))

    def test_reject_conflicting_labels(self):
        with self.assertRaises(ValueError):
            d.prefix_tree([("a", True), ("a", False)])
        with self.assertRaises(ValueError):
            d.prefix_tree([("c", True)])

    def test_merge_conflicting_samples_rejected(self):
        examples = [("", False), ("a", True)]
        m = d.prefix_tree(examples)
        self.assertIsNone(d.try_merge(m, 0, 1, examples))

    def test_parity_induces_real_loop_not_lookup(self):
        examples = [(s, s.count("a") % 2 == 0) for s in d.training_words()]
        m, trials = d.infer(examples)
        self.assertEqual(m.reachable(), 2)
        self.assertLess(trials, d.MAX_MERGES)
        for word in ["a" * 99, "ba" * 50, "bb" * 80, "ab" * 67]:
            self.assertEqual(m.run(word), word.count("a") % 2 == 0)

    def test_learner_is_deterministic(self):
        examples = [(s, "aba" not in s) for s in d.training_words()]
        m1, t1 = d.infer(examples)
        m2, t2 = d.infer(examples)
        self.assertEqual(t1, t2)
        self.assertEqual(m1.signature(), m2.signature())

    def test_all_regular_training_consistent(self):
        for name, judge in d.regular_tasks():
            with self.subTest(task=name):
                examples = [(s, judge(s)) for s in d.training_words()]
                m, attempts = d.infer(examples)
                self.assertTrue(all(m.run(s) == y for s, y in examples))
                self.assertLess(attempts, d.MAX_MERGES)
                self.assertLessEqual(m.reachable(), 63)

    def test_frozen_holdout_regular_report(self):
        # Full 9+2 tasks; enough to detect scoring/replay implementation drift.
        report = d.run_experiment()
        self.assertEqual(len(report["tasks"]), 11)
        self.assertEqual(report["total_evaluator_labels"], 5621)
        self.assertTrue(report["primary"]["predeclared_h1_accepted"])
        for row in report["tasks"][:9]:
            self.assertEqual(row["scores"]["induced"]["holdout"]["accuracy"], 1.0)
        for row in report["tasks"][9:]:
            self.assertLess(row["scores"]["induced"]["holdout"]["accuracy"], 0.8)

    def test_noisy_label_can_break_generalization(self):
        # Negative: a synthetic label corruption can force a noncanonical DFA.
        examples = [(s, s.count("a") % 2 == 0) for s in d.training_words()]
        flipped = [(s, not y if s == "aabba" else y) for s, y in examples]
        model, _ = d.infer(flipped)
        self.assertTrue(all(model.run(s) == y for s, y in flipped))
        self.assertGreater(model.reachable(), 2)
        holdout = [(s, s.count("a") % 2 == 0) for s in d.heldout_regular(0)]
        self.assertLess(d.metric(model.run, holdout)["correct"], 256)

    def test_budget_halts_closed(self):
        examples = [(s, s.count("a") % 2 == 0) for s in d.training_words()]
        with self.assertRaises(RuntimeError):
            d.infer(examples, max_merges=1)
        with self.assertRaises(ValueError):
            d.infer(examples + [("a" * 7, True)])

    def test_fixed_library_not_learner_target_cheat(self):
        self.assertGreater(len(d.fixed_predicates()), 70)
        for name, judge in d.regular_tasks():
            examples = [(s, judge(s)) for s in d.training_words()]
            m, _ = d.infer(examples)
            # Reordering examples must not affect inferred representation.
            reversed_model, _ = d.infer(list(reversed(examples)))
            self.assertEqual(m.signature(), reversed_model.signature(), name)


if __name__ == "__main__":
    unittest.main()
