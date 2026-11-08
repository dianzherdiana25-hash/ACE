"""ACE Multi-Objective Pareto DSL Optimizer (NSGA-II).

Optimizes candidate program grammar weights and program ASTs balancing:
1. Accuracy: classification accuracy on input task distributions.
2. Parsimony: structural simplicity measured by AST node count.
3. Evaluation Latency: execution runtime and computational cost.

Implements Deb et al.'s fast non-dominated sorting and crowding distance assignment,
providing Pareto frontier analysis, hypervolume calculation, and multi-stage curriculum transfer.
"""
from __future__ import annotations

import copy
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from ace_evolution.island_search import ProgramCandidate, TypedASTNode


@dataclass(frozen=True)
class Objectives:
    """Multi-objective evaluation metrics for Pareto dominance."""

    accuracy: float       # Maximize: [0.0, 1.0]
    parsimony: float      # Minimize: AST node count (>= 1.0)
    latency: float        # Minimize: execution runtime in seconds (>= 0.0)

    def dominates(self, other: Objectives) -> bool:
        """Determines whether self Pareto-dominates other.

        self dominates other iff:
        1. self is no worse than other in all three objectives.
        2. self is strictly better than other in at least one objective.
        """
        no_worse = (
            self.accuracy >= other.accuracy
            and self.parsimony <= other.parsimony
            and self.latency <= other.latency
        )
        strictly_better = (
            self.accuracy > other.accuracy
            or self.parsimony < other.parsimony
            or self.latency < other.latency
        )
        return bool(no_worse and strictly_better)

    def to_dict(self) -> Dict[str, float]:
        return {
            "accuracy": round(self.accuracy, 6),
            "parsimony": round(self.parsimony, 4),
            "latency": round(self.latency, 8),
        }


@dataclass
class MacroPrimitive:
    """A modular macro primitive / sub-routine induced for hierarchical program synthesis."""

    name: str
    return_type: str  # 'INT' or 'BOOL'
    ast: TypedASTNode
    description: str = ""

    def to_node(self) -> TypedASTNode:
        return TypedASTNode(self.name, self.return_type, val=self.ast)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "return_type": self.return_type,
            "description": self.description,
            "code": self.ast.to_code(),
            "size": self.ast.size(),
            "depth": self.ast.depth(),
        }


class DSLGrammarWeights:
    """Configurable probability weights for DSL grammar production rules.

    Categorizes operators into:
    - terminal_int: integer terminals (count_a, count_b, len, int_const)
    - compound_int: integer compound operations (add, sub, mul, mod)
    - terminal_bool: boolean terminals (starts_with, ends_with, contains, graph_bfs, bool_const)
    - compound_bool_cmp: comparison operations (eq, neq, lte, gte)
    - compound_bool_logic: boolean logical operations (and, or, not)
    - structural: structural branching probabilities (terminal_prob, bool_cmp_prob)
    """

    DEFAULT_TERMINAL_INT: Dict[str, float] = {
        "count_a": 1.0,
        "count_b": 1.0,
        "len": 1.0,
        "int_const": 1.0,
    }
    DEFAULT_COMPOUND_INT: Dict[str, float] = {
        "add": 1.0,
        "sub": 1.0,
        "mul": 1.0,
        "mod": 1.0,
    }
    DEFAULT_TERMINAL_BOOL: Dict[str, float] = {
        "starts_with": 1.0,
        "ends_with": 1.0,
        "contains": 1.0,
        "graph_bfs": 0.5,
        "dyck_balanced": 0.5,
        "bool_const": 0.5,
    }
    DEFAULT_COMPOUND_BOOL_CMP: Dict[str, float] = {
        "eq": 1.0,
        "neq": 1.0,
        "lte": 1.0,
        "gte": 1.0,
    }
    DEFAULT_COMPOUND_BOOL_LOGIC: Dict[str, float] = {
        "and": 1.0,
        "or": 1.0,
        "not": 1.0,
    }
    DEFAULT_STRUCTURAL: Dict[str, float] = {
        "terminal_prob": 0.35,
        "bool_cmp_prob": 0.5,
    }

    def __init__(
        self,
        terminal_int: Optional[Dict[str, float]] = None,
        compound_int: Optional[Dict[str, float]] = None,
        terminal_bool: Optional[Dict[str, float]] = None,
        compound_bool_cmp: Optional[Dict[str, float]] = None,
        compound_bool_logic: Optional[Dict[str, float]] = None,
        structural: Optional[Dict[str, float]] = None,
        macros: Optional[Dict[str, MacroPrimitive]] = None,
    ):
        self.terminal_int = dict(terminal_int or self.DEFAULT_TERMINAL_INT)
        self.compound_int = dict(compound_int or self.DEFAULT_COMPOUND_INT)
        self.terminal_bool = dict(terminal_bool or self.DEFAULT_TERMINAL_BOOL)
        self.compound_bool_cmp = dict(compound_bool_cmp or self.DEFAULT_COMPOUND_BOOL_CMP)
        self.compound_bool_logic = dict(compound_bool_logic or self.DEFAULT_COMPOUND_BOOL_LOGIC)
        self.structural = dict(structural or self.DEFAULT_STRUCTURAL)
        self.macros: Dict[str, MacroPrimitive] = dict(macros or {})
        for name, macro in self.macros.items():
            if macro.return_type == "INT" and name not in self.terminal_int:
                self.terminal_int[name] = 2.0
            elif macro.return_type == "BOOL" and name not in self.terminal_bool:
                self.terminal_bool[name] = 2.0
        self.normalize()

    def register_macro(self, macro: MacroPrimitive, weight: float = 2.0) -> None:
        """Registers a modular macro primitive into the hierarchical grammar."""
        self.macros[macro.name] = macro
        if macro.return_type == "INT":
            self.terminal_int[macro.name] = weight
        else:
            self.terminal_bool[macro.name] = weight
        self.normalize()

    def normalize(self) -> DSLGrammarWeights:
        """Ensures all weights are strictly positive and categories are valid."""
        min_weight = 0.001
        for category in (
            self.terminal_int,
            self.compound_int,
            self.terminal_bool,
            self.compound_bool_cmp,
            self.compound_bool_logic,
        ):
            for k in category:
                if category[k] < min_weight or math.isnan(category[k]):
                    category[k] = min_weight

        # Normalize structural probabilities to [0.05, 0.95]
        for k in self.structural:
            v = self.structural[k]
            if math.isnan(v):
                v = 0.5
            self.structural[k] = max(0.05, min(0.95, v))
        return self

    def sample_op(self, category_name: str, rng: random.Random) -> str:
        """Samples an operator key according to category weights."""
        cat_map: Dict[str, Dict[str, float]] = {
            "terminal_int": self.terminal_int,
            "compound_int": self.compound_int,
            "terminal_bool": self.terminal_bool,
            "compound_bool_cmp": self.compound_bool_cmp,
            "compound_bool_logic": self.compound_bool_logic,
        }
        category = cat_map[category_name]
        ops = list(category.keys())
        weights = [category[op] for op in ops]
        return rng.choices(ops, weights=weights, k=1)[0]

    def to_vector(self) -> List[float]:
        """Flattens all grammar weights into an ordered numerical vector."""
        vec: List[float] = []
        for cat in (
            self.terminal_int,
            self.compound_int,
            self.terminal_bool,
            self.compound_bool_cmp,
            self.compound_bool_logic,
            self.structural,
        ):
            for k in sorted(cat.keys()):
                vec.append(cat[k])
        return vec

    @classmethod
    def from_vector(cls, vec: List[float]) -> DSLGrammarWeights:
        """Reconstructs DSLGrammarWeights from an ordered numerical vector."""
        idx = 0

        def _unpack(template: Dict[str, float]) -> Dict[str, float]:
            nonlocal idx
            res = {}
            for k in sorted(template.keys()):
                res[k] = vec[idx] if idx < len(vec) else template[k]
                idx += 1
            return res

        return cls(
            terminal_int=_unpack(cls.DEFAULT_TERMINAL_INT),
            compound_int=_unpack(cls.DEFAULT_COMPOUND_INT),
            terminal_bool=_unpack(cls.DEFAULT_TERMINAL_BOOL),
            compound_bool_cmp=_unpack(cls.DEFAULT_COMPOUND_BOOL_CMP),
            compound_bool_logic=_unpack(cls.DEFAULT_COMPOUND_BOOL_LOGIC),
            structural=_unpack(cls.DEFAULT_STRUCTURAL),
        )

    def mutate(self, rng: random.Random, rate: float = 0.25, scale: float = 0.3) -> DSLGrammarWeights:
        """Applies multiplicative and additive mutations to grammar weights."""
        mutated = copy.deepcopy(self)
        for cat in (
            mutated.terminal_int,
            mutated.compound_int,
            mutated.terminal_bool,
            mutated.compound_bool_cmp,
            mutated.compound_bool_logic,
        ):
            for k in cat:
                if rng.random() < rate:
                    factor = math.exp(rng.gauss(0.0, scale))
                    cat[k] = max(0.001, cat[k] * factor)

        for k in mutated.structural:
            if rng.random() < rate:
                delta = rng.gauss(0.0, scale * 0.5)
                mutated.structural[k] = max(0.05, min(0.95, mutated.structural[k] + delta))

        return mutated.normalize()

    def crossover(
        self, other: DSLGrammarWeights, rng: random.Random, alpha: float = 0.5
    ) -> DSLGrammarWeights:
        """Blend crossover (BLX-alpha) between two grammar weight configurations."""
        v1 = self.to_vector()
        v2 = other.to_vector()
        child_vec: List[float] = []
        for x1, x2 in zip(v1, v2):
            low = min(x1, x2)
            high = max(x1, x2)
            diff = high - low
            val = rng.uniform(low - alpha * diff, high + alpha * diff)
            child_vec.append(max(0.001, val))
        child = DSLGrammarWeights.from_vector(child_vec)
        return child.normalize()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "terminal_int": {k: round(v, 4) for k, v in self.terminal_int.items()},
            "compound_int": {k: round(v, 4) for k, v in self.compound_int.items()},
            "terminal_bool": {k: round(v, 4) for k, v in self.terminal_bool.items()},
            "compound_bool_cmp": {k: round(v, 4) for k, v in self.compound_bool_cmp.items()},
            "compound_bool_logic": {k: round(v, 4) for k, v in self.compound_bool_logic.items()},
            "structural": {k: round(v, 4) for k, v in self.structural.items()},
        }


class WeightedASTGenerator:
    """Generates TypedASTNode instances guided by a DSLGrammarWeights distribution."""

    def __init__(self, grammar: DSLGrammarWeights):
        self.grammar = grammar

    def generate(
        self,
        target_type: str = "BOOL",
        depth: int = 1,
        max_depth: int = 3,
        rng: Optional[random.Random] = None,
    ) -> TypedASTNode:
        """Generates a type-safe AST node using weighted grammar sampling."""
        rand = rng or random.Random()
        is_terminal = (depth >= max_depth) or (
            depth > 1 and rand.random() < self.grammar.structural.get("terminal_prob", 0.35)
        )

        if is_terminal:
            if target_type == "INT":
                op = self.grammar.sample_op("terminal_int", rand)
                if op in self.grammar.macros:
                    macro = self.grammar.macros[op]
                    return TypedASTNode(op, "INT", val=macro.ast)
                elif op == "int_const":
                    val = rand.choice([0, 1, 2, 3, 4])
                    return TypedASTNode("int_const", "INT", val=val)
                return TypedASTNode(op, "INT")
            else:  # BOOL
                op = self.grammar.sample_op("terminal_bool", rand)
                if op in self.grammar.macros:
                    macro = self.grammar.macros[op]
                    return TypedASTNode(op, "BOOL", val=macro.ast)
                elif op == "starts_with":
                    return TypedASTNode("starts_with", "BOOL", val=rand.choice(["a", "b"]))
                elif op == "ends_with":
                    return TypedASTNode("ends_with", "BOOL", val=rand.choice(["a", "b"]))
                elif op == "contains":
                    return TypedASTNode("contains", "BOOL", val=rand.choice(["ab", "ba", "aa", "bb"]))
                elif op == "bool_const":
                    return TypedASTNode("bool_const", "BOOL", val=rand.choice([True, False]))
                elif op == "graph_bfs":
                    return TypedASTNode("graph_bfs", "BOOL")
                elif op == "dyck_balanced":
                    return TypedASTNode("dyck_balanced", "BOOL")
                return TypedASTNode("bool_const", "BOOL", val=True)

        # Compound / Non-terminal
        if target_type == "INT":
            op = self.grammar.sample_op("compound_int", rand)
            left = self.generate("INT", depth + 1, max_depth, rand)
            right = self.generate("INT", depth + 1, max_depth, rand)
            return TypedASTNode(op, "INT", children=[left, right])
        else:  # BOOL
            is_cmp = rand.random() < self.grammar.structural.get("bool_cmp_prob", 0.5)
            if is_cmp:
                op = self.grammar.sample_op("compound_bool_cmp", rand)
                left = self.generate("INT", depth + 1, max_depth, rand)
                right = self.generate("INT", depth + 1, max_depth, rand)
                return TypedASTNode(op, "BOOL", children=[left, right])
            else:
                op = self.grammar.sample_op("compound_bool_logic", rand)
                if op == "not":
                    child = self.generate("BOOL", depth + 1, max_depth, rand)
                    return TypedASTNode("not", "BOOL", children=[child])
                else:
                    left = self.generate("BOOL", depth + 1, max_depth, rand)
                    right = self.generate("BOOL", depth + 1, max_depth, rand)
                    return TypedASTNode(op, "BOOL", children=[left, right])


class HierarchicalSubGrammar:
    """Manages multi-layer hierarchical grammar induction and modular macros."""

    def __init__(self, base_grammar: Optional[DSLGrammarWeights] = None):
        self.grammar = base_grammar or DSLGrammarWeights()

    def induce_macro_from_ast(
        self, name: str, ast: TypedASTNode, description: str = "", weight: float = 2.5
    ) -> MacroPrimitive:
        """Induces a modular macro primitive from an evolved AST subtree."""
        macro = MacroPrimitive(
            name=name,
            return_type=ast.return_type,
            ast=copy.deepcopy(ast),
            description=description or f"Induced macro from AST: {ast.to_code()}",
        )
        self.grammar.register_macro(macro, weight=weight)
        return macro

    def induce_from_pareto_front(
        self, pareto_front: List[Any], prefix: str = "macro_layer1"
    ) -> List[MacroPrimitive]:
        """Extracts top non-dominated subtrees as reusable macro primitives."""
        induced: List[MacroPrimitive] = []
        seen_codes: Set[str] = set()
        for cand in pareto_front:
            ast = None
            if hasattr(cand, "best_program") and cand.best_program:
                ast = cand.best_program.root
            elif hasattr(cand, "root"):
                ast = cand.root

            if ast and ast.depth() >= 2:
                code = ast.to_code()
                if code not in seen_codes:
                    seen_codes.add(code)
                    macro_name = f"{prefix}_{len(induced)}"
                    macro = self.induce_macro_from_ast(macro_name, ast, description=code)
                    induced.append(macro)
        return induced


@dataclass
class SelfRefiningResult:
    """Outcomes from bounded-budget self-refining program synthesis."""

    candidate: Any
    refinement_steps: int
    budget_used: int
    counterexamples_resolved: int
    history: List[Dict[str, Any]] = field(default_factory=list)


class SelfRefiningProgramSynthesizer:
    """Self-refining multi-goal program synthesizer with bounded resource allocation.

    Iteratively diagnoses counter-examples (false positives & false negatives) on task
    specifications, spending bounded expansion budgets to repair AST nodes or conjoin guards.
    """

    def __init__(
        self,
        grammar: Optional[DSLGrammarWeights] = None,
        resource_budget: int = 40,
        max_depth: int = 4,
        seed: int = 42,
    ):
        self.grammar = grammar or DSLGrammarWeights()
        self.resource_budget = resource_budget
        self.max_depth = max_depth
        self.rng = random.Random(seed)
        self.generator = WeightedASTGenerator(self.grammar)

    def synthesize_and_refine(
        self,
        dataset: List[Tuple[str, bool]],
        deterministic_latency: bool = True,
    ) -> SelfRefiningResult:
        """Executes self-refining synthesis on dataset within allocated resource budget."""
        root = self.generator.generate("BOOL", depth=1, max_depth=self.max_depth, rng=self.rng)
        cand = ProgramParetoCandidate(root)
        cand.evaluate(dataset, deterministic_latency=deterministic_latency)

        budget_remaining = self.resource_budget
        steps = 0
        resolved_count = 0
        history: List[Dict[str, Any]] = []

        best_cand = copy.deepcopy(cand)

        while budget_remaining > 0 and best_cand.objectives.accuracy < 1.0:
            steps += 1
            budget_remaining -= 1

            fps: List[str] = []
            fns: List[str] = []
            for i, (word, lbl) in enumerate(dataset):
                pred = best_cand.predictions[i]
                if pred and not lbl:
                    fps.append(word)
                elif not pred and lbl:
                    fns.append(word)

            prev_acc = best_cand.objectives.accuracy

            # Propose candidate refinement
            proposal_root = copy.deepcopy(best_cand.root)
            if fps and self.rng.random() < 0.6:
                # Too permissive: conjoin a discriminative guard
                guard = self.generator.generate("BOOL", depth=1, max_depth=2, rng=self.rng)
                proposal_root = TypedASTNode("and", "BOOL", children=[proposal_root, guard])
            elif fns and self.rng.random() < 0.6:
                # Too restrictive: disjoin with a fallback predicate
                patch = self.generator.generate("BOOL", depth=1, max_depth=2, rng=self.rng)
                proposal_root = TypedASTNode("or", "BOOL", children=[proposal_root, patch])
            else:
                # Subtree mutation
                subtrees = [proposal_root]
                for c in proposal_root.children:
                    subtrees.append(c)
                target = self.rng.choice(subtrees)
                new_sub = self.generator.generate(
                    target.return_type, depth=target.depth(), max_depth=target.depth() + 2, rng=self.rng
                )
                target.op = new_sub.op
                target.return_type = new_sub.return_type
                target.children = new_sub.children
                target.val = new_sub.val

            proposal = ProgramParetoCandidate(proposal_root)
            proposal.evaluate(dataset, deterministic_latency=deterministic_latency)

            # Accept if Pareto improved or higher accuracy
            if proposal.objectives.accuracy > best_cand.objectives.accuracy or (
                proposal.objectives.accuracy == best_cand.objectives.accuracy
                and proposal.objectives.parsimony < best_cand.objectives.parsimony
            ):
                resolved_count += max(0, int((proposal.objectives.accuracy - prev_acc) * len(dataset)))
                best_cand = proposal

            history.append({
                "step": steps,
                "budget_remaining": budget_remaining,
                "accuracy": round(best_cand.objectives.accuracy, 4),
                "parsimony": best_cand.objectives.parsimony,
                "latency": round(best_cand.objectives.latency, 8),
            })

        return SelfRefiningResult(
            candidate=best_cand,
            refinement_steps=steps,
            budget_used=self.resource_budget - budget_remaining,
            counterexamples_resolved=resolved_count,
            history=history,
        )


class GrammarCandidate:
    """Candidate individual in grammar space evaluated on sample program synthesis."""

    def __init__(self, weights: DSLGrammarWeights):
        self.weights = weights
        self.objectives = Objectives(0.0, 1.0, 0.0)
        self.rank: int = -1
        self.crowding_distance: float = 0.0
        self.best_program: Optional[ProgramCandidate] = None
        self.sampled_programs: List[ProgramCandidate] = []

    def evaluate(
        self,
        dataset: List[Tuple[str, bool]],
        samples: int = 8,
        max_depth: int = 3,
        rng: Optional[random.Random] = None,
        deterministic_latency: bool = False,
    ) -> Objectives:
        """Evaluates grammar weights by sampling programs and computing trade-off objectives."""
        rand = rng or random.Random()
        generator = WeightedASTGenerator(self.weights)
        self.sampled_programs = []

        total_latency = 0.0
        best_acc = 0.0
        best_prog = None
        sizes: List[int] = []

        for _ in range(samples):
            root = generator.generate("BOOL", depth=1, max_depth=max_depth, rng=rand)
            cand = ProgramCandidate(root)

            t0 = time.perf_counter()
            acc = cand.evaluate_dataset(dataset)
            elapsed = time.perf_counter() - t0

            if deterministic_latency:
                # Analytical model for deterministic latency testing
                simulated_time = 1e-6 * (cand.root.size() * len(dataset) + (10 if "graph_bfs" in cand.root.to_code() else 1))
                total_latency += simulated_time
            else:
                total_latency += elapsed

            sz = cand.root.size()
            sizes.append(sz)
            self.sampled_programs.append(cand)

            if acc > best_acc or best_prog is None or (acc == best_acc and sz < best_prog.root.size()):
                best_acc = acc
                best_prog = cand

        self.best_program = best_prog
        mean_parsimony = float(sum(sizes) / len(sizes)) if sizes else 1.0
        mean_latency = total_latency / max(1, samples)

        self.objectives = Objectives(
            accuracy=best_acc,
            parsimony=mean_parsimony,
            latency=mean_latency,
        )
        return self.objectives


class ProgramParetoCandidate:
    """Individual program candidate evaluated directly along multi-objective Pareto dimensions."""

    def __init__(self, root: TypedASTNode):
        self.root = root
        self.objectives = Objectives(0.0, float(root.size()), 0.0)
        self.rank: int = -1
        self.crowding_distance: float = 0.0
        self.predictions: List[bool] = []

    def evaluate(
        self,
        dataset: List[Tuple[str, bool]],
        deterministic_latency: bool = False,
    ) -> Objectives:
        """Evaluates program accuracy, parsimony (AST size), and execution latency."""
        self.predictions = []
        correct = 0

        t0 = time.perf_counter()
        for word, label in dataset:
            try:
                pred = bool(self.root.evaluate(word))
            except Exception:
                pred = False
            self.predictions.append(pred)
            if pred == label:
                correct += 1
        elapsed = time.perf_counter() - t0

        acc = correct / len(dataset) if dataset else 0.0
        node_count = float(self.root.size())

        if deterministic_latency:
            lat = 1e-6 * (node_count * len(dataset) + (10.0 if "graph_bfs" in self.root.to_code() else 1.0))
        else:
            lat = elapsed

        self.objectives = Objectives(
            accuracy=acc,
            parsimony=node_count,
            latency=lat,
        )
        return self.objectives


# Generic Candidate Type for NSGA-II operations
CandidateT = Union[GrammarCandidate, ProgramParetoCandidate]


def fast_non_dominated_sort(population: List[CandidateT]) -> List[List[CandidateT]]:
    """Partitions population into Pareto dominance fronts (Deb et al., 2002).

    Front 0 contains all non-dominated individuals (Pareto frontier).
    Front k contains individuals dominated only by members of Fronts 0..(k-1).
    """
    if not population:
        return []

    fronts: List[List[CandidateT]] = [[]]
    domination_counts: Dict[int, int] = {}
    dominated_sets: Dict[int, List[CandidateT]] = {}

    for p in population:
        p_id = id(p)
        p_dominated: List[CandidateT] = []
        n_p = 0

        for q in population:
            if p is q:
                continue
            if p.objectives.dominates(q.objectives):
                p_dominated.append(q)
            elif q.objectives.dominates(p.objectives):
                n_p += 1

        domination_counts[p_id] = n_p
        dominated_sets[p_id] = p_dominated

        if n_p == 0:
            p.rank = 0
            fronts[0].append(p)

    current_idx = 0
    while current_idx < len(fronts) and len(fronts[current_idx]) > 0:
        next_front: List[CandidateT] = []
        for p in fronts[current_idx]:
            for q in dominated_sets[id(p)]:
                q_id = id(q)
                domination_counts[q_id] -= 1
                if domination_counts[q_id] == 0:
                    q.rank = current_idx + 1
                    next_front.append(q)
        if next_front:
            fronts.append(next_front)
        current_idx += 1

    return fronts


def calculate_crowding_distance(front: List[CandidateT]) -> None:
    """Computes crowding distance for all individuals within a Pareto front.

    Boundary individuals in each objective receive infinite distance to preserve diversity.
    Intermediate individuals receive distance proportional to the cuboid volume formed by neighbors.
    """
    l = len(front)
    if l == 0:
        return

    for ind in front:
        ind.crowding_distance = 0.0

    if l <= 2:
        for ind in front:
            ind.crowding_distance = float("inf")
        return

    # Objective 1: Accuracy (Maximize)
    front.sort(key=lambda ind: ind.objectives.accuracy)
    front[0].crowding_distance = float("inf")
    front[-1].crowding_distance = float("inf")
    acc_range = front[-1].objectives.accuracy - front[0].objectives.accuracy
    if acc_range > 1e-9:
        for i in range(1, l - 1):
            front[i].crowding_distance += (
                front[i + 1].objectives.accuracy - front[i - 1].objectives.accuracy
            ) / acc_range

    # Objective 2: Parsimony / AST Node Count (Minimize)
    front.sort(key=lambda ind: ind.objectives.parsimony)
    front[0].crowding_distance = float("inf")
    front[-1].crowding_distance = float("inf")
    par_range = front[-1].objectives.parsimony - front[0].objectives.parsimony
    if par_range > 1e-9:
        for i in range(1, l - 1):
            front[i].crowding_distance += (
                front[i + 1].objectives.parsimony - front[i - 1].objectives.parsimony
            ) / par_range

    # Objective 3: Evaluation Latency (Minimize)
    front.sort(key=lambda ind: ind.objectives.latency)
    front[0].crowding_distance = float("inf")
    front[-1].crowding_distance = float("inf")
    lat_range = front[-1].objectives.latency - front[0].objectives.latency
    if lat_range > 1e-12:
        for i in range(1, l - 1):
            front[i].crowding_distance += (
                front[i + 1].objectives.latency - front[i - 1].objectives.latency
            ) / lat_range


def crowded_comparison(a: CandidateT, b: CandidateT) -> int:
    """NSGA-II Crowded Comparison Operator (Deb et al.).

    Returns:
    -1 if a is preferred over b (better front or larger crowding distance).
     1 if b is preferred over a.
     0 if tied.
    """
    if a.rank < b.rank:
        return -1
    elif a.rank > b.rank:
        return 1

    # Same rank: prefer greater crowding distance (less crowded region)
    if a.crowding_distance > b.crowding_distance:
        return -1
    elif a.crowding_distance < b.crowding_distance:
        return 1
    return 0


def tournament_selection(population: List[CandidateT], rng: random.Random) -> CandidateT:
    """Binary tournament selection using the crowded-comparison operator."""
    cand1, cand2 = rng.sample(population, 2)
    cmp = crowded_comparison(cand1, cand2)
    if cmp < 0:
        return cand1
    elif cmp > 0:
        return cand2
    return rng.choice([cand1, cand2])


def compute_hypervolume_2d(
    front: List[CandidateT],
    ref_accuracy: float = 0.0,
    ref_parsimony: float = 50.0,
) -> float:
    """Computes 2D hypervolume indicator for accuracy (maximize) vs parsimony (minimize).

    Higher hypervolume indicates superior convergence and diversity along the frontier.
    """
    valid = [
        ind for ind in front
        if ind.objectives.accuracy >= ref_accuracy and ind.objectives.parsimony <= ref_parsimony
    ]
    if not valid:
        return 0.0

    # Sort descending by accuracy
    valid.sort(key=lambda ind: ind.objectives.accuracy, reverse=True)

    hv = 0.0
    current_min_parsimony = ref_parsimony

    for ind in valid:
        acc = ind.objectives.accuracy
        par = ind.objectives.parsimony
        if par < current_min_parsimony:
            width = acc - ref_accuracy
            height = current_min_parsimony - par
            hv += width * height
            current_min_parsimony = par

    return hv


@dataclass
class ParetoOptimizationResult:
    """Encapsulates Pareto optimization outcomes and diagnostic metrics."""

    pareto_front: List[CandidateT]
    all_fronts: List[List[CandidateT]]
    best_by_accuracy: CandidateT
    best_by_parsimony: CandidateT
    best_by_latency: CandidateT
    knee_point: CandidateT
    hypervolume_estimate: float
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pareto_front_size": len(self.pareto_front),
            "num_fronts": len(self.all_fronts),
            "hypervolume_2d": round(self.hypervolume_estimate, 4),
            "best_accuracy": self.best_by_accuracy.objectives.to_dict(),
            "best_parsimony": self.best_by_parsimony.objectives.to_dict(),
            "best_latency": self.best_by_latency.objectives.to_dict(),
            "knee_point": self.knee_point.objectives.to_dict(),
            "generations_completed": len(self.history),
        }


class ParetoDSLOptimizer:
    """Multi-Objective NSGA-II Optimizer for DSL Grammar Weights and Programs."""

    def __init__(
        self,
        population_size: int = 20,
        crossover_rate: float = 0.7,
        mutation_rate: float = 0.3,
        mutation_scale: float = 0.25,
        max_depth: int = 3,
        samples_per_grammar: int = 6,
        seed: int = 42,
        deterministic_latency: bool = False,
    ):
        self.population_size = max(4, population_size)
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.mutation_scale = mutation_scale
        self.max_depth = max_depth
        self.samples_per_grammar = samples_per_grammar
        self.rng = random.Random(seed)
        self.deterministic_latency = deterministic_latency

    def find_knee_point(self, front: List[CandidateT]) -> CandidateT:
        """Selects the knee point on the Pareto front minimizing distance to ideal point (1, min_par, min_lat)."""
        if not front:
            raise ValueError("Front cannot be empty to find knee point")
        if len(front) == 1:
            return front[0]

        min_par = min(ind.objectives.parsimony for ind in front)
        max_par = max(ind.objectives.parsimony for ind in front)
        min_lat = min(ind.objectives.latency for ind in front)
        max_lat = max(ind.objectives.latency for ind in front)

        par_span = max(1e-6, max_par - min_par)
        lat_span = max(1e-9, max_lat - min_lat)

        best_cand = front[0]
        min_dist = float("inf")

        for ind in front:
            acc_term = (1.0 - ind.objectives.accuracy) ** 2
            par_term = ((ind.objectives.parsimony - min_par) / par_span) ** 2
            lat_term = ((ind.objectives.latency - min_lat) / lat_span) ** 2
            dist = math.sqrt(acc_term + par_term + lat_term)
            if dist < min_dist:
                min_dist = dist
                best_cand = ind

        return best_cand

    def optimize_grammar_weights(
        self,
        train_data: List[Tuple[str, bool]],
        generations: int = 10,
        initial_priors: Optional[List[DSLGrammarWeights]] = None,
    ) -> ParetoOptimizationResult:
        """Runs NSGA-II evolution over DSL grammar weights."""
        # 1. Initialize population
        population: List[GrammarCandidate] = []
        if initial_priors:
            for prior in initial_priors[: self.population_size]:
                population.append(GrammarCandidate(copy.deepcopy(prior)))

        while len(population) < self.population_size:
            weights = DSLGrammarWeights().mutate(self.rng, rate=0.6, scale=0.5)
            population.append(GrammarCandidate(weights))

        # Evaluate initial population
        for ind in population:
            ind.evaluate(
                train_data,
                samples=self.samples_per_grammar,
                max_depth=self.max_depth,
                rng=self.rng,
                deterministic_latency=self.deterministic_latency,
            )

        history: List[Dict[str, Any]] = []

        # 2. Main NSGA-II generational loop
        for gen in range(generations):
            # Sort current population
            fronts = fast_non_dominated_sort(population)  # type: ignore
            for front in fronts:
                calculate_crowding_distance(front)

            # Record generation diagnostics
            p_front = fronts[0] if fronts else []
            best_acc = max((ind.objectives.accuracy for ind in population), default=0.0)
            avg_par = sum(ind.objectives.parsimony for ind in population) / len(population)
            avg_lat = sum(ind.objectives.latency for ind in population) / len(population)
            hv = compute_hypervolume_2d(p_front)  # type: ignore

            history.append({
                "generation": gen,
                "front0_size": len(p_front),
                "best_accuracy": round(best_acc, 4),
                "avg_parsimony": round(avg_par, 2),
                "avg_latency": round(avg_lat, 8),
                "hypervolume": round(hv, 4),
            })

            # Generate offspring population Q_t
            offspring_pop: List[GrammarCandidate] = []
            while len(offspring_pop) < self.population_size:
                p1 = tournament_selection(population, self.rng)  # type: ignore
                if self.rng.random() < self.crossover_rate:
                    p2 = tournament_selection(population, self.rng)  # type: ignore
                    child_weights = p1.weights.crossover(p2.weights, self.rng)
                else:
                    child_weights = copy.deepcopy(p1.weights)

                if self.rng.random() < self.mutation_rate:
                    child_weights = child_weights.mutate(
                        self.rng, rate=self.mutation_rate, scale=self.mutation_scale
                    )

                child = GrammarCandidate(child_weights)
                child.evaluate(
                    train_data,
                    samples=self.samples_per_grammar,
                    max_depth=self.max_depth,
                    rng=self.rng,
                    deterministic_latency=self.deterministic_latency,
                )
                offspring_pop.append(child)

            # Combine R_t = P_t + Q_t (size 2N)
            combined = population + offspring_pop
            combined_fronts = fast_non_dominated_sort(combined)  # type: ignore

            # Fill next generation P_{t+1}
            next_pop: List[GrammarCandidate] = []
            for front in combined_fronts:
                calculate_crowding_distance(front)
                if len(next_pop) + len(front) <= self.population_size:
                    next_pop.extend(front)  # type: ignore
                else:
                    needed = self.population_size - len(next_pop)
                    front.sort(key=lambda ind: ind.crowding_distance, reverse=True)
                    next_pop.extend(front[:needed])  # type: ignore
                    break

            population = next_pop

        # Final non-dominated sort and crowding distance assignment
        final_fronts = fast_non_dominated_sort(population)  # type: ignore
        for front in final_fronts:
            calculate_crowding_distance(front)

        pareto_front = final_fronts[0]
        best_acc_cand = max(pareto_front, key=lambda ind: ind.objectives.accuracy)
        best_par_cand = min(pareto_front, key=lambda ind: ind.objectives.parsimony)
        best_lat_cand = min(pareto_front, key=lambda ind: ind.objectives.latency)
        knee = self.find_knee_point(pareto_front)
        final_hv = compute_hypervolume_2d(pareto_front)

        return ParetoOptimizationResult(
            pareto_front=pareto_front,
            all_fronts=final_fronts,
            best_by_accuracy=best_acc_cand,
            best_by_parsimony=best_par_cand,
            best_by_latency=best_lat_cand,
            knee_point=knee,
            hypervolume_estimate=final_hv,
            history=history,
        )

    def optimize_programs(
        self,
        train_data: List[Tuple[str, bool]],
        grammar: Optional[DSLGrammarWeights] = None,
        generations: int = 10,
    ) -> ParetoOptimizationResult:
        """Runs NSGA-II directly over typed program ASTs using grammar-directed operators."""
        active_grammar = grammar or DSLGrammarWeights()
        generator = WeightedASTGenerator(active_grammar)

        # 1. Initialize population of AST candidates
        population: List[ProgramParetoCandidate] = []
        for _ in range(self.population_size):
            root = generator.generate("BOOL", depth=1, max_depth=self.max_depth, rng=self.rng)
            cand = ProgramParetoCandidate(root)
            cand.evaluate(train_data, deterministic_latency=self.deterministic_latency)
            population.append(cand)

        history: List[Dict[str, Any]] = []

        for gen in range(generations):
            fronts = fast_non_dominated_sort(population)  # type: ignore
            for front in fronts:
                calculate_crowding_distance(front)

            p_front = fronts[0] if fronts else []
            best_acc = max((ind.objectives.accuracy for ind in population), default=0.0)
            avg_par = sum(ind.objectives.parsimony for ind in population) / len(population)
            avg_lat = sum(ind.objectives.latency for ind in population) / len(population)

            history.append({
                "generation": gen,
                "front0_size": len(p_front),
                "best_accuracy": round(best_acc, 4),
                "avg_parsimony": round(avg_par, 2),
                "avg_latency": round(avg_lat, 8),
                "hypervolume": round(compute_hypervolume_2d(p_front), 4),  # type: ignore
            })

            # Create offspring
            offspring_pop: List[ProgramParetoCandidate] = []
            while len(offspring_pop) < self.population_size:
                p1 = tournament_selection(population, self.rng)  # type: ignore
                child_root = copy.deepcopy(p1.root)

                # Mutate subtree using grammar
                if self.rng.random() < self.mutation_rate:
                    subtrees = self._get_subtrees(child_root)
                    if subtrees:
                        target = self.rng.choice(subtrees)
                        new_sub = generator.generate(
                            target.return_type,
                            depth=target.depth(),
                            max_depth=target.depth() + 2,
                            rng=self.rng,
                        )
                        target.op = new_sub.op
                        target.return_type = new_sub.return_type
                        target.children = new_sub.children
                        target.val = new_sub.val

                child = ProgramParetoCandidate(child_root)
                child.evaluate(train_data, deterministic_latency=self.deterministic_latency)
                offspring_pop.append(child)

            combined = population + offspring_pop
            combined_fronts = fast_non_dominated_sort(combined)  # type: ignore

            next_pop: List[ProgramParetoCandidate] = []
            for front in combined_fronts:
                calculate_crowding_distance(front)
                if len(next_pop) + len(front) <= self.population_size:
                    next_pop.extend(front)  # type: ignore
                else:
                    needed = self.population_size - len(next_pop)
                    front.sort(key=lambda ind: ind.crowding_distance, reverse=True)
                    next_pop.extend(front[:needed])  # type: ignore
                    break
            population = next_pop

        final_fronts = fast_non_dominated_sort(population)  # type: ignore
        for front in final_fronts:
            calculate_crowding_distance(front)

        pareto_front = final_fronts[0]
        best_acc_cand = max(pareto_front, key=lambda ind: ind.objectives.accuracy)
        best_par_cand = min(pareto_front, key=lambda ind: ind.objectives.parsimony)
        best_lat_cand = min(pareto_front, key=lambda ind: ind.objectives.latency)
        knee = self.find_knee_point(pareto_front)
        final_hv = compute_hypervolume_2d(pareto_front)

        return ParetoOptimizationResult(
            pareto_front=pareto_front,
            all_fronts=final_fronts,
            best_by_accuracy=best_acc_cand,
            best_by_parsimony=best_par_cand,
            best_by_latency=best_lat_cand,
            knee_point=knee,
            hypervolume_estimate=final_hv,
            history=history,
        )

    def _get_subtrees(self, node: TypedASTNode) -> List[TypedASTNode]:
        nodes = [node]
        for c in node.children:
            nodes.extend(self._get_subtrees(c))
        return nodes

    def self_refining_universal_synthesis(
        self,
        dataset: List[Tuple[str, bool]],
        grammar: Optional[DSLGrammarWeights] = None,
        budget: int = 50,
        generations: int = 6,
    ) -> ParetoOptimizationResult:
        """Executes universal multi-goal self-refining synthesis combining NSGA-II and active counter-example refinement."""
        active_grammar = grammar or DSLGrammarWeights()
        synthesizer = SelfRefiningProgramSynthesizer(
            grammar=active_grammar,
            resource_budget=budget,
            max_depth=self.max_depth,
            seed=self.rng.randint(1, 100000),
        )

        # 1. Run base program NSGA-II
        base_result = self.optimize_programs(dataset, grammar=active_grammar, generations=generations)

        # 2. Refine Pareto front candidates using counterexample repair
        refined_population: List[CandidateT] = []
        for cand in base_result.pareto_front:
            refined_res = synthesizer.synthesize_and_refine(dataset, deterministic_latency=self.deterministic_latency)
            refined_population.append(refined_res.candidate)
            refined_population.append(cand)

        # 3. Non-dominated sort of refined frontier
        fronts = fast_non_dominated_sort(refined_population)
        for front in fronts:
            calculate_crowding_distance(front)

        pareto_front = fronts[0]
        best_acc = max(pareto_front, key=lambda ind: ind.objectives.accuracy)
        best_par = min(pareto_front, key=lambda ind: ind.objectives.parsimony)
        best_lat = min(pareto_front, key=lambda ind: ind.objectives.latency)
        knee = self.find_knee_point(pareto_front)
        hv = compute_hypervolume_2d(pareto_front)

        return ParetoOptimizationResult(
            pareto_front=pareto_front,
            all_fronts=fronts,
            best_by_accuracy=best_acc,
            best_by_parsimony=best_par,
            best_by_latency=best_lat,
            knee_point=knee,
            hypervolume_estimate=hv,
            history=base_result.history,
        )


@dataclass
class CurriculumStage:
    """A stage in the progressive optimization curriculum."""

    stage_id: str
    name: str
    description: str
    level: int
    train_data: List[Tuple[str, bool]]
    val_data: List[Tuple[str, bool]]
    target_accuracy: float = 1.0


class OptimizationCurriculum:
    """Manages sequential curriculum stages and cross-stage grammar transfer."""

    def __init__(self):
        self.stages: List[CurriculumStage] = self._build_curriculum_stages()

    def _build_curriculum_stages(self) -> List[CurriculumStage]:
        # Stage 0: Prefix / Suffix Terminal Rules (Level 0)
        train_s0 = [
            ("a", True), ("ab", True), ("aab", True), ("aba", True),
            ("b", False), ("ba", False), ("bb", False), ("bab", False),
        ]
        val_s0 = [
            ("aa", True), ("abb", True), ("bba", False), ("bbb", False),
        ]

        # Stage 1: Modular Parity Counting (Level 1: a % 2 == 0)
        train_s1 = [
            ("", True), ("aa", True), ("baab", True), ("b", True), ("bb", True),
            ("a", False), ("aba", True), ("aaa", False), ("baa", True), ("aab", False),
        ]
        val_s1 = [
            ("baba", True), ("aaaa", True), ("aabaa", False), ("ba", False),
        ]

        # Stage 2: Substring & Combinational Logic (Level 2: "ab" in word and "ba" in word)
        train_s2 = [
            ("aba", True), ("baba", True), ("abab", True), ("aaba", True),
            ("a", False), ("b", False), ("aa", False), ("bb", False), ("ba", False), ("ab", False),
        ]
        val_s2 = [
            ("abba", True), ("baab", True), ("aaa", False), ("bbb", False),
        ]

        # Stage 3: Compositional Multi-Property Synthesis (Level 3: starts_with('a') and (count_b >= 1))
        train_s3 = [
            ("ab", True), ("aab", True), ("aba", True), ("abb", True),
            ("a", False), ("aa", False), ("aaa", False), ("b", False), ("ba", False), ("bb", False),
        ]
        val_s3 = [
            ("aabb", True), ("abab", True), ("bba", False), ("aaaa", False),
        ]

        # Stage 4: Context-Free Dyck Balanced Bracket & Nested Invariants (Level 4)
        train_s4 = [
            ("", True), ("ab", True), ("aabb", True), ("abab", True),
            ("aababb", True), ("aaabbb", True), ("abaabb", True),
            ("ba", False), ("baba", False), ("bbaa", False), ("a", False),
            ("b", False), ("aab", False), ("abb", False), ("abba", False),
        ]
        val_s4 = [
            ("aabbaabb", True), ("ababab", True), ("aaababbb", True), ("aabbabab", True),
            ("bbbaaa", False), ("aabaabbb", False), ("baabbaab", False), ("aba", False),
        ]

        # Stage 5: Context-Sensitive Relational Structural Invariants (Level 5)
        # Invariant: Graph connectivity (GraphAdjacencyPrimitive) AND counter balance (count_a == count_b)
        train_s5 = [
            ("abbaba", True),  # connected path (0-1-2-3), balanced (3a, 3b)
            ("aaabbb", True),  # connected star (center 0), balanced (3a, 3b)
            ("baaabb", True),  # connected path, balanced (3a, 3b)
            ("ababba", True),  # connected tree, balanced (3a, 3b)
            ("bbbaaa", False), # disconnected node 0 (3a, 3b)
            ("aababb", False), # disconnected node 3 (3a, 3b)
            ("aaaaaa", False), # connected K4, unbalanced (6a, 0b)
            ("aaaaab", False), # connected, unbalanced (5a, 1b)
            ("bbbbbb", False), # disconnected, unbalanced (0a, 6b)
            ("ab", False),     # short, length < 6
        ]
        val_s5 = [
            ("abaabb", True),  # connected tree, balanced (3a, 3b)
            ("aabbab", True),  # connected path, balanced (3a, 3b)
            ("bababa", True),  # connected cycle, balanced (3a, 3b)
            ("baabba", False), # disconnected node 0 (3a, 3b)
            ("aabaab", False), # connected, unbalanced (4a, 2b)
            ("bbaabb", False), # disconnected, unbalanced (2a, 4b)
        ]

        # Stage 6: Hierarchical Sub-Grammar Program Induction (Level 6)
        train_s6 = [
            ("abbaba", True), ("aaabbb", True), ("abaabb", True),
            ("bbbaaa", False), ("aaaaaa", False), ("bbbbbb", False),
        ]
        val_s6 = [
            ("aabbab", True), ("baabba", False), ("aaaaab", False),
        ]

        # Stage 7: Cross-Domain Meta-Transfer & Generalized Structural Abstraction (Level 7)
        train_s7 = [
            ("ab", True), ("aabb", True), ("abab", True),
            ("abbaba", True), ("aaabbb", True), ("abaabb", True),
            ("ba", False), ("bbaa", False), ("aab", False),
            ("bbbaaa", False), ("baabba", False), ("aaaaaa", False), ("bbbbbb", False),
        ]
        val_s7 = [
            ("aabbab", True), ("aaaabbbb", True), ("bababa", True),
            ("bbaabb", False), ("aaaaab", False), ("aab", False),
        ]

        # Stage 8: Universal Structural Synthesis & Self-Refining Program Discovery (Level 8)
        train_s8 = [
            ("ab", True), ("aabb", True), ("abbaba", True), ("aaabbb", True),
            ("ba", False), ("bbbaaa", False), ("aaaaaa", False), ("bbbbbb", False),
        ]
        val_s8 = [
            ("abab", True), ("abaabb", True), ("baabba", False), ("bbaabb", False),
        ]

        # Stage 9: Autonomous Open-Ended Meta-Curriculum & Self-Sustaining Evolutionary Loop (Level 9)
        train_s9 = [
            ("abbaba", True), ("aaabbb", True), ("ab", True), ("aabb", True), ("abab", True),
            ("bbbaaa", False), ("baabba", False), ("aaaaaa", False), ("bbbbbb", False), ("ba", False),
        ]
        val_s9 = [
            ("aabbab", True), ("aaaabbbb", True), ("bababa", True),
            ("bbaabb", False), ("aaaaab", False), ("bbaa", False),
        ]

        return [
            CurriculumStage(
                stage_id="CURR_S0_TERMINAL",
                name="Regular Prefix Constraints",
                description="Synthesize prefix/suffix rules balancing minimal AST size and zero latency.",
                level=0,
                train_data=train_s0,
                val_data=val_s0,
            ),
            CurriculumStage(
                stage_id="CURR_S1_PARITY",
                name="Modular Parity Counting",
                description="Evolve grammar weights favoring modular integer arithmetic and parity predicates.",
                level=1,
                train_data=train_s1,
                val_data=val_s1,
            ),
            CurriculumStage(
                stage_id="CURR_S2_SUBSTRING",
                name="Combinational Substring Logic",
                description="Balance conjunction of substring and relational grammar rules.",
                level=2,
                train_data=train_s2,
                val_data=val_s2,
            ),
            CurriculumStage(
                stage_id="CURR_S3_COMPOSITIONAL",
                name="Compositional Multi-Property",
                description="Jointly synthesize compound structural and count-based predicate ASTs.",
                level=3,
                train_data=train_s3,
                val_data=val_s3,
            ),
            CurriculumStage(
                stage_id="CURR_S4_DYCK_CONTEXT_FREE",
                name="Context-Free Dyck Balanced Bracket & Nested Invariants",
                description="Evolve grammar weights to discover context-free Dyck-1 balanced bracket and nested structural invariants.",
                level=4,
                train_data=train_s4,
                val_data=val_s4,
            ),
            CurriculumStage(
                stage_id="CURR_S5_CONTEXT_SENSITIVE",
                name="Context-Sensitive Relational Invariants",
                description="Evolve grammar weights for structural multi-constraint reasoning across compositional domains.",
                level=5,
                train_data=train_s5,
                val_data=val_s5,
            ),
            CurriculumStage(
                stage_id="CURR_S6_PROGRAM_INDUCTION",
                name="Hierarchical Sub-Grammar Program Induction",
                description="Induce modular macro-primitives and multi-level AST abstractions for complex relational tasks.",
                level=6,
                train_data=train_s6,
                val_data=val_s6,
            ),
            CurriculumStage(
                stage_id="CURR_S7_CROSS_DOMAIN_TRANSFER",
                name="Cross-Domain Meta-Transfer & Generalized Structural Abstraction",
                description="Meta-transfer hierarchical macro primitives across composite multi-domain language and graph tasks.",
                level=7,
                train_data=train_s7,
                val_data=val_s7,
            ),
            CurriculumStage(
                stage_id="CURR_S8_UNIVERSAL_STRUCTURAL_SYNTHESIS",
                name="Universal Structural Synthesis & Self-Refining Program Discovery",
                description="Self-refining multi-goal synthesis across arbitrary composition of grammatical invariants with bounded resource allocation.",
                level=8,
                train_data=train_s8,
                val_data=val_s8,
            ),
            CurriculumStage(
                stage_id="CURR_S9_AUTONOMOUS_META_CURRICULUM",
                name="Autonomous Open-Ended Meta-Curriculum & Self-Sustaining Evolutionary Loop",
                description="Autonomous generation and evaluation of self-invented task distributions without external supervision.",
                level=9,
                train_data=train_s9,
                val_data=val_s9,
            ),
        ]

    def get_stage(self, level: int) -> CurriculumStage:
        idx = max(0, min(level, len(self.stages) - 1))
        return self.stages[idx]

    def prepare_next_curriculum(
        self, current_level: int, prior_weights: Optional[DSLGrammarWeights] = None
    ) -> Tuple[CurriculumStage, DSLGrammarWeights]:
        """Prepares the next curriculum stage and adapts grammar weights as transfer priors."""
        next_level = current_level + 1
        stage = self.get_stage(next_level)

        base_weights = copy.deepcopy(prior_weights) if prior_weights else DSLGrammarWeights()

        # Adapt priors depending on stage characteristics
        if next_level == 1:
            # Emphasize counting & modulo
            base_weights.terminal_int["count_a"] *= 2.0
            base_weights.compound_int["mod"] *= 2.0
            base_weights.compound_bool_cmp["eq"] *= 1.5
        elif next_level == 2:
            # Emphasize substring & boolean logic
            base_weights.terminal_bool["contains"] *= 2.5
            base_weights.compound_bool_logic["and"] *= 2.0
        elif next_level == 3:
            # Compositional mixture
            base_weights.structural["terminal_prob"] = 0.25
            base_weights.structural["bool_cmp_prob"] = 0.5
            base_weights.compound_bool_logic["and"] *= 2.0
        elif next_level == 4:
            # Context-Free Dyck balance & nested invariant adaptation
            base_weights.terminal_bool["dyck_balanced"] = 4.0
            base_weights.terminal_int["count_a"] *= 2.0
            base_weights.terminal_int["count_b"] *= 2.0
            base_weights.compound_bool_cmp["eq"] *= 2.0
            base_weights.compound_bool_logic["and"] *= 2.0
            base_weights.structural["terminal_prob"] = 0.4
        elif next_level == 5:
            # Context-sensitive multi-constraint: graph connectivity + counter balance
            base_weights.terminal_bool["graph_bfs"] = 4.0
            base_weights.terminal_int["count_a"] *= 2.5
            base_weights.terminal_int["count_b"] *= 2.5
            base_weights.compound_bool_cmp["eq"] *= 2.5
            base_weights.compound_bool_logic["and"] *= 3.0
            base_weights.structural["terminal_prob"] = 0.25
            base_weights.structural["bool_cmp_prob"] = 0.5
        elif next_level == 6:
            # Hierarchical macro induction
            base_weights.terminal_bool["graph_bfs"] = 3.0
            base_weights.terminal_bool["dyck_balanced"] = 3.0
            base_weights.compound_bool_logic["and"] *= 2.5
            base_weights.structural["terminal_prob"] = 0.3
        elif next_level == 7:
            # Cross-domain meta-transfer across formal language, graph, and counters
            base_weights.terminal_bool["graph_bfs"] = 3.5
            base_weights.terminal_bool["dyck_balanced"] = 3.5
            base_weights.terminal_int["count_a"] *= 2.0
            base_weights.terminal_int["count_b"] *= 2.0
            base_weights.compound_bool_logic["or"] *= 3.0
            base_weights.compound_bool_logic["and"] *= 2.5
            base_weights.structural["terminal_prob"] = 0.35
            base_weights.structural["bool_cmp_prob"] = 0.5
        elif next_level == 8:
            # Universal self-refining synthesis
            base_weights.terminal_bool["graph_bfs"] = 3.0
            base_weights.terminal_bool["dyck_balanced"] = 3.0
            base_weights.compound_bool_logic["and"] *= 2.5
            base_weights.compound_bool_logic["or"] *= 2.5
            base_weights.structural["terminal_prob"] = 0.3
        elif next_level >= 9:
            # Autonomous meta-curriculum open-ended evolution
            base_weights.terminal_bool["graph_bfs"] = 3.0
            base_weights.terminal_bool["dyck_balanced"] = 3.0
            base_weights.compound_bool_cmp["eq"] *= 2.0
            base_weights.compound_bool_logic["and"] *= 2.0
            base_weights.compound_bool_logic["or"] *= 2.0
            base_weights.structural["terminal_prob"] = 0.35

        return stage, base_weights.normalize()
