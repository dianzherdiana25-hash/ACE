"""Tunjukkan perubahan setelah checkpoint yang benar dengan catatan sumber dan batas liputan."""
from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text
from ._journal import instant

def brief(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.while-away.v1", ("after", "through", "events", "limit"))
    first, last = instant(plan["after"]), instant(plan["through"])
    if first >= last:
        raise PresenceError("Jendela hilang harus maju.")
    matches, seen = [], set()
    for row in items(plan["events"], 5000):
        obj(row, ("id", "kind", "at", "message", "source", "importance"))
        key = identifier(row["id"], "Kejadian")
        tag = identifier(row["kind"], "Jenis")
        when = instant(row["at"])
        text(row["message"], "Petikan", 750)
        text(row["source"], "Bukti")
        rank = integer(row["importance"], "Prioritas", 0, 100)
        if key in seen:
            raise PresenceError("Kejadian ganda.")
        seen.add(key)
        if first < when <= last:
            matches.append((-rank, when, key, row))
    cap = integer(plan["limit"], "Batas laporan", 1, 100)
    selected = sorted(matches)[:cap]
    return {"events": [row[-1] for row in sorted(selected, key=lambda row: row[1:3])],
            "captured": len(matches), "omitted": max(0, len(matches) - cap)}

if __name__ == "__main__":
    raise SystemExit(cli(brief, __doc__))
