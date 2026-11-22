"""Ukur tren deret lokal dengan estimator Theil-Sen dan laporkan gap kalender."""
from decimal import Decimal, localcontext
from statistics import median

from ._contracts import ResearchError, anchor, cli, fmt, identifier, integer, obj, schema, source_bytes
from ._tabular import NUMBERS, load


def trends(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.trend-plan.v1", ("data", "format", "date", "value", "expected_gap_days", "comparison_days"))
    link = obj(plan["data"], ("path", "sha256"))
    table = load(source_bytes(root, link["path"], link["sha256"], 3_000_000), link["sha256"], plan["format"])
    timer = identifier(plan["date"], "Kolom tanggal")
    value = identifier(plan["value"], "Kolom nilai")
    if (timer not in table.columns or table.columns[timer][0] != "date"
            or value not in table.columns or table.columns[value][0] not in NUMBERS):
        raise ResearchError("Analisis tren membutuhkan tanggal dan nilai numerik.")
    cadence = integer(plan["expected_gap_days"], "Jeda kalender maksimum", 1, 365)
    width = integer(plan["comparison_days"], "Lebar jendela perbandingan", 1, 730)
    points = [(row["cells"][timer], row["cells"][value], row["line"]) for row in table.rows
              if row["cells"][timer] is not None and row["cells"][value] is not None]
    if not 2 <= len(points) <= 500:
        raise ResearchError("Estimasi tren membutuhkan 2–500 observasi lengkap.")
    points.sort()
    if any(a[0] == b[0] for a, b in zip(points, points[1:])):
        raise ResearchError("Tanggal duplikat perlu diselesaikan sebelum estimasi.")
    gaps = [{"after": left.isoformat(), "before": right.isoformat(), "days": (right - left).days,
             "source_lines": [before, after]} for (left, _, before), (right, _, after) in zip(points, points[1:])
            if (right - left).days > cadence]
    with localcontext() as current:
        current.prec = 30
        slope = median([(points[i][1] - points[j][1]) / Decimal((points[i][0] - points[j][0]).days)
                        for i in range(len(points)) for j in range(i)])
        left, right = points[0][0], points[-1][0]
        first = [(measurement, line) for date, measurement, line in points if (date - left).days < width]
        last = [(measurement, line) for date, measurement, line in points if (right - date).days < width]
        overlap = {line for _, line in first} & {line for _, line in last}
        change = None
        if not overlap:
            initial = median([measurement for measurement, _ in first])
            final = median([measurement for measurement, _ in last])
            change = {"early_median": fmt(initial), "late_median": fmt(final), "delta": fmt(final - initial),
                      "early_lines": [line for _, line in first], "late_lines": [line for _, line in last]}
    return {"schema": "ace.institute.trend-report.v1", "plan_sha256": expected, "source": link,
            "n_complete": len(points), "method": "theil_sen_per_day",
            "slope_per_day": fmt(slope), "window_change": change,
            "source_lines_used": [line for _, _, line in points], "overlapping_windows": bool(overlap),
            "missing_or_rejected": len(table.rows) - len(points) + len(table.rejected), "calendar_gaps": gaps}


if __name__ == "__main__":
    raise SystemExit(cli(trends, __doc__, rooted=True))
