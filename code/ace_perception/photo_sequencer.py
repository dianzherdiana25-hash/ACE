"""Susun urutan foto dari interval waktu dan relasi bersumber.

Byte foto diverifikasi sebelum dipakai. Dua interval hanya memaksa
urutan bila terpisah tegas. Prioritas waktu dan relasi eksplisit
membentuk DAG dengan pilihan yang dicatat pada tiap langkah.
Siklus menghalangi dugaan urutan lengkap.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _perception_io, _raster, _vision
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest, _utc


MAX_PHOTOS = 256
MAX_RELATIONS = 2048
MAX_PHOTO_BYTES = 20_000_000
MAX_TOTAL_BYTES = 72_000_000


def _photos(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_PHOTOS:
        raise ValueError("Jumlah foto di luar batas.")
    photos = {}
    refs = set()
    total = 0
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"id", "path", "bytes", "sha256", "timestamp"}:
            raise ValueError("Bentuk metadata foto tidak sah.")
        key = _token(row["id"], "ID foto")
        if key in photos:
            raise ValueError("Foto ganda.")
        path = row["path"]
        _perception_io.relative_parts(path)
        checksum = _digest(row["sha256"])
        size = _integer(row["bytes"], 1, MAX_PHOTO_BYTES, "Ukuran foto")
        total += size
        stamp = row["timestamp"]
        parsed = None
        if stamp is not None:
            if not isinstance(stamp, dict) or set(stamp) != {"earliest", "latest", "source_ref"}:
                raise ValueError("Bentuk cap waktu foto tidak sah.")
            first, last = _utc(stamp["earliest"]), _utc(stamp["latest"])
            ref = _token(stamp["source_ref"], "Rujukan interval foto")
            if first > last or ref in refs:
                raise ValueError("Interval waktu terbalik atau rujukan ganda.")
            refs.add(ref)
            parsed = (first, last, ref)
        photos[key] = (path, size, checksum, parsed)
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Ukuran total foto melampaui batas.")
    return photos, refs


def _add(graph, evidence, earlier, later, record):
    graph[earlier].add(later)
    evidence.setdefault((earlier, later), []).append(record)


def _relation_graph(raw, photos, refs):
    if not isinstance(raw, list) or len(raw) > MAX_RELATIONS:
        raise ValueError("Jumlah relasi foto di luar batas.")
    graph = {key: set() for key in photos}
    evidence = {}
    known = [(key, data[3]) for key, data in sorted(photos.items()) if data[3] is not None]
    for first, left in known:
        for second, right in known:
            if left[1] < right[0]:
                _add(graph, evidence, first, second, {"kind": "disjoint_time", "refs": [left[2], right[2]]})
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"before", "after", "source_ref"}:
            raise ValueError("Bentuk relasi foto tidak sah.")
        one, two, pointer = (_token(row[key], key) for key in ("before", "after", "source_ref"))
        if one not in graph or two not in graph or one == two or pointer in refs:
            raise ValueError("Relasi menunjuk foto yang sama, tidak dikenal, atau memakai rujukan ulang.")
        refs.add(pointer)
        _add(graph, evidence, one, two, {"kind": "declared_precedence", "refs": [pointer]})
    return graph, evidence


def _order(graph):
    incoming = {key: 0 for key in graph}
    for targets in graph.values():
        for target in targets:
            incoming[target] += 1
    decisions = []
    while incoming:
        ready = sorted(key for key, count in incoming.items() if count == 0)
        if not ready:
            break
        chosen = ready[0]
        decisions.append({"selected": chosen, "possible_here": ready})
        del incoming[chosen]
        for target in graph[chosen]:
            incoming[target] -= 1
    return decisions, sorted(incoming)


def sequence(root, plan, anchor):
    data = _vision.spec(plan, "ace.perception-photo-sequence.v1", ("series_ref", "photos", "constraints"))
    if _sha(data) != _digest(anchor):
        raise ValueError("Rencana foto berbeda dari anchor.")
    series = _token(data["series_ref"], "Rujukan rangkaian")
    photos, refs = _photos(data["photos"])
    graph, evidence = _relation_graph(data["constraints"], photos, refs)
    items = []
    for key, (path, length, checksum, parsed) in sorted(photos.items()):
        observed = _perception_io.read_relative(root, path, length, checksum)
        if len(observed) != length:
            raise ValueError("Ukuran foto berbeda dari deklarasi.")
        timestamp = None if parsed is None else {"earliest": parsed[0].isoformat(), "latest": parsed[1].isoformat(),
                                                 "source_ref": parsed[2]}
        items.append({"id": key, "sha256": checksum, "timestamp": timestamp})
    decisions, remaining = _order(graph)
    state = "contradictory" if remaining else "ambiguous" if any(len(row["possible_here"]) > 1 for row in decisions) else "ordered"
    return {"schema": "ace.perception-photo-order.v1", "series_ref": series, "plan_sha256": anchor,
            "plan_bytes_sha256": sha256(plan).hexdigest(), "status": state, "photos": items,
            "order": None if remaining else [row["selected"] for row in decisions],
            "decisions": decisions, "unresolved": remaining,
            "precedence": [{"before": a, "after": b, "evidence": support}
                           for (a, b), support in sorted(evidence.items())]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = sequence(args.root, _raster.read(args.plan, _vision.MAX_SPEC_BYTES), args.expect_sha256)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result["status"] != "ordered")


if __name__ == "__main__":
    raise SystemExit(main())
