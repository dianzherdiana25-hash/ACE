"""Pelajari beban dari interval historis dengan alokasi per jam UTC dan hari pekan."""
from collections import defaultdict
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, items, obj, schema, text
from ._timeline import minute_slots, minutes

def learn(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.rhythm-plan.v1", ("records",))
    rows = items(plan["records"], 600)
    for row in rows:
        obj(row, ("start", "end", "source"))
        text(row["source"], "Sumber")
    intervals = minute_slots([{key: row[key] for key in ("start", "end")} for row in rows])
    sources = {row["start"]: row["source"] for row in rows}
    buckets = defaultdict(lambda: {"minutes": 0, "days": set(), "sources": set()})
    for start, end in intervals:
        if minutes(start, end) > 10_080:
            raise PresenceError("Rekaman kerja lebih panjang dari sepekan.")
        point = start
        while point < end:
            limit = min(end, point.replace(minute=0) + timedelta(hours=1))
            bucket = buckets[(point.weekday(), point.hour)]
            bucket["minutes"] += minutes(point, limit)
            bucket["days"].add(point.date().isoformat())
            bucket["sources"].add(sources[start.isoformat().replace("+00:00", "Z")])
            point = limit
    return {"buckets": [{"weekday": key[0], "utc_hour": key[1], "minutes": row["minutes"],
                         "recorded_days": len(row["days"]), "sources": sorted(row["sources"])}
                        for key, row in sorted(buckets.items())]}

if __name__ == "__main__":
    raise SystemExit(cli(learn, __doc__))
