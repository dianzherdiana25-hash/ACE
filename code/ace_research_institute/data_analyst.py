"""Profilkan CSV asing dengan distribusi, persentil, missingness, dan korelasi berdenominator."""
from collections import Counter
from decimal import Decimal, localcontext

from ._contracts import anchor, cli, fmt, identifier, items, obj, schema, source_bytes
from ._tabular import NUMBERS, load, quantile, serialize, values


def _numeric(series):
    if not series:
        return {"n": 0, "mean": None, "quantiles": None, "sample_stddev": None}
    n = len(series)
    mean = sum(series) / n
    variance = sum((value - mean) ** 2 for value in series) / (n - 1) if n > 1 else None
    return {"n": n, "mean": fmt(mean),
            "quantiles": {f"p{100 * rank // 4}": fmt(quantile(series, rank, 4)) for rank in range(5)},
            "sample_stddev": fmt(variance.sqrt()) if variance is not None else None}


def pearson(pairs):
    n = len(pairs)
    if n <= 1:
        return None
    xv, yv = [list(rows) for rows in zip(*pairs, strict=True)]
    x_mean, y_mean = sum(xv) / n, sum(yv) / n
    x_err = [value - x_mean for value in xv]
    y_err = [value - y_mean for value in yv]
    scale = sum(value**2 for value in x_err) * sum(value**2 for value in y_err)
    if not scale:
        return None
    coefficient = sum(x * y for x, y in zip(x_err, y_err, strict=True)) / scale.sqrt()
    return fmt(min(Decimal(1), max(Decimal(-1), coefficient)))


def analyze_table(table, pairings):
    with localcontext() as context:
        context.prec = 30
        profiles = {}
        for key, spec in table.columns.items():
            sample = values(table, key)
            profile = {"missing": len(table.rows) - len(sample), "kind": spec[0]}
            if spec[0] in NUMBERS:
                profile.update(_numeric(sample))
            else:
                counts = Counter(serialize(value, spec) for value in sample)
                sorted_counts = sorted(counts.items(), key=lambda row: (-row[1], row[0]))
                profile.update({"distinct": len(counts), "n": len(sample),
                                "most_frequent": [{"value": value, "n": n} for value, n in sorted_counts[:12]]})
            profiles[key] = profile
        correlations = []
        for item in items(pairings, 50):
            obj(item, ("first", "second"))
            x, y = (identifier(item[key], "Kolom korelasi") for key in ("first", "second"))
            values(table, x, numeric=True)
            values(table, y, numeric=True)
            selected = [(row["cells"][x], row["cells"][y], row["line"]) for row in table.rows
                        if row["cells"][x] is not None and row["cells"][y] is not None]
            estimates = [(xv, yv) for xv, yv, _ in selected]
            correlations.append({"first": x, "second": y, "pearson_r": pearson(estimates),
                                 "pairwise_n": len(estimates), "lines": [line for _, _, line in selected]})
        return {"accepted": len(table.rows), "rejected": list(table.rejected),
                "columns": profiles, "correlations": correlations}


def analyze(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.analysis-plan.v1", ("data", "format", "pairs"))
    link = obj(plan["data"], ("path", "sha256"))
    data = source_bytes(root, link["path"], link["sha256"], 3_000_000)
    table = load(data, link["sha256"], plan["format"])
    return {"schema": "ace.institute.analysis-report.v1", "plan_sha256": expected,
            "source": link, **analyze_table(table, plan["pairs"])}


if __name__ == "__main__":
    raise SystemExit(cli(analyze, __doc__, rooted=True))
