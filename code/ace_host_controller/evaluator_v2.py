"""Sealed Evaluation V2 and Dual-Oracle Governance for ACE Host Controller.

Enforces:
1. Dual Oracle Separation:
   - Experiment Oracle (O_exp): Strictly metered for active learning queries on training domain.
   - Terminal Holdout Oracle (O_term): Sealed for evaluation only; never queryable by candidate.
2. Tamper-Resistant Merkle Exposure Ledger:
   - Hash-chained audit trail of all exposures.
   - Multi-tier contamination detection (exact string match, substring n-gram leakage).
3. Pre-Registration Commitment:
   - Cryptographically locks evaluation parameters and manifests before benchmark execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .budget_permits import BudgetExceededError, ExecutionBudget
from .sealed_evaluator import EvaluationReceipt, EvaluatorManifest


class OracleBoundaryViolation(PermissionError):
    """Raised when candidate generator attempts to query terminal holdouts directly."""


class ContaminationDetectedError(RuntimeError):
    """Raised when benchmark contamination is detected across exact or n-gram checks."""


class LedgerTamperError(ValueError):
    """Raised when exposure ledger hash chain is broken or records are modified."""


@dataclass(frozen=True)
class ChainedExposureRecord:
    """Tamper-resistant exposure record within a cryptographic hash chain."""
    record_id: int
    candidate_id: str
    query_type: str
    query_content: str
    prev_hash: str
    current_hash: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MerkleExposureLedger:
    """Cryptographic hash-chained exposure ledger with multi-tier contamination auditing."""

    def __init__(self):
        self.records: List[ChainedExposureRecord] = []
        self._exposed_strings: set[str] = set()
        self._exposed_ngrams: set[str] = set()

    def record_query(self, candidate_id: str, query_type: str, content: str) -> ChainedExposureRecord:
        """Record an exposure in the hash chain."""
        prev_h = self.records[-1].current_hash if self.records else "0" * 64
        rec_id = len(self.records)

        payload = f"{rec_id}:{candidate_id}:{query_type}:{content}:{prev_h}"
        curr_h = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        rec = ChainedExposureRecord(
            record_id=rec_id,
            candidate_id=candidate_id,
            query_type=query_type,
            query_content=content,
            prev_hash=prev_h,
            current_hash=curr_h,
        )
        self.records.append(rec)
        self._exposed_strings.add(content)

        # Index 4-grams and above (up to 16-grams) for substring leakage checking
        max_n = min(16, len(content))
        for n in range(4, max_n + 1):
            for i in range(len(content) - n + 1):
                self._exposed_ngrams.add(content[i : i + n])

        return rec

    def verify_chain_integrity(self) -> bool:
        """Verify that no record in the ledger has been modified, deleted, or inserted."""
        prev = "0" * 64
        for rec in self.records:
            if rec.prev_hash != prev:
                return False
            payload = f"{rec.record_id}:{rec.candidate_id}:{rec.query_type}:{rec.query_content}:{rec.prev_hash}"
            expected_h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if rec.current_hash != expected_h:
                return False
            prev = rec.current_hash
        return True

    def check_contamination_multitier(
        self, holdout_samples: Sequence[str], min_ngram_overlap_len: int = 8
    ) -> Dict[str, Any]:
        """Perform multi-tier contamination verification:
        1. Exact string matches
        2. Long substring / n-gram leakage
        """
        exact_leaks: List[str] = []
        ngram_leaks: List[Tuple[str, str]] = []

        for h in holdout_samples:
            if h in self._exposed_strings:
                exact_leaks.append(h)
            # Check long substring overlap if holdout length >= min_ngram_overlap_len
            if len(h) >= min_ngram_overlap_len:
                for i in range(len(h) - min_ngram_overlap_len + 1):
                    sub = h[i : i + min_ngram_overlap_len]
                    if sub in self._exposed_ngrams:
                        ngram_leaks.append((h, sub))
                        break

        is_contaminated = bool(exact_leaks or ngram_leaks)
        return {
            "is_contaminated": is_contaminated,
            "exact_leak_count": len(exact_leaks),
            "exact_leaks": exact_leaks[:5],
            "ngram_leak_count": len(ngram_leaks),
            "ngram_leaks": ngram_leaks[:5],
        }

    @property
    def merkle_root(self) -> str:
        """Top cryptographic hash of the ledger chain."""
        return self.records[-1].current_hash if self.records else "0" * 64

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_count": len(self.records),
            "merkle_root": self.merkle_root,
            "chain_valid": self.verify_chain_integrity(),
            "records": [r.to_dict() for r in self.records],
        }


@dataclass(frozen=True)
class PreRegistrationCommitment:
    """Pre-registration commitment locking evaluation parameters before opening holdouts."""
    commitment_id: str
    manifest_digest: str
    min_gain: float
    max_regression: float
    target_tasks: Tuple[str, ...]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def commitment_hash(self) -> str:
        payload = f"{self.commitment_id}:{self.manifest_digest}:{self.min_gain:.4f}:{self.max_regression:.4f}:{sorted(self.target_tasks)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "commitment_hash": self.commitment_hash,
            "manifest_digest": self.manifest_digest,
            "min_gain": self.min_gain,
            "max_regression": self.max_regression,
            "target_tasks": list(self.target_tasks),
            "timestamp": self.timestamp,
        }


class DualOracleHarness:
    """Decoupled dual-oracle evaluation harness strictly separating training from terminal evaluation."""

    def __init__(
        self,
        experiment_oracles: Mapping[str, Callable[[str], bool]],
        terminal_holdouts: Mapping[str, Sequence[Tuple[str, bool]]],
        prior_baseline_scores: Optional[Mapping[str, float]] = None,
        signing_key: Optional[bytes] = None,
    ):
        self._experiment_oracles = dict(experiment_oracles)
        self._terminal_holdouts = {k: list(v) for k, v in terminal_holdouts.items()}
        self._prior_baseline_scores = dict(prior_baseline_scores or {})
        self._signing_key = signing_key or secrets.token_bytes(32)

        self.exposure_ledger = MerkleExposureLedger()

        # Compute terminal manifest
        bank_hashes: Dict[str, str] = {}
        for name, bank in sorted(self._terminal_holdouts.items()):
            serialized_bank = json.dumps([[x[0], x[1]] for x in bank], sort_keys=True)
            bank_hashes[name] = hashlib.sha256(serialized_bank.encode("utf-8")).hexdigest()

        self.manifest = EvaluatorManifest(
            manifest_id="dual_oracle_manifest_v2",
            manifest_version="2.0.0",
            holdout_bank_hashes=bank_hashes,
            oracle_hash=hashlib.sha256(b"dual_oracle_sealed_v2").hexdigest(),
        )

    def query_experiment_oracle(
        self,
        candidate_id: str,
        task_id: str,
        input_str: str,
        budget: ExecutionBudget,
    ) -> bool:
        """Execute a metered epistemic query against the experiment oracle only."""
        budget.consume_queries(1)

        # Log query in Merkle exposure ledger
        self.exposure_ledger.record_query(
            candidate_id=candidate_id,
            query_type="epistemic_experiment_probe",
            content=input_str,
        )

        if task_id not in self._experiment_oracles:
            raise KeyError(f"Task '{task_id}' not found in experiment oracle registry")

        # Answer strictly from experiment oracle; never consult terminal holdout
        return bool(self._experiment_oracles[task_id](input_str))

    def query_terminal_oracle(self, candidate_id: str, task_id: str, input_str: str) -> None:
        """Terminal holdout oracle cannot be queried by candidates under any circumstances."""
        raise OracleBoundaryViolation(
            f"Candidate '{candidate_id}' attempted forbidden direct query to terminal holdout oracle for task '{task_id}'"
        )

    def update_baseline_scores(self, new_scores: Mapping[str, float]) -> None:
        """Safely update prior baseline scores in dual oracle harness."""
        for k, v in new_scores.items():
            self._prior_baseline_scores[k] = float(v)

    def evaluate_terminal_holdouts(
        self,
        candidate_id: str,
        candidate_fn: Callable[[str, Optional[str]], bool],
        budget: ExecutionBudget,
        min_gain: float = 0.15,
        max_regression: float = 0.02,
        parent_score: float = 0.50,
    ) -> EvaluationReceipt:
        """Evaluate candidate mechanism on sealed terminal holdouts and check contamination."""
        budget.record_candidate_eval()

        # Check ledger chain integrity first
        if not self.exposure_ledger.verify_chain_integrity():
            raise LedgerTamperError("Exposure ledger integrity violation detected")

        # Check multi-tier contamination
        all_terminal_inputs = [inp for bank in self._terminal_holdouts.values() for inp, _ in bank]
        contam = self.exposure_ledger.check_contamination_multitier(all_terminal_inputs)
        if contam["is_contaminated"]:
            raise ContaminationDetectedError(
                f"Contamination detected! Exact: {contam['exact_leak_count']}, N-gram: {contam['ngram_leak_count']}"
            )

        t_start = time.monotonic()
        total_correct = 0
        total_samples = 0
        task_accuracies: Dict[str, float] = {}

        for task_name, bank in self._terminal_holdouts.items():
            task_correct = 0
            for inp, expected in bank:
                try:
                    try:
                        pred = bool(candidate_fn(inp, task_name))
                    except TypeError:
                        pred = bool(candidate_fn(inp))
                except Exception:
                    pred = not expected
                if pred == expected:
                    task_correct += 1
            acc = task_correct / max(1, len(bank))
            task_accuracies[task_name] = acc
            total_correct += task_correct
            total_samples += len(bank)

        elapsed = time.monotonic() - t_start
        budget.consume_time(elapsed)

        overall_acc = total_correct / max(1, total_samples)

        # Compute prior regression
        max_reg = 0.0
        for task_name, prior_acc in self._prior_baseline_scores.items():
            curr_acc = task_accuracies.get(task_name, 0.0)
            if curr_acc < prior_acc:
                diff = prior_acc - curr_acc
                if diff > max_reg:
                    max_reg = diff

        gain = overall_acc - parent_score
        passed = (gain >= min_gain) and (max_reg <= max_regression)

        receipt_id = f"rcpt_dual_{candidate_id}_{int(time.time())}"
        payload = f"{receipt_id}:{candidate_id}:{overall_acc:.4f}:{total_samples}:{max_reg:.4f}:{self.manifest.manifest_digest}:{passed}"
        sig = hmac.new(self._signing_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()

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
        """Verify authenticity of signed evaluation receipt."""
        payload = f"{receipt.receipt_id}:{receipt.candidate_id}:{receipt.holdout_accuracy:.4f}:{receipt.holdout_count}:{receipt.prior_regression:.4f}:{receipt.evaluator_manifest_digest}:{receipt.passed}"
        expected_sig = hmac.new(self._signing_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(receipt.hmac_signature, expected_sig)
