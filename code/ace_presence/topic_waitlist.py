"""Susun daftar topik terbuka yang siap dibahas dengan aging dan dependensi eksplisit."""
from ._contracts import PresenceError, anchor, cli, day, identifier, integer, items, obj, schema, text

def queue(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.topic-waitlist.v1", ("as_of", "topics"))
    as_of = day(plan["as_of"])
    all_topics = {}
    for row in items(plan["topics"], 1500):
        obj(row, ("id", "state", "added", "not_before", "priority", "blocked_by", "source"))
        key = identifier(row["id"], "Topik")
        added, ready = day(row["added"]), day(row["not_before"])
        importance = integer(row["priority"], "Prioritas", 0, 99)
        deps = {identifier(value, "Topik prasyarat") for value in items(row["blocked_by"], 30)}
        text(row["source"], "Bukti topik")
        if key in all_topics or key in deps or ready < added or row["state"] not in ("queued", "resolved"):
            raise PresenceError("Topik, jadwal, atau prasyarat tidak sah.")
        all_topics[key] = (added, ready, importance, deps, row)
    eligible, waiting = [], []
    for key, (added, ready, importance, deps, row) in all_topics.items():
        if row["state"] == "resolved":
            continue
        blockers = sorted(dep for dep in deps if dep not in all_topics or all_topics[dep][4]["state"] != "resolved")
        age = max(0, (as_of - added).days)
        if ready > as_of or blockers:
            waiting.append({"id": key, "not_before": row["not_before"], "blocked_by": blockers, "source": row["source"]})
        else:
            eligible.append((-(importance + min(20, age // 7)), row["added"], key, row["source"]))
    return {"ready": [{"id": key, "score": -score, "source": source} for score, _, key, source in sorted(eligible)],
            "waiting": sorted(waiting, key=lambda row: row["id"])}

if __name__ == "__main__":
    raise SystemExit(cli(queue, __doc__))
