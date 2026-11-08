"""ACE Graph Neural Network (GNN) & AST Graph Representation Learning Engine.

Provides:
- ASTGraph: Graph topology representation of strongly-typed AST nodes.
- ASTGraphConverter: Converts TypedASTNode to node feature matrix X and relational edge lists.
- RelationalGCNLayer & GraphSAGELayer: Directional message passing across child-to-parent and parent-to-child edges.
- TreeLSTMLayer: Child-sum recursive Tree-LSTM embedder.
- ReadoutPooling: Global graph pooling (mean, sum, max, root, attention).
- RulePredictionHead & SemanticEquivalenceHead: Grammar rule distribution and semantic cosine similarity.
- ASTGraphEmbedder: Unified representation learning engine.
"""
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

__all__ = [
    "ASTGraph",
    "ASTGraphConverter",
    "ASTGraphEmbedder",
    "GraphSAGELayer",
    "ReadoutPooling",
    "RelationalGCNLayer",
    "RulePredictionHead",
    "SemanticEquivalenceHead",
    "TreeLSTMLayer",
]
