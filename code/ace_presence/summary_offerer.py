"""Tawarkan ringkasan berdasar pertumbuhan sesi dan jeda sejak penawaran terakhir."""
from ._contracts import PresenceError, anchor, cli, digest, integer, obj, schema, source_bytes
from ._journal import load_export

def offer(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.summary-offer.v1", ("dialogue", "last_offer_sha256", "turn_threshold", "char_threshold", "cooldown"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    events = doc["events"]
    turn_threshold = integer(plan["turn_threshold"], "Ambang turn", 1, 500)
    char_threshold = integer(plan["char_threshold"], "Ambang karakter", 1, 400_000)
    cooldown = integer(plan["cooldown"], "Jeda antar tawaran", 0, 500)
    previous = plan["last_offer_sha256"]
    if previous is None:
        delta = events
    else:
        index = next((i for i, event in enumerate(events) if event["sha256"] == digest(previous)), None)
        if index is None:
            raise PresenceError("Penawaran terakhir tidak ada dalam rantai sesi.")
        delta = events[index + 1:]
    chars = sum(len(event["turn"]["message"]) for event in delta)
    threshold = len(delta) >= turn_threshold or chars >= char_threshold
    ready = threshold and (previous is None or len(delta) >= cooldown)
    return {"offer": ready, "additional_turns": len(delta), "additional_chars": chars,
            "head_sha256": doc["head_sha256"], "source": ref}

if __name__ == "__main__":
    raise SystemExit(cli(offer, __doc__, rooted=True))
