"""Planning simulation for paired E1.3 rule blocks, without confirmatory data."""

import argparse
import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np

from .paired_analysis import MIN_EFFECT, bootstrap_means

SEED = 131509
TRIALS = 2_000
BOOTSTRAP = 999
BLOCKS = (16, 24, 32, 48, 64, 96)
SCENARIOS = (
    ("null_moderate", (0.0, 0.0), (0.35, 0.35)),
    ("null_stress", (0.0, 0.0), (0.45, 0.45)),
    ("boundary_moderate", (0.10, 0.10), (0.35, 0.35)),
    ("boundary_stress", (0.10, 0.10), (0.45, 0.45)),
    ("design_low_variation", (0.15, 0.15), (0.25, 0.25)),
    ("design_moderate", (0.15, 0.15), (0.35, 0.35)),
    ("design_stress", (0.15, 0.15), (0.45, 0.45)),
    ("design_uneven", (0.25, 0.05), (0.35, 0.45)),
)
REQUIRED = ("design_moderate", "design_stress", "design_uneven")


def _blocks(rng, *, effect, sd, trials, n):
    # Scale a beta distribution to the feasible range of an accuracy difference.
    average = (1 + effect) / 2
    concentration = average * (1 - average) / (sd / 2) ** 2 - 1
    return 2 * rng.beta(average * concentration, (1 - average) * concentration,
                        size=(trials, n)) - 1


def _probability(indicator):
    count, n = int(indicator.sum()), len(indicator)
    p = count / n
    z = NormalDist().inv_cdf(0.975)
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return {"successes": count, "rate": round(p, 4),
            "mc_interval": [round(max(0, center - margin), 4), round(min(1, center + margin), 4)]}


def simulate(name, effects, sds, n, *, rng, trials=TRIALS, resamples=BOOTSTRAP):
    groups = [_blocks(rng, effect=effect, sd=sd, trials=trials, n=n)
              for effect, sd in zip(effects, sds, strict=True)]
    estimates = np.mean([group.mean(axis=1) for group in groups], axis=0)
    draws = bootstrap_means(groups, rng=rng, resamples=resamples)
    lower = np.quantile((draws[0] + draws[1]) / 2, 0.025, axis=1, method="linear")
    family_lower = [np.quantile(draw, 0.025, axis=1, method="linear") for draw in draws]
    return {
        "scenario": name, "blocks_per_family": n, "family_effects": effects, "family_sd": sds,
        "lower_above_zero": _probability(lower > 0),
        "primary_gate": _probability((lower > 0) & (estimates >= MIN_EFFECT)),
        "both_family_lowers_above_zero": _probability((family_lower[0] > 0) & (family_lower[1] > 0)),
    }


def report(profile):
    rng = np.random.default_rng(SEED)
    results = [simulate(name, effects, sds, n, rng=rng)
               for name, effects, sds in SCENARIOS for n in BLOCKS]
    by_case = {(row["scenario"], row["blocks_per_family"]): row for row in results}
    # Require the lower Monte Carlo interval endpoint to clear 80% for the
    # prespecified planning alternatives, including the high-variation case.
    chosen = next((n for n in BLOCKS if all(
        by_case[name, n]["primary_gate"]["mc_interval"][0] >= 0.80 for name in REQUIRED
    )), None)
    resources = []
    for n in BLOCKS:
        # Include an equally sized negative-transfer stratum in both families.
        arms_per_policy = 2 * 2 * n * 2 * 3
        cpu = sum(p["cpu_mean_us"] for p in profile["by_policy"].values()) / 1_000_000
        wall = sum(p["wall_mean_us"] for p in profile["by_policy"].values()) / 1_000_000
        resources.append({
            "blocks_per_family_per_regime": n, "episodes_per_block": 2, "seeds_per_episode": 3,
            "eight_measured_policy_arms": 8 * arms_per_policy,
            "planned_nine_policy_arms": 9 * arms_per_policy,
            "profile_projected_eight_policy_cpu_seconds": round(cpu * arms_per_policy, 1),
            "profile_projected_eight_policy_wall_seconds": round(wall * arms_per_policy, 1),
            "nine_policy_cpu_ceiling_seconds": 9 * arms_per_policy,
            "nine_policy_wall_ceiling_seconds": 3 * 9 * arms_per_policy,
        })
    return {
        "mode": "preconfirmation_design_sensitivity", "numpy_version": np.__version__,
        "seed": SEED, "trials_per_scenario": TRIALS, "bootstrap_draws_per_trial": BOOTSTRAP,
        "model": "independent beta-distributed paired block effects on [-1,1], equal family weights",
        "bootstrap": "independent family weights, shared across simulated trials within each scenario",
        "minimum_observed_effect": MIN_EFFECT, "required_scenarios": REQUIRED,
        "planning_block_count_per_family_per_regime": chosen, "results": results, "resources": resources,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="public resource profile JSON")
    args = parser.parse_args()
    print(json.dumps(report(json.loads(args.profile.read_text())), separators=(",", ":")))


if __name__ == "__main__":
    main()
