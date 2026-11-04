"""Frozen, corrected second development pilot for query-policy transfer.

Uses exactly the same candidate, eight policies, and predeclared GO/HOLD gate
as v1. The only intended scientific change is bank PRNG independence.
"""
import argparse
import json
import re
from pathlib import Path

from e13.contract import canonical_json
from .cross_episode import (
    SEED, decide, evaluate_source, evaluate_target, select_inherited, summary,
)
from .cross_episode_bank_v2 import bank, bank_digest, POOL_SEED, DEMO_SEED


def run(source_commit):
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("frozen source commit is required")
    pairs = bank()
    source_rows = [evaluate_source(source) for source, _ in pairs]
    policies = select_inherited(source_rows)
    targets = [evaluate_target(target, policies[target.family]) for _, target in pairs]
    summaries = summary(targets)
    caps = 0  # finite grammar enumeration; external process supervisor checks wall clock
    return {
        "mode": "E1.4c_public_development_v2", "freeze_version": 2,
        "seed": SEED, "bank_seed": DEMO_SEED, "pool_seed": POOL_SEED,
        "source_commit": source_commit, "bank_sha256": bank_digest(pairs),
        "source_episodes": len(source_rows), "target_episodes": len(targets),
        "total_training_labels": 8 * len(source_rows),
        "target_counterfactual_oracle_calls": 8 * len(targets),
        "one_label_target_budget_per_policy": 1,
        "learned_policies": policies, "sources": source_rows, "targets": targets,
        "summary": summaries, "caps": caps, "decision": decide(summaries, caps),
        "limitations": [
            "Corrected pool preallocation is independent of target-dependent demo RNG.",
            "Posthoc corrective design based on v1 quality audit, not independent confirmation.",
            "Finite known 4-event grammar, not open-ended architecture invention.",
            "96 source labels; per-target one-label parity excludes training amortization.",
            "Eight target counterfactual oracle calls per target, not one observed random arm.",
            "Candidate and evaluator share a process; no worker isolation or sealed data.",
            "Small, human-designed balanced-probe distribution; no confirmatory inference.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--verify", type=Path)
    args = p.parse_args()
    result = run(args.source_commit)
    if args.verify:
        saved = json.loads(args.verify.read_text())
        if canonical_json(saved) != canonical_json(result):
            raise ValueError("E1.4c-v2 deterministic replay mismatch")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
