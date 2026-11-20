"""Buat ramalan biner yang menjelaskan prior dan perubahan odds per sumber.

Pemanggil menyediakan prior, aturan resolusi, dan likelihood ratio dengan
rentang. Kalkulasi memakai asumsi independensi bersyarat yang dicatat.
Rujukan sekeluarga atau dari masa depan ditolak. Interval skenario bukan
interval confidence statistik dan tidak menjadi dasar aktivasi.
"""
from fractions import Fraction
import json
from pathlib import Path
import re

from .brier_scorer import _probability, _rational, _stamp, _text


MAX_EVIDENCE = 128
MAX_INPUT_BYTES = 2_000_000
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,6})(?:\.[0-9]{1,12})?")
_MIN_LIKELIHOOD = Fraction(1, 10**6)
_MAX_LIKELIHOOD = Fraction(10**6)
_SCALE = 10**18


class ForecastError(ValueError):
    """Masukan tidak mendefinisikan ramalan biner yang bisa diaudit."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise ForecastError("Field ramalan tidak sesuai skema.")


def _likelihood(value):
    if type(value) not in (str, int) or (type(value) is int and not 1 <= value <= 10**6):
        raise ForecastError("Likelihood ratio perlu desimal eksplisit.")
    if not _DECIMAL.fullmatch(str(value)):
        raise ForecastError("Likelihood ratio perlu literal desimal berbatas.")
    result = Fraction(value)
    if not _MIN_LIKELIHOOD <= result <= _MAX_LIKELIHOOD:
        raise ForecastError("Likelihood ratio di luar batas.")
    return result


def _from_odds(odds):
    return odds / (1 + odds)


def _display(value):
    """Simpan representasi Brier sampai 18 digit dengan half-even eksak."""
    quotient, remainder = divmod(value.numerator * _SCALE, value.denominator)
    halfway = 2 * remainder == value.denominator
    if 2 * remainder > value.denominator or halfway and quotient % 2:
        quotient += 1
    integer, decimals = divmod(quotient, _SCALE)
    if not decimals:
        return str(integer)
    return f"{integer}.{decimals:018d}".rstrip("0")


def _stable_range(low, actual, high):
    if not low <= actual <= high:
        raise ForecastError("Likelihood utama harus berada dalam rentang skenario.")


def make_forecast(raw):
    """Hitung probabilitas dan jejak posterior dari masukan bertanggal."""
    _shape(raw, ("question_id", "question", "forecast_at", "resolve_by", "resolution_rule_ref",
                 "forecast_ref", "assumption_ref", "prior", "evidence"))
    at, deadline = _stamp(raw["forecast_at"]), _stamp(raw["resolve_by"])
    if at >= deadline:
        raise ForecastError("Ramalan wajib dibuat sebelum tenggat resolusi.")
    question_id = _text(raw["question_id"], "ID pertanyaan")
    question = _text(raw["question"], "pertanyaan")
    forecast_ref = _text(raw["forecast_ref"], "rujukan ramalan")
    resolution_rule_ref = _text(raw["resolution_rule_ref"], "aturan resolusi")
    assumption_ref = _text(raw["assumption_ref"], "asumsi independensi")

    prior = raw["prior"]
    _shape(prior, ("probability", "source_ref", "known_at"))
    probability = _probability(prior["probability"])
    prior_ref = _text(prior["source_ref"], "sumber prior")
    prior_known = _stamp(prior["known_at"])
    if not 0 < probability < 1 or prior_known > at:
        raise ForecastError("Prior wajib di dalam (0, 1) dan sudah tersedia.")
    prior_odds = probability / (1 - probability)
    sample = raw["evidence"]
    if not isinstance(sample, list) or len(sample) > MAX_EVIDENCE:
        raise ForecastError("Jumlah bukti ramalan melebihi batas.")

    indexed = {}
    seen_refs = {prior_ref, forecast_ref, resolution_rule_ref, assumption_ref}
    if len(seen_refs) != 4:
        raise ForecastError("Prior, ramalan, aturan resolusi, dan asumsi harus terpisah.")
    families = set()
    for row in sample:
        _shape(row, ("id", "source_ref", "family", "known_at", "lower", "likelihood", "upper"))
        name = _text(row["id"], "ID bukti")
        ref = _text(row["source_ref"], "sumber bukti")
        family = _text(row["family"], "keluarga sumber")
        known = _stamp(row["known_at"])
        if name in indexed or family in families or ref in seen_refs:
            raise ForecastError("Bukti, rujukan, atau keluarga sumber dihitung dua kali.")
        if known > at:
            raise ForecastError("Bukti dari sesudah ramalan.")
        low, actual, high = (_likelihood(row[key]) for key in ("lower", "likelihood", "upper"))
        _stable_range(low, actual, high)
        indexed[name] = (ref, family, known, low, actual, high)
        seen_refs.add(ref)
        families.add(family)

    aggregate = lower = upper = prior_odds
    trace = []
    for name, (ref, family, known, lo, actual, hi) in sorted(indexed.items()):
        aggregate *= actual
        lower *= lo
        upper *= hi
        trace.append({"id": name, "source_ref": ref, "family": family,
                      "known_at": known.isoformat(), "likelihood": _rational(actual),
                      "lower_likelihood": _rational(lo), "upper_likelihood": _rational(hi),
                      "posterior_after": _rational(_from_odds(aggregate))})
    posterior = _from_odds(aggregate)
    counterfactuals = []
    for name, (ref, family, _, _, likelihood, _) in sorted(indexed.items()):
        without = _from_odds(aggregate / likelihood)
        counterfactuals.append({
            "id": name, "source_ref": ref, "family": family,
            "posterior_without": _rational(without),
            "change_without": _rational(without - posterior),
        })
    if counterfactuals:
        largest_shift = min(
            counterfactuals,
            key=lambda row: (-abs(Fraction(**row["change_without"])), row["id"]),
        )["id"]
    else:
        largest_shift = None
    return {
        "schema": "ace.forecaster.v1", "question": question, "resolve_by": deadline.isoformat(),
        "resolution_rule_ref": resolution_rule_ref, "assumption_ref": assumption_ref,
        "prior": {"probability": _rational(probability), "source_ref": prior_ref,
                  "known_at": prior_known.isoformat()},
        "probability_exact": _rational(posterior),
        "scenario_range": {"lower": _rational(_from_odds(lower)), "upper": _rational(_from_odds(upper))},
        "evidence_trace": trace, "counterfactuals": counterfactuals,
        "largest_single_source_shift": largest_shift,
        "forecast": {"question_id": question_id, "forecast_at": at.isoformat(),
                     "forecast_ref": forecast_ref, "probability": _display(posterior)},
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise ForecastError("Masukan ramalan melampaui ukuran.")
        print(json.dumps(make_forecast(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
