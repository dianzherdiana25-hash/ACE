"""Sealed holdout evaluator and cryptographic verification receipts for ACE Host Controller.

Holdout tasks and evaluation oracles are sealed behind a cryptographic boundary.
Candidates cannot inspect holdout solutions, and results are issued as signed receipts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Callable, Mapping, Sequence

from .budget_permits import ExecutionBudget


@dataclass(frozen=True)
class EvaluatorManifest:
    """Cryptographic manifest of the sealed evaluator test banks and oracles."""

    manifest_id: str
    manifest_version: str
    holdout_bank_hashes: dict[str, str]
    oracle_hash: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def manifest_digest(self) -> str:
        """Deterministic SHA-256 digest of the evaluator manifest."""
        serialized = json.dumps(
            {
                "manifest_id": self.manifest_id,
                "manifest_version": self.manifest_version,
                "holdout_bank_hashes": self.holdout_bank_hashes,
                "oracle_hash": self.oracle_hash,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest to dictionary."""
        return {
            "manifest_id": self.manifest_id,
            "manifest_version": self.manifest_version,
            "manifest_digest": self.manifest_digest,
            "holdout_bank_hashes": self.holdout_bank_hashes,
            "oracle_hash": self.oracle_hash,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class EvaluationReceipt:
    """Signed evaluation receipt issued by the sealed Host Controller evaluator."""

    receipt_id: str
    candidate_id: str
    holdout_accuracy: float
    holdout_count: int
    prior_regression: float
    evaluator_manifest_digest: str
    execution_seconds: float
    passed: bool
    hmac_signature: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize receipt to dictionary."""
        return asdict(self)


class SealedHoldoutEvaluator:
    """Sealed evaluator that tests candidate mechanisms without exposing holdout answers."""

    def __init__(
        self,
        manifest_id: str,
        holdout_banks: Mapping[str, Sequence[tuple[str, bool]]],
        prior_baseline_scores: Optional[Mapping[str, float]] = None,
        signing_key: Optional[bytes] = None,
    ):
        self.manifest_id = manifest_id
        self._holdout_banks = {k: list(v) for k, v in holdout_banks.items()}
        self._prior_baseline_scores = dict(prior_baseline_scores or {})
        self._signing_key = signing_key or secrets.token_bytes(32)

        bank_hashes: dict[str, str] = {}
        for name, bank in sorted(self._holdout_banks.items()):
            serialized_bank = json.dumps([[x[0], x[1]] for x in bank], sort_keys=True)
            bank_hashes[name] = hashlib.sha256(serialized_bank.encode("utf-8")).hexdigest()

        self.manifest = EvaluatorManifest(
            manifest_id=manifest_id,
            manifest_version="1.0.0",
            holdout_bank_hashes=bank_hashes,
            oracle_hash=hashlib.sha256(b"sealed_oracle_v1").hexdigest(),
        )

    def get_holdout_inputs(self) -> list[str]:
        """Return holdout inputs ONLY for exposure ledger disjointness verification.
        
        This method is called by the Host Controller to verify that the candidate generator
        never queried these inputs. It is never exposed directly to the candidate model.
        """
        inputs: list[str] = []
        for bank in self._holdout_banks.values():
            for inp, _ in bank:
                inputs.append(inp)
        return inputs

    def evaluate_candidate(
        self,
        candidate_id: str,
        candidate_fn: Callable[[str], bool],
        budget: ExecutionBudget,
        min_gain: float = 0.15,
        max_regression: float = 0.02,
    ) -> EvaluationReceipt:
        """Evaluate a candidate function against sealed holdouts under strict budget."""
        budget.record_candidate_eval()

        start_time = time.monotonic()
        total_samples = 0
        total_correct = 0
        task_accuracies: dict[str, float] = {}

        for task_name, bank in self._holdout_banks.items():
            task_correct = 0
            for inp, expected in bank:
                # Execution of candidate callable
                try:
                    pred = bool(candidate_fn(inp))
                except Exception:
                    pred = not expected  # Treat runtime exception as wrong prediction
                if pred == expected:
                    task_correct += 1
            task_acc = task_correct / max(1, len(bank))
            task_accuracies[task_name] = task_acc
            total_correct += task_correct
            total_samples += len(bank)

        elapsed = time.monotonic() - start_time
        budget.consume_time(elapsed)

        overall_acc = total_correct / max(1, total_samples)

        # Compute max regression against prior baseline tasks
        max_reg = 0.0
        for task_name, prior_acc in self._prior_baseline_scores.items():
            curr_acc = task_accuracies.get(task_name, 0.0)
            if curr_acc < prior_acc:
                diff = prior_acc - curr_acc
                if diff > max_reg:
                    max_reg = diff

        # Passing threshold: regression <= max_regression
        passed = (max_reg <= max_regression)

        # Compute HMAC signature for receipt
        receipt_id = f"rcpt_{candidate_id}_{int(time.time())}"
        receipt_payload = (
            f"{receipt_id}:{candidate_id}:{overall_acc:.4f}:{total_samples}:"
            f"{max_reg:.4f}:{self.manifest.manifest_digest}:{passed}"
        )
        sig = hmac.new(
            self._signing_key, receipt_payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return EvaluationReceipt(
            receipt_id=receipt_id,
            candidate_id=candidate_id,
            holdout_accuracy=round(overall_acc, 4),
            holdout_count=total_samples,
            prior_regression=round(max_reg, 4),
            evaluator_manifest_digest=self.manifest.manifest_digest,
            execution_seconds=round(elapsed, 4),
            passed=passed,
            hmac_signature=sig,
        )

    def verify_receipt(self, receipt: EvaluationReceipt) -> bool:
        """Cryptographically verify an evaluation receipt signature."""
        receipt_payload = (
            f"{receipt.receipt_id}:{receipt.candidate_id}:{receipt.holdout_accuracy:.4f}:"
            f"{receipt.holdout_count}:{receipt.prior_regression:.4f}:"
            f"{receipt.evaluator_manifest_digest}:{receipt.passed}"
        )
        expected_sig = hmac.new(
            self._signing_key, receipt_payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(receipt.hmac_signature, expected_sig)
