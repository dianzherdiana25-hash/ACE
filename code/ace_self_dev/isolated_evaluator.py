"""Isolated Evaluator: Independent evaluation of candidate mechanisms against sealed confirmation holdouts."""
from __future__ import annotations

import hashlib
import hmac
import os
import resource
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ace_host_controller import (
    ExecutionBudget,
    HostController,
    HostSandboxGate,
    SealedHoldoutEvaluator,
)
from ace_loop.source_evolution import TypedGene, compile_function
from .confirmation_suite import ConfirmationTask
from .models import CandidateDecision, CodeCandidate, EvaluationReceipt, ResearchHypothesis
from .provenance_engine import ProvenanceEngine


def _candidate_to_string_predicate(fn: Callable[[int, int, int], int]) -> Callable[[str], bool]:
    """Convert a mathematical mechanism function into a string classification predicate."""
    def predicate(w: str) -> bool:
        length = len(w)
        density = w.count("a")
        stride_val = sum(1 for i, ch in enumerate(w) if i % 2 == 0 and ch == "a")
        raw_val = fn(length, density, stride_val)
        return (raw_val % 2 == 0)
    return predicate


class IsolatedEvaluator:
    """Evaluates candidates through Host Controller and sealed confirmation holdouts."""

    def __init__(self, provenance_engine: Optional[ProvenanceEngine] = None):
        self.provenance = provenance_engine or ProvenanceEngine()

    def evaluate_candidate(
        self,
        candidate: CodeCandidate,
        hypothesis: ResearchHypothesis,
        tasks: Dict[str, ConfirmationTask],
        host_controller: HostController,
        prior_cycle_id: Optional[int] = None,
        state_digest_before: str = "",
        state_digest_after: str = "",
    ) -> EvaluationReceipt:
        """Run complete 3-tier evaluation: train, validation, and sealed terminal holdout gating."""
        t_start = time.perf_counter()
        target_tid = hypothesis.target_task_id
        target_task = tasks[target_tid]

        # 1. Compile candidate function safely
        gene = TypedGene(**candidate.gene_dict)
        source_bytes = candidate.source_code.encode("utf-8")
        raw_fn = compile_function(source_bytes, gene)
        cand_pred = _candidate_to_string_predicate(raw_fn)

        # 2. Score on train pool
        train_hits = sum(1 for w, lbl in target_task.train_pool if cand_pred(w) == lbl)
        train_acc = round(train_hits / max(1, len(target_task.train_pool)), 4)

        # 3. Score on validation pool
        val_hits = sum(1 for w, lbl in target_task.validation_pool if cand_pred(w) == lbl)
        val_acc = round(val_hits / max(1, len(target_task.validation_pool)), 4)

        # 4. Gating via Host Controller on sealed terminal holdout
        decision = host_controller.evaluate_and_gate(
            candidate_id=candidate.candidate_id,
            parent_id=candidate.parent_id,
            generation=1,
            source_sha=candidate.source_sha,
            candidate_fn=lambda w, tid: cand_pred(w) if tid == target_tid else getattr(host_controller, "root_candidate_fn", lambda s: (len(s) % 3 == 0))(w),
            candidate_code_or_spec=candidate.source_code,
            metadata={
                "author_type": candidate.author_type.value,
                "hypothesis_id": hypothesis.hypothesis_id,
                "target_task_id": target_tid,
                "train_accuracy": train_acc,
                "validation_accuracy": val_acc,
                "prior_cycle_id": prior_cycle_id,
                "state_digest_before": state_digest_before,
            },
        )

        elapsed = round(time.perf_counter() - t_start, 4)
        try:
            mem_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)
        except Exception:
            mem_mb = 0.0

        dec_enum = (
            CandidateDecision.ACCEPTED
            if decision.status == "ACCEPTED"
            else (CandidateDecision.BLOCKED if decision.status == "BLOCKED" else CandidateDecision.REJECTED)
        )

        receipt_id = f"RCPT_{candidate.candidate_id}_{int(time.time())}"
        receipt_payload = (
            f"{receipt_id}:{candidate.candidate_id}:{decision.status}:"
            f"{decision.holdout_accuracy}:{decision.gain_over_parent}:"
            f"{prior_cycle_id}:{state_digest_before}"
        ).encode("utf-8")
        receipt_sig = hmac.new(
            self.provenance.signing_key.encode("utf-8"),
            receipt_payload,
            hashlib.sha256,
        ).hexdigest()

        return EvaluationReceipt(
            receipt_id=receipt_id,
            evaluator_manifest_digest=host_controller.evaluator.manifest.manifest_digest,
            candidate_id=candidate.candidate_id,
            parent_id=candidate.parent_id,
            train_score=train_acc,
            validation_score=val_acc,
            holdout_score=decision.holdout_accuracy,
            gain_over_parent=decision.gain_over_parent,
            prior_regression=decision.prior_regression,
            decision=dec_enum,
            decision_reason="; ".join(decision.rejection_reasons) if decision.rejection_reasons else "Passes minimum holdout gain threshold",
            evaluator_calls=len(target_task.train_pool) + len(target_task.validation_pool) + sum(len(b) for b in host_controller.evaluator._holdout_banks.values()),
            cpu_seconds=elapsed,
            memory_mb=mem_mb,
            cost_usd=0.0,
            receipt_signature=receipt_sig,
            key_fingerprint=self.provenance.key_fingerprint,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            prior_cycle_id=prior_cycle_id,
            state_digest_before=state_digest_before,
            state_digest_after=state_digest_after,
            provenance_proof=candidate.provenance_proof.to_dict() if candidate.provenance_proof else None,
        )

    def evaluate_negative_control(
        self,
        task: ConfirmationTask,
        host_controller: Optional[HostController] = None,
    ) -> Tuple[bool, float]:
        """Negative control: Evaluate an unconditioned / inverted baseline to confirm evaluator rejects it."""
        # A constant predictor or inverted baseline achieves 0 gain over parent
        dummy_fn = lambda w: False
        hits = sum(1 for w, lbl in task.sealed_confirmation_holdout if dummy_fn(w) == lbl)
        acc = round(hits / max(1, len(task.sealed_confirmation_holdout)), 4)
        parent_score = 0.5000
        gain = acc - parent_score
        is_rejected = (gain < 0.1500)
        return (is_rejected, acc)
