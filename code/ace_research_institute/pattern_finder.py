"""Cari penyimpangan robust dan rentang kenaikan/penurunan dengan pointer data konkret."""
from collections import defaultdict
from decimal import Decimal, localcontext

from ._contracts import ResearchError, anchor, cli, fmt, identifier, integer, items, number, obj, schema, source_bytes
from ._tabular import NUMBERS, load, quantile, serialize


def _trend(rows, minimum):
    patterns = []
    direction = 0
    start = 0
    for index in range(1, len(rows) + 1):
        if index == len(rows):
            new_direction = 0
        else:
            a, b = rows[index - 1]["value"], rows[index]["value"]
            new_direction = (b > a) - (b < a)
        if new_direction == direction:
            continue
        if direction and index - start >= minimum:
            patterns.append({"trend": "increase" if direction > 0 else "decrease",
                             "from_index": start, "through_index": index - 1,
                             "from_line": rows[start]["line"], "through_line": rows[index - 1]["line"],
                             "length": index - start, "delta": fmt(rows[index - 1]["value"] - rows[start]["value"])})
        start = index - 1
        direction = new_direction
    return patterns


def find_patterns(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.pattern-plan.v1", ("data", "format", "value", "order", "group", "minimum_run", "mad_multiplier"))
    pointer = obj(plan["data"], ("path", "sha256"))
    table = load(source_bytes(root, pointer["path"], pointer["sha256"], 3_000_000), pointer["sha256"], plan["format"])
    field = identifier(plan["value"], "Nilai")
    ordering = identifier(plan["order"], "Kolom urut")
    grouping = plan["group"] if plan["group"] is None else identifier(plan["group"], "Kolom kelompok")
    if (field not in table.columns or table.columns[field][0] not in NUMBERS
            or ordering not in table.columns or table.columns[ordering][0] not in (*NUMBERS, "date")
            or grouping is not None and grouping not in table.columns):
        raise ResearchError("Kolom pencarian pola belum sesuai tipe.")
    minimum = integer(plan["minimum_run"], "Panjang urut minimum", 3, 500)
    threshold = number(plan["mad_multiplier"], "Kelipatan MAD")
    if not Decimal(1) <= threshold <= 100:
        raise ResearchError("Kelipatan MAD perlu 1–100.")
    cohorts = defaultdict(list)
    missing = []
    keys = [field, ordering] + ([grouping] if grouping else [])
    for row in table.rows:
        cells = row["cells"]
        if any(cells[key] is None for key in keys):
            missing.append(row["line"])
            continue
        group = serialize(cells[grouping], table.columns[grouping]) if grouping else "__all__"
        cohorts[group].append({"line": row["line"], "order": cells[ordering], "value": cells[field]})
    result = []
    with localcontext() as context:
        context.prec = 34
        for group, rows in sorted(cohorts.items()):
            rows.sort(key=lambda row: (row["order"], row["line"]))
            duplicates = [right["line"] for left, right in zip(rows, rows[1:]) if left["order"] == right["order"]]
            numbers = [row["value"] for row in rows]
            center = quantile(numbers, 1, 2)
            deviations = [abs(value - center) for value in numbers]
            mad = quantile(deviations, 1, 2)
            flags = [{"line": row["line"], "value": fmt(row["value"]), "abs_difference": fmt(delta),
                      "basis": "mad_threshold"} for row, delta in zip(rows, deviations, strict=True) if mad and delta > mad * threshold]
            status = "mad_zero" if mad == 0 else "evaluated"
            result.append({"group": group, "count": len(rows), "median": fmt(center), "mad": fmt(mad),
                           "anomaly_status": status, "anomalies": flags, "duplicate_order_lines": duplicates,
                           "runs": [] if duplicates else _trend(rows, minimum)})
    return {"schema": "ace.institute.pattern-findings.v1", "plan_sha256": expected, "source": pointer,
            "groups": result, "missing_analysis_lines": missing, "rejected": list(table.rejected)}


if __name__ == "__main__":
    raise SystemExit(cli(find_patterns, __doc__, rooted=True))
