"""Susun antrean interupsi lokal hanya dari permintaan yang secara eksplisit diberi izin."""
from ._contracts import PresenceError, anchor, cli, digest, identifier, identity, items, obj, schema, text
from ._journal import instant

def route(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.priority.v1", ("now", "grants", "requests"))
    now = instant(plan["now"])
    grants = {digest(value) for value in items(plan["grants"], 500)}
    result = []
    refused = []
    seen = set()
    for request in items(plan["requests"], 500):
        obj(request, ("id", "speaker", "priority", "at", "expires", "message"))
        key = identifier(request["id"], "Permintaan")
        identifier(request["speaker"], "Pembicara")
        text(request["message"], "Pesan", 1200)
        at, expires = instant(request["at"]), instant(request["expires"])
        priority = request["priority"]
        if key in seen or at >= expires or priority not in ("interrupt", "normal"):
            raise PresenceError("Prioritas, waktu, atau ID antrean tidak sah.")
        seen.add(key)
        fingerprint = identity(request)
        if not at <= now < expires or (priority == "interrupt" and fingerprint not in grants):
            refused.append(key)
            continue
        result.append({**request, "request_sha256": fingerprint})
    result.sort(key=lambda row: (row["priority"] != "interrupt", row["at"], row["id"]))
    return {"queue": result, "refused": sorted(refused)}

if __name__ == "__main__":
    raise SystemExit(cli(route, __doc__))
