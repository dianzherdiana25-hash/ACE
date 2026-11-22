"""Hubungkan janji ke keputusan yang sudah disahkan dengan pointer dua arah yang dapat diaudit."""
from ._contracts import PresenceError, anchor, cli, digest, identifier, items, obj, schema, text

def link(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.decision-links.v1", ("decisions", "promises", "links"))
    approved = {}
    seen = set()
    for row in items(plan["decisions"], 5000):
        obj(row, ("id", "status", "sha256"))
        key = identifier(row["id"], "Putusan")
        if key in seen or row["status"] not in ("approved", "rejected", "deferred"):
            raise PresenceError("Putusan ganda atau status tidak sah.")
        seen.add(key)
        sha = digest(row["sha256"])
        if row["status"] == "approved":
            approved[key] = sha
    promises = {}
    for row in items(plan["promises"], 5000):
        obj(row, ("id", "source"))
        key = identifier(row["id"], "Janji")
        if key in promises:
            raise PresenceError("Janji ganda.")
        promises[key] = text(row["source"], "Bukti janji")
    links = set()
    dangling = []
    for row in items(plan["links"], 5000):
        obj(row, ("decision", "promise"))
        key = identifier(row["decision"], "Putusan"), identifier(row["promise"], "Janji")
        if key[0] in approved and key[1] in promises:
            links.add(key)
        else:
            dangling.append(dict(row))
    result = [{"decision": decision, "promise": promise, "decision_sha256": approved[decision],
               "promise_source": promises[promise]} for decision, promise in sorted(links)]
    return {"links": result, "dangling": sorted(dangling, key=lambda row: (row["decision"], row["promise"]))}

if __name__ == "__main__":
    raise SystemExit(cli(link, __doc__))
