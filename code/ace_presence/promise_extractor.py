"""Ambil hanya janji orang pertama yang eksplisit dan bertanggal absolut dari turn asli."""
import re

from ._contracts import anchor, cli, day, obj, schema, source_bytes
from ._journal import instant, load_export

PATTERNS = (
    re.compile(r"Saya akan (?P<action>.+?) pada (?P<day>\d{4}-\d{2}-\d{2})[.!]?", re.IGNORECASE),
    re.compile(r"I will (?P<action>.+?) on (?P<day>\d{4}-\d{2}-\d{2})[.!]?", re.IGNORECASE),
)
HEDGE = re.compile(r"\b(tidak|bukan|mungkin|jika|kalau|belum|not|maybe|perhaps|if|might|unless)\b", re.IGNORECASE)

def extract(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.promises-plan.v1", ("dialogue",))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    promises = []
    for row in doc["events"]:
        turn = row["turn"]
        if turn["role"] != "user":
            continue
        for pattern in PATTERNS:
            match = pattern.fullmatch(turn["message"].strip())
            if not match or HEDGE.search(match["action"]):
                continue
            deadline = day(match["day"])
            if deadline >= instant(turn["at"]).date():
                promises.append({"id": turn["id"], "speaker": turn["speaker"], "action": match["action"],
                                 "due_on": match["day"], "turn_sha256": row["sha256"], "source": ref})
            break
    return {"promises": promises, "source": ref}

if __name__ == "__main__":
    raise SystemExit(cli(extract, __doc__, rooted=True))
