"""Ingat preferensi bicara hanya dari pilihan eksplisit orang yang sama dan belum kedaluwarsa."""
from ._contracts import PresenceError, anchor, cli, day, identifier, items, obj, schema, text

def preferences(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.preferences.v1", ("speaker", "as_of", "updates"))
    speaker = identifier(plan["speaker"], "Lawan bicara")
    now = day(plan["as_of"])
    updates = {}
    for row in items(plan["updates"], 3000):
        obj(row, ("speaker", "author", "key", "value", "set_on", "expires_on", "source"))
        subject = identifier(row["speaker"], "Subjek")
        author = identifier(row["author"], "Penulis")
        key = identifier(row["key"], "Preferensi")
        when, end = day(row["set_on"]), day(row["expires_on"])
        source = text(row["source"], "Bukti pilihan")
        value = row["value"]
        if value is not None:
            text(value, "Pilihan", 120)
        if when >= end:
            raise PresenceError("Masa simpan preferensi tidak valid.")
        if subject != speaker or author != subject or when > now:
            continue
        older = updates.get(key)
        if older is not None and older[0] == when:
            raise PresenceError("Dua preferensi satu tanggal memerlukan urutan eksplisit.")
        if older is None or when > older[0]:
            updates[key] = (when, end, source, value)
    return {"speaker": speaker, "preferences": {
        key: {"value": value, "source": source, "expires_on": end.isoformat()}
        for key, (_, end, source, value) in sorted(updates.items()) if value is not None and now < end
    }}

if __name__ == "__main__":
    raise SystemExit(cli(preferences, __doc__))
