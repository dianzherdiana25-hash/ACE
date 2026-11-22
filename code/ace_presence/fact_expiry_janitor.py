"""Susun daftar kedaluwarsa yang dapat ditinjau tanpa menghapus atau menulis ulang riwayat."""
from ._contracts import PresenceError, anchor, cli, day, identifier, items, obj, schema, text

def mark(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.expiry-plan.v1", ("as_of", "facts"))
    now = day(plan["as_of"])
    expired = []
    retained = []
    seen = set()
    for row in items(plan["facts"], 3000):
        obj(row, ("id", "until", "source", "hold"))
        key = identifier(row["id"], "Fakta")
        if key in seen or type(row["hold"]) is not bool:
            raise PresenceError("Fakta ganda atau status hold bukan boolean.")
        seen.add(key)
        text(row["source"], "Sumber")
        due = row["until"] is not None and day(row["until"]) <= now
        if due and not row["hold"]:
            expired.append({"id": key, "source": row["source"], "until": row["until"]})
        else:
            retained.append({"id": key, "reason": "held" if row["hold"] else "valid"})
    return {"as_of": plan["as_of"], "expire_candidates": sorted(expired, key=lambda row: row["id"]),
            "retained": sorted(retained, key=lambda row: row["id"])}

if __name__ == "__main__":
    raise SystemExit(cli(mark, __doc__))
