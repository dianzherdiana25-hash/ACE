"""Gabungkan ukuran efek sejenis dan ungkap heterogenitas serta bobot studi."""
from decimal import Decimal, localcontext
from itertools import combinations

from ._contracts import ResearchError, anchor, cli, fmt, schema
from ._effect_sizes import effect_sizes


Z = {"90": Decimal("1.644853626951"), "95": Decimal("1.959963984540"), "99": Decimal("2.575829303549")}


def _aggregate(weights, studies):
    total = sum(weights)
    estimate = sum(weight * row["effect"] for row, weight in zip(studies, weights, strict=True)) / total
    return estimate, (1 / total).sqrt()


def meta_analyze(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.meta-plan.v1", ("source", "method", "confidence"))
    method = plan["method"]
    if method not in ("fixed", "random_dl") or plan["confidence"] not in Z:
        raise ResearchError("Metode meta atau tingkat confidence tidak tersedia.")
    effect_kind, studies = effect_sizes(plan["source"], root)
    with localcontext() as context:
        context.prec = 35
        weights = [1 / row["error"] ** 2 for row in studies]
        point, _ = _aggregate(weights, studies)
        q = sum(weight * (row["effect"] - point) ** 2 for weight, row in zip(weights, studies, strict=True))
        degrees = len(studies) - 1
        correction = 2 * sum(a * b for a, b in combinations(weights, 2)) / sum(weights)
        tau2 = max(Decimal(0), (q - degrees) / correction)
        diversity = max(0, int(10000 * (q - degrees) / q)) if q else 0
        if method == "random_dl":
            weights = [1 / (row["error"]**2 + tau2) for row in studies]
        estimate, uncertainty = _aggregate(weights, studies)
        margin = Z[plan["confidence"]] * uncertainty
        result = {"schema": "ace.institute.meta-result.v1", "plan_sha256": expected, "source": plan["source"],
                  "effect_kind": effect_kind, "method": method, "confidence": plan["confidence"],
                  "study_count": len(studies), "pooled_effect": fmt(estimate), "standard_error": fmt(uncertainty),
                  "normal_interval": [fmt(estimate - margin), fmt(estimate + margin)], "q": fmt(q), "degrees_of_freedom": degrees,
                  "i_squared_bp": diversity, "tau_squared_dl": fmt(tau2),
                  "studies": [{"id": row["id"], "weight_bp": int(10000 * weight / sum(weights)), **row["pointer"]}
                              for row, weight in zip(studies, weights, strict=True)]}
    return result


if __name__ == "__main__":
    raise SystemExit(cli(meta_analyze, __doc__, rooted=True))
