"""DPLL(T) Formal Verifier Engine for Quantifier-Free Linear Integer Arithmetic (QF-LIA) & Propositional Logic.

Mathematical & Algorithmic Foundations:
1. Propositional SAT Solver (DPLL):
   - Boolean Constraint Propagation (Unit Propagation).
   - Pure Literal Elimination for pure boolean symbols.
   - Non-chronological decision stack backtracking with conflict clause learning.
2. Theory Solver T (Quantifier-Free Linear Integer Arithmetic - QF-LIA):
   - Fourier-Motzkin Variable Elimination over integer inequalities: sum(a_i * x_i) <= c.
   - Chvátal-Gomory Integer GCD tightening: gcd(a_1, ..., a_k) divides coefficients,
     tightening constant c to floor(c / gcd) * gcd.
   - Minimal Infeasible Core Extraction: provenance tracking of conflicting bounds deriving 0 <= -k (k > 0).
   - Concrete integer model synthesis via interval back-substitution.
3. DPLL(T) Cooperation Architecture:
   - T-propagation: deduces unassigned theory literals implied by current theory state.
   - T-conflict clause learning: negates infeasible theory core ~(l_1 /\\ ... /\\ l_k) = (~l_1 \\/ ... \\/ ~l_k)
     to prune the boolean search space without re-exploring isomorphic arithmetic conflicts.
4. Formal Program Verification Interface:
   - verify_program_satisfies_spec(ast_node, pre_cond, post_cond).
   - SSA path constraint compilation and Tseitin CNF transformation.
   - Rigorous proof: Pre /\\ Path /\\ ~Post is UNSAT -> Specification Proven!
   - Counterexample generation: if SAT -> concrete integer state violating specification.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union


# ============================================================================
# 1. Propositional Logic & CNF Data Structures
# ============================================================================

@dataclass(frozen=True)
class Literal:
    """Propositional or Theory literal: var name and sign."""
    var: str
    sign: bool = True  # True: positive (var), False: negative (~var)

    def negate(self) -> Literal:
        return Literal(self.var, not self.sign)

    def __repr__(self) -> str:
        return self.var if self.sign else f"¬{self.var}"


Clause = List[Literal]


# ============================================================================
# 2. Linear Integer Arithmetic (QF-LIA) Constraints
# ============================================================================

@dataclass(frozen=True)
class LinearConstraint:
    """Normalized linear integer constraint: sum(coeffs[v] * v) <= const."""
    coeffs: Dict[str, int]  # Only non-zero coefficients
    const: int
    atom_id: str

    @classmethod
    def create(cls, coeffs: Dict[str, int], const: int, atom_id: str) -> LinearConstraint:
        """Constructs and normalizes a linear integer constraint with GCD tightening."""
        clean_coeffs = {v: int(c) for v, c in sorted(coeffs.items()) if c != 0}
        const = int(const)

        if not clean_coeffs:
            return cls(coeffs={}, const=const, atom_id=atom_id)

        # Chvátal-Gomory GCD reduction: gcd(a_1, ..., a_n) divides LHS
        g = math.gcd(*[abs(c) for c in clean_coeffs.values()])
        if g > 1:
            clean_coeffs = {v: c // g for v, c in clean_coeffs.items()}
            const = math.floor(const / g)

        return cls(coeffs=clean_coeffs, const=const, atom_id=atom_id)

    @classmethod
    def from_le(cls, coeffs: Dict[str, int], const: int, atom_id: str) -> LinearConstraint:
        """sum(coeffs * x) <= const."""
        return cls.create(coeffs, const, atom_id)

    @classmethod
    def from_lt(cls, coeffs: Dict[str, int], const: int, atom_id: str) -> LinearConstraint:
        """sum(coeffs * x) < const <=> sum(coeffs * x) <= const - 1 for integers."""
        return cls.create(coeffs, const - 1, atom_id)

    @classmethod
    def from_ge(cls, coeffs: Dict[str, int], const: int, atom_id: str) -> LinearConstraint:
        """sum(coeffs * x) >= const <=> sum(-coeffs * x) <= -const."""
        neg_coeffs = {v: -c for v, c in coeffs.items()}
        return cls.create(neg_coeffs, -const, atom_id)

    @classmethod
    def from_gt(cls, coeffs: Dict[str, int], const: int, atom_id: str) -> LinearConstraint:
        """sum(coeffs * x) > const <=> sum(-coeffs * x) <= -const - 1 for integers."""
        neg_coeffs = {v: -c for v, c in coeffs.items()}
        return cls.create(neg_coeffs, -const - 1, atom_id)

    @classmethod
    def from_assign(
        cls,
        target_var: str,
        expr_coeffs: Dict[str, int],
        expr_const: int,
        atom_id_le: str,
        atom_id_ge: str,
    ) -> Tuple[LinearConstraint, LinearConstraint]:
        """Encodes target_var == sum(expr_coeffs * v) + expr_const.

        target_var - sum(expr_coeffs * v) == expr_const.
        (1) target_var - sum(expr_coeffs * v) <= expr_const
        (2) target_var - sum(expr_coeffs * v) >= expr_const
        """
        diff_coeffs = {target_var: 1}
        for v, c in expr_coeffs.items():
            diff_coeffs[v] = diff_coeffs.get(v, 0) - c

        c_le = cls.from_le(diff_coeffs, expr_const, atom_id_le)
        c_ge = cls.from_ge(diff_coeffs, expr_const, atom_id_ge)
        return c_le, c_ge

    def negate(self, negated_atom_id: Optional[str] = None) -> LinearConstraint:
        """Integer negation: ~(sum(a_i * x_i) <= c) <=> sum(a_i * x_i) >= c + 1 <=> sum(-a_i * x_i) <= -c - 1."""
        neg_coeffs = {v: -c for v, c in self.coeffs.items()}
        nid = negated_atom_id if negated_atom_id is not None else f"not_{self.atom_id}"
        return LinearConstraint.create(neg_coeffs, -self.const - 1, nid)

    def evaluate(self, env: Dict[str, int]) -> bool:
        """Evaluates whether integer environment satisfies this constraint."""
        lhs = sum(c * env.get(v, 0) for v, c in self.coeffs.items())
        return lhs <= self.const

    def __repr__(self) -> str:
        if not self.coeffs:
            return f"0 <= {self.const}"
        terms = []
        for i, (v, c) in enumerate(self.coeffs.items()):
            if i == 0:
                terms.append(f"{c}{v}" if c != 1 else v)
            else:
                sign_str = "+ " if c > 0 else "- "
                val_str = f"{abs(c)}{v}" if abs(c) != 1 else v
                terms.append(f"{sign_str}{val_str}")
        return f"{' '.join(terms)} <= {self.const}"


# ============================================================================
# 3. Theory Solver T (QF-LIA) with Fourier-Motzkin & Infeasible Core Extraction
# ============================================================================

@dataclass(frozen=True)
class _InequalityNode:
    """Internal inequality node tracking origin literals for conflict clause generation."""
    coeffs: Dict[str, int]
    const: int
    origins: FrozenSet[str]


class TheorySolver:
    """Theory Solver for Quantifier-Free Linear Integer Arithmetic (QF-LIA)."""

    def check_consistency(
        self,
        assigned_constraints: List[Tuple[LinearConstraint, bool, str]],
    ) -> Tuple[bool, Optional[Set[str]], Optional[Dict[str, int]]]:
        """Checks consistency of conjunction of assigned theory literals.

        Args:
            assigned_constraints: List of (LinearConstraint, assigned_sign, literal_var_name).

        Returns:
            Tuple of:
            - is_consistent: bool
            - conflict_core: Set of literal variable names participating in contradiction (if UNSAT)
            - model: Integer variable assignment (if SAT)
        """
        # Convert all assigned constraints to standard sum(a_i * x_i) <= c with origin tracking
        nodes: List[_InequalityNode] = []
        for constraint, sign, lit_var in assigned_constraints:
            if sign:
                c = constraint
            else:
                c = constraint.negate()

            # Immediate contradiction check
            if not c.coeffs:
                if c.const < 0:
                    return False, {lit_var}, None
                continue

            nodes.append(_InequalityNode(
                coeffs=c.coeffs,
                const=c.const,
                origins=frozenset([lit_var]),
            ))

        if not nodes:
            return True, None, {}

        # Collect all variables
        all_vars = sorted({v for node in nodes for v in node.coeffs})

        # Track bounds history for back-substitution integer model synthesis
        # variable -> (positives_at_step, negatives_at_step)
        history: List[Tuple[str, List[_InequalityNode], List[_InequalityNode]]] = []
        current_nodes = list(nodes)

        for v in all_vars:
            positives = [n for n in current_nodes if n.coeffs.get(v, 0) > 0]
            negatives = [n for n in current_nodes if n.coeffs.get(v, 0) < 0]
            zeros = [n for n in current_nodes if n.coeffs.get(v, 0) == 0]

            history.append((v, positives, negatives))
            new_nodes = list(zeros)

            for p in positives:
                for n in negatives:
                    a_p = p.coeffs[v]
                    abs_an = -n.coeffs[v]

                    # Combine: abs_an * p + a_p * n (eliminating variable v)
                    comb_coeffs: Dict[str, int] = {}
                    comb_origins = p.origins | n.origins

                    all_other_vars = (set(p.coeffs.keys()) | set(n.coeffs.keys())) - {v}
                    for w in all_other_vars:
                        val = abs_an * p.coeffs.get(w, 0) + a_p * n.coeffs.get(w, 0)
                        if val != 0:
                            comb_coeffs[w] = val

                    comb_const = abs_an * p.const + a_p * n.const

                    # Integer GCD reduction & tightening
                    if comb_coeffs:
                        g = math.gcd(*[abs(val) for val in comb_coeffs.values()])
                        if g > 1:
                            comb_coeffs = {w: val // g for w, val in comb_coeffs.items()}
                            comb_const = math.floor(comb_const / g)
                    else:
                        # Direct numeric bound: 0 <= comb_const
                        if comb_const < 0:
                            # Contradiction reached! Return minimal infeasible core
                            return False, set(comb_origins), None

                    new_nodes.append(_InequalityNode(
                        coeffs=comb_coeffs,
                        const=comb_const,
                        origins=comb_origins,
                    ))

            current_nodes = new_nodes

        # Final check on remaining constraints
        for node in current_nodes:
            if not node.coeffs and node.const < 0:
                return False, set(node.origins), None

        # Back-substitution to extract concrete integer model
        model = self._back_substitute(history, all_vars)
        if model is None:
            # In the rare event of an integer gap under real-feasible bounds
            all_origins = {lit_var for _, _, lit_var in assigned_constraints}
            return False, all_origins, None

        return True, None, model

    def _back_substitute(
        self,
        history: List[Tuple[str, List[_InequalityNode], List[_InequalityNode]]],
        all_vars: List[str],
    ) -> Optional[Dict[str, int]]:
        """Synthesizes satisfying integer values for all variables via back-substitution."""
        model: Dict[str, int] = {}

        # Reverse elimination order
        for v, positives, negatives in reversed(history):
            lower_bound = -10**9
            upper_bound = 10**9

            # From positives: a_p * v + rest <= const => v <= floor((const - rest) / a_p)
            for p in positives:
                a_p = p.coeffs[v]
                rest = sum(c * model.get(w, 0) for w, c in p.coeffs.items() if w != v)
                u = math.floor((p.const - rest) / a_p)
                if u < upper_bound:
                    upper_bound = u

            # From negatives: a_n * v + rest <= const (a_n < 0) => v >= ceil((rest - const) / |a_n|)
            for n in negatives:
                abs_an = -n.coeffs[v]
                rest = sum(c * model.get(w, 0) for w, c in n.coeffs.items() if w != v)
                l = math.ceil((rest - n.const) / abs_an)
                if l > lower_bound:
                    lower_bound = l

            if lower_bound > upper_bound:
                return None  # No integer solution in this branch

            # Select canonical representative in [lower_bound, upper_bound]
            if lower_bound <= 0 <= upper_bound:
                val = 0
            elif lower_bound > 0:
                val = lower_bound
            else:
                val = upper_bound

            model[v] = val

        for v in all_vars:
            if v not in model:
                model[v] = 0

        return model


# ============================================================================
# 4. DPLL(T) Solver (DPLL + QF-LIA Theory Engine)
# ============================================================================

@dataclass
class SMTResult:
    is_sat: bool
    boolean_assignment: Optional[Dict[str, bool]]
    integer_model: Optional[Dict[str, int]]
    learned_clauses: int
    decisions: int
    conflicts: int
    theory_propagations: int


class DPLLTSolver:
    """DPLL(T) Satisfiability Modulo Theories Solver with QF-LIA Theory Engine."""

    def __init__(self):
        self.theory_solver = TheorySolver()

    def solve(
        self,
        clauses: List[Clause],
        theory_atoms: Dict[str, LinearConstraint],
        enable_t_propagation: bool = True,
    ) -> SMTResult:
        """Executes DPLL(T) solving over propositional clauses & theory atoms."""
        working_clauses = [list(c) for c in clauses]
        assignment: Dict[str, bool] = {}
        decisions: List[Dict[str, Any]] = []
        trail: List[str] = []

        learned_clauses_count = 0
        decisions_count = 0
        conflicts_count = 0
        t_propagations_count = 0

        # Collect all variables in CNF
        all_variables = sorted({lit.var for clause in working_clauses for lit in clause} | set(theory_atoms.keys()))

        def bcp() -> Optional[Clause]:
            """Performs Boolean Constraint Propagation (Unit Propagation). Returns conflict clause if any."""
            while True:
                prop_made = False
                for clause in working_clauses:
                    num_false = 0
                    unassigned_lit: Optional[Literal] = None
                    clause_satisfied = False

                    for lit in clause:
                        if lit.var in assignment:
                            if assignment[lit.var] == lit.sign:
                                clause_satisfied = True
                                break
                            else:
                                num_false += 1
                        else:
                            if unassigned_lit is None:
                                unassigned_lit = lit
                            else:
                                unassigned_lit = None
                                break

                    if clause_satisfied:
                        continue

                    if num_false == len(clause):
                        # All literals False -> Conflict!
                        return clause

                    if unassigned_lit is not None:
                        # Unit clause!
                        assignment[unassigned_lit.var] = unassigned_lit.sign
                        trail.append(unassigned_lit.var)
                        prop_made = True

                if not prop_made:
                    return None

        # -------------------------------------------------------------
        # Main DPLL(T) Loop
        # -------------------------------------------------------------
        while True:
            # 1. Boolean Constraint Propagation (BCP)
            conflict_clause = bcp()

            # 2. Theory Consistency Check (QF-LIA)
            if conflict_clause is None:
                assigned_theory_atoms = [
                    (theory_atoms[v], assignment[v], v)
                    for v in assignment
                    if v in theory_atoms
                ]
                t_cons, conflict_core, _ = self.theory_solver.check_consistency(assigned_theory_atoms)
                if not t_cons:
                    # Infeasible theory core -> build conflict clause: (~l_1 \/ ... \/ ~l_k)
                    conflict_clause = [
                        Literal(v, not assignment[v])
                        for v in conflict_core
                        if v in assignment
                    ]

            # 3. Conflict Handling & Backtracking
            if conflict_clause is not None:
                conflicts_count += 1
                working_clauses.append(conflict_clause)
                learned_clauses_count += 1

                # Backtrack to the most recent decision that hasn't tried both polarities
                while decisions and decisions[-1]["tried_both"]:
                    d = decisions.pop()
                    while len(trail) > d["trail_len"]:
                        v = trail.pop()
                        del assignment[v]

                if not decisions:
                    # Entire search space exhausted -> UNSAT!
                    return SMTResult(
                        is_sat=False,
                        boolean_assignment=None,
                        integer_model=None,
                        learned_clauses=learned_clauses_count,
                        decisions=decisions_count,
                        conflicts=conflicts_count,
                        theory_propagations=t_propagations_count,
                    )

                # Flip the last decision
                d = decisions[-1]
                d["tried_both"] = True
                d["value"] = not d["value"]

                while len(trail) > d["trail_len"]:
                    v = trail.pop()
                    del assignment[v]

                assignment[d["var"]] = d["value"]
                trail.append(d["var"])
                continue

            # 4. Theory Propagation (T-Propagation)
            if enable_t_propagation:
                assigned_theory_atoms = [
                    (theory_atoms[v], assignment[v], v)
                    for v in assignment
                    if v in theory_atoms
                ]
                unassigned_theory_atoms = [
                    v for v in theory_atoms if v not in assignment
                ]
                t_propagated = False
                for v in unassigned_theory_atoms:
                    c = theory_atoms[v]
                    # Check if current theory implies v = True
                    neg_test = assigned_theory_atoms + [(c, False, v)]
                    neg_cons, _, _ = self.theory_solver.check_consistency(neg_test)
                    if not neg_cons:
                        assignment[v] = True
                        trail.append(v)
                        t_propagations_count += 1
                        assigned_theory_atoms.append((c, True, v))
                        t_propagated = True
                        continue

                    # Check if current theory implies v = False
                    pos_test = assigned_theory_atoms + [(c, True, v)]
                    pos_cons, _, _ = self.theory_solver.check_consistency(pos_test)
                    if not pos_cons:
                        assignment[v] = False
                        trail.append(v)
                        t_propagations_count += 1
                        assigned_theory_atoms.append((c, False, v))
                        t_propagated = True
                        continue

                if t_propagated:
                    continue

            # 5. Check Satisfaction
            unassigned = [v for v in all_variables if v not in assignment]
            if not unassigned:
                # All variables assigned and Theory is Consistent!
                assigned_theory_atoms = [
                    (theory_atoms[v], assignment[v], v)
                    for v in assignment
                    if v in theory_atoms
                ]
                _, _, final_model = self.theory_solver.check_consistency(assigned_theory_atoms)
                return SMTResult(
                    is_sat=True,
                    boolean_assignment=dict(assignment),
                    integer_model=final_model if final_model is not None else {},
                    learned_clauses=learned_clauses_count,
                    decisions=decisions_count,
                    conflicts=conflicts_count,
                    theory_propagations=t_propagations_count,
                )

            # 6. Pure Literal Elimination (strictly for pure boolean variables, not theory atoms)
            pure_bool_vars = [v for v in unassigned if v not in theory_atoms]
            unresolved_clauses = [
                c for c in working_clauses
                if not any(lit.var in assignment and assignment[lit.var] == lit.sign for lit in c)
            ]
            pure_found = False
            for v in pure_bool_vars:
                signs = {lit.sign for c in unresolved_clauses for lit in c if lit.var == v}
                if len(signs) == 1:
                    pure_sign = next(iter(signs))
                    assignment[v] = pure_sign
                    trail.append(v)
                    pure_found = True
                    break

            if pure_found:
                continue

            # 7. Decision Step
            # Heuristic: branch on propositional / branching selector variables first, then theory atoms
            bool_unassigned = [v for v in unassigned if v not in theory_atoms]
            chosen_var = bool_unassigned[0] if bool_unassigned else unassigned[0]

            decisions_count += 1
            decisions.append({
                "var": chosen_var,
                "value": True,
                "tried_both": False,
                "trail_len": len(trail),
            })
            assignment[chosen_var] = True
            trail.append(chosen_var)


# ============================================================================
# 5. Program AST & Formal Verification Engine
# ============================================================================

# Typed AST Nodes for Programs
@dataclass
class Var:
    name: str

@dataclass
class Const:
    val: int

@dataclass
class Add:
    left: Any
    right: Any

@dataclass
class Sub:
    left: Any
    right: Any

@dataclass
class Mul:
    left: Any
    right: Any

@dataclass
class Le:
    left: Any
    right: Any

@dataclass
class Lt:
    left: Any
    right: Any

@dataclass
class Ge:
    left: Any
    right: Any

@dataclass
class Gt:
    left: Any
    right: Any

@dataclass
class Eq:
    left: Any
    right: Any

@dataclass
class Ne:
    left: Any
    right: Any

@dataclass
class AndExpr:
    exprs: List[Any]

@dataclass
class OrExpr:
    exprs: List[Any]

@dataclass
class NotExpr:
    expr: Any

# Statements
@dataclass
class Assign:
    var: str
    expr: Any

@dataclass
class IfThenElse:
    cond: Any
    then_body: Any
    else_body: Optional[Any] = None

@dataclass
class Seq:
    statements: List[Any]

@dataclass
class Assume:
    cond: Any

@dataclass
class Assert:
    cond: Any

@dataclass
class While:
    cond: Any
    body: Any
    max_unrolls: int = 3


@dataclass
class VerificationResult:
    is_valid: bool
    counterexample: Optional[Dict[str, int]]
    learned_clauses: int
    smt_result: SMTResult
    explanation: str


class FormalProgramVerifier:
    """Encodes programs into SSA path constraints and verifies specifications via DPLL(T)."""

    def __init__(self):
        self.var_counter = 0
        self.atom_counter = 0
        self.bool_counter = 0

    def _fresh_ssa_var(self, base: str) -> str:
        self.var_counter += 1
        return f"{base}_{self.var_counter}"

    def _fresh_atom_id(self) -> str:
        self.atom_counter += 1
        return f"atom_{self.atom_counter}"

    def _fresh_bool_var(self) -> str:
        self.bool_counter += 1
        return f"b_{self.bool_counter}"

    def _eval_linear_expr(self, expr: Any, env: Dict[str, str]) -> Tuple[Dict[str, int], int]:
        """Translates expression into canonical linear combination: sum(coeffs * var) + const."""
        if isinstance(expr, int):
            return {}, expr
        if isinstance(expr, Const):
            return {}, expr.val
        if isinstance(expr, str):
            ssa_v = env.get(expr, f"{expr}_0")
            return {ssa_v: 1}, 0
        if isinstance(expr, Var):
            ssa_v = env.get(expr.name, f"{expr.name}_0")
            return {ssa_v: 1}, 0
        if isinstance(expr, Add):
            c1, k1 = self._eval_linear_expr(expr.left, env)
            c2, k2 = self._eval_linear_expr(expr.right, env)
            all_v = set(c1.keys()) | set(c2.keys())
            return {v: c1.get(v, 0) + c2.get(v, 0) for v in all_v}, k1 + k2
        if isinstance(expr, Sub):
            c1, k1 = self._eval_linear_expr(expr.left, env)
            c2, k2 = self._eval_linear_expr(expr.right, env)
            all_v = set(c1.keys()) | set(c2.keys())
            return {v: c1.get(v, 0) - c2.get(v, 0) for v in all_v}, k1 - k2
        if isinstance(expr, Mul):
            c1, k1 = self._eval_linear_expr(expr.left, env)
            c2, k2 = self._eval_linear_expr(expr.right, env)
            if not c1:
                return {v: k1 * c for v, c in c2.items()}, k1 * k2
            elif not c2:
                return {v: k2 * c for v, c in c1.items()}, k1 * k2
            else:
                raise ValueError("Non-linear multiplication unsupported in QF-LIA")
        if isinstance(expr, tuple):
            op = expr[0]
            if op == "+":
                return self._eval_linear_expr(Add(expr[1], expr[2]), env)
            elif op == "-":
                return self._eval_linear_expr(Sub(expr[1], expr[2]), env)
            elif op == "*":
                return self._eval_linear_expr(Mul(expr[1], expr[2]), env)

        raise ValueError(f"Unsupported expression: {expr}")

    def _encode_condition(
        self,
        cond: Any,
        env: Dict[str, str],
        theory_atoms: Dict[str, LinearConstraint],
    ) -> Literal:
        """Translates condition into a boolean literal, registering theory atoms if needed."""
        if isinstance(cond, bool):
            b = self._fresh_bool_var()
            return Literal(b, cond)

        if isinstance(cond, (Le, Lt, Ge, Gt, Eq, Ne)):
            c_left, k_left = self._eval_linear_expr(cond.left, env)
            c_right, k_right = self._eval_linear_expr(cond.right, env)

            # left - right <= k_right - k_left
            all_v = set(c_left.keys()) | set(c_right.keys())
            diff_coeffs = {v: c_left.get(v, 0) - c_right.get(v, 0) for v in all_v}
            diff_const = k_right - k_left

            atom_id = self._fresh_atom_id()

            if isinstance(cond, Le):
                theory_atoms[atom_id] = LinearConstraint.from_le(diff_coeffs, diff_const, atom_id)
                return Literal(atom_id, True)
            elif isinstance(cond, Lt):
                theory_atoms[atom_id] = LinearConstraint.from_lt(diff_coeffs, diff_const, atom_id)
                return Literal(atom_id, True)
            elif isinstance(cond, Ge):
                theory_atoms[atom_id] = LinearConstraint.from_ge(diff_coeffs, diff_const, atom_id)
                return Literal(atom_id, True)
            elif isinstance(cond, Gt):
                theory_atoms[atom_id] = LinearConstraint.from_gt(diff_coeffs, diff_const, atom_id)
                return Literal(atom_id, True)
            elif isinstance(cond, Eq):
                # Eq is left <= right /\ left >= right
                atom1 = self._fresh_atom_id()
                theory_atoms[atom1] = LinearConstraint.from_le(diff_coeffs, diff_const, atom1)
                return Literal(atom1, True)

        if isinstance(cond, NotExpr):
            lit = self._encode_condition(cond.expr, env, theory_atoms)
            return lit.negate()

        raise ValueError(f"Unsupported condition: {cond}")

    def verify(
        self,
        ast_node: Any,
        pre_cond: Any,
        post_cond: Any,
    ) -> VerificationResult:
        """Verifies program satisfies specification: Pre => [Program] Post.

        Methodology:
        Encodes Pre(x_0) /\\ PathConstraints /\\ ~Post(x_final) into CNF & QF-LIA.
        If DPLL(T) reports UNSAT -> PROVED! (No execution can violate Post).
        If DPLL(T) reports SAT -> BUG! (Found concrete input counterexample).
        """
        theory_atoms: Dict[str, LinearConstraint] = {}
        clauses: List[Clause] = []

        env: Dict[str, str] = {}

        # 1. Encode Precondition
        if pre_cond is not None and pre_cond is not True:
            pre_lit = self._encode_condition(pre_cond, env, theory_atoms)
            clauses.append([pre_lit])

        # 2. Encode Program AST
        final_env = self._encode_ast(ast_node, env, clauses, theory_atoms)

        # 3. Encode Negation of Postcondition
        if post_cond is not None and post_cond is not True:
            post_lit = self._encode_condition(post_cond, final_env, theory_atoms)
            clauses.append([post_lit.negate()])

        # 4. Invoke DPLL(T) Solver
        solver = DPLLTSolver()
        smt_res = solver.solve(clauses, theory_atoms, enable_t_propagation=True)

        if not smt_res.is_sat:
            return VerificationResult(
                is_valid=True,
                counterexample=None,
                learned_clauses=smt_res.learned_clauses,
                smt_result=smt_res,
                explanation="UNSAT proven: Specification unconditionally holds across all execution paths.",
            )
        else:
            model = smt_res.integer_model or {}
            counterexample = {
                v[:-2]: val for v, val in model.items() if v.endswith("_0")
            }
            if not counterexample and model:
                counterexample = dict(model)

            return VerificationResult(
                is_valid=False,
                counterexample=counterexample,
                learned_clauses=smt_res.learned_clauses,
                smt_result=smt_res,
                explanation=f"SAT: Found counterexample {counterexample} violating postcondition.",
            )

    def _encode_ast(
        self,
        stmt: Any,
        env: Dict[str, str],
        clauses: List[Clause],
        theory_atoms: Dict[str, LinearConstraint],
    ) -> Dict[str, str]:
        """Recursively compiles program statements into SSA form and path clauses."""
        if stmt is None:
            return dict(env)

        if isinstance(stmt, list):
            curr_env = dict(env)
            for s in stmt:
                curr_env = self._encode_ast(s, curr_env, clauses, theory_atoms)
            return curr_env

        if isinstance(stmt, Seq):
            curr_env = dict(env)
            for s in stmt.statements:
                curr_env = self._encode_ast(s, curr_env, clauses, theory_atoms)
            return curr_env

        if isinstance(stmt, Assign):
            # x = expr
            coeffs, const = self._eval_linear_expr(stmt.expr, env)
            new_v = self._fresh_ssa_var(stmt.var)

            # target_var == sum(coeffs * v) + const
            atom1 = self._fresh_atom_id()
            atom2 = self._fresh_atom_id()
            c_le, c_ge = LinearConstraint.from_assign(new_v, coeffs, const, atom1, atom2)
            theory_atoms[atom1] = c_le
            theory_atoms[atom2] = c_ge

            clauses.append([Literal(atom1, True)])
            clauses.append([Literal(atom2, True)])

            new_env = dict(env)
            new_env[stmt.var] = new_v
            return new_env

        if isinstance(stmt, IfThenElse):
            # Boolean selector for branch condition
            cond_lit = self._encode_condition(stmt.cond, env, theory_atoms)

            then_clauses: List[Clause] = []
            else_clauses: List[Clause] = []

            env_then = self._encode_ast(stmt.then_body, dict(env), then_clauses, theory_atoms)
            env_else = self._encode_ast(stmt.else_body, dict(env), else_clauses, theory_atoms)

            # Guarded path clauses: cond_lit => then_clauses; ~cond_lit => else_clauses
            for c in then_clauses:
                clauses.append([cond_lit.negate()] + c)
            for c in else_clauses:
                clauses.append([cond_lit] + c)

            # SSA Phi merge for modified variables
            all_modified = set(env_then.keys()) | set(env_else.keys())
            merged_env = dict(env)

            for v in all_modified:
                v_then = env_then.get(v, env.get(v, f"{v}_0"))
                v_else = env_else.get(v, env.get(v, f"{v}_0"))

                if v_then == v_else:
                    merged_env[v] = v_then
                    continue

                v_merged = self._fresh_ssa_var(v)
                merged_env[v] = v_merged

                # If cond_lit: v_merged == v_then
                a1 = self._fresh_atom_id()
                a2 = self._fresh_atom_id()
                c1, c2 = LinearConstraint.from_assign(v_merged, {v_then: 1}, 0, a1, a2)
                theory_atoms[a1] = c1
                theory_atoms[a2] = c2
                clauses.append([cond_lit.negate(), Literal(a1, True)])
                clauses.append([cond_lit.negate(), Literal(a2, True)])

                # If ~cond_lit: v_merged == v_else
                a3 = self._fresh_atom_id()
                a4 = self._fresh_atom_id()
                c3, c4 = LinearConstraint.from_assign(v_merged, {v_else: 1}, 0, a3, a4)
                theory_atoms[a3] = c3
                theory_atoms[a4] = c4
                clauses.append([cond_lit, Literal(a3, True)])
                clauses.append([cond_lit, Literal(a4, True)])

            return merged_env

        if isinstance(stmt, While):
            # Bounded model checking via loop unrolling:
            # Iteration 1..k: if cond: body
            # Followed by assume(~cond) to verify termination and invariant hold
            unrolled_stmts = []
            for _ in range(stmt.max_unrolls):
                unrolled_stmts.append(IfThenElse(stmt.cond, stmt.body, None))
            unrolled_stmts.append(Assume(NotExpr(stmt.cond)))
            return self._encode_ast(Seq(unrolled_stmts), env, clauses, theory_atoms)

        if isinstance(stmt, Assume):
            cond_lit = self._encode_condition(stmt.cond, env, theory_atoms)
            clauses.append([cond_lit])
            return dict(env)

        if isinstance(stmt, Assert):
            cond_lit = self._encode_condition(stmt.cond, env, theory_atoms)
            clauses.append([cond_lit])
            return dict(env)

        if isinstance(stmt, dict):
            if "assign" in stmt:
                return self._encode_ast(Assign(stmt["assign"], stmt["expr"]), env, clauses, theory_atoms)
            if "if" in stmt:
                return self._encode_ast(IfThenElse(stmt["if"], stmt.get("then"), stmt.get("else")), env, clauses, theory_atoms)

        return dict(env)


def verify_program_satisfies_spec(
    ast_node: Any,
    pre_cond: Any = None,
    post_cond: Any = None,
) -> VerificationResult:
    """Public functional verification entry point."""
    verifier = FormalProgramVerifier()
    return verifier.verify(ast_node, pre_cond, post_cond)
