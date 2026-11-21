"""Simpan indeks persepsi lepas dari memory store runtime ACE.

Record membawa hash media, waktu ingat, sumber receipt, dan lokator
bukti. Kustodi mengikat urutan record dan memungkinkan replay. Recall
mengurutkan bukti menurut overlap istilah, waktu, dan ID. Dua
transkrip yang bertentangan pada lokator sama tidak dipilih diam-diam.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import unicodedata

from . import _raster
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .ocr_engine import _pairs


MAX_RECORDS = 8000
MAX_RELATED_REFS = 32
MAX_INPUT_BYTES = 16_000_000
HASH = re.compile(r"[0-9a-f]{64}")
WORDS = re.compile(r"[^\W_]+", re.UNICODE)
GENESIS = _sha({"schema": "ace.perceptual-index.v1", "records": []})


def _digest(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ValueError("SHA-256 tidak sah.")
    return value


def _utc(value):
    try:
        parsed = datetime.fromisoformat(_token(value, "Cap waktu"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValueError("Cap waktu perlu ISO-8601 bertimezone.") from exc


def _record(raw):
    fields = {"id", "modality", "media_sha256", "observed_at", "receipt_ref", "location", "excerpt"}
    if not isinstance(raw, dict) or set(raw) != fields or raw["modality"] not in ("image", "audio"):
        raise ValueError("Record persepsi tidak sesuai skema.")
    key = _token(raw["id"], "ID persepsi")
    src = _token(raw["receipt_ref"], "Rujukan receipt media")
    media = _digest(raw["media_sha256"])
    stamp = _utc(raw["observed_at"]).isoformat()
    loc = raw["location"]
    if raw["modality"] == "image":
        if not isinstance(loc, list) or len(loc) != 4:
            raise ValueError("Lokator gambar perlu boks piksel.")
        limits = [_integer(value, 0, _raster.MAX_PIXELS, "Koordinat") for value in loc]
        x0, y0, x1, y1 = limits
        if x1 <= x0 or y1 <= y0:
            raise ValueError("Boks piksel kosong.")
    else:
        if not isinstance(loc, list) or len(loc) != 2:
            raise ValueError("Lokator audio perlu dua waktu mikrodetik.")
        limits = [_integer(value, 0, 10**12, "Mikrodetik") for value in loc]
        if limits[0] >= limits[1]:
            raise ValueError("Rentang audio kosong.")
    text = raw["excerpt"]
    if not isinstance(text, str) or not 1 <= len(text) <= 1000 or not text.isprintable() or not text.strip():
        raise ValueError("Kutipan perlu teks terbaca berbatas.")
    return {"id": key, "modality": raw["modality"], "media_sha256": media,
            "observed_at": stamp, "receipt_ref": src, "location": limits, "excerpt": text}


def catalog(records):
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError("Jumlah record persepsi di luar batas.")
    sequence = []
    head = GENESIS
    ids = set()
    pointers = set()
    for index, raw in enumerate(records, 1):
        record = _record(raw)
        if record["id"] in ids or record["receipt_ref"] in pointers:
            raise ValueError("Identitas atau receipt persepsi ganda.")
        ids.add(record["id"])
        pointers.add(record["receipt_ref"])
        edge = {"ordinal": index, "previous_sha256": head, "record": record}
        head = _sha(edge)
        sequence.append({**edge, "sha256": head})
    return {"schema": "ace.perceptual-index.v1", "head_sha256": head, "entries": sequence}


def inspect(index, expected):
    fields = {"schema", "head_sha256", "entries"}
    if not isinstance(index, dict) or set(index) != fields or index["schema"] != "ace.perceptual-index.v1":
        raise ValueError("Indeks persepsi tidak sesuai skema.")
    entries = index["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_RECORDS or any(
            not isinstance(row, dict) or "record" not in row for row in entries):
        raise ValueError("Rantai persepsi tidak sah.")
    replay = catalog([row["record"] for row in entries])
    if _digest(expected) != replay["head_sha256"] or _canonical(index) != _canonical(replay):
        raise ValueError("Rantai persepsi berbeda dari anchor.")
    return replay


def _terms(text):
    return set(WORDS.findall(unicodedata.normalize("NFC", text.casefold())))


def recall(index, expected, query, *, modality=None, since=None, until=None, limit=20):
    log = inspect(index, expected)
    terms = _terms(_token(query, "Kueri"))
    if not terms or modality not in (None, "image", "audio"):
        raise ValueError("Kueri kosong atau modalitas tidak sah.")
    _integer(limit, 1, 500, "Batas hasil")
    low, high = _utc(since) if since is not None else None, _utc(until) if until is not None else None
    if low is not None and high is not None and low > high:
        raise ValueError("Batas waktu pencarian terbalik.")
    groups = defaultdict(list)
    candidates = []
    for entry in log["entries"]:
        record = entry["record"]
        key = (record["modality"], record["media_sha256"], tuple(record["location"]))
        groups[key].append(record)
        timestamp = _utc(record["observed_at"])
        hits = terms & _terms(record["excerpt"])
        if hits and (modality is None or record["modality"] == modality) and (
                low is None or timestamp >= low) and (high is None or timestamp <= high):
            candidates.append((len(hits), timestamp, record["id"], key, sorted(hits), entry))
    candidates.sort(key=lambda item: item[2])
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    related = {}
    results = []
    for score, _, _, key, hits, item in candidates[:limit]:
        if key not in related:
            records = groups[key]
            conflicting = len({_terms_normalized(record["excerpt"]) for record in records}) > 1
            pointers = sorted(record["receipt_ref"] for record in records)[:MAX_RELATED_REFS+1]
            related[key] = conflicting, pointers, len(records)-1
        conflicting, pointers, count = related[key]
        refs = [pointer for pointer in pointers if pointer != item["record"]["receipt_ref"]][:MAX_RELATED_REFS]
        results.append({**item["record"], "record_sha256": item["sha256"], "matched_terms": hits,
                        "overlap": score, "status": "conflicting_receipts" if conflicting else "matched",
                        "other_receipt_count": count, "other_receipt_refs": refs})
    return {"schema": "ace.perceptual-recall.v1", "head_sha256": expected, "matched": len(candidates),
            "results": results}


def _terms_normalized(text):
    return unicodedata.normalize("NFC", " ".join(text.split()).casefold())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("index")
    make.add_argument("source", type=Path)
    read = commands.add_parser("search")
    read.add_argument("source", type=Path)
    read.add_argument("query")
    read.add_argument("--expect-head", required=True)
    read.add_argument("--modality", choices=("image", "audio"))
    read.add_argument("--since")
    read.add_argument("--until")
    read.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        data = json.loads(_raster.read(args.source, MAX_INPUT_BYTES).decode("utf-8"), object_pairs_hook=_pairs)
        product = catalog(data) if args.command == "index" else recall(
            data, args.expect_head, args.query, modality=args.modality, since=args.since, until=args.until, limit=args.limit)
        sys.stdout.buffer.write(_canonical(product) + b"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
