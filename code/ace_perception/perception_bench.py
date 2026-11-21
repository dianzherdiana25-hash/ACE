"""Hitung akurasi bidang, sel, dan WER dari kasus held-out tertambat.

Roster mendaftarkan hash media dan rujukan gold. Nilai salah,
observasi absen, dan pembanding tanpa token dipisah. WER berasal
dari edit distance dengan operasi substitusi, hapus, dan sisip
yang dapat ditelusuri pada ringkasan per kasus.
"""
import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys
import unicodedata

from . import _raster, _vision
from .audio_pipeline import _canonical, _sha
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_CASES = 1000
MAX_CELLS = 2500
MAX_TEXT = 16000
MAX_WORK = 4_000_000
KINDS = ("document", "table", "asr")


def _scalar(value):
    if value is None or type(value) is bool:
        return value
    if type(value) is int and abs(value) <= 10**20:
        return value
    if isinstance(value, str) and len(value) <= 1024 and (not value or value.isprintable()):
        return value
    if isinstance(value, dict) and set(value) == {"unscaled", "scale"}:
        if type(value["unscaled"]) is int and abs(value["unscaled"]) <= 10**24 and type(value["scale"]) is int and 0 <= value["scale"] <= 6:
            return value
    raise ValueError("Nilai gold/hasil perlu scalar atau desimal eksak berbatas.")


def _fields(raw):
    if not isinstance(raw, dict) or len(raw) > MAX_CELLS:
        raise ValueError("Bidang dokumen tidak sah.")
    return {_token(key, "ID bidang"): _scalar(value) for key, value in raw.items()}


def _matrix(raw):
    if raw == []:
        return []
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], list) or not raw[0]:
        raise ValueError("Bentuk tabel tidak sah.")
    span = len(raw[0])
    if len(raw)*span > MAX_CELLS or any(not isinstance(row, list) or len(row) != span for row in raw):
        raise ValueError("Tabel ragged atau terlalu besar.")
    return [[_scalar(item) for item in row] for row in raw]


def _words(raw):
    if not isinstance(raw, str) or len(raw) > MAX_TEXT:
        raise ValueError("Transkrip tolok ukur tidak sah.")
    return unicodedata.normalize("NFC", raw.casefold()).split()


def _check_value(kind, raw):
    return {"document": _fields, "table": _matrix, "asr": _words}[kind](raw)


def _plan(data, expected):
    plan = _vision.spec(data, "ace.perception-held-out.v1", ("protocol_ref", "cases"))
    if _sha(plan) != _digest(expected):
        raise ValueError("Rencana held-out berbeda dari anchor.")
    pointer = _token(plan["protocol_ref"], "Rujukan protokol")
    rows = plan["cases"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CASES:
        raise ValueError("Jumlah kasus di luar batas.")
    roster = {}
    refs = {pointer}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "kind", "media_sha256", "gold_ref", "reference"}:
            raise ValueError("Bentuk kasus held-out tidak sah.")
        key = _token(row["id"], "ID kasus")
        kind = _token(row["kind"], "Jenis kasus")
        gold = _token(row["gold_ref"], "Rujukan gold")
        if kind not in KINDS or key in roster or gold in refs:
            raise ValueError("Jenis, kasus atau rujukan gold bermasalah.")
        refs.add(gold)
        value = _check_value(kind, row["reference"])
        if kind in ("document", "table") and not value:
            raise ValueError("Gold perlu setidaknya satu bidang atau sel.")
        roster[key] = (kind, _digest(row["media_sha256"]), gold, value)
    return pointer, roster, refs


def _observations(data, roster, refs):
    raw = _vision.spec(data, "ace.perception-held-out-results.v1", ("results",))
    rows = raw["results"]
    if not isinstance(rows, list) or len(rows) > len(roster):
        raise ValueError("Jumlah hasil melebihi roster.")
    lookup = {}
    work = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "media_sha256", "receipt_ref", "result"}:
            raise ValueError("Bentuk hasil tidak sah.")
        key = _token(row["id"], "ID hasil")
        ref = _token(row["receipt_ref"], "Rujukan hasil")
        if key not in roster or key in lookup or ref in refs or row["media_sha256"] != roster[key][1]:
            raise ValueError("Hasil ganda atau tidak terikat media.")
        kind, _, _, target = roster[key]
        refs.add(ref)
        normalized = _check_value(kind, row["result"])
        if kind == "asr":
            work += (len(target)+1)*(len(normalized)+1)
            if work > MAX_WORK:
                raise ValueError("Beban edit distance melebihi batas.")
        lookup[key] = (ref, normalized)
    return lookup


def _same(a, b):
    return type(a) is type(b) and a == b


def _align(reference, output):
    # Sel adalah (biaya, substitusi, penghapusan, penyisipan).
    # Minimum leksikografis dipakai saat biaya total seri.
    states = [(j, 0, 0, j) for j in range(len(output)+1)]
    for i, gold in enumerate(reference, 1):
        row = [(i, 0, i, 0)]
        for j, result in enumerate(output, 1):
            change = int(gold != result)
            diagonal = states[j-1]
            up, left = states[j], row[j-1]
            row.append(min((diagonal[0]+change, diagonal[1]+change, diagonal[2], diagonal[3]),
                           (up[0]+1, up[1], up[2]+1, up[3]),
                           (left[0]+1, left[1], left[2], left[3]+1)))
        states = row
    return states[-1]


def _score(kind, expected, actual):
    if kind == "document":
        correct = sum(key in actual and _same(value, actual[key]) for key, value in expected.items())
        return {"units": len(expected), "correct": correct, "missing_units": len(expected.keys()-actual.keys()),
                "extra_units": len(actual.keys()-expected.keys())}
    if kind == "table":
        rows, columns = len(expected), len(expected[0])
        n, m = len(actual), len(actual[0]) if actual else 0
        positions = min(n, rows)*min(m, columns)
        correct = sum(_same(expected[y][x], actual[y][x]) for y in range(min(n, rows)) for x in range(min(m, columns)))
        return {"units": rows*columns, "correct": correct, "missing_units": rows*columns-positions,
                "extra_units": n*m-positions}
    _, s, d, i = _align(expected, actual)
    return {"units": len(expected), "substitutions": s, "deletions": d, "insertions": i}


def _require_units(kind, raw):
    if kind == "table":
        return len(raw)*len(raw[0])
    return len(raw)


def _rate(value, size):
    if not size:
        return None
    result = Fraction(value, size)
    return {"numerator": result.numerator, "denominator": result.denominator}


def report(plan, receipts, expected_protocol):
    pointer, roster, refs = _plan(plan, expected_protocol)
    observations = _observations(receipts, roster, refs)
    results = []
    totals = {kind: Counter() for kind in KINDS}
    for key, (kind, checksum, gold, reference) in sorted(roster.items()):
        counts = totals[kind]
        counts["cases"] += 1
        counts["expected_units"] += _require_units(kind, reference)
        evidence = observations.get(key)
        if evidence is None:
            source, score = None, None
        else:
            source, actual = evidence
            score = _score(kind, reference, actual)
            counts["observed_cases"] += 1
            counts.update(score)
        results.append({"id": key, "kind": kind, "media_sha256": checksum, "gold_ref": gold,
                        "receipt_ref": source, "status": "missing" if evidence is None else "scored", "score": score})
    measures = []
    for kind, tally in totals.items():
        metric = "wer" if kind == "asr" else "accuracy"
        numerator = tally["substitutions"]+tally["deletions"]+tally["insertions"] if kind == "asr" else tally["correct"]
        coverage = tally["observed_cases"] == tally["cases"] and tally["cases"] > 0
        denominator = tally["units"] + (tally["extra_units"] if kind != "asr" else 0)
        measures.append({"kind": kind, "metric": metric, "complete": coverage, **tally,
                         "rate_denominator": denominator, "observed_rate": _rate(numerator, denominator),
                         "full_rate": _rate(numerator, denominator) if coverage else None})
    return {"schema": "ace.perception-bench.v1", "protocol_ref": pointer, "protocol_sha256": expected_protocol,
            "receipts_sha256": sha256(receipts).hexdigest(), "metrics": measures, "cases": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = report(_raster.read(args.protocol, _vision.MAX_SPEC_BYTES),
                        _raster.read(args.observations, _vision.MAX_SPEC_BYTES), args.expect_protocol_sha256)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(row["status"] != "scored" for row in result["cases"]))


if __name__ == "__main__":
    raise SystemExit(main())
