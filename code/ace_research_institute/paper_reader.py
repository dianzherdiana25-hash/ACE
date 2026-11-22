"""Ekstrak pengukuran yang ditandai dalam tabel hasil dan tautkan ke baris sumber paper."""
from hashlib import sha256
import re

from ._contracts import ResearchError, anchor, cli, digest, fmt, identifier, items, obj, schema, source_bytes, text
from ._evidence import DIMENSIONS, quantity


HEADER = ("id", *DIMENSIONS, "value", "unit", "n", "lower", "upper")
SECTIONS = {"results", "hasil", "findings"}
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$")
SEPARATOR = re.compile(r":?-{3,}:?")


def _split(row):
    if not row.startswith("|") or not row.endswith("|"):
        return None
    return [value.strip() for value in row[1:-1].split("|")]


def _record(values, title, source, group, line, anchor):
    label, *parts, value, unit, size, lower, upper = values
    if not size.isascii() or not size.isdecimal() or not 0 < len(size) <= 8 or not int(size):
        raise ResearchError("Ukuran sampel tabel hasil harus integer positif.")
    name = identifier(label, "Klaim")
    result = {field: identifier(part, field) for field, part in zip(DIMENSIONS, parts, strict=True)}
    family, point = quantity(value, unit)
    if (lower == "-") != (upper == "-"):
        raise ResearchError("Batas interval perlu keduanya atau kosong keduanya.")
    interval = None
    if lower != "-":
        _, low = quantity(lower, unit)
        _, high = quantity(upper, unit)
        if not low <= point <= high:
            raise ResearchError("Interval tabel tidak mengapit estimasi.")
        interval = {"lower": fmt(low), "upper": fmt(high)}
    return {"id": name, "dimensions": result, "estimate": fmt(point), "unit": family, "source_unit": unit,
            "sample_size": int(size), "interval": interval, "source": {"path": source, "line": line,
            "sha256": anchor, "title": title, "independence_group": group}}


def extract(raw, title, source, group, expected):
    if sha256(raw).hexdigest() != digest(expected):
        raise ResearchError("Paper berbeda dari anchor.")
    if len(raw) > 1_000_000:
        raise ResearchError("Paper melewati batas parser.")
    lines = raw.decode("utf-8").splitlines()
    readings = []
    held = []
    region = ""
    seen = set()
    fenced = False
    state = "none"
    fenced_marker = None
    for index, original in enumerate(lines, 1):
        line = original.strip()
        if line.startswith(("```", "~~~")):
            marker = line[:3]
            if not fenced:
                fenced, fenced_marker = True, marker
            elif marker == fenced_marker:
                fenced, fenced_marker = False, None
            state = "none"
            continue
        if fenced:
            continue
        heading = HEADING.fullmatch(line)
        if heading:
            region = heading[1].strip().casefold()
            state = "none"
            continue
        cells = _split(line)
        if region not in SECTIONS or not cells:
            state = "none"
            continue
        if tuple(cells) == HEADER:
            state = "separator"
            continue
        if state == "separator":
            if len(cells) == len(HEADER) and all(SEPARATOR.fullmatch(cell) for cell in cells):
                state = "rows"
            else:
                held.append({"line": index, "reason": "malformed_table_separator"})
                state = "none"
            continue
        if state != "rows":
            continue
        if len(cells) != len(HEADER):
            held.append({"line": index, "reason": "malformed_measurement_row"})
            continue
        try:
            record = _record(cells, title, source, group, index, expected)
        except (ValueError, TypeError) as error:
            held.append({"line": index, "reason": str(error)})
            continue
        if record["id"] in seen:
            raise ResearchError("ID klaim terulang dalam tabel hasil paper.")
        seen.add(record["id"])
        readings.append(record)
        if len(readings) > 500:
            raise ResearchError("Tabel memuat terlalu banyak pengukuran.")
    return {"schema": "ace.institute.paper-reading.v1", "paper_sha256": expected, "path": source,
            "claims": readings, "held": held, "basis": "annotated_results_tables"}


def read_papers(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.paper-plan.v1", ("papers",))
    result = []
    seen = set()
    for link in items(plan["papers"], 40, 1):
        obj(link, ("id", "title", "path", "sha256", "independence_group"))
        key = identifier(link["id"], "ID paper")
        if key in seen:
            raise ResearchError("ID paper ganda.")
        seen.add(key)
        study = extract(source_bytes(root, link["path"], link["sha256"]), text(link["title"], "Judul paper"),
                        link["path"], identifier(link["independence_group"], "Grup"), link["sha256"])
        result.append({"id": key, **study})
    return {"schema": "ace.institute.paper-readings.v1", "plan_sha256": expected, "papers": result}


if __name__ == "__main__":
    raise SystemExit(cli(read_papers, __doc__, rooted=True))
