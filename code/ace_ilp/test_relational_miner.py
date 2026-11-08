"""Unit tests for Inductive Logic Programming (ILP) Relational Predicate Miner."""
from __future__ import annotations

import unittest
from ace_ilp.relational_miner import (
    Atom,
    Clause,
    KnowledgeBase,
    RelationalMiner,
    is_variable,
)


class TestRelationalMiner(unittest.TestCase):
    def test_term_and_atom_representation(self):
        self.assertTrue(is_variable("X"))
        self.assertTrue(is_variable("Var1"))
        self.assertFalse(is_variable("a"))
        self.assertFalse(is_variable("node_123"))

        atom = Atom("edge", "a", "b")
        self.assertTrue(atom.is_ground)
        self.assertEqual(atom.arity, 2)
        self.assertEqual(str(atom), "edge(a, b)")

        var_atom = Atom("edge", "X", "Y")
        self.assertFalse(var_atom.is_ground)
        self.assertEqual(var_atom.variables, {"X", "Y"})

        # Substitution
        subst_atom = var_atom.substitute({"X": "nodeA", "Y": "nodeB"})
        self.assertEqual(subst_atom, Atom("edge", "nodeA", "nodeB"))
        self.assertTrue(subst_atom.is_ground)

        # Ground matching
        m1 = var_atom.match_ground(atom, {})
        self.assertEqual(m1, {"X": "a", "Y": "b"})

        m_mismatch = var_atom.match_ground(Atom("node", "a"), {})
        self.assertIsNone(m_mismatch)

    def test_clause_representation_and_theta_subsumption(self):
        head = Atom("path", "X", "Y")
        b1 = Atom("edge", "X", "Y")
        clause = Clause(head, b1)
        self.assertEqual(str(clause), "path(X, Y) :- edge(X, Y).")

        # Theta subsumption (Plotkin 1970)
        # General clause p(X, Y) :- edge(X, Y) subsumes p(X, Y) :- edge(X, Y), color(X, red)
        specific_clause = Clause(head, b1, Atom("color", "X", "red"))
        self.assertTrue(clause.theta_subsumes(specific_clause))
        self.assertFalse(specific_clause.theta_subsumes(clause))

    def test_knowledge_base_forward_chaining(self):
        facts = [
            Atom("edge", "1", "2"),
            Atom("edge", "2", "3"),
            Atom("edge", "3", "4"),
        ]
        # Transitive path clauses:
        # path(X, Y) :- edge(X, Y).
        # path(X, Y) :- edge(X, Z), path(Z, Y).
        c1 = Clause(Atom("path", "X", "Y"), Atom("edge", "X", "Y"))
        c2 = Clause(Atom("path", "X", "Y"), Atom("edge", "X", "Z"), Atom("path", "Z", "Y"))

        kb = KnowledgeBase(facts, [c1, c2])
        derived = kb.forward_chain()

        # All transitive edges must be derived
        self.assertIn(Atom("path", "1", "2"), derived)
        self.assertIn(Atom("path", "1", "3"), derived)
        self.assertIn(Atom("path", "1", "4"), derived)
        self.assertIn(Atom("path", "2", "4"), derived)

        # Negative checks (directed graph)
        self.assertFalse(kb.entails(Atom("path", "4", "1")))
        self.assertFalse(kb.entails(Atom("path", "3", "1")))

    def test_relational_miner_induces_direct_edge_relation(self):
        bg = [
            Atom("edge", "a", "b"),
            Atom("edge", "b", "c"),
            Atom("edge", "c", "d"),
            Atom("edge", "x", "y"),
            Atom("node", "a"),
            Atom("node", "b"),
        ]
        pos = [
            Atom("connected", "a", "b"),
            Atom("connected", "b", "c"),
            Atom("connected", "c", "d"),
            Atom("connected", "x", "y"),
        ]
        neg = [
            Atom("connected", "b", "a"),
            Atom("connected", "d", "c"),
            Atom("connected", "a", "d"),
            Atom("connected", "a", "x"),
        ]

        miner = RelationalMiner(bg, pos, neg, "connected", 2)
        clauses = miner.mine(max_clause_length=2)

        self.assertGreater(len(clauses), 0)
        # First induced clause must be connected(X0, X1) :- edge(X0, X1)
        best = clauses[0]
        self.assertEqual(best.head.predicate, "connected")
        self.assertEqual(len(best.body), 1)
        self.assertEqual(best.body[0].predicate, "edge")

        # Verify completeness on positive and consistency on negative
        test_kb = KnowledgeBase(bg, clauses)
        for p in pos:
            self.assertTrue(test_kb.entails(p), f"Should entail positive {p}")
        for n in neg:
            self.assertFalse(test_kb.entails(n), f"Should NOT entail negative {n}")

    def test_relational_miner_induces_length_two_paths(self):
        bg = [
            Atom("edge", "a", "b"),
            Atom("edge", "b", "c"),
            Atom("edge", "b", "k"),
            Atom("edge", "k", "m"),
            Atom("edge", "p", "q"),
            Atom("edge", "q", "r"),
        ]
        # Length 2 paths:
        # a -> b -> c
        # a -> b -> k
        # b -> k -> m
        # p -> q -> r
        pos = [
            Atom("reach2", "a", "c"),
            Atom("reach2", "a", "k"),
            Atom("reach2", "b", "m"),
            Atom("reach2", "p", "r"),
        ]
        neg = [
            Atom("reach2", "a", "b"),  # length 1
            Atom("reach2", "b", "c"),  # length 1
            Atom("reach2", "a", "m"),  # length 3
            Atom("reach2", "c", "a"),  # reversed
            Atom("reach2", "p", "m"),  # disconnected
        ]

        miner = RelationalMiner(bg, pos, neg, "reach2", 2)
        clauses = miner.mine(max_clause_length=3)

        self.assertGreater(len(clauses), 0)
        best = clauses[0]
        self.assertEqual(best.head.predicate, "reach2")
        self.assertEqual(len(best.body), 2)
        # Body should compose two edge literals sharing an intermediate variable
        pred_names = [b.predicate for b in best.body]
        self.assertEqual(pred_names, ["edge", "edge"])

        test_kb = KnowledgeBase(bg, clauses)
        for p in pos:
            self.assertTrue(test_kb.entails(p))
        for n in neg:
            self.assertFalse(test_kb.entails(n))

    def test_compiled_python_function(self):
        bg = [
            Atom("edge", "1", "2"),
            Atom("edge", "2", "3"),
        ]
        pos = [Atom("path2", "1", "3")]
        neg = [Atom("path2", "1", "2"), Atom("path2", "3", "1")]

        miner = RelationalMiner(bg, pos, neg, "path2", 2)
        clauses = miner.mine(max_clause_length=3)

        fn = miner.compile_to_python(clauses)
        test_graph = [("edge", "u", "v"), ("edge", "v", "w")]

        self.assertTrue(fn(test_graph, "u", "w"))
        self.assertFalse(fn(test_graph, "u", "v"))
        self.assertFalse(fn(test_graph, "w", "u"))


if __name__ == "__main__":
    unittest.main()
