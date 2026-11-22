"""Rekap observasi pasar dengan denominator terpisah dan total resmi per periode."""
from collections import defaultdict
from decimal import Decimal, localcontext

from ._contracts import ResearchError, anchor, cli, fmt, identifier, items, number, obj, schema, source_bytes, text
from ._tabular import NUMBERS, load, serialize


def analyze_market(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.market-plan.v1", ("data", "format", "columns", "unit", "market_totals"))
    link = obj(plan["data"], ("path", "sha256"))
    fmt_table = plan["format"]
    table = load(source_bytes(root, link["path"], link["sha256"], 3_000_000), link["sha256"], fmt_table)
    declared = obj(plan["columns"], ("period", "competitor", "amount"))
    period, competing, value = [identifier(declared[name], name) for name in ("period", "competitor", "amount")]
    if (len({period, competing, value}) != 3 or any(name not in table.columns for name in (period, competing, value))
            or table.columns[value][0] not in NUMBERS):
        raise ResearchError("Pemetaan kolom pasar tidak sesuai.")
    totals = {}
    for row in items(plan["market_totals"], 160):
        obj(row, ("period", "total", "source_ref"))
        key = text(row["period"], "Periode total")
        count = number(row["total"], "Denominator pasar")
        if key in totals or count <= 0:
            raise ResearchError("Denominator pasar perlu unik dan positif.")
        totals[key] = (count, text(row["source_ref"], "Pointer denominator"))
    groups = defaultdict(dict)
    missing = []
    for row in table.rows:
        cells = row["cells"]
        if any(cells[key] is None for key in (period, competing, value)):
            missing.append(row["line"])
            continue
        date = serialize(cells[period], table.columns[period])
        competitor = serialize(cells[competing], table.columns[competing])
        count = cells[value]
        if count < 0 or competitor in groups[date]:
            raise ResearchError("Satu periode dan pesaing perlu observasi unik nonnegatif.")
        groups[date][competitor] = (count, row["line"])
    measurements = []
    with localcontext() as ctx:
        ctx.prec = 32
        for date in sorted(groups.keys() | totals.keys()):
            observed = groups[date]
            external, source = totals.get(date, (None, None))
            total = sum(count for count, _ in observed.values())
            if external is not None and total > external:
                raise ResearchError("Observasi pesaing melebihi denominator pasar.")
            if not observed:
                state = "no_observations"
            elif external is None:
                state = "no_market_denominator"
            elif external == total:
                state = "complete_declared_market"
            else:
                state = "partial_market"
            order = sorted(observed.items(), key=lambda row: (-row[1][0], row[0]))
            rows = [{"competitor": key, "amount": fmt(count), "csv_line": line,
                     "market_share_bp": int(count * 10000 / external) if external else None}
                    for key, (count, line) in order]
            hhi = sum(((count / external) ** 2) for count, _ in observed.values()) * 10000 if state == "complete_declared_market" else None
            measurements.append({"period": date, "status": state, "observed_total": fmt(total),
                                 "market_total": fmt(external) if external else None, "total_source_ref": source,
                                 "coverage_bp": int(total * 10000 / external) if external else None,
                                 "hhi": None if hhi is None else fmt(hhi), "competitors": rows})
    return {"schema": "ace.institute.market-report.v1", "plan_sha256": expected, "source": link,
            "unit": text(plan["unit"], "Satuan pasar"), "periods": measurements,
            "missing_lines": missing, "rejected": list(table.rejected)}


if __name__ == "__main__":
    raise SystemExit(cli(analyze_market, __doc__, rooted=True))
