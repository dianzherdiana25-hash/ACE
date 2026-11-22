"""Tentukan pengingat lokal yang jatuh tempo sekali per janji, tenggat, dan tahap."""
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, day, digest, identifier, identity, integer, items, obj, schema, text

def reminders(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.promise-reminders.v1", ("as_of", "before_days", "promises", "emitted"))
    now = day(plan["as_of"])
    stages = sorted({integer(value, "Tahap pengingat", 0, 90) for value in items(plan["before_days"], 30, 1)}, reverse=True)
    emitted = {digest(value) for value in items(plan["emitted"], 5000)}
    result = []
    seen = set()
    for row in items(plan["promises"], 1500):
        obj(row, ("id", "action", "due_on", "status", "source"))
        key = identifier(row["id"], "Janji")
        text(row["action"], "Isi janji", 300)
        text(row["source"], "Bukti janji")
        due = day(row["due_on"])
        if key in seen or row["status"] not in ("open", "fulfilled", "cancelled"):
            raise PresenceError("Janji ganda atau status tidak sah.")
        seen.add(key)
        if row["status"] != "open":
            continue
        for stage in stages:
            if due - timedelta(days=stage) == now:
                identity_fields = {"promise": key, "due_on": row["due_on"], "days_before": stage}
                fingerprint = identity(identity_fields)
                if fingerprint not in emitted:
                    result.append({**identity_fields, "sha256": fingerprint, "action": row["action"], "source": row["source"]})
    return {"as_of": plan["as_of"], "reminders": sorted(result, key=lambda row: (row["due_on"], row["promise"]))}

if __name__ == "__main__":
    raise SystemExit(cli(reminders, __doc__))
