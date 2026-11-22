"""Ubah jadwal konten menjadi kalender ICS dengan batas kanal dan prasyarat yang eksplisit."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ProductionError, anchor, canonical, decode, identifier, identity, items, obj, read, schema, text


def _instant(raw):
    try:
        value = datetime.fromisoformat(raw[:-1]).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, IndexError, AttributeError) as error:
        raise ProductionError("Timestamp kalender perlu YYYY-MM-DDTHH:MM:SSZ.") from error
    if value.isoformat(timespec="seconds").replace("+00:00", "Z") != raw:
        raise ProductionError("Timestamp kalender harus kanonis.")
    return value


def _escape(raw):
    return raw.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


def _fold(line):
    fragments = []
    limits = 75
    current = ""
    for char in line:
        if len((current + char).encode()) > limits:
            fragments.append(current)
            limits = 75
            current = " " + char
        else:
            current += char
    fragments.append(current)
    return "\r\n".join(fragments)


def create_calendar(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.production.calendar-plan.v1", ("id", "as_of", "channels", "entries"))
    key = identifier(plan["id"], "ID jadwal")
    stamp = _instant(plan["as_of"])
    channels = [identifier(item, "Kanal") for item in items(plan["channels"], 25, 1)]
    if len(set(channels)) != len(channels):
        raise ProductionError("Daftar kanal ganda.")
    items_by_id = {}
    windows = set()
    for row in items(plan["entries"], 450, 1):
        obj(row, ("id", "title", "channel", "start", "end", "requires", "source_ref"))
        item = identifier(row["id"], "Acara")
        room = identifier(row["channel"], "Kanal acara")
        first, last = _instant(row["start"]), _instant(row["end"])
        if item in items_by_id or room not in channels or last <= first:
            raise ProductionError("Acara ganda, kanal tak dikenal atau interval terbalik.")
        need = [identifier(ref, "Prasyarat acara") for ref in items(row["requires"], 30)]
        items_by_id[item] = (first, last, {"id": item, "channel": room, "start": row["start"], "end": row["end"],
                    "title": text(row["title"], "Judul acara", 200), "source_ref": text(row["source_ref"], "Pointer acara"),
                    "requires": sorted(set(need))})
        if (room, first) in windows:
            raise ProductionError("Awal slot pada kanal yang sama ganda.")
        windows.add((room, first))
    inside = {}
    ordered = sorted(items_by_id.values(), key=lambda row: (row[0], row[2]["id"]))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ACE//Local Production Calendar//ID", "CALSCALE:GREGORIAN"]
    dateformat = "%Y%m%dT%H%M%SZ"
    for first, last, row in ordered:
        room = row["channel"]
        if room in inside and inside[room] > first:
            raise ProductionError("Slot waktu tumpang tindih pada kanal.")
        inside[room] = last
        if any(before not in items_by_id or items_by_id[before][1] > first for before in row["requires"]):
            raise ProductionError("Prasyarat tidak selesai sebelum slot.")
        uid = identity({"calendar": key, "event": row["id"]})[:32] + "@ace.local"
        lines.extend(["BEGIN:VEVENT", "UID:" + uid, "DTSTAMP:" + stamp.strftime(dateformat),
                      "DTSTART:" + first.strftime(dateformat), "DTEND:" + last.strftime(dateformat),
                      "SUMMARY:" + _escape(row["title"]), "DESCRIPTION:" + _escape(row["source_ref"]),
                      "CATEGORIES:" + room, "END:VEVENT"])
    lines.append("END:VCALENDAR")
    raw = ("\r\n".join(map(_fold, lines)) + "\r\n").encode()
    return raw, {"schema": "ace.production.calendar-draft.v1", "plan_sha256": expected, "ical_sha256": sha256(raw).hexdigest(),
                 "events": [row for _, _, row in ordered], "status": "local_draft"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, receipt = create_calendar(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
