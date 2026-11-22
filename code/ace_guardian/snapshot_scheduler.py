"""Tentukan snapshot berikut dari jadwal terjangkar, catch-up terbatas, dan deduplikasi slot."""
from datetime import datetime, timedelta, timezone
import re

from ._contracts import GuardianError, anchor, cli, digest, identity, integer, items, obj, schema

UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

def instant(raw):
    if not isinstance(raw, str) or not UTC.fullmatch(raw):
        raise GuardianError("Timestamp perlu UTC kanonis.")
    return datetime.fromisoformat(raw[:-1]).replace(tzinfo=timezone.utc)

def iso(instant_value):
    return instant_value.isoformat(timespec="seconds").replace("+00:00", "Z")

def schedule(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.snapshot-schedule.v1", ("schedule", "now", "completed", "max_catch_up"))
    rule = obj(plan["schedule"], ("origin", "every_minutes", "keep"))
    origin, now = instant(rule["origin"]), instant(plan["now"])
    delta = timedelta(minutes=integer(rule["every_minutes"], "Periode", 1, 43_200))
    keep = integer(rule["keep"], "Retensi slot", 1, 500)
    max_jobs = integer(plan["max_catch_up"], "Catch-up", 1, keep)
    completed = {digest(value) for value in items(plan["completed"], 4000)}
    current = (now - origin) // delta
    eligible, ignored = [], 0
    if current >= 0:
        first = max(0, current - keep + 1)
        ignored = first
        for index in range(first, current + 1):
            start = origin + index * delta
            token = {"index": index, "at": iso(start), "schedule_sha256": identity(rule)}
            identifier = identity(token)
            if identifier not in completed:
                eligible.append({**token, "idempotency_key": identifier})
    return {"due": eligible[:max_jobs], "pending_after_cap": max(0, len(eligible) - max_jobs),
            "outside_retention_slots": ignored, "next_at": iso(origin + max(0, current + 1) * delta)}

if __name__ == "__main__":
    raise SystemExit(cli(schedule, __doc__))
