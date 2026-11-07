"""HostController coordinating lineage, budget, sandbox isolation, holdout evaluation, and rollback.

Maintains strict separation between the candidate research generator and the external
governance and evaluation harness, enforcing fail-closed release gates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable, Optional, Sequence

from .budget_permits import CapabilityPermit, ExecutionBudget
from .exposure_ledger import ExposureLedger
from .lineage import CandidateNode, LineageGraph
from .sandbox_gate import HostSandboxGate
from .sealed_evaluator import EvaluationReceipt, SealedHoldoutEvaluator


@dataclass(frozen=True)
class AcceptanceDecision:
    """Decision emitted by Host Controller upon candidate evaluation."""

    candidate_id: str
    status: str  # ACCEPTED, REJECTED, ROLLED_BACK
    holdout_accuracy: float
    prior_regression: float
    gain_over_parent: float
    contamination_detected: bool
    sandbox_passed: bool
    receipt: EvaluationReceipt
    rejection_reasons: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize acceptance decision to dictionary."""
        d = asdict(self)
        d["receipt"] = self.receipt.to_dict()
        return d


@dataclass(frozen=True)
class RollbackRecord:
    """Audit record of a rollback operation."""

    rolled_back_from: str
    restored_head: str
    reason: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize rollback record to dictionary."""
        return asdict(self)


class HostController:
    """Independent Host Controller governing candidate generation, evaluation, and promotion."""

    def __init__(
        self,
        evaluator: SealedHoldoutEvaluator,
        budget: Optional[ExecutionBudget] = None,
        permit: Optional[CapabilityPermit] = None,
        sandbox_gate: Optional[HostSandboxGate] = None,
        root_candidate_id: str = "G0_root",
        root_source_sha: str = "0000000000000000000000000000000000000000000000000000000000000000",
        min_gain: float = 0.15,
        max_regression: float = 0.02,
    ):
        self.evaluator = evaluator
        self.budget = budget or ExecutionBudget()
        self.permit = permit or CapabilityPermit()
        self.sandbox_gate = sandbox_gate or HostSandboxGate()
        self.min_gain = min_gain
        self.max_regression = max_regression

        self.lineage = LineageGraph(root_id=root_candidate_id)
        self.lineage.register_candidate(
            candidate_id=root_candidate_id,
            parent_id=None,
            source_sha=root_source_sha,
            generation=0,
            metadata={"description": "Baseline root model G0"},
        )
        self.lineage.update_status(root_candidate_id, "ACCEPTED", holdout_score=0.50)

        self.exposure_ledger = ExposureLedger()
        self.rollback_history: list[RollbackRecord] = []
        self.decisions: list[AcceptanceDecision] = []

        # Immutable fail-closed governance invariants
        self.release_gate = "BLOCK_RELEASE"
        self.scientific_status = "NOT_ASSESSED"
        self.oaie_established = False

    def evaluate_and_gate(
        self,
        candidate_id: str,
        parent_id: str,
        generation: int,
        source_sha: str,
        candidate_fn: Callable[[str], bool],
        candidate_code_or_spec: Optional[str | dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AcceptanceDecision:
        """Evaluate a candidate, verify non-contamination and sandbox rules, and decide promotion."""
        rejection_reasons: list[str] = []

        # 1. Register candidate in lineage or check if blocked
        if candidate_id in self.lineage.nodes:
            if self.lineage.nodes[candidate_id].status == "BLOCKED":
                rejection_reasons.append(f"Candidate '{candidate_id}' is BLOCKED by supervisor")
            else:
                self.lineage.update_status(candidate_id, "EVALUATING")
        else:
            self.lineage.register_candidate(
                candidate_id=candidate_id,
                parent_id=parent_id,
                source_sha=source_sha,
                generation=generation,
                metadata=metadata,
            )
            self.lineage.update_status(candidate_id, "EVALUATING")

        # 2. Audit Sandbox
        sandbox_passed = True
        if candidate_code_or_spec is not None:
            if isinstance(candidate_code_or_spec, str):
                audit_res = self.sandbox_gate.audit_ast(candidate_code_or_spec)
            else:
                audit_res = self.sandbox_gate.audit_mechanism_spec(candidate_code_or_spec)
            if not audit_res.allowed:
                sandbox_passed = False
                rejection_reasons.append(f"Sandbox audit failed: {audit_res.reason} ({audit_res.violations})")

        # 3. Verify benchmark non-contamination via exposure ledger
        holdout_inputs = self.evaluator.get_holdout_inputs()
        is_contaminated, leaks = self.exposure_ledger.check_contamination(holdout_inputs)
        if is_contaminated:
            rejection_reasons.append(
                f"Benchmark contamination: {len(leaks)} holdout inputs leaked into candidate search"
            )

        # 4. Sealed Evaluation under budget
        receipt = self.evaluator.evaluate_candidate(
            candidate_id=candidate_id,
            candidate_fn=candidate_fn,
            budget=self.budget,
            min_gain=self.min_gain,
            max_regression=self.max_regression,
        )

        parent_node = self.lineage.nodes[parent_id]
        parent_score = parent_node.holdout_score
        gain = receipt.holdout_accuracy - parent_score

        if receipt.prior_regression > self.max_regression:
            rejection_reasons.append(
                f"Prior regression {receipt.prior_regression:.4f} exceeds max {self.max_regression:.4f}"
            )
        if gain < self.min_gain:
            rejection_reasons.append(
                f"Holdout gain {gain:.4f} below required min_gain {self.min_gain:.4f}"
            )
        if not receipt.passed:
            rejection_reasons.append("Evaluator marked test receipt as failed")

        # 5. Gating decision
        if not rejection_reasons and sandbox_passed and not is_contaminated:
            status = "ACCEPTED"
            self.lineage.update_status(
                candidate_id=candidate_id,
                status="ACCEPTED",
                holdout_score=receipt.holdout_accuracy,
                prior_score=parent_score,
                regression=receipt.prior_regression,
            )
        else:
            status = "REJECTED"
            self.lineage.update_status(
                candidate_id=candidate_id,
                status="REJECTED",
                holdout_score=receipt.holdout_accuracy,
                prior_score=parent_score,
                regression=receipt.prior_regression,
            )

        decision = AcceptanceDecision(
            candidate_id=candidate_id,
            status=status,
            holdout_accuracy=receipt.holdout_accuracy,
            prior_regression=receipt.prior_regression,
            gain_over_parent=round(gain, 4),
            contamination_detected=is_contaminated,
            sandbox_passed=sandbox_passed,
            receipt=receipt,
            rejection_reasons=rejection_reasons,
        )
        self.decisions.append(decision)
        return decision

    def rollback(self, reason: str, target_id: Optional[str] = None) -> RollbackRecord:
        """Roll back active lineage head to parent or target checkpoint upon regression."""
        if self.lineage.active_head_id is None:
            raise ValueError("No active head to roll back")
        prev_head = self.lineage.active_head_id

        if target_id is None:
            ancestors = self.lineage.get_ancestors(prev_head)
            if not ancestors:
                raise ValueError("Active head has no ancestor to roll back to")
            target_id = ancestors[0]

        self.lineage.rollback_to(target_id)
        record = RollbackRecord(
            rolled_back_from=prev_head,
            restored_head=target_id,
            reason=reason,
        )
        self.rollback_history.append(record)
        return record

    def block_candidate(self, candidate_id: str, reason: str) -> None:
        """Supervisor explicitly blocks a candidate from promotion."""
        if candidate_id not in self.lineage.nodes:
            self.lineage.register_candidate(
                candidate_id=candidate_id,
                parent_id=self.lineage.active_head_id,
                source_sha="0" * 64,
                generation=1,
                metadata={"blocked_reason": reason},
            )
        self.lineage.update_status(candidate_id, "BLOCKED")

    def revoke_promotion(self, candidate_id: str, reason: str) -> RollbackRecord:
        """Supervisor explicitly revokes promotion of an accepted candidate and rolls back active head."""
        if candidate_id not in self.lineage.nodes:
            raise KeyError(f"Candidate {candidate_id} not found in lineage")
        node = self.lineage.nodes[candidate_id]
        if node.status != "ACCEPTED":
            raise ValueError(f"Cannot revoke candidate {candidate_id} with status {node.status}")
        node.status = "REVOKED"
        node.metadata["revocation_reason"] = reason

        if self.lineage.active_head_id == candidate_id:
            ancestors = self.lineage.get_ancestors(candidate_id)
            if not ancestors:
                raise ValueError(f"Candidate {candidate_id} has no ancestor to roll back to")
            target_id = ancestors[0]
            self.lineage.active_head_id = target_id
            record = RollbackRecord(
                rolled_back_from=candidate_id,
                restored_head=target_id,
                reason=f"Promotion revoked: {reason}",
            )
            self.rollback_history.append(record)
            return record
        else:
            record = RollbackRecord(
                rolled_back_from=candidate_id,
                restored_head=self.lineage.active_head_id or self.lineage.root_id or "",
                reason=f"Promotion revoked (inactive head): {reason}",
            )
            self.rollback_history.append(record)
            return record

    def update_baseline_scores(self, new_scores: dict[str, float]) -> None:
        """Safely update prior baseline scores in the evaluator without exposing private banks."""
        if hasattr(self.evaluator, "update_baseline_scores"):
            self.evaluator.update_baseline_scores(new_scores)
        elif hasattr(self.evaluator, "_prior_baseline_scores"):
            self.evaluator._prior_baseline_scores.update({k: float(v) for k, v in new_scores.items()})

    def get_governance_report(self) -> dict[str, Any]:
        """Generate authoritative cryptographic governance report."""
        return {
            "schema": "ace.host_controller_governance.v1",
            "release_gate": self.release_gate,
            "scientific_status": self.scientific_status,
            "oaie_established": self.oaie_established,
            "manifest": self.evaluator.manifest.to_dict(),
            "lineage": self.lineage.to_dict(),
            "budget": self.budget.to_dict(),
            "permit": self.permit.to_dict(),
            "exposure_ledger": self.exposure_ledger.to_dict(),
            "decisions": [d.to_dict() for d in self.decisions],
            "rollback_history": [r.to_dict() for r in self.rollback_history],
        }
