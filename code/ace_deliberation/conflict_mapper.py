"""Petakan potensi konflik yang bisa ditelusuri melalui relasi bertanggal.

Arah relasi mengikuti deklarasi masukan. Pemetaan memakai relasi yang
berlaku untuk topik dan tanggal bersangkutan. Kemunculan jalur kepentingan
menandai kebutuhan review dan tidak menyimpulkan motif atau pengaruh nyata.
"""
from collections import deque
from datetime import date
import json
from pathlib import Path


MAX_ACTORS = 600
MAX_LINKS = 4_000
MAX_POSITIONS = 100
MAX_DEPTH = 8
MAX_BYTES = 6_000_000
_LINKS = ("holds_interest", "member_of", "controls", "consults_for")


class ConflictError(ValueError):
    """Catatan hubungan atau posisi tidak sah."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise ConflictError("Field konflik menyimpang dari skema.")


def _text(value, label, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise ConflictError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ConflictError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _date(value):
    if not isinstance(value, str):
        raise ConflictError("Tanggal harus YYYY-MM-DD.")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ConflictError("Tanggal tidak sah.") from exc
    if result.isoformat() != value:
        raise ConflictError("Tanggal harus YYYY-MM-DD.")
    return result


def _rows(values, maximum):
    if not isinstance(values, list) or len(values) > maximum:
        raise ConflictError("Jumlah record konflik di luar batas.")
    return values


def _identifiers(values, maximum, catalog=None):
    items = [_text(item, "identifier") for item in _rows(values, maximum)]
    if len(set(items)) != len(items) or catalog is not None and set(items) - catalog:
        raise ConflictError("Identifier ganda atau tidak ditemukan.")
    return sorted(items)


def _link(raw, actors, registered_refs):
    _shape(raw, ("source", "target", "relation", "topic", "valid_from", "valid_until", "source_ref"))
    source, target = (_text(raw[key], key) for key in ("source", "target"))
    ref = _text(raw["source_ref"], "rujukan relasi", 512)
    if source == target or source not in actors or target not in actors or ref in registered_refs:
        raise ConflictError("Ujung relasi atau rujukan ganda/tak sah.")
    if raw["relation"] not in _LINKS:
        raise ConflictError("Relasi kepentingan tidak dikenal.")
    topic = _text(raw["topic"], "topik") if raw["topic"] is not None else None
    beginning = _date(raw["valid_from"])
    end = _date(raw["valid_until"]) if raw["valid_until"] is not None else None
    if end is not None and end <= beginning:
        raise ConflictError("Interval relasi kosong atau terbalik.")
    registered_refs.add(ref)
    return source, target, raw["relation"], topic, beginning, end, ref


def _paths(outbound, start, maximum):
    previous = {start: None}
    queue = deque([(start, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth == maximum:
            continue
        for edge in outbound.get(current, ()):
            if edge["target"] not in previous:
                previous[edge["target"]] = edge
                queue.append((edge["target"], depth + 1))
    return previous


def _witness(previous, beneficiary):
    path = []
    while (hop := previous[beneficiary]) is not None:
        path.append(hop.copy())
        beneficiary = hop["source"]
    return path[::-1]


def map_conflicts(raw):
    _shape(raw, ("as_of", "actors", "links", "positions", "oppositions", "max_depth"))
    as_of = _date(raw["as_of"])
    maximum = raw["max_depth"]
    if type(maximum) is not int or not 1 <= maximum <= MAX_DEPTH:
        raise ConflictError("max_depth harus 1–8.")
    actors = set(_identifiers(raw["actors"], MAX_ACTORS))
    refs = set()
    links = [_link(item, actors, refs) for item in _rows(raw["links"], MAX_LINKS)]
    positions = {}
    for row in _rows(raw["positions"], MAX_POSITIONS):
        _shape(row, ("id", "topic", "advocates", "beneficiaries", "source_ref"))
        identifier = _text(row["id"], "posisi")
        ref = _text(row["source_ref"], "sumber posisi", 512)
        if identifier in positions or ref in refs:
            raise ConflictError("ID posisi atau sumber ganda.")
        refs.add(ref)
        advocates = _identifiers(row["advocates"], MAX_ACTORS, actors)
        beneficiaries = _identifiers(row["beneficiaries"], MAX_ACTORS, actors)
        positions[identifier] = {
            "id": identifier, "topic": _text(row["topic"], "topik posisi"),
            "advocates": advocates, "beneficiaries": beneficiaries, "source_ref": ref,
        }

    by_topic = {}
    position_reports = []
    for identifier, row in sorted(positions.items()):
        label = row["topic"]
        if label not in by_topic:
            outbound = {}
            for source, target, relation, topic, beginning, end, ref in links:
                if topic in (None, label) and beginning <= as_of and (end is None or as_of < end):
                    outbound.setdefault(source, []).append({"source": source, "target": target,
                                                           "relation": relation, "source_ref": ref})
            for edges in outbound.values():
                edges.sort(key=lambda edge: (edge["target"], edge["relation"], edge["source_ref"]))
            by_topic[label] = outbound
        witness_rows = []
        for advocate in row["advocates"]:
            reachable = _paths(by_topic[label], advocate, maximum)
            for beneficiary in row["beneficiaries"]:
                if beneficiary in reachable:
                    witness_rows.append({
                        "advocate": advocate, "beneficiary": beneficiary,
                        "kind": "direct" if advocate == beneficiary else "linked",
                        "path": _witness(reachable, beneficiary),
                    })
        position_reports.append({**row, "interest_witnesses": witness_rows})

    comparisons = {}
    for row in _rows(raw["oppositions"], 2_000):
        _shape(row, ("left", "right", "source_ref"))
        left, right = sorted(_text(row[key], "sisi oposisi") for key in ("left", "right"))
        ref = _text(row["source_ref"], "sumber oposisi", 512)
        if (left == right or left not in positions or right not in positions
                or positions[left]["topic"] != positions[right]["topic"]
                or (left, right) in comparisons or ref in refs):
            raise ConflictError("Oposisi ganda atau mengacu posisi yang tidak sebanding.")
        refs.add(ref)
        a, b = positions[left], positions[right]
        comparisons[left, right] = {
            "left": left, "right": right, "source_ref": ref,
            "shared_advocates": sorted(set(a["advocates"]) & set(b["advocates"])),
            "shared_beneficiaries": sorted(set(a["beneficiaries"]) & set(b["beneficiaries"])),
        }
    return {"schema": "ace.conflict-mapper.v1", "as_of": as_of.isoformat(), "max_depth": maximum,
            "positions": position_reports, "oppositions": [comparisons[key] for key in sorted(comparisons)]}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ConflictError("Masukan konflik melampaui batas.")
        print(json.dumps(map_conflicts(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
