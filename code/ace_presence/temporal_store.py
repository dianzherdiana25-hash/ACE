"""Simpan snapshot fakta dengan interval validitas setengah terbuka dan supersession eksplisit."""
from collections import defaultdict

from ._contracts import PresenceError, anchor, cli, day, identifier, items, obj, schema, text

def timeline(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.facts-plan.v1", ("events", "as_of"))
    at = day(plan["as_of"])
    history = defaultdict(list)
    records = set()
    for row in items(plan["events"], 2500):
        obj(row, ("id", "fact", "value", "from", "until", "source", "supersedes"))
        key = identifier(row["fact"], "Fakta")
        event = identifier(row["id"], "Versi fakta")
        text(row["value"], "Nilai fakta", 800)
        text(row["source"], "Sumber", 400)
        start = day(row["from"])
        end = day(row["until"]) if row["until"] is not None else None
        prior = history[key][-1] if history[key] else None
        if event in records or (end is not None and end <= start):
            raise PresenceError("ID berulang atau interval tidak maju.")
        records.add(event)
        if prior is None:
            if row["supersedes"] is not None:
                raise PresenceError("Versi pertama tidak punya induk.")
        elif prior["id"] != row["supersedes"] or start <= day(prior["from"]):
            raise PresenceError("Supersession harus menunjuk versi sebelumnya pada tanggal lebih baru.")
        elif prior["until"] is None or start < day(prior["until"]):
            prior["until"] = row["from"]
        history[key].append(dict(row))
    active = {key: row for key, rows in history.items() for row in rows
              if day(row["from"]) <= at and (row["until"] is None or at < day(row["until"]))}
    return {"as_of": plan["as_of"], "history": dict(history), "active": active}

if __name__ == "__main__":
    raise SystemExit(cli(timeline, __doc__))
