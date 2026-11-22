"""Taksir durasi dari analog tercatat dengan prioritas jenis dan kompleksitas yang transparan."""
from ._contracts import anchor, cli, identifier, integer, items, obj, schema, text
from ._timeline import quantile

def estimate(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.duration-plan.v1", ("kind", "complexity", "history", "minimum_samples"))
    kind = identifier(plan["kind"], "Kelompok tugas")
    complexity = integer(plan["complexity"], "Kompleksitas", 1, 10)
    minimum = integer(plan["minimum_samples"], "Sampel minimum", 1, 100)
    history = []
    for row in items(plan["history"], 3000):
        obj(row, ("kind", "complexity", "minutes", "source"))
        label = identifier(row["kind"], "Kelompok histori")
        level = integer(row["complexity"], "Kompleksitas histori", 1, 10)
        length = integer(row["minutes"], "Durasi histori", 1, 100_000)
        source = text(row["source"], "Bukti histori")
        if label == kind:
            history.append((abs(complexity - level), length, source))
    history.sort()
    selected = []
    if len(history) >= minimum:
        radius = history[minimum - 1][0]
        selected = [row for row in history if row[0] <= radius]
    durations = [row[1] for row in selected]
    return {"samples": len(selected), "eligible_history": len(history),
            "median_minutes": quantile(durations, 50) if durations else None,
            "p90_minutes": quantile(durations, 90) if durations else None,
            "sources": [row[2] for row in selected]}

if __name__ == "__main__":
    raise SystemExit(cli(estimate, __doc__))
