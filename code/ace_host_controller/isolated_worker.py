"""Isolated evaluator process worker for ACE Host Boundary V2.

Executes candidate evaluation inside a separate OS process:
- Holdout test samples exist exclusively in this worker process.
- Candidate code is compiled in a sandbox namespace with safe builtins only.
- Returns only HMAC-signed EvaluationReceipt JSON to stdout; never holdout inputs or labels.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import sys
import time
from typing import Any, Callable, Dict, List, Tuple

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "enumerate": enumerate,
    "int": int,
    "len": len,
    "max": max,
    "min": min,
    "range": range,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "None": None,
    "True": True,
    "False": False,
}


def compile_candidate_safe(source_code: str) -> Callable[..., bool]:
    """Compile candidate source code in restricted namespace without dangerous builtins."""
    namespace: Dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    compiled = compile(source_code, "<candidate_isolated>", "exec")
    exec(compiled, namespace)

    # Candidate must expose candidate_fn
    if "candidate_fn" not in namespace or not callable(namespace["candidate_fn"]):
        raise ValueError("Candidate source must define callable 'candidate_fn'")
    return namespace["candidate_fn"]


def run_isolated_evaluation(
    holdout_banks: Dict[str, List[Tuple[str, bool]]],
    prior_baseline_scores: Dict[str, float],
    signing_key: bytes,
    candidate_id: str,
    source_code: str,
    max_regression: float = 0.02,
) -> Dict[str, Any]:
    """Execute evaluation in isolated memory space."""
    t_start = time.monotonic()
    cand_fn = compile_candidate_safe(source_code)

    total_correct = 0
    total_samples = 0
    task_accuracies: Dict[str, float] = {}

    for task_name, bank in holdout_banks.items():
        task_correct = 0
        for inp, expected in bank:
            try:
                try:
                    pred = bool(cand_fn(inp, task_name))
                except TypeError:
                    pred = bool(cand_fn(inp))
            except Exception:
                pred = not expected
            if pred == expected:
                task_correct += 1
        acc = task_correct / max(1, len(bank))
        task_accuracies[task_name] = acc
        total_correct += task_correct
        total_samples += len(bank)

    elapsed = time.monotonic() - t_start
    overall_acc = total_correct / max(1, total_samples)

    # Compute regression against prior baseline tasks
    max_reg = 0.0
    for task_name, prior_acc in prior_baseline_scores.items():
        curr_acc = task_accuracies.get(task_name, 0.0)
        if curr_acc < prior_acc:
            diff = prior_acc - curr_acc
            if diff > max_reg:
                max_reg = diff

    passed = (max_reg <= max_regression)

    # Compute HMAC receipt
    manifest_digest = hashlib.sha256(
        json.dumps(
            {t: hashlib.sha256(json.dumps(b).encode("utf-8")).hexdigest() for t, b in sorted(holdout_banks.items())},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    receipt_id = f"rcpt_iso_{candidate_id}_{int(time.time())}"
    payload = f"{receipt_id}:{candidate_id}:{overall_acc:.4f}:{total_samples}:{max_reg:.4f}:{manifest_digest}:{passed}"
    sig = hmac.new(signing_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    return {
        "receipt_id": receipt_id,
        "candidate_id": candidate_id,
        "holdout_accuracy": round(overall_acc, 4),
        "holdout_count": total_samples,
        "prior_regression": round(max_reg, 4),
        "evaluator_manifest_digest": manifest_digest,
        "execution_seconds": round(elapsed, 4),
        "passed": passed,
        "hmac_signature": sig,
        "isolation_mode": "SUBPROCESS_SEALED",
    }


def main() -> int:
    """CLI entrypoint reading candidate payload from stdin."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            print(json.dumps({"error": "Empty input payload"}))
            return 1
        data = json.loads(raw_input)

        holdout_banks = {k: [tuple(x) for x in v] for k, v in data["holdout_banks"].items()}
        prior_baseline_scores = data.get("prior_baseline_scores", {})
        signing_key = bytes.fromhex(data["signing_key_hex"])
        candidate_id = data["candidate_id"]
        source_code = data["source_code"]
        max_regression = float(data.get("max_regression", 0.02))

        receipt = run_isolated_evaluation(
            holdout_banks=holdout_banks,
            prior_baseline_scores=prior_baseline_scores,
            signing_key=signing_key,
            candidate_id=candidate_id,
            source_code=source_code,
            max_regression=max_regression,
        )
        print(json.dumps(receipt))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc), "failed": True}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
