"""Craig Interpolation Engine & Inductive Invariant Synthesizer.

Provenance: ADVISOR_AGENT

Theoretical Foundations:
1. Craig's Interpolation Theorem (William Craig, 1957):
   Given formulas A and B such that A and B is mutually inconsistent (A and B |= False),
   there exists an interpolant formula I such that:
   (i)   A => I
   (ii)  I and B == False (i.e., I => not B)
   (iii) Symbol(I) subseteq (Symbol(A) intersect Symbol(B))

2. McMillan's Propositional Interpolation Algorithm (Ken McMillan, 2003):
   Extracts Craig interpolants inductively from a resolution refutation proof DAG/tree.
   - For leaf clause C in A: [C] = C|_B (subclause with literals occurring in B, or False if none)
   - For leaf clause C in B: [C] = True
   - For resolvent C with pivot p from C1 and C2:
     - if p not in vars(B): [C] = [C1] \/ [C2]
     - if p in vars(B):     [C] = [C1] /\ [C2]
   At the root empty clause square, [square] is a valid Craig interpolant.

3. Farkas' Lemma for Linear Real/Integer Arithmetic Constraints:
   For inconsistent systems of linear inequalities A and B:
   Exists non-negative multipliers lambda >= 0 such that sum lambda_i g_i(x) = c > 0.
   Separating the A-portion multipliers yields a linear separator I(y) <= 0
   whose non-zero coefficients strictly belong to Symbol(A) intersect Symbol(B).

4. Inductive Loop Invariant Synthesis:
   Given Init(x), Transition(x, x'), and Safety Bad(x):
   Symbolic trace unrolling builds A (reachable prefix) and B (pre-image of Bad).
   Craig interpolants generalize counterexamples, iteratively strengthening I_{k+1}
   until consecution I(x) /\ T(x, x') => I(x') is achieved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import math
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, Union


# ============================================================================
# Section 1: Propositional Logic AST & Expressions
# ============================================================================

class BoolExpr:
    """Abstract base class for propositional formulas."""

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        raise NotImplementedError

    def vars(self) -> Set[str]:
        raise NotImplementedError

    def simplify(self) -> BoolExpr:
        return self

    def to_code(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.to_code()


@dataclass(frozen=True)
class BoolConst(BoolExpr):
    val: bool

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        return self.val

    def vars(self) -> Set[str]:
        return set()

    def simplify(self) -> BoolExpr:
        return self

    def to_code(self) -> str:
        return "True" if self.val else "False"


@dataclass(frozen=True)
class BoolVar(BoolExpr):
    name: str

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        if self.name not in assignment:
            raise KeyError(f"Variable '{self.name}' not bound in assignment {assignment}")
        return assignment[self.name]

    def vars(self) -> Set[str]:
        return {self.name}

    def simplify(self) -> BoolExpr:
        return self

    def to_code(self) -> str:
        return self.name


@dataclass(frozen=True)
class BoolNot(BoolExpr):
    sub: BoolExpr

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        return not self.sub.evaluate(assignment)

    def vars(self) -> Set[str]:
        return self.sub.vars()

    def simplify(self) -> BoolExpr:
        simp_sub = self.sub.simplify()
        if isinstance(simp_sub, BoolConst):
            return BoolConst(not simp_sub.val)
        if isinstance(simp_sub, BoolNot):
            return simp_sub.sub  # not not x -> x
        return BoolNot(simp_sub)

    def to_code(self) -> str:
        if isinstance(self.sub, BoolVar):
            return f"~{self.sub.name}"
        return f"~({self.sub.to_code()})"


@dataclass(frozen=True)
class BoolAnd(BoolExpr):
    args: Tuple[BoolExpr, ...]

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        return all(arg.evaluate(assignment) for arg in self.args)

    def vars(self) -> Set[str]:
        res: Set[str] = set()
        for arg in self.args:
            res.update(arg.vars())
        return res

    def simplify(self) -> BoolExpr:
        flattened: List[BoolExpr] = []
        for arg in self.args:
            simp = arg.simplify()
            if isinstance(simp, BoolConst):
                if not simp.val:
                    return BoolConst(False)
                # True in And can be omitted
                continue
            elif isinstance(simp, BoolAnd):
                flattened.extend(simp.args)
            else:
                flattened.append(simp)

        # Remove duplicates while preserving determinism
        unique: List[BoolExpr] = []
        seen_str: Set[str] = set()
        for item in flattened:
            rep = repr(item)
            if rep not in seen_str:
                seen_str.add(rep)
                unique.append(item)

        # Check for contradiction: x and ~x
        pos_vars: Set[str] = set()
        neg_vars: Set[str] = set()
        for item in unique:
            if isinstance(item, BoolVar):
                pos_vars.add(item.name)
            elif isinstance(item, BoolNot) and isinstance(item.sub, BoolVar):
                neg_vars.add(item.sub.name)
        if pos_vars & neg_vars:
            return BoolConst(False)

        if not unique:
            return BoolConst(True)
        if len(unique) == 1:
            return unique[0]
        return BoolAnd(tuple(unique))

    def to_code(self) -> str:
        return "(" + " & ".join(arg.to_code() for arg in self.args) + ")"


@dataclass(frozen=True)
class BoolOr(BoolExpr):
    args: Tuple[BoolExpr, ...]

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        return any(arg.evaluate(assignment) for arg in self.args)

    def vars(self) -> Set[str]:
        res: Set[str] = set()
        for arg in self.args:
            res.update(arg.vars())
        return res

    def simplify(self) -> BoolExpr:
        flattened: List[BoolExpr] = []
        for arg in self.args:
            simp = arg.simplify()
            if isinstance(simp, BoolConst):
                if simp.val:
                    return BoolConst(True)
                # False in Or can be omitted
                continue
            elif isinstance(simp, BoolOr):
                flattened.extend(simp.args)
            else:
                flattened.append(simp)

        # Remove duplicates
        unique: List[BoolExpr] = []
        seen_str: Set[str] = set()
        for item in flattened:
            rep = repr(item)
            if rep not in seen_str:
                seen_str.add(rep)
                unique.append(item)

        # Check for tautology: x or ~x
        pos_vars: Set[str] = set()
        neg_vars: Set[str] = set()
        for item in unique:
            if isinstance(item, BoolVar):
                pos_vars.add(item.name)
            elif isinstance(item, BoolNot) and isinstance(item.sub, BoolVar):
                neg_vars.add(item.sub.name)
        if pos_vars & neg_vars:
            return BoolConst(True)

        if not unique:
            return BoolConst(False)
        if len(unique) == 1:
            return unique[0]
        return BoolOr(tuple(unique))

    def to_code(self) -> str:
        return "(" + " | ".join(arg.to_code() for arg in self.args) + ")"


# ============================================================================
# Section 2: Propositional Clauses, Resolution & McMillan Interpolation
# ============================================================================

@dataclass(frozen=True)
class PropLiteral:
    var: str
    negated: bool = False

    def negate(self) -> PropLiteral:
        return PropLiteral(self.var, not self.negated)

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        val = assignment[self.var]
        return not val if self.negated else val

    def to_expr(self) -> BoolExpr:
        return BoolNot(BoolVar(self.var)) if self.negated else BoolVar(self.var)

    def __str__(self) -> str:
        return f"~{self.var}" if self.negated else self.var

    def __repr__(self) -> str:
        return str(self)


@dataclass(frozen=True)
class PropClause:
    literals: FrozenSet[PropLiteral]

    @classmethod
    def from_literals(cls, *lits: Union[PropLiteral, str]) -> PropClause:
        items = set()
        for l in lits:
            if isinstance(l, str):
                if l.startswith("~") or l.startswith("!"):
                    items.add(PropLiteral(l[1:], negated=True))
                else:
                    items.add(PropLiteral(l, negated=False))
            else:
                items.add(l)
        return cls(frozenset(items))

    @property
    def is_empty(self) -> bool:
        return len(self.literals) == 0

    @property
    def vars(self) -> Set[str]:
        return {l.var for l in self.literals}

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        # A clause is satisfied if at least one literal is true under assignment
        return any(lit.evaluate(assignment) for lit in self.literals)

    def resolve(self, other: PropClause, pivot: str) -> Optional[PropClause]:
        pos = PropLiteral(pivot, False)
        neg = PropLiteral(pivot, True)
        if pos in self.literals and neg in other.literals:
            res = (self.literals - {pos}) | (other.literals - {neg})
            return PropClause(frozenset(res))
        elif neg in self.literals and pos in other.literals:
            res = (self.literals - {neg}) | (other.literals - {pos})
            return PropClause(frozenset(res))
        return None

    def __str__(self) -> str:
        if self.is_empty:
            return "[]"
        return " | ".join(str(l) for l in sorted(self.literals, key=lambda x: (x.var, x.negated)))

    def __repr__(self) -> str:
        return f"Clause({self})"


@dataclass
class PropCNF:
    clauses: List[PropClause]

    @property
    def vars(self) -> Set[str]:
        v: Set[str] = set()
        for c in self.clauses:
            v.update(c.vars)
        return v

    def evaluate(self, assignment: Dict[str, bool]) -> bool:
        return all(c.evaluate(assignment) for c in self.clauses)


@dataclass
class ResolutionNode:
    """Node in a resolution refutation derivation tree."""
    clause: PropClause
    source: str  # 'A', 'B', or 'RESOLVE'
    pivot: Optional[str] = None
    left: Optional[ResolutionNode] = None
    right: Optional[ResolutionNode] = None
    annotated_interpolant: Optional[BoolExpr] = None


class McMillanPropositionalInterpolator:
    """Implements McMillan's (2003) Propositional Craig Interpolation algorithm."""

    @staticmethod
    def _dpll_prove_unsat(
        clauses_A: List[PropClause],
        clauses_B: List[PropClause],
        all_clauses: List[PropClause],
        variables: List[str],
        var_idx: int,
        assignment: Dict[str, bool],
    ) -> Optional[ResolutionNode]:
        """DPLL search returning an exact ResolutionNode refutation tree if unsatisfiable."""
        # 1. Check if any original clause is already falsified under partial assignment
        for c in all_clauses:
            # A clause is falsified if all its literals are bound to False
            if all(lit.var in assignment and not lit.evaluate(assignment) for lit in c.literals):
                src = "A" if c in clauses_A else "B"
                return ResolutionNode(clause=c, source=src)

        # 2. Check if all clauses are already satisfied
        if all(c.evaluate(assignment) for c in all_clauses if all(lit.var in assignment for lit in c.literals)):
            if len(assignment) == len(variables):
                # Satisfying assignment found -> CNF is satisfiable!
                return None

        if var_idx >= len(variables):
            return None

        var = variables[var_idx]

        # Branch x = True
        assignment[var] = True
        n_true = McMillanPropositionalInterpolator._dpll_prove_unsat(
            clauses_A, clauses_B, all_clauses, variables, var_idx + 1, assignment
        )
        del assignment[var]

        if n_true is None:
            # Found satisfying assignment on True branch
            return None

        # Optimization: if the conflict clause doesn't even contain ~var, var wasn't relevant
        if PropLiteral(var, negated=True) not in n_true.clause.literals:
            return n_true

        # Branch x = False
        assignment[var] = False
        n_false = McMillanPropositionalInterpolator._dpll_prove_unsat(
            clauses_A, clauses_B, all_clauses, variables, var_idx + 1, assignment
        )
        del assignment[var]

        if n_false is None:
            # Found satisfying assignment on False branch
            return None

        # Optimization: if the conflict clause doesn't even contain var
        if PropLiteral(var, negated=False) not in n_false.clause.literals:
            return n_false

        # Resolve n_true and n_false on pivot 'var'
        resolvent = n_true.clause.resolve(n_false.clause, var)
        if resolvent is None:
            # Fallback to one of the nodes
            return n_true

        return ResolutionNode(
            clause=resolvent,
            source="RESOLVE",
            pivot=var,
            left=n_true,
            right=n_false,
        )

    @classmethod
    def interpolate(
        cls,
        A: Union[PropCNF, List[PropClause]],
        B: Union[PropCNF, List[PropClause]],
    ) -> BoolExpr:
        """Computes Craig Interpolant I for propositional formulas A and B using McMillan's algorithm.

        Craig Conditions:
        1. A => I
        2. I /\ B |= False
        3. Symbol(I) subseteq Symbol(A) intersect Symbol(B)
        """
        clauses_A = A.clauses if isinstance(A, PropCNF) else list(A)
        clauses_B = B.clauses if isinstance(B, PropCNF) else list(B)

        vars_A: Set[str] = set()
        for c in clauses_A:
            vars_A.update(c.vars)

        vars_B: Set[str] = set()
        for c in clauses_B:
            vars_B.update(c.vars)

        all_vars = sorted(vars_A | vars_B)
        all_clauses = clauses_A + clauses_B

        # Refutation proof tree derivation
        proof_root = cls._dpll_prove_unsat(clauses_A, clauses_B, all_clauses, all_vars, 0, {})
        if proof_root is None or not proof_root.clause.is_empty:
            raise ValueError(
                "Formulas A and B are mutually consistent (satisfiable). "
                "Craig's Interpolation Theorem requires A and B to be mutually inconsistent (A /\\ B |= False)."
            )

        # Label resolution tree with McMillan's partial interpolants
        def label_tree(node: ResolutionNode) -> BoolExpr:
            if node.source == "A":
                # Literals in leaf whose variables appear in B
                shared_lits = [lit for lit in node.clause.literals if lit.var in vars_B]
                if not shared_lits:
                    node.annotated_interpolant = BoolConst(False)
                elif len(shared_lits) == 1:
                    node.annotated_interpolant = shared_lits[0].to_expr()
                else:
                    node.annotated_interpolant = BoolOr(tuple(l.to_expr() for l in shared_lits))
                return node.annotated_interpolant

            elif node.source == "B":
                node.annotated_interpolant = BoolConst(True)
                return node.annotated_interpolant

            elif node.source == "RESOLVE":
                assert node.left is not None and node.right is not None
                left_interp = label_tree(node.left)
                right_interp = label_tree(node.right)
                pivot = node.pivot
                if pivot is not None and pivot not in vars_B:
                    # Pivot is local to A: [C] = [C1] \/ [C2]
                    node.annotated_interpolant = BoolOr((left_interp, right_interp))
                else:
                    # Pivot is in B (shared or local to B): [C] = [C1] /\ [C2]
                    node.annotated_interpolant = BoolAnd((left_interp, right_interp))
                return node.annotated_interpolant

            return BoolConst(False)

        raw_interpolant = label_tree(proof_root)
        simplified = raw_interpolant.simplify()

        # Sanity check: condition 3 must strictly hold
        shared_vars = vars_A & vars_B
        interp_vars = simplified.vars()
        assert interp_vars.issubset(shared_vars), (
            f"Interpolant variables {interp_vars} violate condition 3: "
            f"not subset of shared variables {shared_vars}"
        )

        return simplified

    @staticmethod
    def verify_craig_conditions(
        A: Union[PropCNF, List[PropClause]],
        B: Union[PropCNF, List[PropClause]],
        I: BoolExpr,
    ) -> Dict[str, Any]:
        """Exhaustively verifies Craig's 3 conditions across all truth assignments."""
        clauses_A = A.clauses if isinstance(A, PropCNF) else list(A)
        clauses_B = B.clauses if isinstance(B, PropCNF) else list(B)

        vars_A = {v for c in clauses_A for v in c.vars}
        vars_B = {v for c in clauses_B for v in c.vars}
        shared_vars = vars_A & vars_B
        all_vars = sorted(vars_A | vars_B)

        # Condition 3: Symbol(I) subseteq Symbol(A) intersect Symbol(B)
        symbols_I = I.vars()
        cond3 = symbols_I.issubset(shared_vars)

        cond1_holds = True
        cond2_holds = True
        num_models_A = 0
        num_models_B = 0

        # Check all 2^N valuations
        num_vars = len(all_vars)
        for i in range(1 << num_vars):
            assignment = {all_vars[j]: bool((i >> j) & 1) for j in range(num_vars)}
            sat_A = all(c.evaluate(assignment) for c in clauses_A)
            sat_B = all(c.evaluate(assignment) for c in clauses_B)
            sat_I = I.evaluate(assignment)

            if sat_A:
                num_models_A += 1
                if not sat_I:
                    # A => I violated!
                    cond1_holds = False

            if sat_B:
                num_models_B += 1
                if sat_I:
                    # I /\ B |= False violated!
                    cond2_holds = False

        return {
            "condition_1_A_implies_I": cond1_holds,
            "condition_2_I_and_B_unsat": cond2_holds,
            "condition_3_shared_symbols": cond3,
            "shared_symbols": sorted(shared_vars),
            "interpolant_symbols": sorted(symbols_I),
            "models_A": num_models_A,
            "models_B": num_models_B,
            "valid": cond1_holds and cond2_holds and cond3,
        }


# ============================================================================
# Section 3: Linear Arithmetic Constraints & Farkas Interpolation
# ============================================================================

@dataclass(frozen=True)
class LinearConstraint:
    """Represents a linear inequality constraint sum_k a_k * x_k <= bound."""
    coeffs: Dict[str, Fraction]
    bound: Fraction
    op: str = "<="  # Normalized to <=

    @classmethod
    def create(
        cls,
        coeffs: Dict[str, Union[int, float, Fraction]],
        bound: Union[int, float, Fraction],
        op: str = "<=",
    ) -> LinearConstraint:
        frac_coeffs: Dict[str, Fraction] = {}
        for k, v in coeffs.items():
            f = Fraction(v).limit_denominator(1_000_000)
            if f != 0:
                frac_coeffs[k] = f
        frac_bound = Fraction(bound).limit_denominator(1_000_000)

        if op == ">=":
            # Convert sum a_k x_k >= b to sum (-a_k) x_k <= -b
            frac_coeffs = {k: -v for k, v in frac_coeffs.items()}
            frac_bound = -frac_bound
            op = "<="

        return cls(frac_coeffs, frac_bound, "<=").canonical()

    @property
    def vars(self) -> Set[str]:
        return {k for k, v in self.coeffs.items() if v != 0}

    def eval(self, point: Dict[str, Union[int, float, Fraction]]) -> bool:
        lhs = sum(self.coeffs[k] * Fraction(point.get(k, 0)) for k in self.coeffs)
        return lhs <= self.bound

    def evaluate_lhs(self, point: Dict[str, Union[int, float, Fraction]]) -> Fraction:
        return sum(self.coeffs[k] * Fraction(point.get(k, 0)) for k in self.coeffs)

    def canonical(self) -> LinearConstraint:
        """Reduces coefficients and bound to canonical integer form where possible."""
        clean_coeffs = {k: v for k, v in self.coeffs.items() if v != 0}
        if not clean_coeffs:
            return LinearConstraint({}, self.bound, self.op)

        # Find LCM of denominators
        dens = [v.denominator for v in clean_coeffs.values()] + [self.bound.denominator]
        lcm_den = dens[0]
        for d in dens[1:]:
            lcm_den = (lcm_den * d) // math.gcd(lcm_den, d)

        # Scale to integers
        int_coeffs = {k: int(v * lcm_den) for k, v in clean_coeffs.items()}
        int_bound = int(self.bound * lcm_den)

        # Divide by GCD of all terms
        gcd_val = abs(int_bound)
        for v in int_coeffs.values():
            gcd_val = math.gcd(gcd_val, abs(v))

        if gcd_val > 1:
            int_coeffs = {k: Fraction(v // gcd_val) for k, v in int_coeffs.items()}
            int_bound_frac = Fraction(int_bound // gcd_val)
        else:
            int_coeffs = {k: Fraction(v) for k, v in int_coeffs.items()}
            int_bound_frac = Fraction(int_bound)

        return LinearConstraint(int_coeffs, int_bound_frac, self.op)

    def negate(self, delta: Fraction = Fraction(1)) -> LinearConstraint:
        """Negation: ~(sum a_k x_k <= b) is sum (-a_k) x_k <= -b - delta."""
        neg_coeffs = {k: -v for k, v in self.coeffs.items()}
        neg_bound = -self.bound - delta
        return LinearConstraint.create(neg_coeffs, neg_bound, "<=")

    def to_string(self) -> str:
        if not self.coeffs:
            return f"0 <= {self.bound}"
        terms = []
        for k in sorted(self.coeffs.keys()):
            coeff = self.coeffs[k]
            sign = "+ " if coeff > 0 else "- "
            val = abs(coeff)
            val_str = "" if val == 1 else f"{val}*"
            terms.append(f"{sign}{val_str}{k}")
        res = " ".join(terms)
        if res.startswith("+ "):
            res = res[2:]
        return f"{res} <= {self.bound}"

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"LinearConstraint({self.to_string()})"


@dataclass
class LinearSystem:
    constraints: List[LinearConstraint]

    @property
    def vars(self) -> Set[str]:
        v: Set[str] = set()
        for c in self.constraints:
            v.update(c.vars)
        return v


@dataclass
class _TrackedConstraint:
    coeffs: Dict[str, Fraction]
    bound: Fraction
    multipliers: Dict[int, Fraction]


class FarkasLinearInterpolator:
    """Computes Craig Interpolants for Linear Constraints via Farkas' Lemma.

    Farkas' Lemma states that for an infeasible system sum a_{i, k} x_k <= b_i,
    there exist non-negative multipliers lambda_i >= 0 such that:
        sum_i lambda_i * a_{i, k} = 0  for all variables k
        sum_i lambda_i * (-b_i) = c > 0 (or sum_i lambda_i * b_i < 0)
    
    The interpolant I is synthesized from the A-portion multipliers:
        sum_{i in A} lambda_i * (sum_k a_{i, k} x_k) <= sum_{i in A} lambda_i * b_i.
    By Farkas duality, non-shared variables have zero coefficients in I.
    """

    @classmethod
    def find_farkas_multipliers(
        cls,
        constraints: List[LinearConstraint],
    ) -> Optional[Dict[int, Fraction]]:
        """Finds non-negative Farkas multipliers proving infeasibility of the constraints.

        Uses Fourier-Motzkin variable elimination with exact multiplier vector tracking.
        Returns multiplier dict {constraint_idx: Fraction} if infeasible, else None.
        """
        tracked: List[_TrackedConstraint] = [
            _TrackedConstraint(
                coeffs=dict(c.coeffs),
                bound=c.bound,
                multipliers={idx: Fraction(1)},
            )
            for idx, c in enumerate(constraints)
        ]

        # Collect all variables
        all_vars = sorted({v for c in constraints for v in c.vars})

        for v in all_vars:
            # Check if any constraint in the current pool is an immediate contradiction
            for tc in tracked:
                if not tc.coeffs and tc.bound < 0:
                    return tc.multipliers

            pos_list: List[_TrackedConstraint] = []
            neg_list: List[_TrackedConstraint] = []
            zero_list: List[_TrackedConstraint] = []

            for tc in tracked:
                coeff = tc.coeffs.get(v, Fraction(0))
                if coeff > 0:
                    pos_list.append(tc)
                elif coeff < 0:
                    neg_list.append(tc)
                else:
                    zero_list.append(tc)

            new_tracked: List[_TrackedConstraint] = list(zero_list)

            # Eliminate v by pairing positive and negative coefficients
            for p in pos_list:
                for q in neg_list:
                    wp = abs(q.coeffs[v])
                    wq = p.coeffs[v]

                    # Combined coeffs
                    comb_coeffs: Dict[str, Fraction] = {}
                    comb_vars = set(p.coeffs.keys()) | set(q.coeffs.keys())
                    for u in comb_vars:
                        if u == v:
                            continue
                        val = wp * p.coeffs.get(u, Fraction(0)) + wq * q.coeffs.get(u, Fraction(0))
                        if val != 0:
                            comb_coeffs[u] = val

                    comb_bound = wp * p.bound + wq * q.bound

                    # Multipliers combination
                    comb_mult: Dict[int, Fraction] = {}
                    for idx in set(p.multipliers.keys()) | set(q.multipliers.keys()):
                        m_val = wp * p.multipliers.get(idx, Fraction(0)) + wq * q.multipliers.get(idx, Fraction(0))
                        if m_val != 0:
                            comb_mult[idx] = m_val

                    # Simplification
                    comb_c = _TrackedConstraint(comb_coeffs, comb_bound, comb_mult)
                    new_tracked.append(comb_c)

                    # Check for contradiction
                    if not comb_coeffs and comb_bound < 0:
                        return comb_mult

            tracked = new_tracked

        # Final check across all eliminated constraints
        for tc in tracked:
            if not tc.coeffs and tc.bound < 0:
                return tc.multipliers

        return None

    @classmethod
    def interpolate(
        cls,
        A: Union[LinearSystem, List[LinearConstraint]],
        B: Union[LinearSystem, List[LinearConstraint]],
    ) -> LinearConstraint:
        """Synthesizes Craig Interpolant I for linear systems A and B using Farkas' Lemma."""
        constraints_A = A.constraints if isinstance(A, LinearSystem) else list(A)
        constraints_B = B.constraints if isinstance(B, LinearSystem) else list(B)

        num_A = len(constraints_A)
        num_B = len(constraints_B)
        all_constraints = constraints_A + constraints_B

        vars_A = {v for c in constraints_A for v in c.vars}
        vars_B = {v for c in constraints_B for v in c.vars}
        shared_vars = vars_A & vars_B

        multipliers = cls.find_farkas_multipliers(all_constraints)
        if multipliers is None:
            raise ValueError(
                "Linear constraint systems A and B are consistent (satisfiable). "
                "Craig interpolation requires A and B to be mutually inconsistent."
            )

        # Extract the A-portion multipliers
        interp_coeffs: Dict[str, Fraction] = {}
        interp_bound = Fraction(0)

        for i in range(num_A):
            m = multipliers.get(i, Fraction(0))
            if m > 0:
                c = constraints_A[i]
                interp_bound += m * c.bound
                for var, coeff in c.coeffs.items():
                    interp_coeffs[var] = interp_coeffs.get(var, Fraction(0)) + m * coeff

        # Farkas duality theorem guarantees coefficients of non-shared variables cancel out to 0
        clean_interp_coeffs: Dict[str, Fraction] = {}
        for var, coeff in interp_coeffs.items():
            if coeff != 0 and var in shared_vars:
                clean_interp_coeffs[var] = coeff

        # Construct candidate interpolant
        interpolant = LinearConstraint.create(clean_interp_coeffs, interp_bound, "<=")
        return interpolant

    @classmethod
    def verify_craig_conditions(
        cls,
        A: Union[LinearSystem, List[LinearConstraint]],
        B: Union[LinearSystem, List[LinearConstraint]],
        I: LinearConstraint,
        delta: Fraction = Fraction(1),
    ) -> Dict[str, Any]:
        """Formally verifies Craig conditions for linear arithmetic interpolant I.

        1. A => I (i.e. A /\ ~I is infeasible)
        2. I /\ B |= False (i.e. {I} U B is infeasible)
        3. Symbol(I) subseteq Symbol(A) intersect Symbol(B)
        """
        constraints_A = A.constraints if isinstance(A, LinearSystem) else list(A)
        constraints_B = B.constraints if isinstance(B, LinearSystem) else list(B)

        vars_A = {v for c in constraints_A for v in c.vars}
        vars_B = {v for c in constraints_B for v in c.vars}
        shared_vars = vars_A & vars_B

        # Condition 3: Symbol(I) subseteq Symbol(A) intersect Symbol(B)
        symbols_I = I.vars
        cond3 = symbols_I.issubset(shared_vars)

        # Condition 1: A => I <=> A /\ ~I is infeasible
        neg_I = I.negate(delta=delta)
        proof_cond1 = cls.find_farkas_multipliers(constraints_A + [neg_I])
        cond1 = proof_cond1 is not None

        # Condition 2: I /\ B |= False <=> {I} U B is infeasible
        proof_cond2 = cls.find_farkas_multipliers([I] + constraints_B)
        cond2 = proof_cond2 is not None

        return {
            "condition_1_A_implies_I": cond1,
            "condition_2_I_and_B_unsat": cond2,
            "condition_3_shared_symbols": cond3,
            "shared_symbols": sorted(shared_vars),
            "interpolant_symbols": sorted(symbols_I),
            "valid": cond1 and cond2 and cond3,
        }


# ============================================================================
# Section 4: Inductive Loop Invariant Synthesizer
# ============================================================================

@dataclass
class LoopProgram:
    """Specification of a loop transition system.

    Variables: state variables V
    Init: constraints over V
    Transition: relation over V and V_prime (e.g., 'x' and 'x_prime')
    PostCondition: safety constraints over V
    """
    name: str
    variables: List[str]
    init_constraints: List[LinearConstraint]
    transition_constraints: List[LinearConstraint]
    post_condition: List[LinearConstraint]
    bad_constraints: Optional[List[LinearConstraint]] = None

    def get_bad_constraints(self, delta: Fraction = Fraction(1)) -> List[LinearConstraint]:
        if self.bad_constraints is not None:
            return self.bad_constraints
        # Auto-negate post condition
        return [c.negate(delta=delta) for c in self.post_condition]


@dataclass
class InvariantResult:
    """Output receipt of the Craig Inductive Invariant Synthesizer."""
    status: str  # 'VERIFIED_INDUCTIVE', 'SAFETY_VIOLATION_AT_INIT', 'MAX_ITERATIONS'
    loop_name: str
    invariant: List[LinearConstraint]
    unroll_depth: int
    proof_certificate: Dict[str, Any]
    counterexamples: List[Dict[str, Any]] = field(default_factory=list)


class InductiveLoopInvariantSynthesizer:
    """Synthesizes inductive loop invariants via Craig Interpolation and Counterexample Refinement."""

    def __init__(self, max_unroll_depth: int = 8, delta: Fraction = Fraction(1)):
        self.max_unroll_depth = max_unroll_depth
        self.delta = delta

    @staticmethod
    def _rename_constraint(c: LinearConstraint, rename_map: Dict[str, str]) -> LinearConstraint:
        new_coeffs = {}
        for k, v in c.coeffs.items():
            new_var = rename_map.get(k, k)
            new_coeffs[new_var] = v
        return LinearConstraint.create(new_coeffs, c.bound, c.op)

    def synthesize(self, program: LoopProgram) -> InvariantResult:
        """Synthesizes and certifies an inductive loop invariant for the given LoopProgram."""
        vars_list = program.variables
        bad_constraints = program.get_bad_constraints(self.delta)

        # 1. Base check: Initiation vs Safety
        for bad_c in bad_constraints:
            check_init = FarkasLinearInterpolator.find_farkas_multipliers(program.init_constraints + [bad_c])
            if check_init is None:
                return InvariantResult(
                    status="SAFETY_VIOLATION_AT_INIT",
                    loop_name=program.name,
                    invariant=[],
                    unroll_depth=0,
                    proof_certificate={"error": "Init states directly violate post_condition"},
                )

        candidate_invariants: List[LinearConstraint] = []
        counterexample_traces: List[Dict[str, Any]] = []

        for k in range(1, self.max_unroll_depth + 1):
            # Build unrolled path formula
            # Step t variables: var_{t}
            A_constraints: List[LinearConstraint] = []

            # Init at step 0
            map_0 = {v: f"{v}_0" for v in vars_list}
            for init_c in program.init_constraints:
                A_constraints.append(self._rename_constraint(init_c, map_0))

            # Transitions for t in 0 .. k-1
            for t in range(k):
                map_trans = {}
                for v in vars_list:
                    map_trans[v] = f"{v}_{t}"
                    map_trans[f"{v}_prime"] = f"{v}_{t+1}"
                for tr_c in program.transition_constraints:
                    A_constraints.append(self._rename_constraint(tr_c, map_trans))

            # Bad at step k
            map_k = {v: f"{v}_{k}" for v in vars_list}
            for bad_c in bad_constraints:
                B_constraints = [self._rename_constraint(bad_c, map_k)]

                # Check if trace prefix A and bad suffix B are mutually inconsistent
                mult = FarkasLinearInterpolator.find_farkas_multipliers(A_constraints + B_constraints)
                if mult is None:
                    # Counterexample trace reaches Bad in k steps!
                    counterexample_traces.append({"step": k, "bad_reached": bad_c.to_string()})
                    continue

                # Extract Craig interpolant at state k
                interp = FarkasLinearInterpolator.interpolate(A_constraints, B_constraints)

                # Rename variables from v_k back to original state variables v
                unmap_k = {f"{v}_{k}": v for v in vars_list}
                inv_c = self._rename_constraint(interp, unmap_k)

                # Avoid duplicate candidate constraints
                inv_str = inv_c.to_string()
                if not any(c.to_string() == inv_str for c in candidate_invariants):
                    candidate_invariants.append(inv_c)

            # Check Inductiveness of current candidate invariant set:
            # 1. Test individual candidates first for minimal parsimonious invariants
            for cand in reversed(candidate_invariants):
                is_ind, cert = self._verify_inductiveness(program, [cand])
                if is_ind:
                    return InvariantResult(
                        status="VERIFIED_INDUCTIVE",
                        loop_name=program.name,
                        invariant=[cand],
                        unroll_depth=k,
                        proof_certificate=cert,
                        counterexamples=counterexample_traces,
                    )

            # 2. Test conjunction of all candidate invariants
            is_ind, cert = self._verify_inductiveness(program, candidate_invariants)
            if is_ind:
                return InvariantResult(
                    status="VERIFIED_INDUCTIVE",
                    loop_name=program.name,
                    invariant=candidate_invariants,
                    unroll_depth=k,
                    proof_certificate=cert,
                    counterexamples=counterexample_traces,
                )

            # 3. Test non-dominated subset by filtering out candidates that violate consecution
            valid_candidates = []
            map_prime = {v: f"{v}_prime" for v in vars_list}
            for cand in candidate_invariants:
                primed_neg = self._rename_constraint(cand.negate(delta=self.delta), map_prime)
                # Self-consecution check: cand(V) /\ T(V, V') /\ ~cand(V') is infeasible
                if FarkasLinearInterpolator.find_farkas_multipliers([cand] + program.transition_constraints + [primed_neg]) is not None:
                    valid_candidates.append(cand)

            if valid_candidates and len(valid_candidates) != len(candidate_invariants):
                is_ind, cert = self._verify_inductiveness(program, valid_candidates)
                if is_ind:
                    return InvariantResult(
                        status="VERIFIED_INDUCTIVE",
                        loop_name=program.name,
                        invariant=valid_candidates,
                        unroll_depth=k,
                        proof_certificate=cert,
                        counterexamples=counterexample_traces,
                    )

        # Fallback if max unroll reached
        return InvariantResult(
            status="MAX_ITERATIONS",
            loop_name=program.name,
            invariant=candidate_invariants,
            unroll_depth=self.max_unroll_depth,
            proof_certificate={"verified": False, "reason": "Max unroll depth reached without consecution"},
            counterexamples=counterexample_traces,
        )

    def _verify_inductiveness(
        self,
        program: LoopProgram,
        invariants: List[LinearConstraint],
    ) -> Tuple[bool, Dict[str, Any]]:
        """Formally verifies the 3 conditions of Inductive Invariant:

        1. Initiation:  Init(V) => Inv(V)
        2. Consecution: Inv(V) /\ T(V, V') => Inv(V')
        3. Safety:      Inv(V) /\ Bad(V) |= False
        """
        vars_list = program.variables
        bad_constraints = program.get_bad_constraints(self.delta)

        # 1. Initiation: For all inv in invariants, Init /\ ~inv is infeasible
        for inv in invariants:
            neg_inv = inv.negate(delta=self.delta)
            if FarkasLinearInterpolator.find_farkas_multipliers(program.init_constraints + [neg_inv]) is None:
                return False, {"failed_stage": "INITIATION", "violating_constraint": inv.to_string()}

        # 2. Consecution: Inv(V) /\ T(V, V') /\ ~inv(V') is infeasible
        # Rename inv to primed variables
        map_prime = {v: f"{v}_prime" for v in vars_list}
        for inv in invariants:
            primed_neg_inv = self._rename_constraint(inv.negate(delta=self.delta), map_prime)
            system = invariants + program.transition_constraints + [primed_neg_inv]
            if FarkasLinearInterpolator.find_farkas_multipliers(system) is None:
                return False, {"failed_stage": "CONSECUTION", "violating_constraint": inv.to_string()}

        # 3. Safety: Inv(V) /\ Bad(V) is infeasible
        for bad_c in bad_constraints:
            if FarkasLinearInterpolator.find_farkas_multipliers(invariants + [bad_c]) is None:
                return False, {"failed_stage": "SAFETY", "violating_constraint": bad_c.to_string()}

        return True, {
            "verified": True,
            "initiation": "VALID (Init => Inv)",
            "consecution": "VALID (Inv /\\ T => Inv')",
            "safety": "VALID (Inv /\\ Bad |= False)",
            "synthesized_invariants": [c.to_string() for c in invariants],
        }


# ============================================================================
# Section 5: Unified Craig Interpolation Engine Interface
# ============================================================================

@dataclass
class CraigInterpolant:
    interpolant: Union[BoolExpr, LinearConstraint]
    domain: str  # 'PROPOSITIONAL' or 'LINEAR_ARITHMETIC'
    shared_symbols: List[str]
    verification_receipt: Dict[str, Any]

    def to_string(self) -> str:
        if isinstance(self.interpolant, BoolExpr):
            return self.interpolant.to_code()
        return self.interpolant.to_string()


class CraigInterpolationEngine:
    """Unified Craig Interpolation Engine for Propositional and Linear Arithmetic."""

    @classmethod
    def interpolate_propositional(
        cls,
        A: Union[PropCNF, List[PropClause]],
        B: Union[PropCNF, List[PropClause]],
    ) -> CraigInterpolant:
        I = McMillanPropositionalInterpolator.interpolate(A, B)
        receipt = McMillanPropositionalInterpolator.verify_craig_conditions(A, B, I)
        return CraigInterpolant(
            interpolant=I,
            domain="PROPOSITIONAL",
            shared_symbols=receipt["shared_symbols"],
            verification_receipt=receipt,
        )

    @classmethod
    def interpolate_linear(
        cls,
        A: Union[LinearSystem, List[LinearConstraint]],
        B: Union[LinearSystem, List[LinearConstraint]],
    ) -> CraigInterpolant:
        I = FarkasLinearInterpolator.interpolate(A, B)
        receipt = FarkasLinearInterpolator.verify_craig_conditions(A, B, I)
        return CraigInterpolant(
            interpolant=I,
            domain="LINEAR_ARITHMETIC",
            shared_symbols=receipt["shared_symbols"],
            verification_receipt=receipt,
        )

    @classmethod
    def synthesize_loop_invariant(
        cls,
        program: LoopProgram,
        max_unroll_depth: int = 8,
    ) -> InvariantResult:
        synthesizer = InductiveLoopInvariantSynthesizer(max_unroll_depth=max_unroll_depth)
        return synthesizer.synthesize(program)
