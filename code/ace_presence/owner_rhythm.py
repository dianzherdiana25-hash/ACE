"""Rangkum ritme kalender yang diizinkan pada tanggal lokal dengan menit yang dapat ditelusuri."""
from collections import defaultdict
from datetime import timedelta
from fractions import Fraction
from zoneinfo import ZoneInfo

from ._contracts import PresenceError, anchor, cli, day, items, obj, schema, text
from ._journal import instant

def rhythm(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.owner-rhythm.v1", ("zone", "first", "last", "calendar"))
    tz = ZoneInfo(text(plan["zone"], "Zona kerja", 100))
    first, last = day(plan["first"]), day(plan["last"])
    if not 0 <= (last - first).days < 366:
        raise PresenceError("Jendela ritme harus satu tahun atau kurang.")
    grouped = defaultdict(int)
    refs = defaultdict(set)
    calendar = items(plan["calendar"], 5000)
    for event in calendar:
        obj(event, ("start", "end", "source", "include"))
        start, end = instant(event["start"]), instant(event["end"])
        with_source = text(event["source"], "Bukti kalender")
        if end <= start or type(event["include"]) is not bool or (end - start).days > 6:
            raise PresenceError("Catatan kalender tidak sah atau terlalu panjang.")
        if not event["include"]:
            continue
        grouped_date = start.astimezone(tz).date()
        if first <= grouped_date <= last:
            grouped[grouped_date] += int((end - start).total_seconds())
            refs[grouped_date].add(with_source)
    days = defaultdict(list)
    for offset in range((last - first).days + 1):
        current = first + timedelta(days=offset)
        days[current.weekday()].append(current)
    return {"zone": plan["zone"], "weekdays": [
        {"weekday": key, "observed_dates": len(values),
         "average_booked_minutes": str(Fraction(sum(grouped[value] for value in values), 60 * len(values))),
         "sources": sorted({ref for value in values for ref in refs[value]})}
        for key, values in sorted(days.items())],
        "accounting": "event_duration_at_local_start_date"}

if __name__ == "__main__":
    raise SystemExit(cli(rhythm, __doc__))
