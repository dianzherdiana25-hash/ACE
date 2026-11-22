"""Susun tinjauan tujuh hari dari garis waktu tanpa mencampur rencana dengan bukti selesai."""
from collections import Counter
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, day, identifier, items, obj, schema, text

def review(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.weekly-review.v1", ("monday", "timeline"))
    first = day(plan["monday"])
    if first.weekday() != 0:
        raise PresenceError("Pekan diawali hari Senin.")
    last = first + timedelta(days=7)
    sections, outside, seen = {"recorded": [], "planned": [], "blocked": []}, 0, set()
    for row in items(plan["timeline"], 4000):
        obj(row, ("id", "date", "status", "title", "source"))
        key = identifier(row["id"], "Kejadian")
        declared = row["status"]
        when = day(row["date"])
        text(row["title"], "Judul")
        text(row["source"], "Bukti")
        if key in seen or declared not in sections:
            raise PresenceError("Kejadian ganda atau status tak dikenal.")
        seen.add(key)
        if first <= when < last:
            sections[declared].append(row)
        else:
            outside += 1
    return {"window": [first.isoformat(), last.isoformat()], "sections": {
        key: sorted(rows, key=lambda row: (row["date"], row["id"])) for key, rows in sections.items()},
        "totals": dict(Counter({key: len(rows) for key, rows in sections.items()})), "outside": outside}

if __name__ == "__main__":
    raise SystemExit(cli(review, __doc__))
