"""Pisahkan janji terbuka, mendesak, dan lewat tenggat dari penyelesaian yang punya bukti."""
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, day, identifier, integer, items, obj, schema, text

def track(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.commitments.v1", ("as_of", "alert_days", "promises", "resolutions"))
    now = day(plan["as_of"])
    window = timedelta(days=integer(plan["alert_days"], "Jendela peringatan", 0, 30))
    resolved = {}
    for row in items(plan["resolutions"], 3000):
        obj(row, ("id", "at", "source"))
        key = identifier(row["id"], "Janji selesai")
        if key in resolved or day(row["at"]) > now:
            raise PresenceError("Penyelesaian ganda atau setelah tanggal laporan.")
        resolved[key] = text(row["source"], "Bukti penyelesaian")
    report = []
    seen = set()
    for row in items(plan["promises"], 3000):
        obj(row, ("id", "due_on", "action", "source"))
        key = identifier(row["id"], "Janji")
        if key in seen:
            raise PresenceError("ID janji berulang.")
        seen.add(key)
        text(row["source"], "Bukti janji")
        text(row["action"], "Isi janji")
        left = day(row["due_on"]) - now
        status = "fulfilled" if key in resolved else "overdue" if left.days < 0 else "due_soon" if left <= window else "open"
        report.append({**row, "status": status, "resolution_source": resolved.get(key), "days_left": left.days})
    if resolved.keys() - seen:
        raise PresenceError("Penyelesaian tidak punya janji asal.")
    return {"as_of": plan["as_of"], "commitments": sorted(report, key=lambda row: (row["due_on"], row["id"]))}

if __name__ == "__main__":
    raise SystemExit(cli(track, __doc__))
