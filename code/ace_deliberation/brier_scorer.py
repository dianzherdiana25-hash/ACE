"""Hitung skor Brier dengan baseline laju dasar dari riwayat sebelum cut-off.

Pertanyaan held-out wajib terpisah, ramalan tercatat sebelum resolusi, dan
semua resolusi menunjuk bukti. Selisih di sini hanya berlaku pada berkas
masukan. Pecahan menyimpan nilai persis agar pembulatan tidak mengubah verdict.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path
import re


MAX_ROWS = 10_000
MAX_BYTES = 10_000_000
_PROBABILITY = re.compile(r"(?:0|1)(?:\.[0-9]{1,18})?")


class ScoringError(ValueError):
    """Skor tidak bisa dihitung dari data yang tidak lengkap atau bocor."""


def _record(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise ScoringError("Field skor tidak sesuai skema.")


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 512 or "\0" in value:
        raise ScoringError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ScoringError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _stamp(value):
    if not isinstance(value, str) or len(value) > 40 or "T" not in value:
        raise ScoringError("Cap waktu wajib berupa ISO 8601 berzona.")
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.utcoffset() is None:
            raise ValueError
        return stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ScoringError("Cap waktu wajib berupa ISO 8601 berzona.") from exc


def _outcome(value):
    if type(value) is not int or value not in (0, 1):
        raise ScoringError("Resolusi wajib integer 0 atau 1.")
    return value


def _probability(value):
    if type(value) is int and value in (0, 1):
        return Fraction(value)
    if not isinstance(value, str) or not _PROBABILITY.fullmatch(value):
        raise ScoringError("Probabilitas wajib desimal 0–1 dengan hingga 18 digit pecahan.")
    result = Fraction(value)
    if result > 1:
        raise ScoringError("Probabilitas di luar rentang [0, 1].")
    return result


def _rational(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


@dataclass(frozen=True, slots=True)
class Resolution:
    question_id: str
    value: int
    at: datetime
    source_ref: str

    @classmethod
    def from_dict(cls, raw):
        _record(raw, ("question_id", "outcome", "resolved_at", "resolution_ref"))
        return cls(_text(raw["question_id"], "ID pertanyaan"), _outcome(raw["outcome"]),
                   _stamp(raw["resolved_at"]), _text(raw["resolution_ref"], "rujukan resolusi"))


@dataclass(frozen=True, slots=True)
class Forecast:
    question_id: str
    probability: Fraction
    at: datetime
    source_ref: str

    @classmethod
    def from_dict(cls, raw):
        _record(raw, ("question_id", "probability", "forecast_at", "forecast_ref"))
        return cls(_text(raw["question_id"], "ID pertanyaan"), _probability(raw["probability"]),
                   _stamp(raw["forecast_at"]), _text(raw["forecast_ref"], "rujukan ramalan"))


def _index(rows, parse, label):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ScoringError(f"{label} memerlukan 1–{MAX_ROWS} entri.")
    indexed = {}
    for row in rows:
        item = parse(row)
        if item.question_id in indexed:
            raise ScoringError(f"ID ganda dalam {label}.")
        indexed[item.question_id] = item
    return indexed


def _pair(forecast, outcome, cutoff, as_of, base_rate):
    if not cutoff <= forecast.at < outcome.at <= as_of:
        raise ScoringError("Ramalan held-out harus berada sebelum resolusi dan di dalam periode.")
    if forecast.source_ref == outcome.source_ref:
        raise ScoringError("Ramalan dan resolusi harus memiliki catatan sumber yang berbeda.")
    score = (forecast.probability - outcome.value) ** 2
    baseline = (base_rate - outcome.value) ** 2
    return score, baseline, {
        "question_id": forecast.question_id,
        "probability": _rational(forecast.probability),
        "outcome": outcome.value,
        "brier": _rational(score), "baseline_brier": _rational(baseline),
        "forecast_at": forecast.at.isoformat(), "resolved_at": outcome.at.isoformat(),
        "forecast_ref": forecast.source_ref, "resolution_ref": outcome.source_ref,
    }


def score_brier(raw):
    """Ukur dua lengan pada himpunan pertanyaan dan resolusi yang sama."""
    _record(raw, ("cutoff", "as_of", "history", "forecasts", "resolutions"))
    cutoff, as_of = _stamp(raw["cutoff"]), _stamp(raw["as_of"])
    if cutoff >= as_of:
        raise ScoringError("Cut-off harus mendahului as_of.")
    history = _index(raw["history"], Resolution.from_dict, "riwayat")
    forecasts = _index(raw["forecasts"], Forecast.from_dict, "ramalan")
    resolutions = _index(raw["resolutions"], Resolution.from_dict, "resolusi")
    if history.keys() & (forecasts.keys() | resolutions.keys()):
        raise ScoringError("Riwayat baseline dan held-out memiliki ID yang bertumpang tindih.")
    if forecasts.keys() != resolutions.keys():
        raise ScoringError("Setiap pertanyaan held-out memerlukan satu ramalan dan satu resolusi.")
    if any(row.at >= cutoff for row in history.values()):
        raise ScoringError("Baseline hanya boleh memakai riwayat sebelum cut-off.")
    if ({row.source_ref for row in history.values()} &
            {row.source_ref for row in resolutions.values()}):
        raise ScoringError("Rujukan resolusi held-out sudah dipakai dalam riwayat.")
    base_rate = Fraction(sum(row.value for row in history.values()), len(history))
    audit_rows = []
    total_model, total_baseline = Fraction(0), Fraction(0)
    for key in sorted(forecasts):
        model, static, row = _pair(forecasts[key], resolutions[key], cutoff, as_of, base_rate)
        total_model += model
        total_baseline += static
        audit_rows.append(row)
    count = len(audit_rows)
    model = total_model / count
    baseline = total_baseline / count
    skill = (1 - model / baseline) if baseline else None
    return {
        "schema": "ace.brier-scorer.v1",
        "cutoff": cutoff.isoformat(), "as_of": as_of.isoformat(),
        "history_count": len(history), "question_count": count,
        "baseline_rate": _rational(base_rate), "brier": _rational(model),
        "baseline_brier": _rational(baseline), "improvement": _rational(baseline - model),
        "brier_skill": _rational(skill) if skill is not None else None,
        "verdict": "better" if model < baseline else "worse" if model > baseline else "tie",
        "baseline_history": [
            {"question_id": item.question_id, "outcome": item.value,
             "resolved_at": item.at.isoformat(), "resolution_ref": item.source_ref}
            for item in (history[key] for key in sorted(history))
        ],
        "questions": audit_rows,
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score_input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.score_input.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ScoringError("Masukan skor melebihi batas.")
        print(json.dumps(score_brier(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
