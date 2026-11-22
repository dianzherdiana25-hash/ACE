"""Jawab pertanyaan masa lalu dengan petikan asli dari sesi yang mengizinkan lawan bicara itu."""
from ._contracts import PresenceError, anchor, cli, day, identifier, integer, items, obj, schema, source_bytes, text, words
from ._journal import instant, load_export

def answer(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.shared-history.v1", ("participant", "query", "after", "through", "max_quotes", "sessions"))
    participant = identifier(plan["participant"], "Peserta")
    first, last = day(plan["after"]), day(plan["through"])
    terms = words(text(plan["query"], "Kueri", 200))
    if first > last or not terms:
        raise PresenceError("Rentang atau kata kueri tidak dapat dipakai.")
    cap = integer(plan["max_quotes"], "Batas petikan", 1, 20)
    result = []
    seen = set()
    for grant in items(plan["sessions"], 200):
        obj(grant, ("ref", "shared_with"))
        ref = obj(grant["ref"], ("path", "sha256"))
        allowed = {identifier(key, "Izin sesi") for key in items(grant["shared_with"], 30)}
        if participant not in allowed:
            continue
        if ref["sha256"] in seen:
            raise PresenceError("Sesi bersama ganda.")
        seen.add(ref["sha256"])
        doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
        events = doc["events"]
        if not any(row["turn"]["speaker"] == participant for row in events):
            continue
        for row in events:
            turn = row["turn"]
            when = instant(turn["at"]).date()
            matched = sorted(terms & words(turn["message"]))
            if first <= when <= last and matched:
                result.append({"source": ref, "at": turn["at"], "quote": turn["message"],
                               "session": turn["session"], "turn_sha256": row["sha256"], "keywords": matched})
    result.sort(key=lambda row: (-len(row["keywords"]), row["at"], row["session"], row["turn_sha256"]))
    return {"status": "found" if result else "no_evidence", "quotes": result[:cap], "matches": len(result)}

if __name__ == "__main__":
    raise SystemExit(cli(answer, __doc__, rooted=True))
