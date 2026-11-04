"""Profile the eight current policies on public cases under selection budgets."""

import json
import platform
import random
from statistics import mean, quantiles

from e13.evaluator.bank import development_bank
from e13.evaluator.pilot import source_digest
from e13.evaluator.selection_budget import LIMITS, evaluate_arm
from e13.evaluator.transfer_bank import transfer_bank


POLICIES = ("fixed", "structured", "enumerative", "beam", "c_extend", "c_no_extend",
            "c_no_transfer", "c_sham")


def profile():
    episodes = (*development_bank()[0], *transfer_bank())
    jobs = [(episode, policy) for episode in episodes for policy in POLICIES]
    random.Random(131507).shuffle(jobs)
    rows = [evaluate_arm(episode, policy) for episode, policy in jobs]
    results = {}
    for policy in POLICIES:
        selected = [row for row in rows if row["policy"] == policy]
        cpu = [row["total_cpu_us"] for row in selected]
        wall = [row["wall_us"] for row in selected]
        results[policy] = {
            "arms": len(selected), "cpu_mean_us": round(mean(cpu)),
            "cpu_p95_us": round(quantiles(cpu, n=20, method="inclusive")[18]),
            "cpu_max_us": max(cpu), "wall_mean_us": round(mean(wall)), "wall_max_us": max(wall),
            "steps_max": max(row["fit_steps"] + row["predict_steps"] for row in selected),
            "rss_max_kib": max(row["fit"]["rss_kib"] for row in selected),
            "score_cap_arms": sum(row["cap_reached"] for row in selected),
            "fit_fuel_exhausted_arms": sum(row["fit_status"] == "fuel_exhausted" for row in selected),
        }
    return {
        "mode": "public_development_resource_profile", "source_sha256": source_digest(),
        "platform": platform.machine(), "kernel": platform.release(), "order_seed": 131507,
        "episodes": len(episodes), "arms": len(rows), "limits": LIMITS, "by_policy": results,
        "scope": "eight candidate policies, evaluator/oracle generation and replay excluded",
    }


if __name__ == "__main__":
    print(json.dumps(profile(), indent=2))
