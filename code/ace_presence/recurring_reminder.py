"""Perluas pengingat berulang pada rentang eksplisit dengan waktu lokal, DST, dan deduplikasi."""
from datetime import datetime, time, timedelta
import re
from zoneinfo import ZoneInfo

from ._contracts import PresenceError, anchor, cli, day, digest, identifier, identity, integer, items, obj, schema, text
from ._journal import format_time, instant

CLOCK = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")

def expand(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.recurring-plan.v1", ("from", "until", "rules", "existing"))
    start, stop = instant(plan["from"]), instant(plan["until"])
    if not timedelta(0) < stop - start <= timedelta(days=90):
        raise PresenceError("Jendela pengingat maksimal 90 hari.")
    receipts = {digest(raw) for raw in items(plan["existing"], 5000)}
    seen = set()
    results = []
    skipped = []
    for row in items(plan["rules"], 100):
        obj(row, ("id", "first", "clock", "zone", "every_days", "source"))
        key = identifier(row["id"], "Pengingat")
        base = day(row["first"])
        tz = ZoneInfo(text(row["zone"], "Zona IANA", 100))
        raw = text(row["clock"], "Jam", 5)
        duration = integer(row["every_days"], "Interval hari", 1, 365)
        if key in seen or not CLOCK.fullmatch(raw):
            raise PresenceError("Pengingat ganda atau waktu tidak sah.")
        seen.add(key)
        text(row["source"], "Bukti pengingat")
        first = max(base, start.astimezone(tz).date())
        end = stop.astimezone(tz).date()
        elapsed = (first - base).days
        if first > end:
            continue
        for offset in range((-elapsed) % duration, (end - first).days + 1, duration):
            date = first + timedelta(days=offset)
            naive = datetime.combine(date, time.fromisoformat(raw))
            local = naive.replace(tzinfo=tz, fold=0)
            when = instant(format_time(local))
            if when.astimezone(tz).replace(tzinfo=None) != naive:
                skipped.append({"id": key, "local_date": date.isoformat(), "reason": "nonexistent_local_time"})
                continue
            if not start <= when < stop:
                continue
            payload = {"rule": key, "at": format_time(when), "source": row["source"]}
            finger = identity(payload)
            if finger not in receipts:
                results.append({**payload, "sha256": finger})
    return {"occurrences": sorted(results, key=lambda row: (row["at"], row["rule"])), "skipped": skipped}

if __name__ == "__main__":
    raise SystemExit(cli(expand, __doc__))
