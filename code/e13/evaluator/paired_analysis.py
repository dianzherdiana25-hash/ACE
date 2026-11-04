"""Paired rule-block estimand and stratified percentile bootstrap for E1.3."""

from collections import defaultdict
from statistics import mean

import numpy as np


FAMILIES = ("S", "G")
PRIMARY = ("c_extend", "beam")
MIN_EFFECT = 0.10
ANALYSIS_SEED = 131508
RESAMPLES = 10_000


def block_effects(rows, *, blocks_per_family, episodes_per_block=2, seed_slots=(0, 1, 2),
                  probes_per_arm=8):
    """Require the planned complete pairing before aggregating primary scores."""
    pairs = defaultdict(dict)
    for row in rows:
        family, policy = row["family"], row["policy"]
        if (family not in FAMILIES or policy not in PRIMARY or row["regime"] != "related"
                or row["seed_slot"] not in seed_slots):
            raise ValueError("unexpected primary observation")
        correct, total = row["correct"], row["total"]
        if (type(correct) is not int or type(total) is not int or total != probes_per_arm
                or not 0 <= correct <= total):
            raise ValueError("unexpected score or denominator")
        status = row["status"]
        if status not in ("scored", "candidate_failure") or (status == "candidate_failure" and correct):
            raise ValueError("invalid or unresolved observation status")
        key = family, row["block"], row["episode"], row["seed_slot"]
        if policy in pairs[key]:
            raise ValueError("duplicate primary arm")
        pairs[key][policy] = correct / total

    blocks = defaultdict(lambda: defaultdict(dict))
    for (family, block, episode, seed_slot), pair in pairs.items():
        if pair.keys() != set(PRIMARY):
            raise ValueError("incomplete paired comparison")
        blocks[family, block][episode][seed_slot] = pair[PRIMARY[0]] - pair[PRIMARY[1]]

    effects = {family: [] for family in FAMILIES}
    for (family, _block), episodes in sorted(blocks.items()):
        if len(episodes) != episodes_per_block:
            raise ValueError("unexpected episodes per block")
        if any(slots.keys() != set(seed_slots) for slots in episodes.values()):
            raise ValueError("incomplete seed pairing")
        effects[family].append(mean(mean(slots.values()) for slots in episodes.values()))
    if any(len(values) != blocks_per_family for values in effects.values()):
        raise ValueError("unexpected rule-block count")
    return effects


def bootstrap_means(groups, *, rng, resamples):
    """Draw independently within each family, preserving pairing within a block."""
    draws = []
    for values in groups:
        values = np.asarray(values, dtype=np.float64)
        n = values.shape[-1]
        if n < 2 or np.any(~np.isfinite(values)) or np.any(np.abs(values) > 1):
            raise ValueError("expected at least two valid paired effects per family")
        weights = rng.multinomial(n, np.full(n, 1.0 / n), size=resamples)
        draws.append(values @ weights.T / n)
    return draws


def analyze(effects, *, seed=ANALYSIS_SEED, resamples=RESAMPLES):
    groups = [np.asarray(effects[family], dtype=np.float64) for family in FAMILIES]
    draws = bootstrap_means(groups, rng=np.random.default_rng(seed), resamples=resamples)
    estimate = float(np.mean([g.mean() for g in groups]))
    lower, upper = np.quantile(np.mean(draws, axis=0), [0.025, 0.975], method="linear")
    decision = "inconclusive"
    if estimate >= MIN_EFFECT and lower > 0:
        decision = "supports_primary_if_other_gates_pass"
    elif upper < MIN_EFFECT:
        decision = "minimum_effect_not_supported"
    return {
        "estimate": estimate, "interval": [float(lower), float(upper)], "decision": decision,
        "families": {
            f: {"blocks": len(values), "estimate": float(values.mean()),
                "interval": np.quantile(boot, [0.025, 0.975], method="linear").tolist()}
            for f, values, boot in zip(FAMILIES, groups, draws, strict=True)
        },
    }
