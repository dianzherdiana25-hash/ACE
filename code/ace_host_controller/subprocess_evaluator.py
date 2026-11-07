"""SubprocessSealedEvaluator managing out-of-process candidate evaluation.

Spawns isolated worker processes to evaluate candidate source code without
ever leaking holdout test labels or signing keys into the worker process.
Parent process evaluates predictions against private holdout banks and signs receipts.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import subprocess
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .boundary import SealingStatus, detect_os_sealing
from .budget_permits import ExecutionBudget
from .sealed_evaluator import EvaluationReceipt, EvaluatorManifest, SealedHoldoutEvaluator


class SubprocessSealedEvaluator:
    """Evaluator that isolates candidate execution within a separate OS subprocess."""

    def __init__(
        self,
        manifest_id: str,
        holdout_banks: Mapping[str, Sequence[Tuple[str, bool]]],
        prior_baseline_scores: Optional[Mapping[str, float]] = None,
        signing_key: Optional[bytes] = None,
        timeout_seconds: float = 30.0,
    ):
        self.manifest_id = manifest_id
        # Private holdouts; NEVER exposed via public properties or sent with labels to workers
        self._holdout_banks = {k: list(v) for k, v in holdout_banks.items()}
        self._prior_baseline_scores = dict(prior_baseline_scores or {})
        self._signing_key = signing_key or secrets.token_bytes(32)
        self.timeout_seconds = timeout_seconds
        self.sealing_status = detect_os_sealing()

        # In-process evaluator for manifest and receipt verification
        self._local_evaluator = SealedHoldoutEvaluator(
            manifest_id=manifest_id,
            holdout_banks=self._holdout_banks,
            prior_baseline_scores=self._prior_baseline_scores,
            signing_key=self._signing_key,
        )
        self.manifest = self._local_evaluator.manifest

    def get_holdout_inputs_for_ledger_only(self) -> List[str]:
        """Restricted supervisor method returning input keys for non-contamination checking only."""
        inputs = []
        for bank in self._holdout_banks.values():
            for inp, _ in bank:
                inputs.append(inp)
        return inputs

    def update_baseline_scores(self, new_scores: Mapping[str, float]) -> None:
        """Update baseline scores safely without leaking holdout banks."""
        for k, v in new_scores.items():
            self._prior_baseline_scores[k] = float(v)
        self._local_evaluator.update_baseline_scores(new_scores)

    def evaluate_candidate_isolated(
        self,
        candidate_id: str,
        candidate_source: str,
        budget: ExecutionBudget,
        max_regression: float = 0.02,
    ) -> EvaluationReceipt:
        """Evaluate candidate code in a separated subprocess.
        
        The worker receives ONLY inputs (queries); holdout labels and signing keys
        remain strictly in the parent process.
        """
        budget.record_candidate_eval()

        # Strip all labels: worker gets ONLY inputs
        inputs_by_task = {k: [inp for inp, _ in v] for k, v in self._holdout_banks.items()}
        payload = {
            "candidate_id": candidate_id,
            "source_code": candidate_source,
            "inputs_by_task": inputs_by_task,
        }

        t_start = time.monotonic()
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "ace_host_controller.isolated_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(
                input=json.dumps(payload), timeout=self.timeout_seconds
            )
            elapsed = time.monotonic() - t_start
            budget.consume_time(elapsed)

            if proc.returncode != 0:
                # Subprocess crashed or exited with error
                return EvaluationReceipt(
                    receipt_id=f"rcpt_fail_{candidate_id}",
                    candidate_id=candidate_id,
                    holdout_accuracy=0.0,
                    holdout_count=0,
                    prior_regression=1.0,
                    evaluator_manifest_digest=self.manifest.manifest_digest,
                    execution_seconds=round(elapsed, 4),
                    passed=False,
                    hmac_signature="0000000000000000000000000000000000000000000000000000000000000000",
                )

            res = json.loads(stdout)
            if "error" in res or "predictions_by_task" not in res:
                return EvaluationReceipt(
                    receipt_id=f"rcpt_err_{candidate_id}",
                    candidate_id=candidate_id,
                    holdout_accuracy=0.0,
                    holdout_count=0,
                    prior_regression=1.0,
                    evaluator_manifest_digest=self.manifest.manifest_digest,
                    execution_seconds=round(elapsed, 4),
                    passed=False,
                    hmac_signature="0000000000000000000000000000000000000000000000000000000000000000",
                )

            # Evaluate worker predictions against private holdout banks
            predictions_by_task = res["predictions_by_task"]
            total_correct = 0
            total_samples = 0
            task_accuracies: Dict[str, float] = {}

            for task_name, bank in self._holdout_banks.items():
                preds = predictions_by_task.get(task_name, [])
                task_correct = 0
                for i, (_, expected) in enumerate(bank):
                    pred = preds[i] if i < len(preds) else (not expected)
                    if pred == expected:
                        task_correct += 1
                acc = task_correct / max(1, len(bank))
                task_accuracies[task_name] = acc
                total_correct += task_correct
                total_samples += len(bank)

            overall_acc = total_correct / max(1, total_samples)

            # Compute regression against prior baseline tasks
            max_reg = 0.0
            for task_name, prior_acc in self._prior_baseline_scores.items():
                curr_acc = task_accuracies.get(task_name, 0.0)
                if curr_acc < prior_acc:
                    diff = prior_acc - curr_acc
                    if diff > max_reg:
                        max_reg = diff

            passed = (max_reg <= max_regression)

            # Issue and sign receipt inside parent process
            receipt_id = f"rcpt_iso_{candidate_id}_{int(time.time())}"
            payload_str = f"{receipt_id}:{candidate_id}:{overall_acc:.4f}:{total_samples}:{max_reg:.4f}:{self.manifest.manifest_digest}:{passed}"
            sig = hmac.new(self._signing_key, payload_str.encode("utf-8"), hashlib.sha256).hexdigest()

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

        except (subprocess.TimeoutExpired, Exception):
            elapsed = time.monotonic() - t_start
            budget.consume_time(elapsed)
            return EvaluationReceipt(
                receipt_id=f"rcpt_timeout_{candidate_id}",
                candidate_id=candidate_id,
                holdout_accuracy=0.0,
                holdout_count=0,
                prior_regression=1.0,
                evaluator_manifest_digest=self.manifest.manifest_digest,
                execution_seconds=round(elapsed, 4),
                passed=False,
                hmac_signature="0000000000000000000000000000000000000000000000000000000000000000",
            )
