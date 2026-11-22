"""Hitung ECE dan Brier per domain dengan rasio eksak serta cakupan bin yang terlihat."""
from collections import defaultdict
from fractions import Fraction

from ._contracts import GuardianError, anchor, cli, digest, identifier, integer, items, obj, schema

def score(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.calibration.v1", ("rows", "bins", "minimum"))
    divisions = integer(plan["bins"], "Bin", 1, 20)
    minimum = integer(plan["minimum"], "Minimum resolusi", 1, 2000)
    groups = defaultdict(list)
    seen = set()
    for row in items(plan["rows"], 6000):
        obj(row, ("id", "domain", "confidence_bp", "observed", "resolved_ref"))
        key = identifier(row["id"], "Prediksi")
        domain = identifier(row["domain"], "Domain")
        probability = integer(row["confidence_bp"], "Probabilitas basis point", 0, 10_000)
        source = digest(row["resolved_ref"])
        if key in seen or type(row["observed"]) is not bool:
            raise GuardianError("Prediksi ganda atau outcome bukan boolean.")
        seen.add(key)
        groups[domain].append((probability, int(row["observed"]), source))
    results = {}
    for domain, rows in sorted(groups.items()):
        bins = defaultdict(list)
        for probability, outcome, source in rows:
            bins[min(divisions - 1, probability * divisions // 10_000)].append((probability, outcome, source))
        residuals = 0
        detail = []
        for index, bucket in sorted(bins.items()):
            predicted = sum(p for p, _, _ in bucket)
            realized = sum(o for _, o, _ in bucket)
            n = len(bucket)
            residuals += abs(predicted - 10_000 * realized)
            detail.append({"index": index, "count": n, "mean_forecast": str(Fraction(predicted, 10_000 * n)),
                           "event_rate": str(Fraction(realized, n))})
        n = len(rows)
        brier = sum((p - 10_000 * o)**2 for p, o, _ in rows)
        results[domain] = {"samples": n, "bins": detail, "sources": sorted({ref for _, _, ref in rows}),
                           "ece": str(Fraction(residuals, 10_000 * n)) if n >= minimum else None,
                           "brier": str(Fraction(brier, 100_000_000 * n)) if n >= minimum else None}
    return {"domains": results, "bin_count": divisions, "method": "equal_width_weighted_l1"}

if __name__ == "__main__":
    raise SystemExit(cli(score, __doc__))
