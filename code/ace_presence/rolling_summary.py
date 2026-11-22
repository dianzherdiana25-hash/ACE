"""Ringkas sesi panjang secara ekstraktif, dengan tiap petikan tetap berasal dari turn bertambat."""
from collections import Counter

from ._contracts import PresenceError, anchor, cli, integer, items, obj, schema, source_bytes, text, words
from ._journal import load_export


def _topics(raw):
    labels = []
    names = set()
    for row in items(raw, 35):
        obj(row, ("id", "terms"))
        key = text(row["id"], "Nama topik", 60)
        phrases = set()
        for term in items(row["terms"], 20, 1):
            phrases.update(words(text(term, "Istilah topik", 80)))
        if not phrases or key in names:
            raise PresenceError("Topik kosong atau ganda.")
        names.add(key)
        labels.append((key, phrases))
    return labels


def summarize(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.summary-plan.v1", ("dialogue", "max_turns", "max_chars", "topics"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    checked = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    cap = integer(plan["max_turns"], "Turn dalam ringkasan", 1, 65)
    budget = integer(plan["max_chars"], "Anggaran karakter", 15, 30000)
    terms = _topics(plan["topics"])
    matches = Counter()
    observations = []
    for row in checked["events"]:
        payload = row["turn"]
        labels = sorted(key for key, voc in terms if voc & words(payload["message"]))
        matches.update(labels)
        observations.append((row, labels))
    # Favor coverage of rarely mentioned requested topics, then the latest turn.
    candidates = sorted(observations, key=lambda record: (
        -sum(1000 // matches[label] for label in record[1]), -record[0]["seq"]))
    picked = []
    included = set()
    for row, labels in candidates:
        line = row["turn"]["message"]
        if len(line) <= budget:
            picked.append({"seq": row["seq"], "id": row["turn"]["id"], "role": row["turn"]["role"],
                           "message": line, "source_turn_sha256": row["sha256"], "refs": row["turn"]["refs"], "topics": labels})
            included.update(labels)
            budget -= len(line)
        if len(picked) == cap:
            break
    picked.sort(key=lambda row: row["seq"])
    return {"schema": "ace.presence.rolling-summary.v1", "plan_sha256": expected,
            "source": ref, "session": checked["session"], "head_sha256": checked["head_sha256"],
            "method": "whole_turn_extraction_rare_topics_then_recency", "selected": picked,
            "observed_turns": len(observations), "omitted_turns": len(observations) - len(picked),
            "unseen_topics": sorted({name for name, _ in terms} - matches.keys()),
            "mentioned_but_omitted_topics": sorted(matches.keys() - included), "characters_left": budget}


if __name__ == "__main__":
    raise SystemExit(cli(summarize, __doc__, rooted=True))
