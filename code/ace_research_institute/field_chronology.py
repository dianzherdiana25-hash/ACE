"""Tata peristiwa dalam interval tanggal yang dapat dipertanggungjawabkan dari sumber."""
import calendar
from datetime import date
import re

from ._contracts import ResearchError, anchor, cli, day, identifier, integer, items, obj, schema, source_bytes, text


def _range(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?", raw):
        raise ResearchError("Waktu peristiwa perlu YYYY, YYYY-MM, atau YYYY-MM-DD.")
    parts = list(map(int, raw.split("-")))
    try:
        if len(parts) == 1:
            return date(parts[0], 1, 1), date(parts[0], 12, 31)
        if len(parts) == 2:
            year, month = parts
            return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        stamp = day(raw)
        return stamp, stamp
    except (ValueError, calendar.IllegalMonthError) as error:
        raise ResearchError("Tanggal atau interval tidak valid.") from error


def chronology(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.chronology-plan.v1", ("field", "documents", "events"))
    field = text(plan["field"], "Bidang")
    referenced = {}
    for row in items(plan["documents"], 100, 1):
        obj(row, ("id", "path", "sha256"))
        key = identifier(row["id"], "Dokumen")
        if key in referenced:
            raise ResearchError("Dokumen kronologi ganda.")
        referenced[key] = (row, source_bytes(root, row["path"], row["sha256"], 250000).decode("utf-8").splitlines())
    history = {}
    for row in items(plan["events"], 500, 1):
        obj(row, ("id", "date", "summary", "document", "line", "after", "excerpt"))
        key = identifier(row["id"], "Peristiwa")
        doc = identifier(row["document"], "Dokumen")
        if key in history or doc not in referenced:
            raise ResearchError("ID peristiwa ganda atau dokumen belum terdaftar.")
        descriptor, lines = referenced[doc]
        low, high = _range(row["date"])
        line = integer(row["line"], "Baris peristiwa", 1, len(lines))
        summary = text(row["summary"], "Ringkasan peristiwa")
        quoted = text(row["excerpt"], "Petikan kronologi")
        observed = lines[line - 1]
        if quoted not in observed or not re.search(r"(?<![0-9-])" + re.escape(row["date"]) + r"(?![0-9-])", observed):
            raise ResearchError("Petikan atau tanggal tidak ditemukan di baris yang ditunjuk.")
        prior = sorted({identifier(value, "Peristiwa sebelumnya") for value in items(row["after"], 40)})
        history[key] = (low, high, {"id": key, "date_signal": row["date"], "range": [low.isoformat(), high.isoformat()],
                                     "summary": summary, "source": {**descriptor, "line": line, "excerpt": quoted}, "after": prior})
    findings = []
    for low, high, row in history.values():
        for parent in row["after"]:
            if parent not in history or parent == row["id"]:
                raise ResearchError("Peristiwa pendahulu tidak sah.")
            before, until, _ = history[parent]
            if before >= high:
                findings.append({"id": row["id"], "after": parent, "reason": "temporal_order_conflict"})
            elif until >= low:
                findings.append({"id": row["id"], "after": parent, "reason": "overlapping_intervals"})
    sorted_keys = sorted(history, key=lambda key: (history[key][0], history[key][1], key))
    return {"schema": "ace.institute.chronology.v1", "plan_sha256": expected, "field": field,
            "events": [history[key][2] for key in sorted_keys], "findings": findings,
            "status": "check_relationships" if findings else "intervals_consistent"}


if __name__ == "__main__":
    raise SystemExit(cli(chronology, __doc__, rooted=True))
