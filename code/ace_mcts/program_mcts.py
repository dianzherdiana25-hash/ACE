"""Monte Carlo Tree Search (MCTS) over Strongly-Typed Program ASTs.

Explores program spaces using UCT (Upper Confidence bound for Trees), balancing
exploration of untested AST branches with exploitation of high-accuracy primitives.
"""
from __future__ import annotations

import copy
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from ace_evolution.island_search import TypedASTNode, ProgramCandidate


class MCTSNode:
    """A search tree node representing a partial or complete program AST."""

    def __init__(
        self,
        ast_node: TypedASTNode,
        parent: Optional[MCTSNode] = None,
        action: str = "",
    ):
        self.ast_node = ast_node
        self.parent = parent
        self.action = action
        self.children: List[MCTSNode] = []
        self.visits: int = 0
        self.total_reward: float = 0.0

    @property
    def value(self) -> float:
        return self.total_reward / self.visits if self.visits > 0 else 0.0

    def uct(self, exploration_weight: float = 1.414) -> float:
        if self.visits == 0:
            return float("inf")
        parent_visits = self.parent.visits if self.parent else self.visits
        return self.value + exploration_weight * math.sqrt(math.log(parent_visits) / self.visits)


class MCTSProgramSearch:
    """MCTS engine for guided program exploration."""

    TERMINAL_INT_OPS = ["count_a", "count_b", "len", "const_0", "const_1", "const_2", "const_4"]
    TERMINAL_BOOL_OPS = ["starts_a", "ends_b", "contains_ab", "graph_bfs"]
    COMPOUND_INT_OPS = ["add", "sub", "mul", "mod"]
    COMPOUND_BOOL_OPS = ["eq", "neq", "lte", "gte", "and", "or", "not"]

    def __init__(
        self,
        exploration_weight: float = 1.414,
        max_simulations: int = 60,
        max_depth: int = 3,
        seed: int = 42,
    ):
        self.exploration_weight = exploration_weight
        self.max_simulations = max_simulations
        self.max_depth = max_depth
        self.rng = random.Random(seed)

    def _create_node_from_action(self, action: str) -> TypedASTNode:
        if action == "count_a":
            return TypedASTNode("count_a", "INT")
        elif action == "count_b":
            return TypedASTNode("count_b", "INT")
        elif action == "len":
            return TypedASTNode("len", "INT")
        elif action.startswith("const_"):
            val = int(action.split("_")[1])
            return TypedASTNode("int_const", "INT", val=val)
        elif action == "starts_a":
            return TypedASTNode("starts_with", "BOOL", val="a")
        elif action == "ends_b":
            return TypedASTNode("ends_with", "BOOL", val="b")
        elif action == "contains_ab":
            return TypedASTNode("contains", "BOOL", val="ab")
        elif action == "graph_bfs":
            return TypedASTNode("graph_bfs", "BOOL")
        elif action in self.COMPOUND_INT_OPS:
            left = TypedASTNode("count_a", "INT")
            right = TypedASTNode("count_b", "INT")
            return TypedASTNode(action, "INT", children=[left, right])
        elif action in ("eq", "neq", "lte", "gte"):
            left = TypedASTNode("count_a", "INT")
            right = TypedASTNode("count_b", "INT")
            return TypedASTNode(action, "BOOL", children=[left, right])
        elif action == "not":
            child = TypedASTNode("starts_with", "BOOL", val="a")
            return TypedASTNode("not", "BOOL", children=[child])
        else:  # and / or
            left = TypedASTNode("starts_with", "BOOL", val="a")
            right = TypedASTNode("ends_with", "BOOL", val="b")
            return TypedASTNode(action, "BOOL", children=[left, right])

    def search(
        self,
        train_data: List[Tuple[str, bool]],
        target_accuracy: float = 1.0,
    ) -> ProgramCandidate:
        """Executes MCTS simulations and returns the highest-reward program."""
        # Root node: default True predicate
        root_ast = TypedASTNode("bool_const", "BOOL", val=True)
        root = MCTSNode(root_ast)

        # Initial actions
        candidate_actions = (
            self.TERMINAL_BOOL_OPS
            + ["eq", "neq", "lte", "gte", "and", "or", "not"]
        )

        best_candidate: Optional[ProgramCandidate] = None
        best_score = -1.0

        for sim in range(self.max_simulations):
            # 1. Selection
            node = root
            while node.children:
                node = max(node.children, key=lambda c: c.uct(self.exploration_weight))

            # 2. Expansion
            if not node.children and node.visits > 0 and len(candidate_actions) > len(node.children):
                untried_actions = [a for a in candidate_actions if a not in [c.action for c in node.children]]
                if untried_actions:
                    chosen_action = self.rng.choice(untried_actions)
                    child_ast = self._create_node_from_action(chosen_action)
                    child_node = MCTSNode(child_ast, parent=node, action=chosen_action)
                    node.children.append(child_node)
                    node = child_node

            # 3. Simulation / Evaluation
            candidate = ProgramCandidate(node.ast_node)
            acc = candidate.evaluate_dataset(train_data)
            reward = candidate.score

            if reward > best_score:
                best_score = reward
                best_candidate = candidate

            if acc >= target_accuracy:
                return candidate

            # 4. Backpropagation
            curr: Optional[MCTSNode] = node
            while curr is not None:
                curr.visits += 1
                curr.total_reward += reward
                curr = curr.parent

        return best_candidate if best_candidate else ProgramCandidate(root_ast)
