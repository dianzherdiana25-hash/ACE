"""Unit tests for Angluin's L* active automata learner."""
from __future__ import annotations

import unittest
from ace_automata.lstar import LStarLearner, DFA


class TestLStarLearner(unittest.TestCase):
    def setUp(self):
        self.learner = LStarLearner(alphabet=("a", "b"))

    def test_learn_parity_language(self):
        # Target: count('a') is even
        teacher = lambda s: s.count("a") % 2 == 0
        training = [
            ("", True), ("a", False), ("b", True), ("aa", True), ("ab", False),
            ("ba", False), ("bb", True), ("aaa", False), ("aab", True), ("aba", True),
            ("baa", True), ("bab", False), ("bba", False), ("bbb", True)
        ]
        dfa = self.learner.learn(teacher, training_samples=training)
        self.assertEqual(len(dfa.states), 2)  # Minimal DFA for parity has exactly 2 states!
        for w, label in training:
            self.assertEqual(dfa.run(w), label)
        # Test on held-out longer words
        self.assertTrue(dfa.run("abba"))
        self.assertFalse(dfa.run("abbaba"))

    def test_learn_modulo_3_language(self):
        # Target: count('a') % 3 == 0
        teacher = lambda s: s.count("a") % 3 == 0
        training = [
            ("", True), ("a", False), ("aa", False), ("aaa", True),
            ("b", True), ("ab", False), ("ba", False), ("aab", False),
            ("aba", False), ("baa", False), ("aaab", True), ("baaa", True)
        ]
        dfa = self.learner.learn(teacher, training_samples=training)
        self.assertEqual(len(dfa.states), 3)  # Minimal DFA has exactly 3 states!
        self.assertTrue(dfa.run("aaaaaa"))
        self.assertFalse(dfa.run("aaaaa"))

    def test_learn_contains_ab(self):
        # Target: "ab" in word
        teacher = lambda s: "ab" in s
        training = [
            ("", False), ("a", False), ("b", False), ("ab", True),
            ("ba", False), ("aab", True), ("aba", True), ("bab", True),
            ("bba", False), ("bb", False), ("aa", False)
        ]
        dfa = self.learner.learn(teacher, training_samples=training)
        self.assertTrue(dfa.run("aab"))
        self.assertTrue(dfa.run("bab"))
        self.assertFalse(dfa.run("ba"))

    def test_to_r1_signature_and_python_code(self):
        teacher = lambda s: s.count("a") % 2 == 0
        dfa = self.learner.learn(teacher)
        sig = dfa.to_r1_signature()
        self.assertIsInstance(sig, list)
        self.assertEqual(len(sig), len(dfa.states))
        # Verify python code generation
        code = dfa.to_python_code("custom_parity")
        self.assertIn("def custom_parity(word: str) -> bool:", code)
        self.assertIn("transitions =", code)
        # Verify generated code executes cleanly
        scope = {}
        exec(code, scope)
        self.assertTrue(scope["custom_parity"]("aa"))
        self.assertFalse(scope["custom_parity"]("a"))


if __name__ == "__main__":
    unittest.main()
