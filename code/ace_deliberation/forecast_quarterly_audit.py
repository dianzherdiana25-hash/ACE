"""Audit satu kohort ramalan triwulanan UTC pada waktu telaah tertentu.

Kohort berisi ramalan yang diterbitkan dalam triwulan. Resolusi sesudah
waktu telaah tetap pending. Laju dasar dibekukan sebelum triwulan
dimulai dan pertanyaan dalam kohort tidak ikut melatihnya. Loss model dan
baseline memakai pasangan resolusi yang sama.
"""
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction

from ._advanced import InputError, integer, json_main, rows, shape, stamp, text, unique
from .brier_scorer import Forecast, Resolution, _rational


MAX_ROWS = 10_000


def _bounds(year, quarter):
    month = 3 * quarter - 2
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    stop = datetime(year + (quarter == 4), 1 if quarter == 4 else month + 3, 1, tzinfo=timezone.utc)
    return start, stop


def _group(raw, reader, references, quantity):
    indexed = {}
    for row in rows(raw, 0, MAX_ROWS):
        data = reader(row)
        if data.question_id in indexed:
            raise InputError(f"ID ganda di {quantity}.")
        ref = data.source_ref
        unique(ref, references)
        indexed[data.question_id] = data
    return indexed


def audit(raw):
    shape(raw, ("year", "quarter", "audit_as_of", "protocol_ref", "forecasts", "resolutions", "baseline"))
    year = integer(raw["year"], 1, 9998)
    quarter = integer(raw["quarter"], 1, 4)
    start, end = _bounds(year, quarter)
    as_of = stamp(raw["audit_as_of"])
    if as_of < start:
        raise InputError("Waktu telaah mendahului awal triwulan.")
    protocol_ref = text(raw["protocol_ref"], "protokol")
    refs = {protocol_ref}
    forecasts = _group(raw["forecasts"], Forecast.from_dict, refs, "ramalan")
    resolutions = _group(raw["resolutions"], Resolution.from_dict, refs, "resolusi")
    # Baseline memiliki daftar tersendiri. Rujukan resolusi identik boleh
    # muncul di dua daftar jika menunjuk fakta yang persis sama.
    prior = _group(raw["baseline"], Resolution.from_dict, {protocol_ref}, "baseline")
    by_ref = {row.source_ref: row for row in resolutions.values()}
    for item in prior.values():
        if item.source_ref in refs and by_ref.get(item.source_ref) != item:
            raise InputError("Rujukan baseline bertabrakan dengan catatan lain.")
    cohort = {key: item for key, item in forecasts.items() if start <= item.at < end}
    training, baseline_excluded = [], []
    for key, item in sorted(prior.items()):
        row = {"question_id": key, "resolution_ref": item.source_ref}
        if key in cohort:
            baseline_excluded.append({**row, "reason": "cohort_question"})
        elif item.at >= start:
            baseline_excluded.append({**row, "reason": "not_before_quarter"})
        elif key in resolutions and resolutions[key] != item:
            raise InputError("Riwayat baseline bertentangan dengan resolusi pertanyaan yang sama.")
        else:
            training.append({**row, "resolved_at": item.at.isoformat(), "outcome": item.value})
    base_rate = Fraction(sum(row["outcome"] for row in training), len(training)) if training else None

    records = []
    model_losses, base_losses = [], []
    for key, forecast in sorted(cohort.items()):
        outcome = resolutions.get(key)
        row = {"question_id": key, "forecast_ref": forecast.source_ref,
               "forecast_at": forecast.at.isoformat(), "probability": _rational(forecast.probability)}
        if forecast.at > as_of:
            row.update(status="unissued_at_audit")
        elif outcome is None or outcome.at > as_of:
            row.update(status="pending")
        elif outcome.at <= forecast.at:
            row.update(status="late_forecast", resolution_ref=outcome.source_ref,
                       resolved_at=outcome.at.isoformat())
        else:
            loss = (forecast.probability - outcome.value)**2
            model_losses.append(loss)
            baseline_loss = None
            if base_rate is not None:
                baseline_loss = (base_rate - outcome.value)**2
                base_losses.append(baseline_loss)
            row.update(status="scored", outcome=outcome.value, resolution_ref=outcome.source_ref,
                       resolved_at=outcome.at.isoformat(), brier=_rational(loss),
                       baseline_brier=_rational(baseline_loss) if baseline_loss is not None else None)
        records.append(row)
    counts = Counter(item["status"] for item in records)
    scores = {}
    for name, values in (("brier", model_losses), ("baseline_brier", base_losses)):
        scores[name] = _rational(sum(values) / len(values)) if values else None
    if model_losses and base_losses:
        scores["improvement"] = _rational((sum(base_losses) - sum(model_losses)) / len(model_losses))
    else:
        scores["improvement"] = None
    return {
        "schema": "ace.forecast-quarterly-audit.v1", "period": f"{year:04}-Q{quarter}", "protocol_ref": protocol_ref,
        "start": start.isoformat(), "end_exclusive": end.isoformat(), "audit_as_of": as_of.isoformat(),
        "closed_period": as_of >= end, "counts": {key: counts[key] for key in
            ("scored", "pending", "late_forecast", "unissued_at_audit")},
        "outside_cohort": sorted(set(forecasts) - set(cohort)), "cohort": records,
        "baseline": {"rate": _rational(base_rate) if base_rate is not None else None,
                     "training": training, "excluded": baseline_excluded},
        "scores": scores,
    }


def main(argv=None):
    return json_main(argv, __doc__, audit)


if __name__ == "__main__":
    raise SystemExit(main())
