"""Unit tests for Equivariant AST Graph Representation and Latent Program Transfer."""
from __future__ import annotations

import unittest
import numpy as np

from ace_evolution.island_search import ProgramCandidate, TypedASTNode
from ace_neurosymbolic.graph_embedding import (
    ASTGraph,
    EquivariantASTGNN,
    LatentProgramLibrary,
    WeisfeilerLehmanASTKernel,
)


class TestGraphEmbedding(unittest.TestCase):
    def setUp(self):
        # Program 1: count_a == count_b
        self.p_eq1 = TypedASTNode("eq", "BOOL", [TypedASTNode("count_a", "INT"), TypedASTNode("count_b", "INT")])
        # Program 2: count_b == count_a (commutative isomorphic)
        self.p_eq2 = TypedASTNode("eq", "BOOL", [TypedASTNode("count_b", "INT"), TypedASTNode("count_a", "INT")])
        # Program 3: len(word) >= 2
        self.p_gte = TypedASTNode("gte", "BOOL", [TypedASTNode("len", "INT"), TypedASTNode("int_const", "INT", val=2)])
        # Program 4: starts_with("a") and ends_with("b")
        self.p_and1 = TypedASTNode("and", "BOOL", [TypedASTNode("starts_with", "BOOL", val="a"), TypedASTNode("ends_with", "BOOL", val="b")])
        # Program 5: ends_with("b") and starts_with("a") (commutative isomorphic)
        self.p_and2 = TypedASTNode("and", "BOOL", [TypedASTNode("ends_with", "BOOL", val="b"), TypedASTNode("starts_with", "BOOL", val="a")])
        # Program 6: Non-commutative: count_a - count_b
        self.p_sub1 = TypedASTNode("sub", "INT", [TypedASTNode("count_a", "INT"), TypedASTNode("count_b", "INT")])
        self.p_sub2 = TypedASTNode("sub", "INT", [TypedASTNode("count_b", "INT"), TypedASTNode("count_a", "INT")])

        self.kernel = WeisfeilerLehmanASTKernel(num_iterations=3)
        self.gnn = EquivariantASTGNN(embedding_dim=32, seed=42)

    def test_ast_graph_construction_and_canonicalization(self):
        g_eq1 = ASTGraph.from_typed_ast(self.p_eq1, canonicalize_commutative=True)
        g_eq2 = ASTGraph.from_typed_ast(self.p_eq2, canonicalize_commutative=True)

        self.assertEqual(g_eq1.num_nodes(), 3)
        self.assertEqual(g_eq1.num_edges(), 4)  # 2 parent->child, 2 child->parent

        # Commutative canonicalization aligns child node operations
        child_ops_1 = [g_eq1.nodes[nid].op for nid in g_eq1.adj_out[g_eq1.root_id]]
        child_ops_2 = [g_eq2.nodes[nid].op for nid in g_eq2.adj_out[g_eq2.root_id]]
        self.assertEqual(child_ops_1, child_ops_2)

        # Non-commutative operations must preserve original order
        g_sub1 = ASTGraph.from_typed_ast(self.p_sub1, canonicalize_commutative=True)
        g_sub2 = ASTGraph.from_typed_ast(self.p_sub2, canonicalize_commutative=True)
        sub1_ops = [g_sub1.nodes[nid].op for nid in g_sub1.adj_out[g_sub1.root_id]]
        sub2_ops = [g_sub2.nodes[nid].op for nid in g_sub2.adj_out[g_sub2.root_id]]
        self.assertNotEqual(sub1_ops, sub2_ops)

    def test_weisfeiler_lehman_isomorphism_and_separation(self):
        # 1. Structural isomorphism preservation (cosine sim >= 0.95)
        sim_identical = self.kernel.similarity(self.p_eq1, self.p_eq1)
        self.assertAlmostEqual(sim_identical, 1.0, places=5)

        sim_comm_eq = self.kernel.similarity(self.p_eq1, self.p_eq2)
        self.assertGreaterEqual(sim_comm_eq, 0.95)
        self.assertAlmostEqual(sim_comm_eq, 1.0, places=5)

        sim_comm_and = self.kernel.similarity(self.p_and1, self.p_and2)
        self.assertGreaterEqual(sim_comm_and, 0.95)
        self.assertAlmostEqual(sim_comm_and, 1.0, places=5)

        # 2. Zero false equivalence on non-isomorphic trees
        sim_eq_vs_gte = self.kernel.similarity(self.p_eq1, self.p_gte)
        self.assertLess(sim_eq_vs_gte, 0.70)

        sim_eq_vs_and = self.kernel.similarity(self.p_eq1, self.p_and1)
        self.assertLess(sim_eq_vs_and, 0.70)

        sim_sub1_vs_sub2 = self.kernel.similarity(self.p_sub1, self.p_sub2)
        # Non-commutative operands produce different graphs
        self.assertLessEqual(sim_sub1_vs_sub2, 0.85)

    def test_equivariant_gnn_embeddings(self):
        z_eq1 = self.gnn.embed_ast(self.p_eq1)
        z_eq2 = self.gnn.embed_ast(self.p_eq2)
        z_gte = self.gnn.embed_ast(self.p_gte)

        # Vector dimension and L2 normalization
        self.assertEqual(len(z_eq1), 32)
        self.assertAlmostEqual(float(np.linalg.norm(z_eq1)), 1.0, places=5)

        # Commutative isomorphism cosine similarity >= 0.95
        cos_sim_comm = float(np.dot(z_eq1, z_eq2))
        self.assertGreaterEqual(cos_sim_comm, 0.95)

        # Non-isomorphic cosine similarity separation
        cos_sim_diff = float(np.dot(z_eq1, z_gte))
        self.assertLess(cos_sim_diff, 0.85)

    def test_latent_program_library_retrieval(self):
        library = LatentProgramLibrary()

        # Register library programs
        c_eq = ProgramCandidate(self.p_eq1)
        c_gte = ProgramCandidate(self.p_gte)
        c_and = ProgramCandidate(self.p_and1)

        library.register_candidate(c_eq, "equality_task")
        library.register_candidate(c_gte, "threshold_task")
        library.register_candidate(c_and, "conjunction_task")

        self.assertEqual(len(library.entries), 3)

        # Query with commutative variant p_eq2: (count_b == count_a)
        neighbors = library.find_nearest_neighbors(self.p_eq2, top_k=2)
        top_sim, top_entry = neighbors[0]

        self.assertEqual(top_entry["task_name"], "equality_task")
        self.assertGreaterEqual(top_sim, 0.95)

        # Isomorphism detection test
        self.assertTrue(library.is_isomorphic(self.p_eq1, self.p_eq2))
        self.assertTrue(library.is_isomorphic(self.p_and1, self.p_and2))
        self.assertFalse(library.is_isomorphic(self.p_eq1, self.p_gte))

    def test_subtree_extraction_and_transfer(self):
        library = LatentProgramLibrary()

        # Nested composite program: (starts_with("a") and (count_a == count_b))
        nested_ast = TypedASTNode("and", "BOOL", [
            TypedASTNode("starts_with", "BOOL", val="a"),
            TypedASTNode("eq", "BOOL", [TypedASTNode("count_a", "INT"), TypedASTNode("count_b", "INT")]),
        ])

        subtrees = library.extract_transferable_subtrees(nested_ast, min_depth=2)
        self.assertGreaterEqual(len(subtrees), 1)

        eq_subtree = next(st for st in subtrees if st.op == "eq")
        self.assertEqual(eq_subtree.op, "eq")
        self.assertEqual(len(eq_subtree.children), 2)
        self.assertEqual(eq_subtree.children[0].op, "count_a")
        self.assertEqual(eq_subtree.children[1].op, "count_b")


if __name__ == "__main__":
    unittest.main()
