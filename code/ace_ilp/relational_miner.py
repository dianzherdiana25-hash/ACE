"""Relational Predicate Mining via Inductive Logic Programming (ILP).

Mathematical Foundation:
- First-order Horn Clause Induction over relational facts B, positive examples E+, and negative examples E-.
- Completeness: B ∧ H |= E+
- Consistency: B ∧ H ∧ E- |/= ⊥
- Plotkin's θ-subsumption lattice (Plotkin, 1970) for rule generalization/specialization.
- Top-down FOIL Information Gain search (Quinlan, 1990) with bottom-clause bounding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import math
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple


def is_variable(name: str) -> bool:
    """A term is a variable if it starts with an uppercase letter or underscore."""
    return bool(name and (name[0].isupper() or name[0] == "_"))


@dataclass(frozen=True)
class Atom:
    """First-order relational atom: predicate(term1, term2, ...)."""
    predicate: str
    terms: Tuple[str, ...]

    def __init__(self, predicate: str, *terms: str):
        object.__setattr__(self, "predicate", predicate)
        # Ensure terms are stored as tuple of strings
        object.__setattr__(self, "terms", tuple(str(t) for t in terms))

    @property
    def arity(self) -> int:
        return len(self.terms)

    @property
    def is_ground(self) -> bool:
        return all(not is_variable(t) for t in self.terms)

    @property
    def variables(self) -> Set[str]:
        return {t for t in self.terms if is_variable(t)}

    def substitute(self, subst: Dict[str, str]) -> Atom:
        new_terms = tuple(subst.get(t, t) for t in self.terms)
        return Atom(self.predicate, *new_terms)

    def match_ground(self, ground_atom: Atom, current_subst: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Matches this atom (possibly containing variables) against a ground atom."""
        if self.predicate != ground_atom.predicate or self.arity != ground_atom.arity:
            return None
        new_subst = dict(current_subst)
        for t, gt in zip(self.terms, ground_atom.terms):
            if is_variable(t):
                if t in new_subst:
                    if new_subst[t] != gt:
                        return None
                else:
                    new_subst[t] = gt
            else:
                if t != gt:
                    return None
        return new_subst

    def __repr__(self) -> str:
        return f"{self.predicate}({', '.join(self.terms)})"


@dataclass(frozen=True)
class Clause:
    """Horn clause: Head :- Body_1, Body_2, ..."""
    head: Atom
    body: Tuple[Atom, ...] = field(default_factory=tuple)

    def __init__(self, head: Atom, *body: Atom):
        object.__setattr__(self, "head", head)
        object.__setattr__(self, "body", tuple(body))

    @property
    def variables(self) -> Set[str]:
        vars_set = set(self.head.variables)
        for b in self.body:
            vars_set.update(b.variables)
        return vars_set

    def substitute(self, subst: Dict[str, str]) -> Clause:
        new_head = self.head.substitute(subst)
        new_body = tuple(b.substitute(subst) for b in self.body)
        return Clause(new_head, *new_body)

    def theta_subsumes(self, other: Clause) -> bool:
        """Checks if self θ-subsumes other (Plotkin, 1970).
        self θ-subsumes other if exists substitution θ such that
        self.headθ == other.head and self.bodyθ ⊆ other.body.
        """
        # Treat other's variables as unique skolem constants
        skolem_map = {v: f"__skolem_{v}" for v in other.variables}
        other_skolem = other.substitute(skolem_map)

        # Unify heads first
        initial_subst = self.head.match_ground(other_skolem.head, {})
        if initial_subst is None:
            return False

        if not self.body:
            return True

        # Search for substitutions satisfying self.bodyθ ⊆ other_skolem.body
        target_body_atoms = set(other_skolem.body)

        def match_body(atom_idx: int, subst: Dict[str, str]) -> bool:
            if atom_idx >= len(self.body):
                return True
            atom = self.body[atom_idx]
            # Try to match atom against any target in other_skolem.body
            for target in target_body_atoms:
                matched = atom.match_ground(target, subst)
                if matched is not None:
                    if match_body(atom_idx + 1, matched):
                        return True
            return False

        return match_body(0, initial_subst)

    def __repr__(self) -> str:
        if not self.body:
            return f"{self.head}."
        return f"{self.head} :- {', '.join(str(b) for b in self.body)}."


class KnowledgeBase:
    """First-order relational knowledge base and deductive inference engine."""

    def __init__(self, facts: Optional[List[Atom]] = None, clauses: Optional[List[Clause]] = None):
        self.facts: Set[Atom] = set(facts) if facts else set()
        self.clauses: List[Clause] = list(clauses) if clauses else []
        self._derived_cache: Optional[Set[Atom]] = None

    def add_fact(self, atom: Atom) -> None:
        if not atom.is_ground:
            raise ValueError(f"KnowledgeBase facts must be ground: {atom}")
        self.facts.add(atom)
        self._derived_cache = None

    def add_clause(self, clause: Clause) -> None:
        self.clauses.append(clause)
        self._derived_cache = None

    def get_predicates(self) -> Set[Tuple[str, int]]:
        preds = {(f.predicate, f.arity) for f in self.facts}
        for c in self.clauses:
            preds.add((c.head.predicate, c.head.arity))
            for b in c.body:
                preds.add((b.predicate, b.arity))
        return preds

    def get_constants(self) -> Set[str]:
        consts = set()
        for f in self.facts:
            consts.update(f.terms)
        return consts

    def forward_chain(self, max_steps: int = 15) -> Set[Atom]:
        """Computes the deductive fixed point of facts under Horn clauses."""
        if self._derived_cache is not None:
            return self._derived_cache

        known: Set[Atom] = set(self.facts)
        step = 0

        while step < max_steps:
            new_derived: Set[Atom] = set()
            for clause in self.clauses:
                # Find all satisfying ground substitutions for clause.body
                substs = self._solve_body(clause.body, known, {})
                for s in substs:
                    derived_head = clause.head.substitute(s)
                    if derived_head.is_ground and derived_head not in known:
                        new_derived.add(derived_head)

            if not new_derived:
                break
            known.update(new_derived)
            step += 1

        self._derived_cache = known
        return known

    def _solve_body(
        self, body: Tuple[Atom, ...], facts: Set[Atom], current_subst: Dict[str, str]
    ) -> List[Dict[str, str]]:
        if not body:
            return [current_subst]

        first_atom = body[0]
        remaining = body[1:]
        results: List[Dict[str, str]] = []

        # Find matching facts for first_atom
        for fact in facts:
            matched_subst = first_atom.match_ground(fact, current_subst)
            if matched_subst is not None:
                results.extend(self._solve_body(remaining, facts, matched_subst))

        return results

    def entails(self, atom: Atom) -> bool:
        """Soundly checks if atom is entailed by the knowledge base."""
        all_facts = self.forward_chain()
        if atom.is_ground:
            return atom in all_facts
        # For non-ground queries:
        for f in all_facts:
            if atom.match_ground(f, {}) is not None:
                return True
        return False

    def query(self, predicate: str, arity: int) -> Set[Tuple[str, ...]]:
        """Returns all ground term tuples satisfying predicate."""
        all_facts = self.forward_chain()
        return {f.terms for f in all_facts if f.predicate == predicate and f.arity == arity}


class RelationalMiner:
    """Inductive Logic Programming (ILP) Rule Inducer using FOIL Information Gain."""

    def __init__(
        self,
        background_facts: List[Atom],
        positive_examples: List[Atom],
        negative_examples: List[Atom],
        target_predicate: str,
        target_arity: int = 2,
    ):
        self.kb = KnowledgeBase(background_facts)
        self.pos_examples = [p for p in positive_examples if p.is_ground and p.predicate == target_predicate]
        self.neg_examples = [n for n in negative_examples if n.is_ground and n.predicate == target_predicate]
        self.target_predicate = target_predicate
        self.target_arity = target_arity

    def mine(self, max_clause_length: int = 3, max_clauses: int = 5) -> List[Clause]:
        """Synthesizes a minimal set of Horn clauses covering E+ and excluding E-."""
        target_vars = [f"X{i}" for i in range(self.target_arity)]
        base_head = Atom(self.target_predicate, *target_vars)

        available_preds = list(self.kb.get_predicates())
        # Filter out target predicate from body unless recursive search
        bg_preds = [p for p in available_preds if p[0] != self.target_predicate]

        hypothesis: List[Clause] = []
        uncovered_pos = list(self.pos_examples)

        while uncovered_pos and len(hypothesis) < max_clauses:
            current_clause = self._find_best_clause(
                base_head, target_vars, uncovered_pos, self.neg_examples, bg_preds, max_clause_length
            )
            if not current_clause:
                break

            # Test clause coverage
            test_kb = KnowledgeBase(list(self.kb.facts), hypothesis + [current_clause])
            covered_this_turn = [p for p in uncovered_pos if test_kb.entails(p)]

            if not covered_this_turn:
                # Fallback: if no new positive examples covered, break loop
                break

            hypothesis.append(current_clause)
            uncovered_pos = [p for p in uncovered_pos if not test_kb.entails(p)]

        return hypothesis

    def _example_satisfies_body(
        self, head: Atom, body: List[Atom], example: Atom, facts: Set[Atom]
    ) -> bool:
        if not body:
            return True
        subst = {h_var: e_term for h_var, e_term in zip(head.terms, example.terms)}
        solutions = self.kb._solve_body(tuple(body), facts, subst)
        return len(solutions) > 0

    def _find_best_clause(
        self,
        head: Atom,
        target_vars: List[str],
        pos_examples: List[Atom],
        neg_examples: List[Atom],
        bg_preds: List[Tuple[str, int]],
        max_length: int,
    ) -> Optional[Clause]:
        """Searches top-down for the minimal, highest-coverage clause satisfying Occam's razor."""
        facts = set(self.kb.facts)

        # Beam of candidate bodies: List of (body, vars, p_cov, n_cov)
        current_beam: List[Tuple[List[Atom], List[str], int, int]] = [([], list(target_vars), len(pos_examples), len(neg_examples))]

        for depth in range(1, max_length + 1):
            next_candidates: List[Tuple[float, int, List[Atom], List[str]]] = []
            perfect_candidates: List[Tuple[int, List[Atom]]] = []

            for body, vars_in_body, p0, n0 in current_beam:
                cand_literals = self._generate_candidate_literals(bg_preds, vars_in_body)

                for lit in cand_literals:
                    # Avoid duplicate literals in body
                    if lit in body:
                        continue

                    trial_body = body + [lit]
                    # Check coverage
                    p1 = sum(1 for p in pos_examples if self._example_satisfies_body(head, trial_body, p, facts))
                    if p1 == 0:
                        continue

                    n1 = sum(1 for n in neg_examples if self._example_satisfies_body(head, trial_body, n, facts))

                    trial_vars = list(set(vars_in_body + list(lit.variables)))
                    all_head_bound = all(v in trial_vars for v in head.variables)

                    # If all head variables are bound and zero negative examples covered:
                    if all_head_bound and n1 == 0:
                        perfect_candidates.append((p1, trial_body))
                    else:
                        gain = self._foil_gain(p0, n0, p1, n1)
                        if n1 < n0:
                            gain += 0.5 * (n0 - n1)
                        if gain > 0:
                            next_candidates.append((gain, p1, trial_body, trial_vars))

            # If any perfect clause found at this minimal depth, pick the one covering most positives
            if perfect_candidates:
                perfect_candidates.sort(key=lambda x: x[0], reverse=True)
                best_body = perfect_candidates[0][1]
                return Clause(head, *best_body)

            if not next_candidates:
                break

            # Keep top candidates by gain (beam width = 10)
            next_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            current_beam = [
                (cand_body, cand_vars, cand_p1, sum(1 for n in neg_examples if self._example_satisfies_body(head, cand_body, n, facts)))
                for _, cand_p1, cand_body, cand_vars in next_candidates[:10]
            ]

        return None

    def _generate_candidate_literals(
        self, bg_preds: List[Tuple[str, int]], current_vars: List[str]
    ) -> List[Atom]:
        literals: List[Atom] = []
        new_var_name = f"Z{len(current_vars)}"
        var_pool = current_vars + [new_var_name]

        for pred_name, arity in bg_preds:
            # Generate variable combinations for arity
            for terms in itertools.product(var_pool, repeat=arity):
                # Must contain at least one currently bound variable
                if any(t in current_vars for t in terms):
                    literals.append(Atom(pred_name, *terms))

        return literals

    @staticmethod
    def _foil_gain(p0: int, n0: int, p1: int, n1: int) -> float:
        if p1 == 0:
            return 0.0
        info_before = -math.log2(p0 / (p0 + n0)) if (p0 + n0) > 0 and p0 > 0 else 0.0
        info_after = -math.log2(p1 / (p1 + n1)) if (p1 + n1) > 0 and p1 > 0 else 0.0
        gain = p1 * (info_before - info_after)
        return max(0.0, gain)

    def compile_to_python(self, clauses: List[Clause]) -> Callable[[List[Tuple[str, str, ...]], str, str], bool]:
        """Compiles synthesized Horn clauses into an executable Python callable."""
        def evaluate(graph_facts: List[Tuple[str, str, ...]], arg0: str, arg1: str) -> bool:
            atoms = [Atom(f[0], *f[1:]) for f in graph_facts]
            kb = KnowledgeBase(atoms, clauses)
            query_atom = Atom(self.target_predicate, arg0, arg1)
            return kb.entails(query_atom)

        return evaluate
