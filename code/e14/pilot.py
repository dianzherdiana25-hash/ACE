"""Execute the prespecified public E1.4 routing pilot."""

import hashlib
import json
import random
from pathlib import Path

from e13.evaluator.selection_budget import LIMITS, evaluate_arm
from e13.isolation import _SOLVER_FILES

from .isolated import fit_isolated
from .pilot_bank import REGIMES, bank, bank_sha256

POLICIES = ("counter_only", "order_only", "adaptive", "beam")
ORDER_SEED = 141502


def source_digest():
    root = Path(__file__).resolve().parents[1]
    files = [*root.joinpath("e14").glob("*.py"),
             *(root / "e13" / file for file in _SOLVER_FILES),
             *(root / "e13" / file for file in ("patterns.py", "isolation.py",
                                               "evaluator/selection_budget.py"))]
    hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in files if not path.name.startswith("test_")}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def run():
    episodes = bank()
    schedule = [(episode, policy) for episode in episodes for policy in POLICIES]
    random.Random(ORDER_SEED).shuffle(schedule)
    rows = []
    for episode, policy in schedule:
        options = {} if policy == "beam" else {
            "fit_policy": fit_isolated, "reference_extension": True, "keep_trace": True,
        }
        rows.append(evaluate_arm(episode, policy, **options))
    summary = []
    for family in ("S", "G"):
        for regime in REGIMES:
            for policy in POLICIES:
                selected = [row for row in rows if (row["family"], row["regime"], row["policy"])
                            == (family, regime, policy)]
                summary.append({
                    "family": family, "regime": regime, "policy": policy,
                    "correct": sum(score["correct"] for row in selected for score in row["scores"].values()),
                    "total": sum(score["total"] for row in selected for score in row["scores"].values()),
                    "order_routes": sum(row.get("fit_trace", {}).get("route") == "order" for row in selected),
                    "fit_caps": sum(row["fit_status"] == "fuel_exhausted" for row in selected),
                })
    return {
        "mode": "public_development", "scope": "two finite machine families; no inheritance",
        "bank_sha256": bank_sha256(episodes), "source_sha256": source_digest(),
        "limits": LIMITS, "order_seed": ORDER_SEED, "episodes": len(episodes),
        "summary": summary, "runs": rows,
    }


if __name__ == "__main__":
    print(json.dumps(run(), separators=(",", ":")))
