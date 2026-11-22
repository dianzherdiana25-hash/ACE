"""Uji hipotesis dengan distribusi eksak serta asumsi desain yang harus dinyatakan."""
from fractions import Fraction
from math import comb

from ._contracts import ResearchError, anchor, cli, identifier, integer, items, number, obj, schema, text


def _fisher(data, alternative):
    obj(data, ("a", "b", "c", "d"))
    a, b, c, d = [integer(data[key], "Hitungan tabel", 0, 2000) for key in "abcd"]
    group1, group2, successes = a + b, c + d, a + c
    total = group1 + group2
    if not group1 or not group2 or not 0 < successes < total or total > 2500:
        raise ResearchError("Tabel perlu dua kelompok, dua kelas, dan ukuran ≤2.500.")
    normalizer = comb(total, successes)
    range_values = range(max(0, successes - group2), min(group1, successes) + 1)

    def count(selected):
        return comb(group1, selected) * comb(group2, successes - selected)

    observed = count(a)
    if alternative == "two_sided":
        numerator = sum(weight for selected in range_values if (weight := count(selected)) <= observed)
    else:
        comparison = (lambda value: value >= a) if alternative == "greater" else (lambda value: value <= a)
        numerator = sum(count(selected) for selected in range_values if comparison(selected))
    return Fraction(numerator, normalizer), {"observed": a, "possible_tables": len(range_values),
                                             "margins": {"group_one": group1, "group_two": group2, "class_one": successes, "total": total}}


def _paired(data, alternative):
    obj(data, ("pairs",))
    differences = []
    seen = set()
    for row in items(data["pairs"], 16, 3):
        obj(row, ("id", "before", "after", "source_ref"))
        name = identifier(row["id"], "Pasangan")
        if name in seen:
            raise ResearchError("ID pasangan observasi ganda.")
        seen.add(name)
        prior = Fraction(number(row["before"], "Sebelum"))
        after = Fraction(number(row["after"], "Sesudah"))
        differences.append((after - prior, text(row["source_ref"], "Pointer pasangan")))
    observed = sum(value for value, _ in differences)
    outcomes = [Fraction(0)]
    for current, _ in differences:
        if current:
            outcomes = [draw + sign * current for draw in outcomes for sign in (-1, 1)]
    if alternative == "two_sided":
        passing = sum(abs(candidate) >= abs(observed) for candidate in outcomes)
    elif alternative == "greater":
        passing = sum(candidate >= observed for candidate in outcomes)
    else:
        passing = sum(candidate <= observed for candidate in outcomes)
    return Fraction(passing, len(outcomes)), {"observed_sum": str(observed), "pairs": len(differences),
                                               "unique_sign_assignments_counted": len(outcomes),
                                               "sources": [source for _, source in differences]}


METHODS = {
    "fisher": (_fisher, ("independent_observations", "fixed_margins")),
    "paired_sign_flip": (_paired, ("independent_pairs", "exchangeable_signs")),
}


def test_hypothesis(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.institute.hypothesis-plan.v1", ("hypothesis", "method", "alternative", "alpha", "assumptions", "data"))
    hypothesis = text(plan["hypothesis"], "Hipotesis")
    method = plan["method"]
    alternative = plan["alternative"]
    if method not in METHODS or alternative not in ("two_sided", "greater", "less"):
        raise ResearchError("Metode atau arah hipotesis tidak terdaftar.")
    alpha = Fraction(number(plan["alpha"], "Taraf signifikansi"))
    if not 0 < alpha < 1:
        raise ResearchError("Taraf signifikansi perlu di antara nol dan satu.")
    call, required = METHODS[method]
    assertions = obj(plan["assumptions"], required)
    detail = {}
    for key, row in assertions.items():
        obj(row, ("declared", "source_ref"))
        if type(row["declared"]) is not bool:
            raise ResearchError("Asumsi harus dinyatakan dengan boolean.")
        detail[key] = {"declared": row["declared"], "source_ref": text(row["source_ref"], "Pointer asumsi")}
    if not all(row["declared"] for row in detail.values()):
        return {"schema": "ace.institute.hypothesis-result.v1", "plan_sha256": expected,
                "status": "held_assumption", "method": method, "assumptions": detail,
                "p_value_exact": None, "hypothesis": hypothesis}
    probability, result = call(plan["data"], alternative)
    return {"schema": "ace.institute.hypothesis-result.v1", "plan_sha256": expected,
            "status": "reject_null" if probability <= alpha else "fail_to_reject",
            "p_value_exact": [probability.numerator, probability.denominator],
            "alpha_exact": [alpha.numerator, alpha.denominator], "method": method, "alternative": alternative,
            "assumptions": detail, "hypothesis": hypothesis, "statistics": result}


if __name__ == "__main__":
    raise SystemExit(cli(test_hypothesis, __doc__))
