"""SubprocessSealedEvaluator managing out-of-process candidate evaluation.

Spawns isolated worker processes to evaluate candidate source code without
ever leaking holdout test sets into the calling candidate generator memory space.
"""
from __future__ import annotations

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
        # Private holdouts; NEVER exposed via public properties
        self._holdout_banks = {k: list(v) for k, v in holdout_banks.items()}
        self._prior_baseline_scores = dict(prior_baseline_scores or {})
        self._signing_key = signing_key or secrets.token_bytes(32)
        self.timeout_seconds = timeout_seconds
        self.sealing_status = detect_os_sealing()

        # In-process backup evaluator for manifest and receipt verification
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

    def evaluate_candidate_isolated(
        self,
        candidate_id: str,
        candidate_source: str,
        budget: ExecutionBudget,
        max_regression: float = 0.02,
    ) -> EvaluationReceipt:
        """Evaluate candidate code in a separated subprocess."""
        budget.record_candidate_eval()

        payload = {
            "candidate_id": candidate_id,
            "source_code": candidate_source,
            "holdout_banks": {k: [list(x) for x in v] for k, v in self._holdout_banks.items()},
            "prior_baseline_scores": self._prior_baseline_scores,
            "signing_key_hex": self._signing_key.hex(),
            "max_regression": max_regression,
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
            if "error" in res or not res.get("passed", False):
                return EvaluationReceipt(
                    receipt_id=res.get("receipt_id", f"rcpt_err_{candidate_id}"),
                    candidate_id=candidate_id,
                    holdout_accuracy=float(res.get("holdout_accuracy", 0.0)),
                    holdout_count=int(res.get("holdout_count", 0)),
                    prior_regression=float(res.get("prior_regression", 1.0)),
                    evaluator_manifest_digest=self.manifest.manifest_digest,
                    execution_seconds=round(elapsed, 4),
                    passed=False,
                    hmac_signature=res.get("hmac_signature", ""),
                )

            receipt = EvaluationReceipt(
                receipt_id=res["receipt_id"],
                candidate_id=res["candidate_id"],
                holdout_accuracy=float(res["holdout_accuracy"]),
                holdout_count=int(res["holdout_count"]),
                prior_regression=float(res["prior_regression"]),
                evaluator_manifest_digest=res["evaluator_manifest_digest"],
                execution_seconds=float(res["execution_seconds"]),
                passed=bool(res["passed"]),
                hmac_signature=res["hmac_signature"],
            )

            # Verify receipt signature with supervisor key
            if not self._local_evaluator.verify_receipt(receipt):
                raise ValueError("Worker returned invalid HMAC signature on receipt")

            return receipt

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
