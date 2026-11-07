"""AST-isolated recursive-descent ordered-tree parser and terminal evaluator.

SECURITY & SCIENTIFIC ISOLATION CONTRACT:
- Zero imports from `dsl`, `discovery`, or `arms`.
- Implements independent `TreeNode` recursive data structures and ground-truth
  relations used solely by `tasks.py`, `runner.py`, `verify.py`, and tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class TreeNode:
    """Ordered rooted tree node with zero or more ordered children."""

    children: tuple[TreeNode, ...] = ()


def encode_tree(node: TreeNode) -> str:
    """Encode `TreeNode` as canonical prime Dyck word `a <children> b`."""
    return "a" + "".join(encode_tree(child) for child in node.children) + "b"


def _parse_tree_at(word: str, pos: int) -> tuple[TreeNode, int] | None:
    if pos >= len(word) or word[pos] != "a":
        return None
    idx = pos + 1
    children: list[TreeNode] = []
    while idx < len(word) and word[idx] == "a":
        parsed_child = _parse_tree_at(word, idx)
        if parsed_child is None:
            return None
        child_node, idx = parsed_child
        children.append(child_node)
    if idx >= len(word) or word[idx] != "b":
        return None
    return TreeNode(tuple(children)), idx + 1


def parse_single_tree(word: str) -> TreeNode | None:
    """Parse `word` iff it is a single valid prime Dyck ordered tree."""
    if type(word) is not str or not word or (set(word) - {"a", "b"}):
        return None
    res = _parse_tree_at(word, 0)
    if res is None or res[1] != len(word):
        return None
    return res[0]


def parse_paired_trees(word: str) -> tuple[TreeNode, TreeNode] | None:
    """Parse `word` iff it is a concatenation `enc(T1) + enc(T2)` of two prime Dyck trees."""
    if type(word) is not str or not word or (set(word) - {"a", "b"}):
        return None
    first = _parse_tree_at(word, 0)
    if first is None or first[1] >= len(word):
        return None
    second = _parse_tree_at(word, first[1])
    if second is None or second[1] != len(word):
        return None
    return first[0], second[0]


# --- Independent Recursive Tree Invariants ---


def tree_nodes(node: TreeNode) -> int:
    return 1 + sum(tree_nodes(c) for c in node.children)


def tree_max_depth(node: TreeNode) -> int:
    if not node.children:
        return 1
    return 1 + max(tree_max_depth(c) for c in node.children)


def tree_leaves(node: TreeNode) -> int:
    if not node.children:
        return 1
    return sum(tree_leaves(c) for c in node.children)


def tree_root_deg(node: TreeNode) -> int:
    return len(node.children)


def tree_bipartite_diff(node: TreeNode, depth: int = 1) -> int:
    sign = 1 if (depth % 2 == 1) else -1
    return sign + sum(tree_bipartite_diff(c, depth + 1) for c in node.children)


def tree_max_outdeg(node: TreeNode) -> int:
    deg = len(node.children)
    if not node.children:
        return deg
    return max(deg, max(tree_max_outdeg(c) for c in node.children))


def tree_branching_nodes(node: TreeNode) -> int:
    own = 1 if len(node.children) >= 2 else 0
    return own + sum(tree_branching_nodes(c) for c in node.children)


def tree_mirror(node: TreeNode) -> TreeNode:
    return TreeNode(tuple(tree_mirror(c) for c in reversed(node.children)))


def tree_leaf_depths_ltr(node: TreeNode, depth: int = 1) -> list[int]:
    if not node.children:
        return [depth]
    out: list[int] = []
    for c in node.children:
        out.extend(tree_leaf_depths_ltr(c, depth + 1))
    return out


def tree_ordered_leaf_hash_mod5(node: TreeNode) -> int:
    depths = tree_leaf_depths_ltr(node, 1)
    return sum((idx + 1) * d for idx, d in enumerate(depths)) % 5


# --- Source Task Ground-Truth Oracles (12 Single-Tree Tasks in S_mixed) ---


def eval_source_task(task_name: str, word: str) -> bool:
    tree = parse_single_tree(word)
    if tree is None:
        return False
    if task_name == "s_struct_depth_odd":
        return tree_max_depth(tree) % 2 == 1
    if task_name == "s_struct_leaves_mod3":
        return tree_leaves(tree) % 3 == 0
    if task_name == "s_struct_root_deg_eq2":
        return tree_root_deg(tree) == 2
    if task_name == "s_struct_bipartite_zero":
        return tree_bipartite_diff(tree) == 0
    if task_name == "s_struct_max_outdeg_le2":
        return tree_max_outdeg(tree) <= 2
    if task_name == "s_struct_branching_ge2":
        return tree_branching_nodes(tree) >= 2
    if task_name == "s_surf_starts_aaa":
        return word.startswith("aaa")
    if task_name == "s_surf_ends_abb":
        return word.endswith("abb")
    if task_name == "s_surf_contains_bba":
        return "bba" in word
    if task_name == "s_surf_count_a_mod3":
        return word.count("a") % 3 == 0
    if task_name == "s_surf_char3_is_a":
        return len(word) >= 4 and word[3] == "a"
    if task_name == "s_surf_aab_and_bbb":
        return word.startswith("aab") and word.endswith("bbb")
    raise ValueError(f"unknown source task: {task_name}")


# --- Target Task Ground-Truth Oracles (15 Paired-Tree Tasks across 4 Strata) ---


def eval_nominal_target_task(task_name: str, word: str) -> bool:
    pair = parse_paired_trees(word)
    if pair is None:
        return False
    t1, t2 = pair

    # U_cross: 6 cross-family paired-tree relational tasks
    if task_name == "u1_leaves_mod4_rel":
        return (tree_leaves(t1) % 4) == (tree_leaves(t2) % 4)
    if task_name == "u2_rootdeg_eq_and_deep":
        return (tree_root_deg(t1) == tree_root_deg(t2)) and (tree_max_depth(t1) >= 3)
    if task_name == "u3_bipartite_diff_rel":
        return tree_bipartite_diff(t1) == tree_bipartite_diff(t2)
    if task_name == "u4_branching_mod3_rel":
        return (tree_branching_nodes(t1) % 3) == (tree_branching_nodes(t2) % 3)
    if task_name == "u5_depth_parity_and_motzkin":
        return (
            (tree_max_depth(t1) % 2 == tree_max_depth(t2) % 2)
            and (tree_max_outdeg(t1) <= 2)
            and (tree_max_outdeg(t2) <= 2)
        )
    if task_name == "u6_max_depth_eq":
        return tree_max_depth(t1) == tree_max_depth(t2)

    # L_surface: 3 flat/surface compositional tasks
    if task_name == "l1_starts_aaa_ends_abb":
        return word.startswith("aaa") and word.endswith("abb")
    if task_name == "l2_total_a_mod4_eq0":
        return word.count("a") % 4 == 0
    if task_name == "l3_starts_aab_even_a":
        return word.startswith("aab") and (word.count("a") % 2 == 0)

    # N_abstain: 3 unbounded/order-sensitive non-expressible relational tasks
    if task_name == "n1_ordered_tree_identity":
        return t1 == t2
    if task_name == "n2_mirror_tree_duality":
        return t2 == tree_mirror(t1)
    if task_name == "n3_ordered_leaf_hash_eq":
        return tree_ordered_leaf_hash_mod5(t1) == tree_ordered_leaf_hash_mod5(t2)

    raise ValueError(f"unknown nominal target task: {task_name}")


DRIFT_BASE_MAP: dict[str, str] = {
    "d1_leaves_mod4_late_invert": "u1_leaves_mod4_rel",
    "d2_bipartite_late_invert": "u3_bipartite_diff_rel",
    "d3_surface_late_invert": "l1_starts_aaa_ends_abb",
}


def eval_target_split_truth(task_name: str, word: str, is_terminal: bool) -> bool:
    """Evaluate target truth; `D_drift` tasks invert truth strictly on terminal split."""
    if task_name in DRIFT_BASE_MAP:
        base_val = eval_nominal_target_task(DRIFT_BASE_MAP[task_name], word)
        return (not base_val) if is_terminal else base_val
    return eval_nominal_target_task(task_name, word)


def score_terminal_predictions(
    predict_fn: Callable[[str], bool],
    terminal_rows: list[tuple[str, bool]],
) -> dict[str, object]:
    """Evaluate a frozen prediction callable on a held-out terminal bank."""
    preds = [bool(predict_fn(w)) for w, _ in terminal_rows]
    correct = sum(1 for p, (_, y) in zip(preds, terminal_rows) if p == y)
    return {
        "predictions": preds,
        "terminal_correct": correct,
        "terminal_total": len(terminal_rows),
        "terminal_accuracy": round(correct / len(terminal_rows), 6),
    }
