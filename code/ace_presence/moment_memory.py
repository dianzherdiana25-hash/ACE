"""Hadirkan kembali peristiwa berprovenance di jendela waktu dan topik yang relevan."""
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, day, identifier, integer, items, obj, schema, text, words

def recall(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.moments-plan.v1", ("as_of", "topic", "tolerance_days", "events"))
    now = day(plan["as_of"])
    vocabulary = words(text(plan["topic"], "Topik", 200))
    width = timedelta(days=integer(plan["tolerance_days"], "Toleransi", 0, 31))
    results = []
    seen = set()
    for row in items(plan["events"], 3000):
        obj(row, ("id", "date", "recur_annually", "summary", "source"))
        key = identifier(row["id"], "Momen")
        if key in seen or type(row["recur_annually"]) is not bool:
            raise PresenceError("Momen duplikat atau recurrence tidak sah.")
        seen.add(key)
        past = day(row["date"])
        text(row["source"], "Bukti momen")
        overlap = len(vocabulary & words(text(row["summary"], "Uraian momen", 500)))
        if not overlap or past > now:
            continue
        dates = [past]
        if row["recur_annually"]:
            dates = []
            for year in range(max(past.year, now.year - 1), min(9999, now.year + 1) + 1):
                try:
                    dates.append(past.replace(year=year))
                except ValueError:
                    continue
        near = [value for value in dates if abs(value - now) <= width]
        if near:
            closest = min(near, key=lambda value: (abs(value - now), value))
            results.append((-overlap, abs(closest - now), key, {**row, "relevant_on": closest.isoformat()}))
    return {"matches": [row[-1] for row in sorted(results)]}

if __name__ == "__main__":
    raise SystemExit(cli(recall, __doc__))
