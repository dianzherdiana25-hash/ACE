"""Temukan ungkapan bingung yang eksplisit tanpa menyimpulkan perasaan dari gaya tanda baca."""
import re

from ._contracts import anchor, cli, obj, schema, source_bytes
from ._journal import load_export

RULES = (
    ("comprehension", re.compile(r"^(?:saya |aku )?(?:belum|tidak) (?:paham|mengerti)\b|^i (?:do not|don't) understand\b", re.I)),
    ("clarification", re.compile(r"^(?:apa maksud|maksudnya apa|what do you mean)\b", re.I)),
    ("repeat", re.compile(r"^(?:tolong jelaskan lagi|bisa jelaskan ulang|please explain again)\b", re.I)),
)

def detect(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.confusion.v1", ("dialogue",))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    turns = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    matches = []
    for event in turns["events"]:
        turn = event["turn"]
        if turn["role"] != "user":
            continue
        line = turn["message"].strip()
        for name, rule in RULES:
            found = rule.search(line)
            if found:
                matches.append({"turn_id": turn["id"], "rule": name, "phrase": found[0], "turn_sha256": event["sha256"]})
                break
    return {"source": ref, "detected": matches}

if __name__ == "__main__":
    raise SystemExit(cli(detect, __doc__, rooted=True))
