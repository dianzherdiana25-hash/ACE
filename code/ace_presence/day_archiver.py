"""Arsipkan episode per tanggal lokal sebagai manifest event bertambat yang dapat dibaca ulang."""
from zoneinfo import ZoneInfo

from ._contracts import PresenceError, anchor, cli, day, identifier, identity, items, obj, schema, source_bytes, text
from ._journal import instant, load_export

def archive(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.day-archive-plan.v1", ("date", "zone", "exports", "speakers"))
    date = day(plan["date"])
    tz = ZoneInfo(text(plan["zone"], "Zona episode", 100))
    speakers = {identifier(value, "Pembicara") for value in items(plan["speakers"], 80, 1)}
    entries = []
    seen = set()
    for ref in items(plan["exports"], 100):
        obj(ref, ("path", "sha256"))
        doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
        if doc["session"] in seen:
            raise PresenceError("Lebih dari satu ekspor sesi membuat arsip ambigu.")
        seen.add(doc["session"])
        for row in doc["events"]:
            turn = row["turn"]
            if turn["speaker"] in speakers and instant(turn["at"]).astimezone(tz).date() == date:
                entries.append({"session": doc["session"], "id": turn["id"], "seq": row["seq"],
                                "at": turn["at"], "source": ref, "turn_sha256": row["sha256"]})
    payload = {"schema": "ace.presence.day-archive.v1", "date": plan["date"], "zone": plan["zone"],
               "turns": sorted(entries, key=lambda row: (row["at"], row["session"], row["seq"]))}
    return {**payload, "sha256": identity(payload)}

if __name__ == "__main__":
    raise SystemExit(cli(archive, __doc__, rooted=True))
