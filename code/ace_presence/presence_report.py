"""Laporkan janji tepat waktu, terlambat, dan belum selesai dari kohort tanggal jatuh tempo."""
from collections import Counter

from ._contracts import PresenceError, anchor, cli, day, identifier, items, obj, schema, text

def report(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.period-report.v1", ("start", "as_of", "promises", "receipts"))
    first, last = day(plan["start"]), day(plan["as_of"])
    if first > last:
        raise PresenceError("Periode laporan harus maju.")
    resolutions = {}
    for row in items(plan["receipts"], 5000):
        obj(row, ("promise", "date", "source", "kind"))
        key = identifier(row["promise"], "ID janji")
        when = day(row["date"])
        text(row["source"], "Bukti resolusi")
        if key in resolutions or row["kind"] not in ("fulfilled", "cancelled"):
            raise PresenceError("Resolusi ganda atau verba tidak dikenal.")
        resolutions[key] = (when, row)
    details = []
    seen = set()
    counts = Counter(dict.fromkeys(("on_time", "late", "missed", "due_today", "cancelled"), 0))
    for row in items(plan["promises"], 5000):
        obj(row, ("id", "date", "due_on", "source"))
        key = identifier(row["id"], "Janji")
        opened, due = day(row["date"]), day(row["due_on"])
        text(row["source"], "Bukti janji")
        if key in seen or due < opened:
            raise PresenceError("Janji ganda atau tenggat mendahului janji.")
        seen.add(key)
        resolution = resolutions.get(key)
        if resolution and resolution[0] < opened:
            raise PresenceError("Receipt resolusi mendahului janji.")
        if not first <= due <= last:
            continue
        if resolution and resolution[0] <= last:
            when, event = resolution
            status = "cancelled" if event["kind"] == "cancelled" else "late" if when > due else "on_time"
            proof = event["source"]
        else:
            status, proof = ("missed" if due < last else "due_today"), None
        counts[status] += 1
        details.append({"id": key, "due_on": row["due_on"], "status": status,
                        "promise_source": row["source"], "resolution_source": proof})
    if resolutions.keys() - seen:
        raise PresenceError("Receipt tanpa janji asal.")
    return {"period": [plan["start"], plan["as_of"]], "counts": dict(counts),
            "entries": sorted(details, key=lambda row: (row["due_on"], row["id"]))}

if __name__ == "__main__":
    raise SystemExit(cli(report, __doc__))
