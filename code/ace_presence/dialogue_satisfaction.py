"""Hitung sinyal kepuasan yang dinyatakan dan tampilkan jumlah turn tanpa sinyal."""
from fractions import Fraction
import re

from ._contracts import anchor, cli, obj, schema, source_bytes
from ._journal import load_export

FEEDBACK = re.compile(r"^(?:Umpan balik|Feedback) \[(helpful|unhelpful|neutral)\](?:\s*:.*)?[.]?$", re.I)

def measure(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.satisfaction.v1", ("dialogue",))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    results = []
    turns = 0
    for row in doc["events"]:
        turn = row["turn"]
        if turn["role"] != "user":
            continue
        turns += 1
        match = FEEDBACK.fullmatch(turn["message"])
        if match and turn["reply_to"] is not None:
            results.append({"feedback": match[1].lower(), "turn_sha256": row["sha256"], "reply_to": turn["reply_to"]})
    helpful = sum(row["feedback"] == "helpful" for row in results)
    return {"source": ref, "feedback": results, "replies_without_signal": turns - len(results),
            "helpful_fraction": str(Fraction(helpful, len(results))) if results else None}

if __name__ == "__main__":
    raise SystemExit(cli(measure, __doc__, rooted=True))
