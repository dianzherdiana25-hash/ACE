"""Behavioral checks for learned composition, custody and negative evidence."""
import itertools
import unittest

from ace_research_primitives import primitive_discovery as r1
from . import compositional as c


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = c.run()

    def test_splits_are_feasible_balanced_and_disjoint(self):
        for task in c.TASKS:
            train, validation, terminal = c.bank(task, c.SEEDS[0])
            self.assertEqual((len(train), len(validation), len(terminal)), (63, 128, 128))
            self.assertEqual(sum(y for _, y in validation), 64)
            self.assertEqual(sum(y for _, y in terminal), 64)
            groups = [{w for w, _ in rows} for rows in (train, validation, terminal)]
            self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
            self.assertTrue(all(6 <= len(w) <= 15 for w, _ in validation))
            self.assertTrue(all(16 <= len(w) <= 30 for w, _ in terminal))

    def test_composition_trigger_is_observed_false_acceptance(self):
        train, validation, _ = c.bank("ends", c.SEEDS[0])
        _, report = c.fit(train, validation)
        self.assertTrue(report["counterexample_triggers"])
        labels = dict(train)
        for trigger in report["counterexample_triggers"]:
            self.assertTrue(trigger["false_positive_words"])
            self.assertTrue(all(labels[w] is False for w in trigger["false_positive_words"]))

    def test_no_residual_guard_without_contradictory_evidence(self):
        train, validation, _ = c.bank("equal", c.SEEDS[0])
        _, report = c.fit(train, validation)
        self.assertEqual(report["counterexample_triggers"], [])

    def test_serialized_product_replays_both_count_and_order(self):
        examples = [(w, w.endswith("b")) for w in r1.training_words()]
        dfa, _ = r1.infer(examples)
        program = c.Program("product", (1, -1), dfa)
        words = ["".join(chars) for n in range(7) for chars in itertools.product("ab", repeat=n)]
        words += ["a" * 30 + "b" * 30, "b" * 30 + "a" * 30]
        for word in words:
            expected = word.count("a") == word.count("b") and word.endswith("b")
            self.assertEqual(program.predict(word), expected)
            self.assertEqual(c.replay(program.data(), word), expected)

    def test_terminal_inversion_changes_scores_without_refitting(self):
        train, validation, terminal = c.bank("equal", c.SEEDS[0])
        selected, before = c.fit(train, validation)
        snapshots = {name: p.identity for name, p in selected.items()}
        for name, program in selected.items():
            normal = c.correct(program, terminal, c.Work())
            inverted = c.correct(program, [(w, not y) for w, y in terminal], c.Work())
            self.assertEqual(normal + inverted, len(terminal))
            self.assertEqual(program.identity, snapshots[name])
        _, after = c.fit(train, validation)
        self.assertEqual(before, after)
        self.assertFalse(self.report["open_world_safe"])

    def test_validation_labels_affect_selection(self):
        train, validation, _ = c.bank("equal", c.SEEDS[0])
        _, normal = c.fit(train, validation)
        _, inverted = c.fit(train, [(w, not y) for w, y in validation])
        self.assertNotEqual(normal["arms"]["composition"], inverted["arms"]["composition"])

    def test_type_conflicts_and_observation_budgets_fail(self):
        train, validation, _ = c.bank("equal", c.SEEDS[0])
        for bad in ([('a', 1)], [('a', True), ('a', False)], [('c', True)], [('a' * 101, True)]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                c.fit(bad, validation)
        with self.assertRaises(ValueError):
            c.fit(train + [('aaaaaa', True)], validation)
        with self.assertRaises(ValueError):
            c.fit(train, validation + [('a' * 50, True)])
        with self.assertRaises(ValueError):
            c.fit(train, [('a', True)])

    def test_rejects_unknown_or_unbounded_prediction_inputs(self):
        program = c.Program("counter", (1, -1))
        for word in (123, "abc", "a" * 101):
            with self.assertRaises(ValueError):
                program.predict(word)

    def test_product_and_search_budgets_are_reported(self):
        for row in self.report["trials"]:
            self.assertLessEqual(row["arms"]["composition"]["candidate_count"], 15)
            self.assertEqual(row["arms"]["fixed_product"]["candidate_count"], 35)
            self.assertLessEqual(row["residual_merge_attempts"], 7 * r1.MAX_MERGES)
            self.assertEqual(row["proposal_work"]["predictions"], 7 * 63)
            for arm in row["arms"].values():
                self.assertGreater(arm["work"]["predictions"], 0)
                self.assertEqual(arm["terminal_work"]["predictions"], 128)

    def test_full_replay_is_deterministic(self):
        self.assertEqual(self.report, c.run())

    def test_no_scientific_or_safety_promotion_from_workflow_success(self):
        self.assertEqual(self.report["scientific_decision"], "NOT_ASSESSED")
        self.assertFalse(self.report["candidate_deployed"])
        self.assertFalse(self.report["oaie_established"])
        self.assertFalse(self.report["compute_matched"])
        self.assertFalse(self.report["complete_compute_accounting"])
        self.assertEqual(self.report["beats_fixed_library"],
                         self.report["terminal_correct"]["composition"] >
                         self.report["terminal_correct"]["fixed_product"])
        self.assertEqual(len(self.report["retained_fingerprints"]), 24)

    def test_admitted_models_really_fit_all_development_labels(self):
        for row in self.report["trials"]:
            train, validation, _ = c.bank(row["task"], row["seed"])
            for arm in row["arms"].values():
                if arm["admitted"]:
                    data = arm["program"]
                    self.assertTrue(all(c.replay(data, w) == y for w, y in train + validation))


if __name__ == "__main__":
    unittest.main()
