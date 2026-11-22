"""Perkirakan risiko tenggat dari episode berdurasi yang benar-benar tercatat."""
from ._contracts import anchor, cli, identifier, integer, items, obj, schema
from ._timeline import histogram, posterior

def forecast(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.deadline-risk.v1", ("history", "tasks", "minimum_sample"))
    histories = histogram(plan["history"], group="kind", key="minutes")
    minimum = integer(plan["minimum_sample"], "Minimum sampel", 1, 1000)
    report = []
    for row in items(plan["tasks"], 500):
        obj(row, ("id", "kind", "minutes_to_deadline"))
        key = identifier(row["id"], "Tugas")
        kind = identifier(row["kind"], "Kelas tugas")
        available = integer(row["minutes_to_deadline"], "Sisa menit", 0, 1_000_000)
        historical = histories.get(kind, [])
        ratio, late = posterior(historical, available)
        report.append({"id": key, "kind": kind, "samples": len(historical), "past_misses": late,
                       "probability": str(ratio) if len(historical) >= minimum else None})
    return {"tasks": report, "method": "observed_durations_laplace_smoothed"}

if __name__ == "__main__":
    raise SystemExit(cli(forecast, __doc__))
