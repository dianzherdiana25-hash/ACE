"""Unit tests for Meta-Curriculum & Frontier Expander."""
from __future__ import annotations

import unittest
from ace_cognition.meta_curriculum import MetaCurriculumExpander, _oracle_l1_balanced_parentheses


class TestMetaCurriculum(unittest.TestCase):
    def test_oracle_l1_balanced_parentheses(self):
        # 'a' is '(', 'b' is ')'
        self.assertTrue(_oracle_l1_balanced_parentheses(""))
        self.assertTrue(_oracle_l1_balanced_parentheses("ab"))  # ()
        self.assertTrue(_oracle_l1_balanced_parentheses("aabb"))  # (())
        self.assertTrue(_oracle_l1_balanced_parentheses("abab"))  # ()()
        self.assertFalse(_oracle_l1_balanced_parentheses("ba"))  # )(
        self.assertFalse(_oracle_l1_balanced_parentheses("a"))  # (
        self.assertFalse(_oracle_l1_balanced_parentheses("abb"))  # ())

    def test_frontier_suite_generation(self):
        expander = MetaCurriculumExpander(seed=123)
        suite = expander.create_frontier_suite()

        self.assertIn("task_l1_balanced_parentheses", suite)
        self.assertIn("task_l2_alternating_palindrome", suite)
        self.assertIn("task_m1_token_chain_divisibility", suite)

        t_l1 = suite["task_l1_balanced_parentheses"]
        self.assertGreater(len(t_l1.train_pool), 10)
        self.assertGreater(len(t_l1.validation_pool), 10)
        self.assertGreater(len(t_l1.sealed_confirmation_holdout), 10)


if __name__ == "__main__":
    unittest.main()
