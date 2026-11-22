"""Tabulasikan biaya unit internal per jenis persepsi dari receipt lokal.

Harga unit harus dinyatakan dalam rencana. Receipt dengan metrik
absen, jendela tidak cocok, atau pasangan kelas/organ tak bertarif
tidak dihitung sebagai biaya nol. Penggunaan sumber dan dasar
estimasi tetap dapat ditelaah tanpa transaksi.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest, _utc


METRICS = ("runtime_us", "processed_bytes", "input_units")
MAX_RECEIPTS = 8192


def _rows(raw, length, required):
    if not isinstance(raw, list) or len(raw) > length:
        raise ValueError("Jumlah record biaya di luar batas.")
    for row in raw:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("Bentuk record biaya tidak sah.")
        yield row


def _metrics(raw, nullable):
    if not isinstance(raw, dict) or set(raw) != set(METRICS):
        raise ValueError("Metrik biaya tidak sesuai skema.")
    return {key: None if nullable and raw[key] is None else _integer(raw[key], 0, 10**12, key) for key in METRICS}


def report(plan, receipts, expected):
    names = ("plan_ref", "from_utc", "to_utc", "tariffs")
    raw = _vision.spec(plan, "ace.perception-costing-plan.v1", names)
    if _sha(raw) != _digest(expected):
        raise ValueError("Rencana biaya berbeda dari anchor.")
    beginning, ending = _utc(raw["from_utc"]), _utc(raw["to_utc"])
    if beginning >= ending:
        raise ValueError("Jendela biaya terbalik atau kosong.")
    tariffs = {}
    for row in _rows(raw["tariffs"], 256, {"class", "organ", "ref", "internal_cost_per_unit"}):
        key = (_token(row["class"], "Kelas"), _token(row["organ"], "Organ"))
        if key in tariffs:
            raise ValueError("Tarif kelas dan organ ganda.")
        tariffs[key] = _token(row["ref"], "Rujukan tarif"), _metrics(row["internal_cost_per_unit"], False)
    observed = _vision.spec(receipts, "ace.perception-cost-receipts.v1", ("receipts",))
    keys = set()
    by_class = defaultdict(list)
    for row in _rows(observed["receipts"], MAX_RECEIPTS, {"class", "organ", "ref", "at", "usage"}):
        kind, organ, ref = (_token(row[key], key) for key in ("class", "organ", "ref"))
        if ref in keys:
            raise ValueError("Rujukan receipt biaya ganda.")
        keys.add(ref)
        at = _utc(row["at"])
        usage = _metrics(row["usage"], True)
        tariff = tariffs.get((kind, organ))
        missing = [key for key, value in usage.items() if value is None]
        if not beginning <= at < ending:
            status = "outside_window"
        elif tariff is None:
            status = "unpriced"
        elif missing:
            status = "missing_usage"
        else:
            status = "estimated"
        cost = sum(usage[key]*tariff[1][key] for key in METRICS) if status == "estimated" else None
        by_class[kind].append({"at": at.isoformat(), "organ": organ, "receipt_ref": ref, "status": status,
                               "tariff_ref": tariff[0] if tariff else None, "usage": usage, "missing_usage": missing,
                               "estimated_internal_units": cost})
    classes = []
    for kind, items in sorted(by_class.items()):
        rows = sorted(items, key=lambda item: (item["at"], item["receipt_ref"]))
        within = [row for row in rows if row["status"] != "outside_window"]
        measured = [row["estimated_internal_units"] for row in within if row["estimated_internal_units"] is not None]
        expected_rows = len(within)
        classes.append({"class": kind, "within_window": expected_rows, "estimated_receipts": len(measured),
                        "observed_estimated_units": sum(measured) if measured else None,
                        "complete_estimated_units": sum(measured) if expected_rows and expected_rows == len(measured) else None,
                        "rows": rows})
    return {"schema": "ace.perception-costing.v1", "plan_ref": _token(raw["plan_ref"], "Rujukan biaya"),
            "plan_sha256": expected, "receipts_sha256": sha256(receipts).hexdigest(),
            "from_utc": beginning.isoformat(), "to_utc": ending.isoformat(), "classes": classes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("receipts", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = report(_raster.read(args.plan, _vision.MAX_SPEC_BYTES),
                        _raster.read(args.receipts, _vision.MAX_SPEC_BYTES), args.expect_sha256)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
