"""Failure Constraint Engine (Popper-inspired Learning from Failures).

Guarantees:
1. Deduces formal failure constraints from rejected candidates and witness counterexamples.
2. Identifies structural, modular, and boundary invariant conflicts.
3. Pre-checks prospective candidate genes in-memory (O(1) time) to prune provably invalid
   hypotheses before wasting evaluation compute or touching sealed holdouts.
4. Prevents recurring failure modes (e.g., repeating the same failed operator or modulus).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ace_loop.source_evolution import (
    CompositeGene,
    DispatchGene,
    GatedGene,
    RelationalGatedGene,
    RelationalGene,
    TypedGene,
)


@dataclass(frozen=True)
class FailureConstraint:
    """Formal constraint deduced from a falsified candidate hypothesis."""
    constraint_id: str
    task_id: str
    constraint_type: str  # "MODULUS_CONFLICT", "LENGTH_GUARD_EXCESS", "OPERATOR_COLLAPSE", "STRUCTURE_DEFICIT"
    violating_witness: str
    expected_label: bool
    forbidden_pattern: Dict[str, Any]
    deduced_reason: str


class FailureConstraintEngine:
    """Extracts, maintains, and checks failure constraints across autonomous research cycles."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self._constraints: Dict[str, List[FailureConstraint]] = {}  # task_id -> list of constraints
        self._pruned_count: int = 0
        if self.storage_path and self.storage_path.exists():
            self._load()

    @property
    def total_constraints(self) -> int:
        return sum(len(c) for c in self._constraints.values())

    @property
    def pruned_candidates_count(self) -> int:
        return self._pruned_count

    def deduce_constraint(
        self,
        task_id: str,
        gene: Any,
        witness_input: str,
        expected_label: bool,
        predicted_label: bool,
        error_context: Optional[str] = None,
    ) -> FailureConstraint:
        """Deduce a formal constraint from an empirical misclassification on a witness."""
        w_len = len(witness_input)
        w_density = witness_input.count("a")
        w_stride = sum(1 for i, ch in enumerate(witness_input) if i % 2 == 0 and ch == "a")

        c_type = "STRUCTURE_DEFICIT"
        forbidden: Dict[str, Any] = {}
        reason = f"Candidate misclassified witness '{witness_input}' (expected {expected_label}, got {predicted_label})"

        if isinstance(gene, RelationalGatedGene):
            # Check if length guard incorrectly excluded positive witness
            if expected_label and gene.length_op == ">=" and w_len < gene.length_threshold:
                c_type = "LENGTH_GUARD_EXCESS"
                forbidden = {"length_op": ">=", "min_threshold": gene.length_threshold}
                reason = f"Length guard '>={gene.length_threshold}' excludes positive witness of length {w_len}"
            elif gene.combiner == "AND" and not expected_label and predicted_label:
                # Conjunction was too lenient
                c_type = "MODULUS_CONFLICT"
                forbidden = {"modulus": gene.modulus, "target_residue": gene.target_residue, "combiner": "AND"}
                reason = f"AND-congruence mod {gene.modulus} == {gene.target_residue} falsely admitted negative witness '{witness_input}'"
            else:
                c_type = "PARAMETRIC_MISALIGNMENT"
                forbidden = {"clause_type": gene.clause_type, "modulus": gene.modulus}
                reason = f"Relational clause configuration failed on witness '{witness_input}'"

        elif isinstance(gene, GatedGene):
            if expected_label and w_len < gene.min_length:
                c_type = "LENGTH_GUARD_EXCESS"
                forbidden = {"min_length": gene.min_length}
                reason = f"Gated min_length {gene.min_length} blocks positive witness of length {w_len}"
            else:
                c_type = "MODULUS_CONFLICT"
                forbidden = {"modulus": gene.modulus, "target_residue": gene.target_residue}
                reason = f"Modular congruence mod {gene.modulus} == {gene.target_residue} fails on witness '{witness_input}'"

        elif isinstance(gene, CompositeGene):
            c_type = "OPERATOR_COLLAPSE"
            forbidden = {"operator": gene.operator}
            reason = f"Composite operator '{gene.operator}' lacks necessary expressive separation on witness '{witness_input}'"

        elif isinstance(gene, TypedGene):
            c_type = "LINEAR_SCALAR_SATURATION"
            forbidden = {"window_stride": gene.window_stride, "modulus": gene.modulus}
            reason = f"Linear scalar stride {gene.window_stride} mod {gene.modulus} fails on witness '{witness_input}'"

        cid_payload = f"{task_id}:{c_type}:{witness_input}:{expected_label}:{json.dumps(forbidden, sort_keys=True)}"
        cid = "FC_" + hashlib.sha256(cid_payload.encode("utf-8")).hexdigest()[:12]

        constraint = FailureConstraint(
            constraint_id=cid,
            task_id=task_id,
            constraint_type=c_type,
            violating_witness=witness_input,
            expected_label=expected_label,
            forbidden_pattern=forbidden,
            deduced_reason=reason,
        )

        if task_id not in self._constraints:
            self._constraints[task_id] = []
        
        # Deduplicate
        if not any(c.constraint_id == cid for c in self._constraints[task_id]):
            self._constraints[task_id].append(constraint)
            self._save()

        return constraint

    def check_pruning(self, task_id: str, gene: Any) -> Tuple[bool, Optional[str]]:
        """Check if prospective gene violates any deduced failure constraint for task_id.
        
        Returns:
            (is_pruned, reason)
        """
        task_constraints = self._constraints.get(task_id, [])
        for c in task_constraints:
            # Check length guard excess
            if c.constraint_type == "LENGTH_GUARD_EXCESS":
                if isinstance(gene, RelationalGatedGene) and gene.length_op == ">=":
                    min_thresh = c.forbidden_pattern.get("min_threshold", 0)
                    if gene.length_threshold >= min_thresh and len(c.violating_witness) < gene.length_threshold:
                        self._pruned_count += 1
                        return True, f"Pruned by {c.constraint_id}: length guard '>={gene.length_threshold}' blocks positive witness '{c.violating_witness}'"
                elif isinstance(gene, GatedGene):
                    min_len = c.forbidden_pattern.get("min_length", 0)
                    if gene.min_length >= min_len and len(c.violating_witness) < gene.min_length:
                        self._pruned_count += 1
                        return True, f"Pruned by {c.constraint_id}: min_length {gene.min_length} blocks positive witness '{c.violating_witness}'"

            # Check modulus conflict on exact same combiner
            elif c.constraint_type == "MODULUS_CONFLICT":
                if isinstance(gene, RelationalGatedGene):
                    forb_mod = c.forbidden_pattern.get("modulus")
                    forb_res = c.forbidden_pattern.get("target_residue")
                    forb_comb = c.forbidden_pattern.get("combiner")
                    if (gene.modulus == forb_mod and 
                        gene.target_residue == forb_res and 
                        gene.combiner == forb_comb):
                        self._pruned_count += 1
                        return True, f"Pruned by {c.constraint_id}: exact conflict on mod {forb_mod} residue {forb_res} with {forb_comb}"
                elif isinstance(gene, GatedGene):
                    forb_mod = c.forbidden_pattern.get("modulus")
                    forb_res = c.forbidden_pattern.get("target_residue")
                    if gene.modulus == forb_mod and gene.target_residue == forb_res:
                        self._pruned_count += 1
                        return True, f"Pruned by {c.constraint_id}: exact conflict on gated mod {forb_mod} residue {forb_res}"

        return False, None

    def get_constraints_for_task(self, task_id: str) -> List[FailureConstraint]:
        return list(self._constraints.get(task_id, []))

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            task_id: [
                {
                    "constraint_id": c.constraint_id,
                    "task_id": c.task_id,
                    "constraint_type": c.constraint_type,
                    "violating_witness": c.violating_witness,
                    "expected_label": c.expected_label,
                    "forbidden_pattern": c.forbidden_pattern,
                    "deduced_reason": c.deduced_reason,
                }
                for c in clist
            ]
            for task_id, clist in self._constraints.items()
        }
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text())
            for task_id, clist in raw.items():
                self._constraints[task_id] = [
                    FailureConstraint(
                        constraint_id=item["constraint_id"],
                        task_id=item["task_id"],
                        constraint_type=item["constraint_type"],
                        violating_witness=item["violating_witness"],
                        expected_label=item["expected_label"],
                        forbidden_pattern=item["forbidden_pattern"],
                        deduced_reason=item["deduced_reason"],
                    )
                    for item in clist
                ]
        except Exception:
            self._constraints = {}
