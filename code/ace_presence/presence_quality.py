"""Laporkan mutu kehadiran per kanal dalam periode yang sama dengan ukuran cakupan bukti."""
from collections import defaultdict
from fractions import Fraction

from ._contracts import PresenceError, anchor, cli, day, identifier, integer, items, obj, schema, text

def quality(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.quality.v1", ("from", "until", "observations", "minimum"))
    first, last = day(plan["from"]), day(plan["until"])
    if first >= last:
        raise PresenceError("Periode mutu harus maju.")
    threshold = integer(plan["minimum"], "Minimum sampel", 1, 1000)
    groups = defaultdict(list)
    seen = set()
    for row in items(plan["observations"], 5000):
        obj(row, ("id", "channel", "date", "answered", "rated", "helpful", "source"))
        key = identifier(row["id"], "Observasi")
        channel = identifier(row["channel"], "Kanal")
        when = day(row["date"])
        flags = [row[name] for name in ("answered", "rated", "helpful")]
        if (key in seen or any(type(flag) is not bool for flag in flags)
                or (row["rated"] and not row["answered"]) or (row["helpful"] and not row["rated"])):
            raise PresenceError("Observasi ganda atau sinyal mutu bertentangan.")
        seen.add(key)
        text(row["source"], "Sumber")
        if first <= when < last:
            groups[channel].append(row)
    channels = {}
    for channel, rows in sorted(groups.items()):
        responses = sum(row["answered"] for row in rows)
        rated = sum(row["rated"] for row in rows)
        helpful = sum(row["helpful"] for row in rows)
        channels[channel] = {"samples": len(rows), "response_fraction": str(Fraction(responses, len(rows))),
                             "rated": rated, "helpful_fraction": str(Fraction(helpful, rated)) if rated >= threshold else None,
                             "sources": sorted({row["source"] for row in rows})}
    return {"range": [plan["from"], plan["until"]], "channels": channels}

if __name__ == "__main__":
    raise SystemExit(cli(quality, __doc__))
