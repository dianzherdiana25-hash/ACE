"""Lanjutkan ulasan utas hanya dari checkpoint pada rantai yang masih konsisten."""
from ._contracts import PresenceError, anchor, cli, digest, integer, obj, schema, source_bytes
from ._journal import initial, load_export

def resume(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.thread-resume.v1", ("dialogue", "after_sha256", "max_turns"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    marker = digest(plan["after_sha256"])
    events = doc["events"]
    start = 0 if marker == initial(doc["session"]) else next(
        (i + 1 for i, event in enumerate(events) if event["sha256"] == marker), None)
    if start is None:
        raise PresenceError("Checkpoint tidak berada dalam utas.")
    cap = integer(plan["max_turns"], "Panjang lanjutan", 1, 500)
    next_turns = events[start:start + cap]
    return {"source": ref, "events": next_turns, "checkpoint": next_turns[-1]["sha256"] if next_turns else marker,
            "remaining": max(0, len(events) - start - cap)}

if __name__ == "__main__":
    raise SystemExit(cli(resume, __doc__, rooted=True))
