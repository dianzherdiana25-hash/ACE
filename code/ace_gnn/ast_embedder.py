"""Graph Neural Network & Tree-LSTM AST Graph Representation Learning Engine.

Mathematical Foundation:
1. AST to Relational Directed Graph Formulation:
   An Abstract Syntax Tree T = (V, E) is represented as a typed relational graph:
     G = (V, E_{c2p}, E_{p2c}, X)
   where:
     - V = {0, 1, ..., N-1} is the set of AST nodes.
     - E_{c2p} = {(u, v) : u is a child of v} represents bottom-up message passing edges.
     - E_{p2c} = {(v, u) : u is a child of v} represents top-down contextual edges.
     - X in R^{N x F} is the node feature matrix encoding operator type, return type,
       arity, tree depth, and constant values.

2. Relational Message Passing (R-GCN / GraphSAGE):
   For each layer l in {0, ..., L-1}, node representations H^{(l)} in R^{N x d_l} are updated via:
     H^{(l+1)} = sigma( H^{(l)} W_{self} + A_{c2p} H^{(l)} W_{c2p} + A_{p2c} H^{(l)} W_{p2c} + b )
   where A_{c2p} and A_{p2c} are row-degree normalized adjacency operators:
     (A H)_i = (1 / |N(i)|) * sum_{j in N(i)} H_j

3. Tree-LSTM (Child-Sum Formulation, Tai et al., 2015):
   For each node j visited bottom-up:
     h_tilde_j = sum_{k in C(j)} h_k
     i_j = sigmoid( W_i x_j + U_i h_tilde_j + b_i )
     f_{jk} = sigmoid( W_f x_j + U_f h_k + b_f )  for each k in C(j)
     o_j = sigmoid( W_o x_j + U_o h_tilde_j + b_o )
     u_j = tanh( W_u x_j + U_u h_tilde_j + b_u )
     c_j = i_j * u_j + sum_{k in C(j)} f_{jk} * c_k
     h_j = o_j * tanh( c_j )

4. Global Readout Pooling:
   Aggregates node embeddings {h_i}_{i=1}^N into a single d-dimensional graph vector:
     z = Readout({h_1, ..., h_N}) in R^d
   Supporting:
     - Mean pooling: z = (1 / N) sum_{i=1}^N h_i
     - Sum pooling:  z = sum_{i=1}^N h_i
     - Max pooling:  z = max_{i=1}^N h_i
     - Root readout: z = h_{root}
     - Attention pooling: z = sum_{i=1}^N alpha_i h_i, alpha = softmax(H w_a)

5. Rule Prediction & Semantic Equivalence Heads:
   - Production Rule Head:
       P(rule_k | z) = exp((z W_r + b_r)_k) / sum_j exp((z W_r + b_r)_j)
   - Semantic Equivalence Head:
       cosine_similarity(z_1, z_2) = (z_1 . z_2) / max(||z_1||_2 * ||z_2||_2, epsilon)
       P(equivalent | z_1, z_2) = sigmoid( w_s * cosine_similarity(z_1, z_2) + b_s )

Provenance: ADVISOR_AGENT
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np

from ace_evolution.island_search import TypedASTNode


# ---------------------------------------------------------------------------
# Activation Functions & Mathematical Utilities
# ---------------------------------------------------------------------------

def sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable element-wise sigmoid activation."""
    clipped = np.clip(x, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def tanh(x: np.ndarray) -> np.ndarray:
    """Element-wise hyperbolic tangent activation."""
    return np.tanh(x)


def relu(x: np.ndarray) -> np.ndarray:
    """Element-wise rectified linear unit."""
    return np.maximum(0.0, x)


def leaky_relu(x: np.ndarray, alpha: float = 0.01) -> np.ndarray:
    """Element-wise leaky ReLU with negative slope alpha."""
    return np.where(x > 0.0, x, alpha * x)


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax along specified axis."""
    shifted = x - np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(shifted)
    sum_exp = np.sum(exp_x, axis=axis, keepdims=True)
    return exp_x / np.maximum(sum_exp, 1e-12)


def get_activation_fn(name: str) -> Callable[[np.ndarray], np.ndarray]:
    """Retrieves activation callable by name."""
    name_lower = name.lower()
    if name_lower == "tanh":
        return tanh
    elif name_lower == "relu":
        return relu
    elif name_lower in ("leaky_relu", "lrelu"):
        return leaky_relu
    elif name_lower in ("sigmoid", "logistic"):
        return sigmoid
    elif name_lower in ("linear", "identity", "none"):
        return lambda x: x
    else:
        raise ValueError(f"Unknown activation function: {name}")


# ---------------------------------------------------------------------------
# AST Graph Data Structure & Converter
# ---------------------------------------------------------------------------

@dataclass
class ASTGraph:
    """Relational directed graph representation of a TypedASTNode tree."""

    num_nodes: int
    x: np.ndarray  # Shape: (N, F)
    edge_index_c2p: List[Tuple[int, int]]  # (child, parent) directed edges
    edge_index_p2c: List[Tuple[int, int]]  # (parent, child) directed edges
    node_ops: List[str]
    node_types: List[str]
    node_depths: List[int]
    root_idx: int
    node_map: Dict[int, TypedASTNode]
    child_map: Dict[int, List[int]] = field(default_factory=dict)
    parent_map: Dict[int, Optional[int]] = field(default_factory=dict)

    def adjacency_matrix(self, edge_type: str = "c2p", normalized: bool = True) -> np.ndarray:
        """Constructs an (N, N) adjacency matrix for message passing.
        
        Args:
            edge_type: 'c2p' (child-to-parent), 'p2c' (parent-to-child), or 'bidirectional'.
            normalized: If True, computes row-degree normalized random walk matrix D^{-1} A.
        """
        N = self.num_nodes
        adj = np.zeros((N, N), dtype=np.float32)

        edges = []
        if edge_type in ("c2p", "bottom_up"):
            edges = self.edge_index_c2p
        elif edge_type in ("p2c", "top_down"):
            edges = self.edge_index_p2c
        elif edge_type in ("bidirectional", "both"):
            edges = self.edge_index_c2p + self.edge_index_p2c
        else:
            raise ValueError(f"Unknown edge_type: {edge_type}")

        for src, dst in edges:
            adj[dst, src] = 1.0  # message flows from src to dst: (A H)_dst = sum_{src} H_src

        if normalized:
            # Row-normalize: divide each row by in-degree (number of senders to that destination)
            row_sum = np.sum(adj, axis=1, keepdims=True)
            # Avoid division by zero for nodes without incoming edges of this type
            row_sum = np.where(row_sum == 0.0, 1.0, row_sum)
            adj = adj / row_sum

        return adj

    def permute_nodes(self, permutation: List[int]) -> ASTGraph:
        """Permutes graph node indexing according to permutation pi.
        
        pi[new_idx] = old_idx, or equivalently maps old_idx to pi_inv[old_idx].
        Useful for formally verifying permutation equivariance and invariance.
        """
        N = self.num_nodes
        if len(permutation) != N or sorted(permutation) != list(range(N)):
            raise ValueError(f"Invalid permutation of length {N}: {permutation}")

        # old_to_new mapping:
        old_to_new = {old: new for new, old in enumerate(permutation)}

        new_x = self.x[permutation].copy()
        new_ops = [self.node_ops[i] for i in permutation]
        new_types = [self.node_types[i] for i in permutation]
        new_depths = [self.node_depths[i] for i in permutation]
        new_root_idx = old_to_new[self.root_idx]

        new_c2p = [(old_to_new[u], old_to_new[v]) for u, v in self.edge_index_c2p]
        new_p2c = [(old_to_new[u], old_to_new[v]) for u, v in self.edge_index_p2c]

        new_node_map = {new: self.node_map[old] for new, old in enumerate(permutation)}
        new_child_map = {
            old_to_new[old]: [old_to_new[c] for c in self.child_map.get(old, [])]
            for old in range(N)
        }
        new_parent_map = {
            old_to_new[old]: (old_to_new[self.parent_map[old]] if self.parent_map[old] is not None else None)
            for old in range(N)
        }

        return ASTGraph(
            num_nodes=N,
            x=new_x,
            edge_index_c2p=new_c2p,
            edge_index_p2c=new_p2c,
            node_ops=new_ops,
            node_types=new_types,
            node_depths=new_depths,
            root_idx=new_root_idx,
            node_map=new_node_map,
            child_map=new_child_map,
            parent_map=new_parent_map,
        )


class ASTGraphConverter:
    """Converts strongly-typed TypedASTNode trees into relational ASTGraph structures.
    
    Generates rich, permutation-aware node feature matrices X in R^{N x F} encoding:
    - Operator vocabulary one-hot (canonical ACE arithmetic, boolean, terminal primitives).
    - Return type one-hot ('INT', 'BOOL', 'OTHER').
    - Arity one-hot (0, 1, 2, >=3).
    - Normalized tree depth & leaf status.
    - Constant value indicators (numeric, boolean, string properties).
    - Position among siblings.
    """

    CANONICAL_OPS: List[str] = [
        "count_a", "count_b", "len", "int_const", "bool_const",
        "starts_with", "ends_with", "contains", "graph_bfs", "dyck_balanced",
        "add", "sub", "mul", "mod",
        "eq", "neq", "lte", "gte",
        "and", "or", "not",
        "call_macro", "unknown",
    ]

    RETURN_TYPES: List[str] = ["INT", "BOOL", "OTHER"]

    def __init__(self, op_vocab: Optional[List[str]] = None):
        self.op_vocab = list(op_vocab or self.CANONICAL_OPS)
        self.op_to_idx = {op: i for i, op in enumerate(self.op_vocab)}
        self.type_to_idx = {t: i for i, t in enumerate(self.RETURN_TYPES)}

        # Total feature dimension calculation:
        # op_onehot (len(op_vocab)) + type_onehot (3) + arity_onehot (4) + depth_feats (2) + val_feats (4) + sibling_pos (4)
        self.feature_dim = len(self.op_vocab) + len(self.RETURN_TYPES) + 4 + 2 + 4 + 4

    def _get_op_idx(self, op: str) -> int:
        if op in self.op_to_idx:
            return self.op_to_idx[op]
        elif op.startswith("macro_"):
            return self.op_to_idx.get("call_macro", self.op_to_idx["unknown"])
        return self.op_to_idx.get("unknown", len(self.op_vocab) - 1)

    def _extract_node_features(
        self,
        node: TypedASTNode,
        depth: int,
        sibling_idx: int,
    ) -> np.ndarray:
        """Extracts dense feature vector for a single TypedASTNode."""
        feat = np.zeros(self.feature_dim, dtype=np.float32)
        offset = 0

        # 1. Operator One-hot
        op_idx = self._get_op_idx(node.op)
        feat[offset + op_idx] = 1.0
        offset += len(self.op_vocab)

        # 2. Return Type One-hot
        rtype = node.return_type.upper() if isinstance(node.return_type, str) else "OTHER"
        type_idx = self.type_to_idx.get(rtype, self.type_to_idx["OTHER"])
        feat[offset + type_idx] = 1.0
        offset += len(self.RETURN_TYPES)

        # 3. Arity One-hot (0, 1, 2, >=3)
        arity = len(node.children) if node.children else 0
        arity_idx = min(arity, 3)
        feat[offset + arity_idx] = 1.0
        offset += 4

        # 4. Depth features: normalized depth and leaf indicator
        feat[offset] = min(depth / 10.0, 1.0)
        feat[offset + 1] = 1.0 if arity == 0 else 0.0
        offset += 2

        # 5. Value features
        is_const = 1.0 if node.op in ("int_const", "bool_const") or node.val is not None else 0.0
        feat[offset] = is_const

        num_val = 0.0
        if isinstance(node.val, (int, float)) and not isinstance(node.val, bool):
            num_val = float(np.tanh(node.val / 10.0))
        feat[offset + 1] = num_val

        bool_val = 0.0
        if isinstance(node.val, bool):
            bool_val = 1.0 if node.val else -1.0
        feat[offset + 2] = bool_val

        str_len = 0.0
        if isinstance(node.val, str):
            str_len = min(len(node.val) / 10.0, 1.0)
        feat[offset + 3] = str_len
        offset += 4

        # 6. Sibling position one-hot (0, 1, 2, >=3)
        sib_idx = min(sibling_idx, 3)
        feat[offset + sib_idx] = 1.0

        return feat

    def ast_to_graph(self, root: TypedASTNode) -> ASTGraph:
        """Converts an AST tree with root TypedASTNode into an ASTGraph."""
        nodes: List[TypedASTNode] = []
        node_depths: List[int] = []
        node_ops: List[str] = []
        node_types: List[str] = []
        node_siblings: List[int] = []

        c2p_edges: List[Tuple[int, int]] = []
        p2c_edges: List[Tuple[int, int]] = []
        child_map: Dict[int, List[int]] = {}
        parent_map: Dict[int, Optional[int]] = {}

        # Preorder traversal to assign indices
        def traverse(node: TypedASTNode, depth: int, parent_idx: Optional[int], sib_pos: int) -> int:
            current_idx = len(nodes)
            nodes.append(node)
            node_depths.append(depth)
            node_ops.append(node.op)
            node_types.append(node.return_type)
            node_siblings.append(sib_pos)

            child_map[current_idx] = []
            parent_map[current_idx] = parent_idx

            if parent_idx is not None:
                c2p_edges.append((current_idx, parent_idx))
                p2c_edges.append((parent_idx, current_idx))

            children = node.children or []
            for i, child in enumerate(children):
                child_idx = traverse(child, depth + 1, current_idx, i)
                child_map[current_idx].append(child_idx)

            return current_idx

        root_idx = traverse(root, depth=0, parent_idx=None, sib_pos=0)
        num_nodes = len(nodes)

        # Build feature matrix X
        X = np.zeros((num_nodes, self.feature_dim), dtype=np.float32)
        for i in range(num_nodes):
            X[i] = self._extract_node_features(
                nodes[i],
                depth=node_depths[i],
                sibling_idx=node_siblings[i],
            )

        node_map = {i: nodes[i] for i in range(num_nodes)}

        return ASTGraph(
            num_nodes=num_nodes,
            x=X,
            edge_index_c2p=c2p_edges,
            edge_index_p2c=p2c_edges,
            node_ops=node_ops,
            node_types=node_types,
            node_depths=node_depths,
            root_idx=root_idx,
            node_map=node_map,
            child_map=child_map,
            parent_map=parent_map,
        )


# ---------------------------------------------------------------------------
# Relational Message Passing Layers
# ---------------------------------------------------------------------------

class RelationalGCNLayer:
    """Relational Graph Convolutional Layer with directional message passing.
    
    Computes:
      H^{(l+1)} = sigma( H W_{self} + A_{c2p} H W_{c2p} + A_{p2c} H W_{p2c} + b )
    """

    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        activation: str = "tanh",
        seed: Optional[int] = None,
    ):
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.activation_name = activation
        self.activation = get_activation_fn(activation)

        rng = np.random.default_rng(seed)
        # Xavier / Glorot uniform initialization:
        limit = math.sqrt(6.0 / (in_dim + out_dim))
        self.W_self = rng.uniform(-limit, limit, (in_dim, out_dim)).astype(np.float32)
        self.W_c2p = rng.uniform(-limit, limit, (in_dim, out_dim)).astype(np.float32)
        self.W_p2c = rng.uniform(-limit, limit, (in_dim, out_dim)).astype(np.float32)
        self.bias = np.zeros(out_dim, dtype=np.float32)

    def forward(self, H: np.ndarray, graph: ASTGraph) -> np.ndarray:
        """Executes forward relational message passing."""
        # 1. Self representation
        out_self = np.matmul(H, self.W_self)

        # 2. Child to parent messages (bottom-up)
        A_c2p = graph.adjacency_matrix(edge_type="c2p", normalized=True)
        H_c2p = np.matmul(A_c2p, H)
        out_c2p = np.matmul(H_c2p, self.W_c2p)

        # 3. Parent to child messages (top-down)
        A_p2c = graph.adjacency_matrix(edge_type="p2c", normalized=True)
        H_p2c = np.matmul(A_p2c, H)
        out_p2c = np.matmul(H_p2c, self.W_p2c)

        # 4. Aggregation + non-linear activation
        total = out_self + out_c2p + out_p2c + self.bias
        return self.activation(total)


class GraphSAGELayer:
    """GraphSAGE Message Passing Layer with mean/sum/max aggregation over directed relations."""

    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        aggregator: str = "mean",
        activation: str = "relu",
        seed: Optional[int] = None,
    ):
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.aggregator = aggregator.lower()
        self.activation = get_activation_fn(activation)

        rng = np.random.default_rng(seed)
        limit = math.sqrt(6.0 / (in_dim + out_dim))
        self.W_self = rng.uniform(-limit, limit, (in_dim, out_dim)).astype(np.float32)
        self.W_neigh = rng.uniform(-limit, limit, (in_dim, out_dim)).astype(np.float32)
        self.bias = np.zeros(out_dim, dtype=np.float32)

    def forward(self, H: np.ndarray, graph: ASTGraph) -> np.ndarray:
        N = graph.num_nodes
        neigh_H = np.zeros_like(H)

        for i in range(N):
            # Inbound neighbors: children sending to parent (c2p) and parent sending to child (p2c)
            children = graph.child_map.get(i, [])
            parent = graph.parent_map.get(i)
            neighbors = list(children)
            if parent is not None:
                neighbors.append(parent)

            if not neighbors:
                neigh_H[i] = 0.0
            else:
                stacked = H[neighbors]
                if self.aggregator == "mean":
                    neigh_H[i] = np.mean(stacked, axis=0)
                elif self.aggregator == "sum":
                    neigh_H[i] = np.sum(stacked, axis=0)
                elif self.aggregator == "max":
                    neigh_H[i] = np.max(stacked, axis=0)
                else:
                    neigh_H[i] = np.mean(stacked, axis=0)

        out_self = np.matmul(H, self.W_self)
        out_neigh = np.matmul(neigh_H, self.W_neigh)
        return self.activation(out_self + out_neigh + self.bias)


class TreeLSTMLayer:
    """Child-Sum Recursive Tree-LSTM AST Embedder (Tai et al., 2015).
    
    Processes the AST bottom-up from leaves to root, maintaining memory cells
    and gating across arbitrary child branching.
    """

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int,
        seed: Optional[int] = None,
    ):
        self.in_dim = in_dim
        self.hidden_dim = hidden_dim

        rng = np.random.default_rng(seed)
        limit = math.sqrt(6.0 / (in_dim + hidden_dim))

        # Input gate parameters: W_i x + U_i h_tilde + b_i
        self.W_i = rng.uniform(-limit, limit, (in_dim, hidden_dim)).astype(np.float32)
        self.U_i = rng.uniform(-limit, limit, (hidden_dim, hidden_dim)).astype(np.float32)
        self.b_i = np.zeros(hidden_dim, dtype=np.float32)

        # Forget gate parameters: W_f x + U_f h_k + b_f
        self.W_f = rng.uniform(-limit, limit, (in_dim, hidden_dim)).astype(np.float32)
        self.U_f = rng.uniform(-limit, limit, (hidden_dim, hidden_dim)).astype(np.float32)
        self.b_f = np.ones(hidden_dim, dtype=np.float32)  # Forget gate bias initialized to 1

        # Output gate parameters: W_o x + U_o h_tilde + b_o
        self.W_o = rng.uniform(-limit, limit, (in_dim, hidden_dim)).astype(np.float32)
        self.U_o = rng.uniform(-limit, limit, (hidden_dim, hidden_dim)).astype(np.float32)
        self.b_o = np.zeros(hidden_dim, dtype=np.float32)

        # Candidate cell parameters: W_u x + U_u h_tilde + b_u
        self.W_u = rng.uniform(-limit, limit, (in_dim, hidden_dim)).astype(np.float32)
        self.U_u = rng.uniform(-limit, limit, (hidden_dim, hidden_dim)).astype(np.float32)
        self.b_u = np.zeros(hidden_dim, dtype=np.float32)

    def forward(self, X: np.ndarray, graph: ASTGraph) -> Tuple[np.ndarray, np.ndarray]:
        """Computes bottom-up Tree-LSTM hidden states H and cell states C."""
        N = graph.num_nodes
        d = self.hidden_dim

        H = np.zeros((N, d), dtype=np.float32)
        C = np.zeros((N, d), dtype=np.float32)

        # Determine topological bottom-up order (nodes with larger depth first)
        depth_order = sorted(range(N), key=lambda idx: graph.node_depths[idx], reverse=True)

        for j in depth_order:
            xj = X[j]
            children = graph.child_map.get(j, [])

            if not children:
                # Leaf node: h_tilde is 0
                h_tilde = np.zeros(d, dtype=np.float32)
                i_j = sigmoid(np.dot(xj, self.W_i) + np.dot(h_tilde, self.U_i) + self.b_i)
                o_j = sigmoid(np.dot(xj, self.W_o) + np.dot(h_tilde, self.U_o) + self.b_o)
                u_j = tanh(np.dot(xj, self.W_u) + np.dot(h_tilde, self.U_u) + self.b_u)

                C[j] = i_j * u_j
                H[j] = o_j * tanh(C[j])
            else:
                # Internal node: sum child hidden states
                h_tilde = np.sum([H[k] for k in children], axis=0)

                i_j = sigmoid(np.dot(xj, self.W_i) + np.dot(h_tilde, self.U_i) + self.b_i)
                o_j = sigmoid(np.dot(xj, self.W_o) + np.dot(h_tilde, self.U_o) + self.b_o)
                u_j = tanh(np.dot(xj, self.W_u) + np.dot(h_tilde, self.U_u) + self.b_u)

                # Each child k has an individual forget gate
                child_c_sum = np.zeros(d, dtype=np.float32)
                for k in children:
                    f_jk = sigmoid(np.dot(xj, self.W_f) + np.dot(H[k], self.U_f) + self.b_f)
                    child_c_sum += f_jk * C[k]

                C[j] = i_j * u_j + child_c_sum
                H[j] = o_j * tanh(C[j])

        return H, C


# ---------------------------------------------------------------------------
# Readout Pooling Module
# ---------------------------------------------------------------------------

class ReadoutPooling:
    """Global graph readout pooling transforming node representations H in R^{N x d} into z in R^d."""

    VALID_MODES: Set[str] = {"mean", "sum", "max", "root", "attention", "concat_mean_max"}

    def __init__(
        self,
        pooling_type: str = "mean",
        hidden_dim: int = 64,
        seed: Optional[int] = None,
    ):
        p_type = pooling_type.lower()
        if p_type not in self.VALID_MODES:
            raise ValueError(f"Unsupported pooling_type '{pooling_type}'. Must be one of {self.VALID_MODES}")
        self.pooling_type = p_type
        self.hidden_dim = hidden_dim

        rng = np.random.default_rng(seed)
        if self.pooling_type == "attention":
            self.w_attn = rng.normal(0.0, 0.1, (hidden_dim, 1)).astype(np.float32)
        elif self.pooling_type == "concat_mean_max":
            # Linear projection from 2*hidden_dim back to hidden_dim
            limit = math.sqrt(6.0 / (2 * hidden_dim + hidden_dim))
            self.W_proj = rng.uniform(-limit, limit, (2 * hidden_dim, hidden_dim)).astype(np.float32)

    def forward(self, H: np.ndarray, graph: ASTGraph) -> np.ndarray:
        """Pools node embeddings H into graph embedding vector z in R^d."""
        if self.pooling_type == "mean":
            return np.mean(H, axis=0)
        elif self.pooling_type == "sum":
            return np.sum(H, axis=0)
        elif self.pooling_type == "max":
            return np.max(H, axis=0)
        elif self.pooling_type == "root":
            return H[graph.root_idx].copy()
        elif self.pooling_type == "attention":
            scores = np.matmul(H, self.w_attn).squeeze(-1)  # (N,)
            weights = softmax(scores, axis=0)  # (N,)
            return np.sum(H * weights[:, np.newaxis], axis=0)
        elif self.pooling_type == "concat_mean_max":
            mean_z = np.mean(H, axis=0)
            max_z = np.max(H, axis=0)
            concat = np.concatenate([mean_z, max_z], axis=0)
            return np.matmul(concat, self.W_proj)
        else:
            return np.mean(H, axis=0)


# ---------------------------------------------------------------------------
# Rule Prediction & Semantic Equivalence Heads
# ---------------------------------------------------------------------------

class RulePredictionHead:
    """Predicts DSL grammar production rule probability distribution P(rule | z)."""

    DEFAULT_RULES: List[str] = [
        "count_a", "count_b", "len", "int_const", "bool_const",
        "starts_with", "ends_with", "contains", "graph_bfs", "dyck_balanced",
        "add", "sub", "mul", "mod",
        "eq", "neq", "lte", "gte",
        "and", "or", "not",
        "call_macro",
    ]

    def __init__(
        self,
        embed_dim: int,
        rules: Optional[List[str]] = None,
        seed: Optional[int] = None,
    ):
        self.rules = list(rules or self.DEFAULT_RULES)
        self.num_rules = len(self.rules)
        self.embed_dim = embed_dim

        rng = np.random.default_rng(seed)
        limit = math.sqrt(6.0 / (embed_dim + self.num_rules))
        self.W_rule = rng.uniform(-limit, limit, (embed_dim, self.num_rules)).astype(np.float32)
        self.b_rule = np.zeros(self.num_rules, dtype=np.float32)

    def forward_logits(self, z: np.ndarray) -> np.ndarray:
        """Computes raw unnormalized logits for grammar production rules."""
        return np.matmul(z, self.W_rule) + self.b_rule

    def predict_rule_probs(self, z: np.ndarray) -> Dict[str, float]:
        """Computes calibrated probability distribution P(rule_k | z)."""
        logits = self.forward_logits(z)
        probs = softmax(logits, axis=-1)
        return {rule: float(probs[i]) for i, rule in enumerate(self.rules)}

    def top_k_rules(self, z: np.ndarray, k: int = 3) -> List[Tuple[str, float]]:
        """Returns top-k predicted production rules sorted by descending probability."""
        probs_dict = self.predict_rule_probs(z)
        sorted_rules = sorted(probs_dict.items(), key=lambda item: item[1], reverse=True)
        return sorted_rules[:k]


class SemanticEquivalenceHead:
    """Estimates semantic similarity and classifies semantic equivalence between two AST representations."""

    def __init__(
        self,
        embed_dim: int,
        threshold: float = 0.85,
        seed: Optional[int] = None,
    ):
        self.embed_dim = embed_dim
        self.threshold = threshold

        rng = np.random.default_rng(seed)
        self.weight_calibrator = float(rng.uniform(1.5, 3.0))
        self.bias_calibrator = float(rng.uniform(-0.5, 0.0))

    @staticmethod
    def cosine_similarity(z1: np.ndarray, z2: np.ndarray, eps: float = 1e-12) -> float:
        """Computes standard cosine similarity between two embedding vectors.
        
        cos(z1, z2) = (z1 . z2) / max(||z1||_2 * ||z2||_2, eps)
        Guaranteed bounded in [-1.0, 1.0].
        """
        dot = float(np.dot(z1, z2))
        norm1 = float(np.linalg.norm(z1))
        norm2 = float(np.linalg.norm(z2))
        denom = max(norm1 * norm2, eps)
        sim = dot / denom
        return float(np.clip(sim, -1.0, 1.0))

    def predict_equivalence_prob(self, z1: np.ndarray, z2: np.ndarray) -> float:
        """Calibrates cosine similarity into an equivalence probability in [0, 1]."""
        cos_sim = self.cosine_similarity(z1, z2)
        logit = self.weight_calibrator * cos_sim + self.bias_calibrator
        prob = 1.0 / (1.0 + math.exp(-max(min(logit, 20.0), -20.0)))
        return float(prob)

    def is_equivalent(
        self,
        z1: np.ndarray,
        z2: np.ndarray,
        threshold: Optional[float] = None,
    ) -> bool:
        """Determines if two embeddings are semantically equivalent."""
        t = threshold if threshold is not None else self.threshold
        return self.cosine_similarity(z1, z2) >= t


# ---------------------------------------------------------------------------
# Unified AST Graph Embedder Engine
# ---------------------------------------------------------------------------

class ASTGraphEmbedder:
    """Unified Graph Neural Network & Tree-LSTM AST Representation Learning Engine.
    
    Seamlessly converts TypedASTNodes into graph representations, performs relational
    message passing, global graph readout pooling, production rule inference, and
    semantic similarity verification.
    """

    def __init__(
        self,
        embed_dim: int = 64,
        hidden_dim: int = 64,
        num_layers: int = 2,
        model_type: str = "relational_gcn",
        readout: str = "mean",
        activation: str = "tanh",
        seed: Optional[int] = 42,
    ):
        self.embed_dim = embed_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.model_type = model_type.lower()
        self.readout_name = readout.lower()
        self.activation_name = activation
        self.seed = seed

        # Graph Converter
        self.converter = ASTGraphConverter()
        in_dim = self.converter.feature_dim

        # Input feature projection if needed
        rng = np.random.default_rng(seed)
        limit = math.sqrt(6.0 / (in_dim + hidden_dim))
        self.W_in = rng.uniform(-limit, limit, (in_dim, hidden_dim)).astype(np.float32)
        self.b_in = np.zeros(hidden_dim, dtype=np.float32)

        # Message passing layers
        self.layers: List[Union[RelationalGCNLayer, GraphSAGELayer, TreeLSTMLayer]] = []

        if self.model_type == "relational_gcn":
            for l in range(num_layers):
                seed_l = (seed + l * 17) if seed is not None else None
                layer = RelationalGCNLayer(
                    in_dim=hidden_dim,
                    out_dim=hidden_dim,
                    activation=activation,
                    seed=seed_l,
                )
                self.layers.append(layer)

        elif self.model_type == "graphsage":
            for l in range(num_layers):
                seed_l = (seed + l * 19) if seed is not None else None
                layer = GraphSAGELayer(
                    in_dim=hidden_dim,
                    out_dim=hidden_dim,
                    aggregator="mean",
                    activation=activation,
                    seed=seed_l,
                )
                self.layers.append(layer)

        elif self.model_type == "tree_lstm":
            # For Tree-LSTM, input projection is handled directly by layer
            self.tree_lstm = TreeLSTMLayer(
                in_dim=in_dim,
                hidden_dim=hidden_dim,
                seed=seed,
            )
        else:
            raise ValueError(f"Unsupported model_type '{model_type}'. Choose 'relational_gcn', 'graphsage', or 'tree_lstm'.")

        # Global Readout Pooling
        self.pooling = ReadoutPooling(
            pooling_type=self.readout_name,
            hidden_dim=hidden_dim,
            seed=(seed + 101) if seed is not None else None,
        )

        # Output projection from hidden_dim to embed_dim if different
        if hidden_dim != embed_dim:
            proj_limit = math.sqrt(6.0 / (hidden_dim + embed_dim))
            self.W_out = rng.uniform(-proj_limit, proj_limit, (hidden_dim, embed_dim)).astype(np.float32)
        else:
            self.W_out = None

        # Prediction Heads
        self.rule_head = RulePredictionHead(
            embed_dim=embed_dim,
            seed=(seed + 202) if seed is not None else None,
        )
        self.equivalence_head = SemanticEquivalenceHead(
            embed_dim=embed_dim,
            seed=(seed + 303) if seed is not None else None,
        )

    def to_graph(self, ast: TypedASTNode) -> ASTGraph:
        """Converts TypedASTNode to ASTGraph representation."""
        return self.converter.ast_to_graph(ast)

    def encode_graph(self, graph: ASTGraph) -> Tuple[np.ndarray, np.ndarray]:
        """Encodes an ASTGraph into node representations H in R^{N x hidden_dim}
        and pooled graph embedding z in R^{embed_dim}.
        """
        if self.model_type == "tree_lstm":
            H, _ = self.tree_lstm.forward(graph.x, graph)
        else:
            # Project input features: H_0 = relu(X W_in + b_in)
            H = relu(np.matmul(graph.x, self.W_in) + self.b_in)
            for layer in self.layers:
                H = layer.forward(H, graph)

        # Global Readout Pooling
        pooled = self.pooling.forward(H, graph)

        if self.W_out is not None:
            z = np.matmul(pooled, self.W_out)
        else:
            z = pooled

        return H, z

    def encode(self, ast: TypedASTNode) -> np.ndarray:
        """Encodes a TypedASTNode into d-dimensional graph embedding vector z in R^{embed_dim}."""
        graph = self.to_graph(ast)
        _, z = self.encode_graph(graph)
        return z

    def get_node_embeddings(self, ast: TypedASTNode) -> np.ndarray:
        """Returns node-level representations H in R^{N x hidden_dim}."""
        graph = self.to_graph(ast)
        H, _ = self.encode_graph(graph)
        return H

    def similarity(self, ast1: TypedASTNode, ast2: TypedASTNode) -> float:
        """Calculates cosine similarity between two AST embeddings."""
        z1 = self.encode(ast1)
        z2 = self.encode(ast2)
        return self.equivalence_head.cosine_similarity(z1, z2)

    def is_semantically_equivalent(
        self,
        ast1: TypedASTNode,
        ast2: TypedASTNode,
        threshold: float = 0.85,
    ) -> bool:
        """Evaluates whether two ASTs meet the cosine similarity equivalence threshold."""
        sim = self.similarity(ast1, ast2)
        return sim >= threshold

    def predict_rules(self, ast: TypedASTNode) -> Dict[str, float]:
        """Predicts production rule probability distribution P(rule | z)."""
        z = self.encode(ast)
        return self.rule_head.predict_rule_probs(z)

    def predict_top_k_rules(self, ast: TypedASTNode, k: int = 3) -> List[Tuple[str, float]]:
        """Predicts top-k production rules for an AST."""
        z = self.encode(ast)
        return self.rule_head.top_k_rules(z, k=k)
