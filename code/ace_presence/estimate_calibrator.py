"""Ukur bias dan galat taksiran durasi dari pasangan estimasi dan bukti aktual."""
from collections import defaultdict
from fractions import Fraction

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text
from ._timeline import quantile

def calibrate(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.estimate-calibration.v1", ("pairs", "minimum"))
    groups = defaultdict(list)
    seen = set()
    minimum = integer(plan["minimum"], "Sampel minimum", 1, 1000)
    for row in items(plan["pairs"], 5000):
        obj(row, ("id", "kind", "forecast", "actual", "source"))
        key = identifier(row["id"], "Tugas")
        kind = identifier(row["kind"], "Kelas")
        if key in seen:
            raise PresenceError("Pasangan estimasi ganda.")
        seen.add(key)
        forecast = integer(row["forecast"], "Estimasi", 1, 100_000)
        actual = integer(row["actual"], "Aktual", 1, 100_000)
        groups[kind].append((actual - forecast, Fraction(actual, forecast), text(row["source"], "Bukti aktual")))
    result = {}
    for kind, records in sorted(groups.items()):
        count = len(records)
        mean_error = Fraction(sum(row[0] for row in records), count)
        absolute = Fraction(sum(abs(row[0]) for row in records), count)
        result[kind] = {"samples": count, "bias_minutes": str(mean_error), "mae_minutes": str(absolute),
                        "ratio_p90": str(quantile([row[1] for row in records], 90)) if count >= minimum else None,
                        "sources": sorted({row[2] for row in records})}
    return {"groups": result}

if __name__ == "__main__":
    raise SystemExit(cli(calibrate, __doc__))
