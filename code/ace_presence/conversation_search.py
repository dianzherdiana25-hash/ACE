"""Cari riwayat berizin dengan ranking kata diskriminatif dan pointer turn yang tepat."""
from collections import Counter
from fractions import Fraction

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, source_bytes, text, words
from ._journal import load_export

def search(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.search-plan.v1", ("exports", "allowed_speakers", "query", "limit"))
    phrase = text(plan["query"], "Kueri", 200)
    tokens = words(phrase)
    if not tokens:
        raise PresenceError("Kueri tidak punya kata yang dapat dicocokkan.")
    allowed = {identifier(key, "Pembicara") for key in items(plan["allowed_speakers"], 100, 1)}
    documents = []
    frequencies = Counter()
    seen = set()
    for ref in items(plan["exports"], 120):
        obj(ref, ("path", "sha256"))
        if ref["sha256"] in seen:
            raise PresenceError("Ekspor sama terdaftar berulang.")
        seen.add(ref["sha256"])
        checked = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
        for row in checked["events"]:
            payload = row["turn"]
            if payload["speaker"] not in allowed:
                continue
            matched = tokens & words(payload["message"])
            frequencies.update(matched)
            if matched:
                documents.append((row, ref, matched))
    matches = []
    for row, ref, matched in documents:
        utterance = row["turn"]
        score = sum((Fraction(1, frequencies[word]) for word in matched), Fraction())
        if phrase.casefold() in utterance["message"].casefold():
            score += 2
        result = {"turn": utterance["id"], "session": utterance["session"], "message": utterance["message"],
                  "source": ref, "turn_sha256": row["sha256"], "score": str(score)}
        matches.append((score, utterance["at"], utterance["session"], row["seq"], result))
    matches.sort(key=lambda item: (-item[0], item[1], item[2], item[3], item[4]["turn_sha256"]))
    return {"hits": [entry[-1] for entry in matches[:integer(plan["limit"], "Batas cari", 1, 100)]], "matches": len(matches)}

if __name__ == "__main__":
    raise SystemExit(cli(search, __doc__, rooted=True))
