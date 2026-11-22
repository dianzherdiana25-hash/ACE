"""Lacak utas bernama dengan transisi yang dapat ditunjuk ulang ke percakapan."""
from ._contracts import PresenceError, anchor, cli, identifier, items, obj, schema, source_bytes, text
from ._journal import load_export

TRANSITIONS = {None: {"open"}, "open": {"paused", "resolved"}, "paused": {"open", "resolved"}, "resolved": {"open"}}

def track(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.topic-plan.v1", ("dialogue", "annotations"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    turns = {event["turn"]["id"]: event for event in doc["events"]}
    annotated = []
    for note in items(plan["annotations"], 1000):
        obj(note, ("topic", "turn_id", "status", "quote"))
        key = identifier(note["topic"], "Topik")
        source = turns.get(identifier(note["turn_id"], "Turn"))
        quote = text(note["quote"], "Petikan", 300)
        if source is None or quote not in source["turn"]["message"] or note["status"] not in TRANSITIONS:
            raise PresenceError("Transisi topik tanpa petikan yang dapat ditunjuk.")
        annotated.append((source["seq"], key, note["status"], source["sha256"], quote))
    topics = {}
    for seq, key, status, sha, quote in sorted(annotated):
        trail = topics.setdefault(key, [])
        previous = trail[-1] if trail else None
        if status not in TRANSITIONS[previous["status"] if previous else None] or (previous and seq == previous["seq"]):
            raise PresenceError("Transisi topik bertentangan atau ganda.")
        trail.append({"status": status, "seq": seq, "sha256": sha, "quote": quote})
    return {"source": ref, "topics": {key: {"status": trail[-1]["status"], "trail": trail} for key, trail in sorted(topics.items())}}

if __name__ == "__main__":
    raise SystemExit(cli(track, __doc__, rooted=True))
