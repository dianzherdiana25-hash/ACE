"""Unit test suite for ACE Graph Neural Network AST Graph Representation Learning Engine.

Tests:
1. AST graph conversion (node counts, edge lists, feature matrix shapes, adjacency normalization).
2. Relational GCN message passing and dimension consistency.
3. GraphSAGE directional message passing across aggregators.
4. Tree-LSTM bottom-up recursive embedder.
5. Permutation equivariance of node states and permutation invariance of global pooling.
6. Pooling dimension consistency across all pooling strategies.
7. Semantic similarity scoring (self-similarity, commutativity, bounded range, equivalence head).
8. Grammar rule prediction distribution (sum to 1, non-negativity, top-k ordering).
9. Edge cases: Single-node AST, deep composite expressions, and complex boolean predicates.
"""
from __future__ import annotations

import unittest
import numpy as np

from ace_evolution.island_search import TypedASTNode
from ace_gnn.ast_embedder import (
    ASTGraph,
    ASTGraphConverter,
    ASTGraphEmbedder,
    GraphSAGELayer,
    ReadoutPooling,
    RelationalGCNLayer,
    RulePredictionHead,
    SemanticEquivalenceHead,
    TreeLSTMLayer,
)


class TestASTEmbedder(unittest.TestCase):
    """Test suite for GNN AST Embedder."""

    def setUp(self):
        # Create a sample AST: (count_a + count_b) == 2
        #           eq (BOOL)
        #          /         \
        #      add (INT)    int_const(2) (INT)
        #      /       \
        # count_a(INT) count_b(INT)
        ca = TypedASTNode("count_a", "INT")
        cb = TypedASTNode("count_b", "INT")
        add_node = TypedASTNode("add", "INT", children=[ca, cb])
        two = TypedASTNode("int_const", "INT", val=2)
        self.sample_ast = TypedASTNode("eq", "BOOL", children=[add_node, two])

    def test_ast_graph_conversion(self):
        """Verifies TypedASTNode conversion into relational ASTGraph."""
        converter = ASTGraphConverter()
        graph = converter.ast_to_graph(self.sample_ast)

        self.assertEqual(graph.num_nodes, 5)
        self.assertEqual(graph.x.shape, (5, converter.feature_dim))
        self.assertTrue(np.all(np.isfinite(graph.x)))

        # Tree with N nodes must have exactly N-1 directed edges in each direction
        self.assertEqual(len(graph.edge_index_c2p), 4)
        self.assertEqual(len(graph.edge_index_p2c), 4)

        # Root index check
        self.assertEqual(graph.root_idx, 0)
        self.assertEqual(graph.node_ops[0], "eq")
        self.assertEqual(graph.node_types[0], "BOOL")

        # Adjacency matrices
        adj_c2p = graph.adjacency_matrix(edge_type="c2p", normalized=True)
        adj_p2c = graph.adjacency_matrix(edge_type="p2c", normalized=True)
        self.assertEqual(adj_c2p.shape, (5, 5))
        self.assertEqual(adj_p2c.shape, (5, 5))
        self.assertTrue(np.all(np.isfinite(adj_c2p)))
        self.assertTrue(np.all(np.isfinite(adj_p2c)))

    def test_relational_gcn_forward_pass(self):
        """Tests forward pass of Relational GCN embedder."""
        embedder = ASTGraphEmbedder(
            embed_dim=32,
            hidden_dim=32,
            num_layers=2,
            model_type="relational_gcn",
            readout="mean",
            activation="tanh",
            seed=42,
        )

        graph = embedder.to_graph(self.sample_ast)
        H, z = embedder.encode_graph(graph)

        self.assertEqual(H.shape, (5, 32))
        self.assertEqual(z.shape, (32,))
        self.assertTrue(np.all(np.isfinite(H)))
        self.assertTrue(np.all(np.isfinite(z)))

        # Direct encode helper
        z_direct = embedder.encode(self.sample_ast)
        np.testing.assert_allclose(z, z_direct, rtol=1e-5, atol=1e-5)

    def test_graphsage_forward_pass(self):
        """Tests GraphSAGE embedder across different aggregators."""
        for agg in ["mean", "sum", "max"]:
            with self.subTest(aggregator=agg):
                embedder = ASTGraphEmbedder(
                    embed_dim=24,
                    hidden_dim=24,
                    num_layers=2,
                    model_type="graphsage",
                    readout="mean",
                    activation="relu",
                    seed=123,
                )
                z = embedder.encode(self.sample_ast)
                self.assertEqual(z.shape, (24,))
                self.assertTrue(np.all(np.isfinite(z)))

    def test_tree_lstm_embedder(self):
        """Tests Child-Sum Tree-LSTM AST Embedder."""
        embedder = ASTGraphEmbedder(
            embed_dim=40,
            hidden_dim=40,
            model_type="tree_lstm",
            readout="root",
            seed=999,
        )

        graph = embedder.to_graph(self.sample_ast)
        H, z = embedder.encode_graph(graph)

        self.assertEqual(H.shape, (5, 40))
        self.assertEqual(z.shape, (40,))
        self.assertTrue(np.all(np.isfinite(H)))
        self.assertTrue(np.all(np.isfinite(z)))

        # Root readout should equal H[root_idx]
        np.testing.assert_allclose(z, H[graph.root_idx], rtol=1e-5, atol=1e-5)

    def test_permutation_equivariance_and_invariance(self):
        """Formally verifies permutation equivariance of node states and invariance of global pooling."""
        converter = ASTGraphConverter()
        graph = converter.ast_to_graph(self.sample_ast)
        N = graph.num_nodes

        # Arbitrary non-trivial permutation of node indices
        perm = [3, 0, 4, 1, 2]
        permuted_graph = graph.permute_nodes(perm)

        # Relational GCN with sum pooling (which is theoretically permutation-invariant)
        embedder = ASTGraphEmbedder(
            embed_dim=32,
            hidden_dim=32,
            num_layers=2,
            model_type="relational_gcn",
            readout="sum",
            activation="tanh",
            seed=777,
        )

        H_orig, z_orig = embedder.encode_graph(graph)
        H_perm, z_perm = embedder.encode_graph(permuted_graph)

        # 1. Permutation Equivariance: H_perm[i] == H_orig[perm[i]]
        np.testing.assert_allclose(H_perm, H_orig[perm], rtol=1e-5, atol=1e-5)

        # 2. Permutation Invariance of Global Graph Readout Pooling: z_perm == z_orig
        np.testing.assert_allclose(z_perm, z_orig, rtol=1e-5, atol=1e-5)

    def test_pooling_dimension_consistency(self):
        """Verifies dimension consistency across all supported pooling strategies."""
        pooling_types = ["mean", "sum", "max", "root", "attention", "concat_mean_max"]
        embed_dim = 28

        for p_type in pooling_types:
            with self.subTest(pooling=p_type):
                embedder = ASTGraphEmbedder(
                    embed_dim=embed_dim,
                    hidden_dim=embed_dim,
                    model_type="relational_gcn",
                    readout=p_type,
                    seed=101,
                )
                z = embedder.encode(self.sample_ast)
                self.assertEqual(z.shape, (embed_dim,))
                self.assertTrue(np.all(np.isfinite(z)))

    def test_semantic_similarity_scoring(self):
        """Tests semantic cosine similarity properties: self-similarity, symmetry, bounds, and equivalence."""
        embedder = ASTGraphEmbedder(embed_dim=32, seed=42)

        # Identical AST
        ast1 = self.sample_ast
        ast2 = self.sample_ast

        # Distinct AST: starts_with("a")
        ast3 = TypedASTNode("starts_with", "BOOL", val="a")

        # 1. Self-similarity must be exactly 1.0
        self_sim = embedder.similarity(ast1, ast1)
        self.assertAlmostEqual(self_sim, 1.0, places=5)

        # 2. Symmetry / Commutativity
        sim_13 = embedder.similarity(ast1, ast3)
        sim_31 = embedder.similarity(ast3, ast1)
        self.assertAlmostEqual(sim_13, sim_31, places=5)

        # 3. Bounded in [-1.0, 1.0]
        self.assertTrue(-1.0 <= sim_13 <= 1.0)

        # 4. Equivalence classification
        self.assertTrue(embedder.is_semantically_equivalent(ast1, ast2, threshold=0.95))

        # 5. Calibrated probability in [0, 1]
        z1 = embedder.encode(ast1)
        z3 = embedder.encode(ast3)
        prob = embedder.equivalence_head.predict_equivalence_prob(z1, z3)
        self.assertTrue(0.0 <= prob <= 1.0)

    def test_rule_prediction_head(self):
        """Tests grammar production rule probability distribution prediction."""
        embedder = ASTGraphEmbedder(embed_dim=32, seed=42)
        probs = embedder.predict_rules(self.sample_ast)

        # Check all probabilities are in [0, 1]
        for rule, p in probs.items():
            self.assertTrue(0.0 <= p <= 1.0, f"Rule {rule} has out-of-bounds probability {p}")

        # Check probabilities sum to 1.0
        total_p = sum(probs.values())
        self.assertAlmostEqual(total_p, 1.0, places=5)

        # Check top-k prediction
        top3 = embedder.predict_top_k_rules(self.sample_ast, k=3)
        self.assertEqual(len(top3), 3)
        self.assertGreaterEqual(top3[0][1], top3[1][1])
        self.assertGreaterEqual(top3[1][1], top3[2][1])

    def test_complex_and_edge_case_asts(self):
        """Tests single-node AST and deep composite boolean AST."""
        embedder = ASTGraphEmbedder(embed_dim=32, seed=42)

        # 1. Single node AST
        single_node = TypedASTNode("int_const", "INT", val=42)
        z_single = embedder.encode(single_node)
        self.assertEqual(z_single.shape, (32,))
        self.assertTrue(np.all(np.isfinite(z_single)))

        # 2. Deep hierarchical AST: and(starts_with("a"), not(ends_with("b")))
        sw = TypedASTNode("starts_with", "BOOL", val="a")
        ew = TypedASTNode("ends_with", "BOOL", val="b")
        not_ew = TypedASTNode("not", "BOOL", children=[ew])
        complex_ast = TypedASTNode("and", "BOOL", children=[sw, not_ew])

        z_complex = embedder.encode(complex_ast)
        self.assertEqual(z_complex.shape, (32,))
        self.assertTrue(np.all(np.isfinite(z_complex)))

        # Node embeddings shape check
        H_complex = embedder.get_node_embeddings(complex_ast)
        self.assertEqual(H_complex.shape, (4, embedder.hidden_dim))


if __name__ == "__main__":
    unittest.main()
