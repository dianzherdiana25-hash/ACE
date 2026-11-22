"""Jawab kalender kerja bertanggal lokal dengan batas hari yang memperhitungkan perubahan zona."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ._contracts import PresenceError, anchor, cli, day, identifier, items, obj, schema, text
from ._journal import format_time, instant

def calendar(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.calendar-plan.v1", ("day", "zone", "events"))
    try:
        tz = ZoneInfo(text(plan["zone"], "Zona", 100))
    except (KeyError, ValueError) as error:
        raise PresenceError("Zona IANA tidak dapat dibaca.") from error
    date = day(plan["day"])
    start = datetime.combine(date, datetime.min.time(), tz).astimezone(timezone.utc)
    end = datetime.combine(date + timedelta(days=1), datetime.min.time(), tz).astimezone(timezone.utc)
    result = []
    seen = set()
    for event in items(plan["events"], 5000):
        obj(event, ("id", "start", "end", "title", "source"))
        key = identifier(event["id"], "Acara")
        text(event["title"], "Judul", 300)
        text(event["source"], "Sumber", 400)
        first, last = instant(event["start"]), instant(event["end"])
        if key in seen or first >= last:
            raise PresenceError("Acara ganda atau interval tidak maju.")
        seen.add(key)
        if first < end and start < last:
            result.append({**event, "local_start": first.astimezone(tz).isoformat(),
                           "local_end": last.astimezone(tz).isoformat()})
    result.sort(key=lambda row: (row["start"], row["id"]))
    return {"day": plan["day"], "zone": plan["zone"], "utc_window": [format_time(start), format_time(end)], "events": result}

if __name__ == "__main__":
    raise SystemExit(cli(calendar, __doc__))
