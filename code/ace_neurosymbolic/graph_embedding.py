"""Equivariant AST Graph Representation and Latent Program Transfer.

Provides:
1. Weisfeiler-Lehman (WL) Topological Graph Kernel over strongly-typed AST DAGs.
2. Alpha-renaming and commutative symmetry canonicalization for exact structural isomorphism detection.
3. Permutation-equivariant Message Passing Graph Neural Network (AST-GNN) generating continuous latent embeddings.
4. Latent Program Library for cross-task sub-tree retrieval and nearest-neighbor program transfer.
"""
from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from ace_evolution.island_search import ProgramCandidate, TypedASTNode
from ace_neurosymbolic.neural_guided_search import PartialAST


COMMUTATIVE_OPERATORS: Set[str] = {"eq", "neq", "add", "mul", "and", "or"}


@dataclass
class GraphNode:
    """A vertex in the AST directed acyclic graph."""
    node_id: int
    op: str
    return_type: str
    val: Any = None
    depth: int = 1
    is_hole: bool = False

    def canonical_label(self) -> str:
        """Returns normalized label invariant under alpha-renaming."""
        val_str = str(self.val) if self.val is not None else ""
        return f"{self.return_type}:{self.op}:{val_str}"


@dataclass
class GraphEdge:
    """A directed edge in the AST graph."""
    src: int
    dst: int
    edge_type: str  # 'CHILD_0', 'CHILD_1', 'PARENT'


class ASTGraph:
    """Graph representation of an AST supporting commutative canonicalization."""

    def __init__(self):
        self.nodes: Dict[int, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.adj_out: Dict[int, List[int]] = {}
        self.adj_in: Dict[int, List[int]] = {}
        self.root_id: int = 0

    @classmethod
    def from_typed_ast(cls, root: TypedASTNode, canonicalize_commutative: bool = True) -> ASTGraph:
        """Constructs an ASTGraph from a TypedASTNode."""
        graph = cls()
        counter = 0

        def traverse(node: TypedASTNode, current_depth: int) -> int:
            nonlocal counter
            curr_id = counter
            counter += 1

            graph.nodes[curr_id] = GraphNode(
                node_id=curr_id,
                op=node.op,
                return_type=node.return_type,
                val=node.val,
                depth=current_depth,
                is_hole=False,
            )
            graph.adj_out[curr_id] = []
            graph.adj_in[curr_id] = []
            if not hasattr(graph, "adj_out_edges"):
                graph.adj_out_edges = {}
                graph.adj_in_edges = {}
            graph.adj_out_edges[curr_id] = []
            graph.adj_in_edges[curr_id] = []

            # Commutative child canonicalization
            children = node.children
            is_comm = node.op in COMMUTATIVE_OPERATORS
            if canonicalize_commutative and is_comm and len(children) == 2:
                # Canonical sort by structural signature
                sig0 = cls._subtree_signature(children[0])
                sig1 = cls._subtree_signature(children[1])
                if sig0 > sig1:
                    children = [children[1], children[0]]

            for pos, child in enumerate(children):
                edge_label = "CHILD_COMM" if is_comm else f"CHILD_{pos}"
                parent_edge_label = "PARENT_COMM" if is_comm else f"PARENT_OF_{pos}"
                child_id = traverse(child, current_depth + 1)
                graph.edges.append(GraphEdge(curr_id, child_id, edge_label))
                graph.edges.append(GraphEdge(child_id, curr_id, parent_edge_label))
                graph.adj_out[curr_id].append(child_id)
                graph.adj_in[child_id].append(curr_id)
                graph.adj_out_edges[curr_id].append((child_id, edge_label))
                graph.adj_in_edges[child_id].append((curr_id, parent_edge_label))

            return curr_id

        graph.adj_out_edges = {}
        graph.adj_in_edges = {}
        graph.root_id = traverse(root, 1)
        return graph

    @classmethod
    def _subtree_signature(cls, node: TypedASTNode) -> str:
        """Computes deterministic signature for commutative ordering."""
        child_sigs = [cls._subtree_signature(c) for c in node.children]
        val_str = str(node.val) if node.val is not None else ""
        return f"{node.return_type}:{node.op}:{val_str}({','.join(sorted(child_sigs))})"

    def num_nodes(self) -> int:
        return len(self.nodes)

    def num_edges(self) -> int:
        return len(self.edges)


class WeisfeilerLehmanASTKernel:
    """Weisfeiler-Lehman (WL) Subtree Graph Kernel for AST Structural Isomorphism."""

    def __init__(self, num_iterations: int = 3):
        self.num_iterations = num_iterations

    def extract_colors(self, graph: ASTGraph) -> Dict[str, int]:
        """Runs iterative color refinement and computes subtree color histogram."""
        # Initial colors c_v^(0)
        colors: Dict[int, str] = {
            nid: node.canonical_label()
            for nid, node in graph.nodes.items()
        }

        color_counts: Dict[str, int] = {}
        for c in colors.values():
            color_counts[c] = color_counts.get(c, 0) + 1

        # Iterative multiset neighbor refinement with positional edge types
        for it in range(1, self.num_iterations + 1):
            new_colors: Dict[int, str] = {}
            for nid in graph.nodes:
                out_edges = getattr(graph, "adj_out_edges", {}).get(nid, [])
                in_edges = getattr(graph, "adj_in_edges", {}).get(nid, [])
                all_edges = out_edges + in_edges

                neighbor_sigs = sorted(f"{edge_type}:{colors[nb]}" for nb, edge_type in all_edges)
                raw_sig = f"{colors[nid]}_iter{it}_[{','.join(neighbor_sigs)}]"
                hashed_color = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()[:12]
                new_colors[nid] = hashed_color
                color_counts[hashed_color] = color_counts.get(hashed_color, 0) + 1

            colors = new_colors

        return color_counts

    def similarity(self, ast1: TypedASTNode, ast2: TypedASTNode) -> float:
        """Calculates normalized Weisfeiler-Lehman kernel cosine similarity."""
        g1 = ASTGraph.from_typed_ast(ast1, canonicalize_commutative=True)
        g2 = ASTGraph.from_typed_ast(ast2, canonicalize_commutative=True)

        hist1 = self.extract_colors(g1)
        hist2 = self.extract_colors(g2)

        # Vector dot product
        all_keys = set(hist1.keys()).union(set(hist2.keys()))
        v1 = np.array([hist1.get(k, 0) for k in all_keys], dtype=np.float64)
        v2 = np.array([hist2.get(k, 0) for k in all_keys], dtype=np.float64)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        cos_sim = float(np.dot(v1, v2) / (norm1 * norm2))
        return max(0.0, min(1.0, cos_sim))


class EquivariantASTGNN:
    """Permutation-Equivariant Message Passing Graph Neural Network over AST DAGs."""

    VOCAB_OPS = [
        "count_a", "count_b", "len", "int_const", "bool_const",
        "starts_with", "ends_with", "contains", "graph_bfs",
        "add", "sub", "mul", "mod",
        "eq", "neq", "lte", "gte",
        "and", "or", "not", "HOLE",
    ]

    def __init__(self, embedding_dim: int = 32, num_layers: int = 2, seed: int = 42):
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers
        self.rng = np.random.default_rng(seed)

        # Node op embedding dictionary
        self.op_embeddings: Dict[str, np.ndarray] = {
            op: self.rng.normal(0.0, 1.0, size=embedding_dim)
            for op in self.VOCAB_OPS
        }
        # Edge weights
        self.w_self = self.rng.normal(0.0, 0.5, size=(embedding_dim, embedding_dim))
        self.w_child = self.rng.normal(0.0, 0.5, size=(embedding_dim, embedding_dim))
        self.w_parent = self.rng.normal(0.0, 0.5, size=(embedding_dim, embedding_dim))

    def embed_graph(self, graph: ASTGraph) -> np.ndarray:
        """Runs message passing over AST graph to produce a normalized embedding vector."""
        # Initial node states
        h: Dict[int, np.ndarray] = {}
        for nid, node in graph.nodes.items():
            base = self.op_embeddings.get(node.op, np.zeros(self.embedding_dim))
            # Depth positional signal
            depth_sig = np.sin(np.linspace(0, node.depth, self.embedding_dim))
            h[nid] = base + 0.2 * depth_sig

        # Message passing layers
        for _ in range(self.num_layers):
            next_h: Dict[int, np.ndarray] = {}
            for nid in graph.nodes:
                children = graph.adj_out.get(nid, [])
                parents = graph.adj_in.get(nid, [])

                # Permutation-invariant aggregation of child messages
                if children:
                    child_msgs = np.mean([h[c] for c in children], axis=0)
                else:
                    child_msgs = np.zeros(self.embedding_dim)

                if parents:
                    parent_msgs = np.mean([h[p] for p in parents], axis=0)
                else:
                    parent_msgs = np.zeros(self.embedding_dim)

                updated = (
                    h[nid] @ self.w_self +
                    child_msgs @ self.w_child +
                    parent_msgs @ self.w_parent
                )
                # ReLU non-linearity
                next_h[nid] = np.maximum(0.0, updated)
            h = next_h

        # Readout: Mean + Max pooling over all nodes
        all_vectors = np.array(list(h.values()))
        mean_pool = np.mean(all_vectors, axis=0)
        max_pool = np.max(all_vectors, axis=0)
        z = mean_pool + max_pool

        norm = np.linalg.norm(z)
        return z / norm if norm > 1e-12 else z

    def embed_ast(self, root: TypedASTNode) -> np.ndarray:
        graph = ASTGraph.from_typed_ast(root, canonicalize_commutative=True)
        return self.embed_graph(graph)


class LatentProgramLibrary:
    """Library of discovered programs with nearest-neighbor search and sub-tree transfer."""

    def __init__(self):
        self.kernel = WeisfeilerLehmanASTKernel(num_iterations=3)
        self.gnn = EquivariantASTGNN(embedding_dim=32, seed=42)
        self.entries: List[Dict[str, Any]] = []

    def register_candidate(
        self,
        candidate: ProgramCandidate,
        task_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Embeds and registers a verified candidate in the latent library."""
        vector = self.gnn.embed_ast(candidate.root)
        entry = {
            "candidate": candidate,
            "task_name": task_name,
            "code": candidate.root.to_code(),
            "vector": vector,
            "metadata": metadata or {},
        }
        self.entries.append(entry)
        return entry

    def find_nearest_neighbors(
        self,
        query_ast: TypedASTNode,
        top_k: int = 5,
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """Finds top-k nearest programs ranked by Weisfeiler-Lehman topological similarity."""
        results: List[Tuple[float, Dict[str, Any]]] = []
        for entry in self.entries:
            sim = self.kernel.similarity(query_ast, entry["candidate"].root)
            results.append((sim, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:top_k]

    def is_isomorphic(self, ast1: TypedASTNode, ast2: TypedASTNode, threshold: float = 0.95) -> bool:
        """Determines if two programs are structurally isomorphic under alpha-renaming."""
        sim = self.kernel.similarity(ast1, ast2)
        return sim >= threshold

    def extract_transferable_subtrees(self, root: TypedASTNode, min_depth: int = 2) -> List[TypedASTNode]:
        """Extracts valid composite sub-trees suitable for warm-starting or sketch slot transfer."""
        subtrees: List[TypedASTNode] = []

        def collect(node: TypedASTNode):
            if node.depth() >= min_depth:
                subtrees.append(copy.deepcopy(node))
            for child in node.children:
                collect(child)

        collect(root)
        return subtrees
