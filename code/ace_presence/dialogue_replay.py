"""Putar ulang bagian sesi setelah memverifikasi seluruh rantai dan pertahankan alamat turn."""
from ._contracts import PresenceError, anchor, cli, integer, obj, schema, source_bytes
from ._journal import load_export

def replay(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.replay-plan.v1", ("dialogue", "start_seq", "stop_seq"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    snapshot = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    start = integer(plan["start_seq"], "Turn mulai", 1, 500)
    stop = integer(plan["stop_seq"], "Turn akhir", start, 500)
    if stop > len(snapshot["events"]):
        raise PresenceError("Turn replay melewati akhir sesi.")
    selected = snapshot["events"][start - 1:stop]
    return {"source": ref, "session": snapshot["session"], "head_sha256": snapshot["head_sha256"],
            "prior_sha256": selected[0]["previous_sha256"], "events": selected}

if __name__ == "__main__":
    raise SystemExit(cli(replay, __doc__, rooted=True))
