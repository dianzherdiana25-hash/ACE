"""Equality Saturation & E-Graphs (Optimal AST Rewriting Engine).

Mathematical Foundation:
1. E-Graph Data Structure (Willsey et al., POPL 2021 'egg'):
   An E-graph G = (C, U, M) represents an equivalence relation over an exponential number
   of expressions in compact polynomial space:
     - C is the set of equivalence classes (e-classes).
     - U is a Union-Find disjoint-set structure with path compression and rank/size balancing.
     - M is a hash-cons memoization table mapping canonical e-nodes to their containing e-classes.

2. E-Node & E-Class Congruence Closure:
   An e-node f(c_1, ..., c_k) represents a function/operator f applied to child e-classes.
   The congruence property ensures:
     c_1 equiv c_1', ..., c_k equiv c_k'  ==>  f(c_1, ..., c_k) equiv f(c_1', ..., c_k')
   Delayed rebuilding (egg algorithm) processes dirty e-classes in batches, repairing upward
   parent pointers and restoring congruence invariants in O(E log E) amortized time.

3. Non-Destructive Equality Saturation:
   Unlike traditional destructive term rewriting which can get trapped in local syntactic minima
   or loop infinitely on commutative rules (e.g. x + y <-> y + x), equality saturation adds
   rewritten terms non-destructively by unioning e-classes without deleting original terms.
   Confluence and termination under resource bounds are mathematically guaranteed.

4. Optimal Term Extraction:
   Given a monotonic cost function Cost: AST -> R^+ (e.g. AST size, tree depth, latency),
   the optimal concrete TypedASTNode is extracted via shortest-path dynamic programming:
     Cost*(c) = min_{n in Nodes(c)} [ Cost_node(n) + sum_{c_i in Children(n)} Cost*(c_i) ]

Provenance: ADVISOR_AGENT
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple, Union

from ace_evolution.island_search import TypedASTNode


# ---------------------------------------------------------------------------
# Disjoint Set Union-Find with Path Compression
# ---------------------------------------------------------------------------

class UnionFind:
    """Disjoint-Set Union-Find structure with path compression and union-by-rank."""

    def __init__(self):
        self.parent: Dict[int, int] = {}
        self.rank: Dict[int, int] = {}
        self._next_id: int = 0

    def make_set(self) -> int:
        """Allocates a fresh set identifier."""
        elem = self._next_id
        self._next_id += 1
        self.parent[elem] = elem
        self.rank[elem] = 0
        return elem

    def find(self, x: int) -> int:
        """Finds canonical representative with recursive path compression."""
        path = []
        curr = x
        while self.parent[curr] != curr:
            path.append(curr)
            curr = self.parent[curr]
        # Path compression
        for node in path:
            self.parent[node] = curr
        return curr

    def union(self, x: int, y: int) -> int:
        """Unions two sets by rank, returning the canonical root of the union."""
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x == root_y:
            return root_x

        # Union by rank
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
            return root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
            return root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1
            return root_x

    def __len__(self) -> int:
        return self._next_id


# ---------------------------------------------------------------------------
# E-Node & E-Class Definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ENode:
    """Strongly-typed Equivalence Node (e-node).
    
    Represents an operator applied to child e-class IDs, with return type and optional literal value.
    """
    op: str
    children: Tuple[int, ...] = field(default_factory=tuple)
    return_type: str = "INT"
    val: Any = None

    def canonicalize(self, uf: UnionFind) -> ENode:
        """Returns a new ENode where all child class IDs are replaced with their canonical roots."""
        canon_children = tuple(uf.find(c) for c in self.children)
        return ENode(
            op=self.op,
            children=canon_children,
            return_type=self.return_type,
            val=self.val,
        )

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def __repr__(self) -> str:
        val_str = f", val={self.val}" if self.val is not None else ""
        if not self.children:
            return f"{self.op}({self.return_type}{val_str})"
        children_str = ", ".join(f"e{c}" for c in self.children)
        return f"{self.op}({children_str}){val_str}"


class EClass:
    """Equivalence Class (e-class) containing equivalent e-nodes and upward parent pointers."""

    def __init__(self, eclass_id: int):
        self.eclass_id: int = eclass_id
        self.nodes: Set[ENode] = set()
        # Upward parent pointers: list of (parent_enode, parent_eclass_id)
        self.parents: List[Tuple[ENode, int]] = []
        # Optional static constant analysis value
        self.constant_val: Optional[Any] = None

    def __len__(self) -> int:
        return len(self.nodes)

    def __repr__(self) -> str:
        return f"EClass({self.eclass_id}, nodes={list(self.nodes)})"


# ---------------------------------------------------------------------------
# Pattern & Pattern Matching
# ---------------------------------------------------------------------------

class Pattern:
    """AST Pattern for equality saturation rewrite matching.
    
    Can represent:
    - Pattern variable: e.g. '?x', '?y' matching any e-class.
    - Constant value: e.g. int_const with val=0.
    - Compound operator node: e.g. add(?x, ?y).
    """

    def __init__(
        self,
        op: str,
        return_type: str = "INT",
        children: Optional[List[Pattern]] = None,
        val: Any = None,
        is_var: bool = False,
        var_name: Optional[str] = None,
    ):
        self.op = op
        self.return_type = return_type
        self.children = children or []
        self.val = val
        self.is_var = is_var
        self.var_name = var_name

    @classmethod
    def var(cls, name: str, return_type: str = "INT") -> Pattern:
        """Constructs a pattern variable '?name'."""
        clean_name = name.lstrip("?")
        return cls(op=f"?{clean_name}", return_type=return_type, is_var=True, var_name=clean_name)

    @classmethod
    def const(cls, val: Any, return_type: str = "INT") -> Pattern:
        """Constructs a pattern matching a literal constant."""
        op = "int_const" if isinstance(val, int) and not isinstance(val, bool) else "bool_const"
        return cls(op=op, return_type=return_type, val=val)

    @classmethod
    def node(cls, op: str, return_type: str = "INT", children: Optional[List[Pattern]] = None, val: Any = None) -> Pattern:
        """Constructs a concrete operator pattern node."""
        return cls(op=op, return_type=return_type, children=children, val=val)

    @classmethod
    def parse(cls, expr: str) -> Pattern:
        """Parses a prefix s-expression string into a Pattern.
        
        Examples:
          '?x' -> Pattern.var('x')
          '0' -> Pattern.const(0)
          'True' -> Pattern.const(True)
          '(add ?x 0)' -> Pattern.node('add', children=[Pattern.var('x'), Pattern.const(0)])
          '(not (not ?x))' -> double negation pattern
        """
        expr = expr.strip()
        if expr.startswith("?") and "(" not in expr:
            return cls.var(expr[1:])
        if expr.isdigit() or (expr.startswith("-") and expr[1:].isdigit()):
            return cls.const(int(expr), return_type="INT")
        if expr in ("True", "False"):
            return cls.const(expr == "True", return_type="BOOL")

        if expr.startswith("(") and expr.endswith(")"):
            inner = expr[1:-1].strip()
            # Tokenize respecting parentheses
            tokens: List[str] = []
            depth = 0
            curr_token = []
            for ch in inner:
                if ch == "(":
                    depth += 1
                    curr_token.append(ch)
                elif ch == ")":
                    depth -= 1
                    curr_token.append(ch)
                elif ch.isspace() and depth == 0:
                    if curr_token:
                        tokens.append("".join(curr_token))
                        curr_token = []
                else:
                    curr_token.append(ch)
            if curr_token:
                tokens.append("".join(curr_token))

            if not tokens:
                raise ValueError(f"Empty s-expression: {expr}")

            op = tokens[0]
            # Infer return type based on operator
            bool_ops = {"eq", "neq", "lte", "gte", "and", "or", "not", "starts_with", "ends_with", "contains", "dyck_balanced", "graph_bfs"}
            ret_type = "BOOL" if op in bool_ops else "INT"

            children = [cls.parse(tok) for tok in tokens[1:]]
            return cls.node(op=op, return_type=ret_type, children=children)

        # Standalone terminal without parentheses (e.g. 'count_a')
        bool_ops = {"starts_with", "ends_with", "contains", "dyck_balanced", "graph_bfs"}
        ret_type = "BOOL" if expr in bool_ops else "INT"
        return cls.node(op=expr, return_type=ret_type, children=[])

    def match_class(self, egraph: EGraph, eclass_id: int, subst: Dict[str, int]) -> Iterator[Dict[str, int]]:
        """Matches this pattern against an e-class, yielding valid substitutions."""
        canon_id = egraph.find(eclass_id)

        if self.is_var:
            v_name = self.var_name
            if v_name in subst:
                # If variable was already bound, verify equivalence
                if egraph.find(subst[v_name]) == canon_id:
                    yield subst
            else:
                # Bind variable to this canonical e-class ID
                yield {**subst, v_name: canon_id}
            return

        # Concrete pattern node: search all e-nodes in the canonical e-class
        if canon_id not in egraph.classes:
            return

        eclass = egraph.classes[canon_id]
        for enode in eclass.nodes:
            if enode.op != self.op:
                continue
            if self.val is not None and enode.val != self.val:
                continue
            if len(enode.children) != len(self.children):
                continue

            # Recursively match child patterns against child e-classes
            def match_children(child_idx: int, current_subst: Dict[str, int]) -> Iterator[Dict[str, int]]:
                if child_idx == len(self.children):
                    yield current_subst
                    return
                child_pat = self.children[child_idx]
                child_class = enode.children[child_idx]
                for next_subst in child_pat.match_class(egraph, child_class, current_subst):
                    yield from match_children(child_idx + 1, next_subst)

            yield from match_children(0, subst)


# ---------------------------------------------------------------------------
# Rewrite Rules
# ---------------------------------------------------------------------------

@dataclass
class RewriteRule:
    """Equivalence rewrite rule: LHS -> RHS under optional condition."""
    name: str
    lhs: Pattern
    rhs: Union[Pattern, Callable[[Dict[str, int], EGraph], int]]
    condition: Optional[Callable[[Dict[str, int], EGraph], bool]] = None

    def apply(self, egraph: EGraph, match_class_id: int, subst: Dict[str, int]) -> Optional[int]:
        """Applies rewrite rule to e-graph, returning the union root ID if a union occurred."""
        if self.condition is not None and not self.condition(subst, egraph):
            return None

        # Instantiate right hand side
        if callable(self.rhs):
            rhs_class_id = self.rhs(subst, egraph)
        else:
            rhs_class_id = self._instantiate_pattern(self.rhs, subst, egraph)

        canon_match = egraph.find(match_class_id)
        canon_rhs = egraph.find(rhs_class_id)

        if canon_match != canon_rhs:
            return egraph.union(canon_match, canon_rhs)
        return None

    def _instantiate_pattern(self, pat: Pattern, subst: Dict[str, int], egraph: EGraph) -> int:
        """Instantiates a pattern into the e-graph using substitution mapping."""
        if pat.is_var:
            if pat.var_name not in subst:
                raise ValueError(f"Unbound variable '{pat.var_name}' during rewrite instantiation")
            return egraph.find(subst[pat.var_name])

        # Instantiate child patterns
        child_classes = tuple(self._instantiate_pattern(child, subst, egraph) for child in pat.children)
        enode = ENode(
            op=pat.op,
            children=child_classes,
            return_type=pat.return_type,
            val=pat.val,
        )
        return egraph.add_node(enode)


# ---------------------------------------------------------------------------
# E-Graph Implementation with Delayed Rebuilding
# ---------------------------------------------------------------------------

class EGraph:
    """Egg-style E-Graph with delayed congruence closure."""

    def __init__(self):
        self.union_find: UnionFind = UnionFind()
        self.classes: Dict[int, EClass] = {}
        # Hash-cons memoization table: canonical ENode -> canonical e-class ID
        self.memo: Dict[ENode, int] = {}
        # Worklist of e-class IDs modified and needing upward congruence rebuilding
        self.worklist: Set[int] = set()
        self.clean: bool = True

    def find(self, class_id: int) -> int:
        """Finds canonical e-class ID via union-find."""
        return self.union_find.find(class_id)

    def total_enodes(self) -> int:
        """Returns the total number of e-nodes across all active e-classes."""
        return sum(len(c.nodes) for c in self.classes.values())

    def total_eclasses(self) -> int:
        """Returns the total number of active e-classes."""
        return len(self.classes)

    def add_node(self, enode: ENode) -> int:
        """Adds an e-node to the e-graph, returning its canonical e-class ID.
        
        If an equivalent canonical e-node already exists in the memo table, returns its class ID;
        otherwise allocates a new e-class.
        """
        canon_node = enode.canonicalize(self.union_find)
        if canon_node in self.memo:
            return self.find(self.memo[canon_node])

        # Allocate new e-class
        new_id = self.union_find.make_set()
        eclass = EClass(eclass_id=new_id)
        eclass.nodes.add(canon_node)
        self.classes[new_id] = eclass
        self.memo[canon_node] = new_id

        # Register as upward parent in all child classes
        for child_id in canon_node.children:
            canon_child = self.find(child_id)
            if canon_child in self.classes:
                self.classes[canon_child].parents.append((canon_node, new_id))

        return new_id

    def add_ast(self, ast: TypedASTNode) -> int:
        """Recursively ingests a TypedASTNode into the E-Graph, returning the root e-class ID."""
        child_class_ids = []
        for child in (ast.children or []):
            child_class_ids.append(self.add_ast(child))

        enode = ENode(
            op=ast.op,
            children=tuple(child_class_ids),
            return_type=ast.return_type,
            val=ast.val,
        )
        return self.add_node(enode)

    def union(self, class1: int, class2: int) -> int:
        """Unions two e-classes, queueing them for delayed rebuild."""
        root1 = self.find(class1)
        root2 = self.find(class2)
        if root1 == root2:
            return root1

        new_root = self.union_find.union(root1, root2)
        old_root = root2 if new_root == root1 else root1

        # Merge old_root data into new_root
        if old_root in self.classes and new_root in self.classes:
            self.classes[new_root].nodes.update(self.classes[old_root].nodes)
            self.classes[new_root].parents.extend(self.classes[old_root].parents)
            del self.classes[old_root]

        self.worklist.add(new_root)
        self.clean = False
        return new_root

    def rebuild(self) -> int:
        """Executes delayed congruence closure (Nelson-Oppen / Downey-Sethi-Tarjan).
        
        Repairs hash-cons memoization and upward parent pointers, unioning classes
        whose canonical parents become congruent.
        
        Returns the number of congruence repair steps performed.
        """
        repairs = 0
        while self.worklist:
            todo = list(self.worklist)
            self.worklist.clear()

            for class_id in todo:
                canon_class = self.find(class_id)
                if canon_class not in self.classes:
                    continue

                eclass = self.classes[canon_class]
                new_parents: List[Tuple[ENode, int]] = []

                for parent_enode, parent_cid in eclass.parents:
                    canon_parent_cid = self.find(parent_cid)
                    canon_parent_enode = parent_enode.canonicalize(self.union_find)

                    # Remove outdated key from memo
                    if parent_enode in self.memo:
                        del self.memo[parent_enode]

                    # Check for congruence closure: identical canonical e-node already registered
                    if canon_parent_enode in self.memo:
                        existing_class = self.find(self.memo[canon_parent_enode])
                        if existing_class != canon_parent_cid:
                            # Congruence detected! Union containing classes
                            repairs += 1
                            united = self.union(existing_class, canon_parent_cid)
                            self.memo[canon_parent_enode] = united
                    else:
                        self.memo[canon_parent_enode] = canon_parent_cid

                    new_parents.append((canon_parent_enode, canon_parent_cid))

                eclass.parents = new_parents

            # Canonicalize all e-nodes in all active e-classes
            for c_id, eclass in list(self.classes.items()):
                eclass.nodes = {n.canonicalize(self.union_find) for n in eclass.nodes}

        self.clean = True
        return repairs


# ---------------------------------------------------------------------------
# Cost Function & Optimal AST Extractor
# ---------------------------------------------------------------------------

class CostFunction:
    """Base cost function for optimal AST extraction from an E-Graph."""

    def node_cost(self, enode: ENode) -> float:
        raise NotImplementedError

    def compute_ast_cost(self, ast: TypedASTNode) -> float:
        """Recursively computes cost for a concrete AST."""
        c = self.node_cost(ENode(op=ast.op, return_type=ast.return_type, val=ast.val))
        for child in (ast.children or []):
            c += self.compute_ast_cost(child)
        return c


class ASTSizeCost(CostFunction):
    """Parsimony cost function: penalizes AST node count (size)."""

    def __init__(self, constant_discount: float = 0.5):
        self.constant_discount = constant_discount

    def node_cost(self, enode: ENode) -> float:
        if enode.is_leaf():
            return self.constant_discount if enode.val is not None else 1.0
        return 1.0


class ASTDepthCost(CostFunction):
    """Penalizes tree depth and complex nesting."""

    def node_cost(self, enode: ENode) -> float:
        return 1.0


class Extractor:
    """Shortest-path dynamic programming extractor finding the minimal-cost TypedASTNode."""

    def __init__(self, egraph: EGraph, cost_fn: Optional[CostFunction] = None):
        self.egraph = egraph
        self.cost_fn = cost_fn or ASTSizeCost()
        # Mapping from canonical class_id -> (best_cost, best_enode)
        self.best: Dict[int, Tuple[float, ENode]] = {}
        self._compute_best_costs()

    def _compute_best_costs(self):
        """Fixed-point shortest path computation across the e-graph DAG."""
        # Ensure egraph is rebuild-clean
        if not self.egraph.clean:
            self.egraph.rebuild()

        changed = True
        max_iters = 100
        iteration = 0

        while changed and iteration < max_iters:
            changed = False
            iteration += 1

            for class_id, eclass in self.egraph.classes.items():
                canon_id = self.egraph.find(class_id)
                current_best_cost = self.best.get(canon_id, (float("inf"), None))[0]

                for enode in eclass.nodes:
                    # Check if all children have known costs
                    children_costs = [self.best.get(self.egraph.find(c), (float("inf"), None))[0] for c in enode.children]
                    if any(math.isinf(c) for c in children_costs):
                        continue

                    node_c = self.cost_fn.node_cost(enode)
                    total_c = node_c + sum(children_costs)

                    if total_c < current_best_cost:
                        current_best_cost = total_c
                        self.best[canon_id] = (total_c, enode)
                        changed = True

    def extract(self, root_class_id: int) -> TypedASTNode:
        """Extracts the optimal TypedASTNode rooted at root_class_id."""
        canon_root = self.egraph.find(root_class_id)
        if canon_root not in self.best:
            raise ValueError(f"Cannot extract term from e-class {root_class_id}: unreached by cost evaluation")

        def build_node(cid: int) -> TypedASTNode:
            c_canon = self.egraph.find(cid)
            _, enode = self.best[c_canon]
            children_ast = [build_node(child_cid) for child_cid in enode.children]
            return TypedASTNode(
                op=enode.op,
                return_type=enode.return_type,
                children=children_ast,
                val=enode.val,
            )

        return build_node(canon_root)


# ---------------------------------------------------------------------------
# Equality Saturation Engine
# ---------------------------------------------------------------------------

@dataclass
class SaturationReport:
    """Detailed telemetry from an equality saturation run."""
    iterations: int
    saturated: bool
    initial_eclasses: int
    initial_enodes: int
    final_eclasses: int
    final_enodes: int
    total_unions: int
    congruence_repairs: int
    elapsed_seconds: float
    initial_cost: float
    final_cost: float


class EqualitySaturation:
    """Explores exponential rewrite equivalence classes non-destructively without cyclic blowup."""

    def __init__(
        self,
        rules: Optional[List[RewriteRule]] = None,
        cost_fn: Optional[CostFunction] = None,
    ):
        self.rules = list(rules or build_ace_dsl_rewrites())
        self.cost_fn = cost_fn or ASTSizeCost()

    def run(
        self,
        egraph: EGraph,
        root_class_id: int,
        max_iterations: int = 25,
        node_limit: int = 5000,
        time_limit_sec: float = 5.0,
    ) -> SaturationReport:
        """Executes the equality saturation loop until saturation or limits reached."""
        start_time = time.perf_counter()
        initial_eclasses = egraph.total_eclasses()
        initial_enodes = egraph.total_enodes()

        extractor_init = Extractor(egraph, self.cost_fn)
        initial_ast = extractor_init.extract(root_class_id)
        initial_cost = self.cost_fn.compute_ast_cost(initial_ast)

        total_unions = 0
        total_repairs = 0
        saturated = False
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            if time.perf_counter() - start_time > time_limit_sec:
                break
            if egraph.total_enodes() > node_limit:
                break

            # 1. Match all rules across all e-classes
            matches: List[Tuple[RewriteRule, int, Dict[str, int]]] = []
            for rule in self.rules:
                for class_id in list(egraph.classes.keys()):
                    canon_id = egraph.find(class_id)
                    for subst in rule.lhs.match_class(egraph, canon_id, {}):
                        matches.append((rule, canon_id, subst))

            # 2. Apply all matches non-destructively
            unions_this_round = 0
            for rule, match_class, subst in matches:
                res = rule.apply(egraph, match_class, subst)
                if res is not None:
                    unions_this_round += 1
                    total_unions += 1

            # 3. Rebuild e-graph to restore congruence closure
            repairs = egraph.rebuild()
            total_repairs += repairs

            # Check for saturation: if no new unions were made, fixed-point reached!
            if unions_this_round == 0:
                saturated = True
                break

        extractor_final = Extractor(egraph, self.cost_fn)
        final_ast = extractor_final.extract(root_class_id)
        final_cost = self.cost_fn.compute_ast_cost(final_ast)

        return SaturationReport(
            iterations=iteration,
            saturated=saturated,
            initial_eclasses=initial_eclasses,
            initial_enodes=initial_enodes,
            final_eclasses=egraph.total_eclasses(),
            final_enodes=egraph.total_enodes(),
            total_unions=total_unions,
            congruence_repairs=total_repairs,
            elapsed_seconds=round(time.perf_counter() - start_time, 5),
            initial_cost=initial_cost,
            final_cost=final_cost,
        )

    def rewrite(self, ast: TypedASTNode, max_iterations: int = 25) -> Tuple[TypedASTNode, SaturationReport]:
        """Convenience method: takes an AST, runs equality saturation, and returns optimal AST."""
        egraph = EGraph()
        root_id = egraph.add_ast(ast)
        report = self.run(egraph, root_id, max_iterations=max_iterations)
        extractor = Extractor(egraph, self.cost_fn)
        optimal_ast = extractor.extract(root_id)
        return optimal_ast, report


# ---------------------------------------------------------------------------
# Standard ACE DSL Rewrite Rules
# ---------------------------------------------------------------------------

def build_ace_dsl_rewrites() -> List[RewriteRule]:
    """Assembles rich domain rewrite rules for ACE arithmetic, boolean, and comparison primitives.
    
    Includes:
    - Additive and multiplicative identities: (x + 0 -> x), (x * 1 -> x), (x * 0 -> 0), (x - x -> 0).
    - Commutative equivalence: (x + y -> y + x), (x * y -> y * x) - explored without cyclic blowup!
    - Boolean identities: (not (not x) -> x), (x and True -> x), (x or False -> x), (x and False -> False).
    - Idempotence: (x and x -> x), (x or x -> x).
    - Comparison identities: (x == x -> True), (x != x -> False), (x <= x -> True).
    - Dynamic constant folding across integer arithmetic and boolean logic.
    """
    rules: List[RewriteRule] = []

    # 1. Arithmetic Identities
    rules.append(RewriteRule("add-zero-right", Pattern.parse("(add ?x 0)"), Pattern.parse("?x")))
    rules.append(RewriteRule("add-zero-left", Pattern.parse("(add 0 ?x)"), Pattern.parse("?x")))
    rules.append(RewriteRule("sub-zero-right", Pattern.parse("(sub ?x 0)"), Pattern.parse("?x")))
    rules.append(RewriteRule("sub-self", Pattern.parse("(sub ?x ?x)"), Pattern.parse("0")))
    rules.append(RewriteRule("mul-one-right", Pattern.parse("(mul ?x 1)"), Pattern.parse("?x")))
    rules.append(RewriteRule("mul-one-left", Pattern.parse("(mul 1 ?x)"), Pattern.parse("?x")))
    rules.append(RewriteRule("mul-zero-right", Pattern.parse("(mul ?x 0)"), Pattern.parse("0")))
    rules.append(RewriteRule("mul-zero-left", Pattern.parse("(mul 0 ?x)"), Pattern.parse("0")))
    rules.append(RewriteRule("mod-one", Pattern.parse("(mod ?x 1)"), Pattern.parse("0")))

    # 2. Commutativity (demonstrates cyclic-safe non-destructive rewriting)
    rules.append(RewriteRule("commute-add", Pattern.parse("(add ?x ?y)"), Pattern.parse("(add ?y ?x)")))
    rules.append(RewriteRule("commute-mul", Pattern.parse("(mul ?x ?y)"), Pattern.parse("(mul ?y ?x)")))

    # 3. Boolean Logic Identities
    rules.append(RewriteRule("double-not", Pattern.parse("(not (not ?x))"), Pattern.parse("?x")))
    rules.append(RewriteRule("and-true-right", Pattern.parse("(and ?x True)"), Pattern.parse("?x")))
    rules.append(RewriteRule("and-true-left", Pattern.parse("(and True ?x)"), Pattern.parse("?x")))
    rules.append(RewriteRule("and-false-right", Pattern.parse("(and ?x False)"), Pattern.parse("False")))
    rules.append(RewriteRule("and-false-left", Pattern.parse("(and False ?x)"), Pattern.parse("False")))
    rules.append(RewriteRule("and-idempotent", Pattern.parse("(and ?x ?x)"), Pattern.parse("?x")))

    rules.append(RewriteRule("or-false-right", Pattern.parse("(or ?x False)"), Pattern.parse("?x")))
    rules.append(RewriteRule("or-false-left", Pattern.parse("(or False ?x)"), Pattern.parse("?x")))
    rules.append(RewriteRule("or-true-right", Pattern.parse("(or ?x True)"), Pattern.parse("True")))
    rules.append(RewriteRule("or-true-left", Pattern.parse("(or True ?x)"), Pattern.parse("True")))
    rules.append(RewriteRule("or-idempotent", Pattern.parse("(or ?x ?x)"), Pattern.parse("?x")))

    # 4. Comparison Identities
    rules.append(RewriteRule("eq-self", Pattern.parse("(eq ?x ?x)"), Pattern.parse("True")))
    rules.append(RewriteRule("neq-self", Pattern.parse("(neq ?x ?x)"), Pattern.parse("False")))
    rules.append(RewriteRule("lte-self", Pattern.parse("(lte ?x ?x)"), Pattern.parse("True")))
    rules.append(RewriteRule("gte-self", Pattern.parse("(gte ?x ?x)"), Pattern.parse("True")))

    # 5. Dynamic Constant Folding
    def constant_eval_add(subst: Dict[str, int], egraph: EGraph) -> int:
        v1 = _extract_constant_value(subst["x"], egraph)
        v2 = _extract_constant_value(subst["y"], egraph)
        res = int(v1 + v2)
        return egraph.add_node(ENode(op="int_const", return_type="INT", val=res))

    def constant_eval_mul(subst: Dict[str, int], egraph: EGraph) -> int:
        v1 = _extract_constant_value(subst["x"], egraph)
        v2 = _extract_constant_value(subst["y"], egraph)
        res = int(v1 * v2)
        return egraph.add_node(ENode(op="int_const", return_type="INT", val=res))

    def constant_eval_sub(subst: Dict[str, int], egraph: EGraph) -> int:
        v1 = _extract_constant_value(subst["x"], egraph)
        v2 = _extract_constant_value(subst["y"], egraph)
        res = int(v1 - v2)
        return egraph.add_node(ENode(op="int_const", return_type="INT", val=res))

    def is_int_const(var_name: str) -> Callable[[Dict[str, int], EGraph], bool]:
        return lambda subst, egraph: _is_class_constant_of_type(subst[var_name], egraph, int)

    rules.append(RewriteRule(
        name="const-fold-add",
        lhs=Pattern.parse("(add ?x ?y)"),
        rhs=constant_eval_add,
        condition=lambda s, g: is_int_const("x")(s, g) and is_int_const("y")(s, g),
    ))
    rules.append(RewriteRule(
        name="const-fold-mul",
        lhs=Pattern.parse("(mul ?x ?y)"),
        rhs=constant_eval_mul,
        condition=lambda s, g: is_int_const("x")(s, g) and is_int_const("y")(s, g),
    ))
    rules.append(RewriteRule(
        name="const-fold-sub",
        lhs=Pattern.parse("(sub ?x ?y)"),
        rhs=constant_eval_sub,
        condition=lambda s, g: is_int_const("x")(s, g) and is_int_const("y")(s, g),
    ))

    return rules


def _is_class_constant_of_type(class_id: int, egraph: EGraph, expected_type: type) -> bool:
    """Helper: checks if an e-class contains a constant node of expected type."""
    canon_id = egraph.find(class_id)
    if canon_id not in egraph.classes:
        return False
    for enode in egraph.classes[canon_id].nodes:
        if enode.op in ("int_const", "bool_const") and isinstance(enode.val, expected_type):
            if expected_type is int and isinstance(enode.val, bool):
                continue
            return True
    return False


def _extract_constant_value(class_id: int, egraph: EGraph) -> Any:
    """Helper: retrieves constant literal value from an e-class."""
    canon_id = egraph.find(class_id)
    for enode in egraph.classes[canon_id].nodes:
        if enode.op in ("int_const", "bool_const") and enode.val is not None:
            return enode.val
    raise ValueError(f"No constant node in e-class {class_id}")
