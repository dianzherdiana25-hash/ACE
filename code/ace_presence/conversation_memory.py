"""Ingat percakapan lintas sesi dengan izin terpisah dan rekaman yang dapat diperiksa ulang."""
from collections import Counter

from ._contracts import PresenceError, anchor, cli, day, identifier, integer, items, obj, schema, source_bytes, text, words
from ._journal import instant, load_export


def recall(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.recall-plan.v1",
           ("person", "query", "as_of", "retention_days", "maximum", "sessions"))
    target = identifier(plan["person"], "Pseudonim lawan bicara")
    question = text(plan["query"], "Query memori", 400)
    query = words(question)
    if not query:
        raise PresenceError("Query harus memuat kata.")
    now = day(plan["as_of"])
    span = integer(plan["retention_days"], "Jendela recall", 0, 36500)
    maximum = integer(plan["maximum"], "Temuan maksimum", 1, 70)
    seen = set()
    group = []
    coverage = Counter()
    for source in items(plan["sessions"], 180):
        obj(source, ("path", "sha256", "people", "grant_ref"))
        permitted = [identifier(value, "Pseudonim yang mengizinkan") for value in items(source["people"], 40)]
        if target not in permitted or source["grant_ref"] is None:
            coverage["no_grant"] += 1
            continue
        grant = text(source["grant_ref"], "Pointer izin recall")
        report = load_export(source_bytes(root, source["path"], source["sha256"], 4_000_000))
        session = report["session"]
        if session in seen:
            raise PresenceError("Beberapa snapshot sesi yang sama tidak boleh dihitung dua kali.")
        seen.add(session)
        for row in report["events"]:
            item = row["turn"]
            when = instant(item["at"])
            age = (now - when.date()).days
            if item["speaker"] != target:
                coverage["other_speaker"] += 1
                continue
            if not 0 <= age <= span:
                coverage["outside_retention"] += 1
                continue
            content = words(item["message"])
            matched = query & content
            if not matched:
                coverage["no_text_match"] += 1
                continue
            group.append({"session": session, "turn": item["id"], "turn_sha256": row["sha256"], "excerpt": item["message"],
                          "at": item["at"], "terms": sorted(matched), "grant_ref": grant,
                          "source": {"path": source["path"], "sha256": source["sha256"], "seq": row["seq"]}})
    group.sort(key=lambda row: (-len(row["terms"]), -instant(row["at"]).timestamp(), row["session"], row["turn"]))
    return {"schema": "ace.presence.conversation-recall.v1", "plan_sha256": expected, "person": target,
            "scope": "authorized_stored_turns", "considered_sessions": len(seen), "matches": group[:maximum],
            "omitted_matching": max(0, len(group) - maximum), "exclusions": dict(sorted(coverage.items()))}


if __name__ == "__main__":
    raise SystemExit(cli(recall, __doc__, rooted=True))
