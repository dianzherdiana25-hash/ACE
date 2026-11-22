"""Audit putaran bench persepsi berkala dari bukti lokal yang tersedia.

Setiap jendela memiliki satu observasi dan protokol held-out yang
sama. Ambang dokumen dan tabel berasal dari rencana tertambat.
WER tetap wajib tersedia. Jendela kosong serta regresi terhadap
putaran sebelumnya tampak tanpa menjadwalkan proses eksternal.
"""
import argparse
from datetime import timedelta
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys

from . import _perception_io, _raster, _vision, perception_bench
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest, _utc


MAX_WINDOWS = 60
MAX_RECEIPT_TOTAL = 12_000_000


def _settings(data, expected):
    names = ("series_ref", "first_window_at", "as_of", "period_days", "windows", "protocol_sha256",
             "document_min_bp", "table_min_bp", "rounds")
    raw = _vision.spec(data, "ace.perception-eval-series.v1", names)
    if _sha(raw) != _digest(expected):
        raise ValueError("Rencana berkala berbeda dari anchor.")
    pointer = _token(raw["series_ref"], "Rujukan seri")
    now, first = _utc(raw["as_of"]), _utc(raw["first_window_at"])
    days = _integer(raw["period_days"], 1, 365, "Periode")
    count = _integer(raw["windows"], 1, MAX_WINDOWS, "Jumlah jendela")
    limits = {kind: _integer(raw[f"{kind}_min_bp"], 1, 10_000, f"Ambang {kind}")
              for kind in ("document", "table")}
    rounds = raw["rounds"]
    if not isinstance(rounds, list) or len(rounds) > count:
        raise ValueError("Jumlah putaran di luar rencana.")
    period = timedelta(days=days)
    start = [first+period*i for i in range(count+1)]
    entries = {}
    refs, paths = {pointer}, set()
    bytes_total = 0
    for row in rounds:
        if not isinstance(row, dict) or set(row) != {"at", "source_ref", "path", "sha256", "bytes"}:
            raise ValueError("Bentuk putaran bench tidak sah.")
        source = _token(row["source_ref"], "Rujukan putaran")
        stamp = _utc(row["at"])
        index = (stamp-first)//period
        _perception_io.relative_parts(row["path"])
        if source in refs or row["path"] in paths or not 0 <= index < count or stamp > now or index in entries:
            raise ValueError("Putaran ganda, lewat jadwal, atau dari masa depan.")
        refs.add(source)
        paths.add(row["path"])
        size = _integer(row["bytes"], 1, _vision.MAX_SPEC_BYTES, "Ukuran bukti")
        bytes_total += size
        entries[index] = (stamp, source, row["path"], _digest(row["sha256"]), size)
    if bytes_total > MAX_RECEIPT_TOTAL:
        raise ValueError("Jumlah byte bukti putaran melebihi batas.")
    return pointer, now, start, _digest(raw["protocol_sha256"]), limits, entries


def _rates(product):
    return {item["kind"]: Fraction(**item["full_rate"]) if item["full_rate"] is not None else None
            for item in product["metrics"]}


def _quantify(values):
    return {key: None if value is None else {"numerator": value.numerator, "denominator": value.denominator}
            for key, value in values.items()}


def evaluate(root, protocol, plan, expected):
    pointer, now, start, anchor, limits, entries = _settings(plan, expected)
    perception_bench._plan(protocol, anchor)
    previous = {}
    windows = []
    for index, (begins, closes) in enumerate(zip(start, start[1:])):
        row = {"index": index+1, "starts_at": begins.isoformat(), "closes_at": closes.isoformat(),
               "status": "overdue" if now >= closes else "pending", "receipt_ref": None, "receipts_sha256": None,
               "rates": None, "delta_since_previous": None, "below_threshold": []}
        if index in entries:
            at, source, path, checksum, size = entries[index]
            try:
                observations = _perception_io.read_relative(root, path, size, checksum)
                if len(observations) != size:
                    raise ValueError("Ukuran bukti putaran berbeda.")
                product = perception_bench.report(protocol, observations, anchor)
            except (OSError, OverflowError, RecursionError, ValueError):
                row.update(status="invalid_receipt", at=at.isoformat(), receipt_ref=source, expected_receipts_sha256=checksum)
                previous = {}
                windows.append(row)
                continue
            rates = _rates(product)
            below = [key for key, limit in sorted(limits.items()) if rates[key] is not None and rates[key]*10_000 < limit]
            delta = {key: rate-previous[key] if rate is not None and previous.get(key) is not None else None
                     for key, rate in rates.items()}
            complete = all(value is not None for value in rates.values())
            status = "incomplete" if not complete else "below_threshold" if below else "thresholds_met"
            row.update(status=status, at=at.isoformat(), receipt_ref=source, receipts_sha256=checksum,
                       rates=_quantify(rates), delta_since_previous=_quantify(delta), below_threshold=below,
                       measurements=product["metrics"])
        else:
            rates = {}
        previous = rates
        windows.append(row)
    return {"schema": "ace.perception-eval-report.v1", "series_ref": pointer, "series_sha256": expected,
            "protocol_sha256": anchor, "thresholds_bp": limits, "as_of": now.isoformat(), "windows": windows,
            "plan_bytes_sha256": sha256(plan).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        summary = evaluate(args.root, _raster.read(args.protocol, _vision.MAX_SPEC_BYTES),
                           _raster.read(args.plan, _vision.MAX_SPEC_BYTES), args.expect_sha256)
        sys.stdout.buffer.write(_canonical(summary)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(row["status"] in ("incomplete", "below_threshold", "overdue", "invalid_receipt") for row in summary["windows"]))


if __name__ == "__main__":
    raise SystemExit(main())
