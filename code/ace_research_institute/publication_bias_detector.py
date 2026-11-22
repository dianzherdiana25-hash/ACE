"""Tandai asimetri terkait ukuran studi dengan korelasi rank dan uji permutasi terbatas."""
from fractions import Fraction
from itertools import permutations

from ._contracts import ResearchError, anchor, cli, fmt, number, schema
from ._effect_sizes import effect_sizes


def _ranks(values):
    ranked = sorted(range(len(values)), key=lambda index: (values[index], index))
    result = [0] * len(values)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[ranked[start]] == values[ranked[end]]:
            end += 1
        double_rank = start + 1 + end
        for index in ranked[start:end]:
            result[index] = double_rank
        start = end
    return result


def asymmetry(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.asymmetry-plan.v1", ("source", "alpha"))
    alpha = Fraction(number(plan["alpha"], "Taraf deteksi"))
    if not 0 < alpha < 1:
        raise ResearchError("Taraf deteksi perlu di antara nol dan satu.")
    name, studies = effect_sizes(plan["source"], root, minimum=5)
    if len(studies) > 8:
        raise ResearchError("Permutasi rank eksak memerlukan 5–8 studi.")
    left, right = (_ranks([row[field] for row in studies]) for field in ("effect", "error"))
    origin = len(studies) + 1
    x = [rank - origin for rank in left]
    z = [rank - origin for rank in right]
    scale = sum(value * value for value in x) * sum(value * value for value in z)
    if not scale:
        return {"schema": "ace.institute.small-study-asymmetry.v1", "plan_sha256": expected,
                "source": plan["source"], "status": "indeterminate_constant_rank", "p_exact": None, "effect_kind": name}
    delta = sum(a * b for a, b in zip(x, z, strict=True))
    all_counts = 0
    successes = 0
    for order in permutations(z):
        all_counts += 1
        successes += abs(sum(a * b for a, b in zip(x, order, strict=True))) >= abs(delta)
    p = Fraction(successes, all_counts)
    return {"schema": "ace.institute.small-study-asymmetry.v1", "plan_sha256": expected, "source": plan["source"],
            "status": "asymmetry_signal" if p <= alpha else "no_asymmetry_signal",
            "p_exact": [p.numerator, p.denominator], "effect_kind": name, "test": "two_sided_exact_rank_permutation",
            "correlation": round(delta / scale**0.5, 10), "matched_permutations": successes, "permutations": all_counts,
            "studies": [{"id": row["id"], "effect": fmt(row["effect"]), "standard_error": fmt(row["error"]), **row["pointer"]}
                        for row in studies]}


if __name__ == "__main__":
    raise SystemExit(cli(asymmetry, __doc__, rooted=True))
