"""Gabungkan ramalan berbobot per kelompok lalu terapkan extremizing terukur.

Setiap keluarga menyumbang satu rata-rata. Penggandaan ramalan di satu
keluarga tidak memberinya kursi ekstra. Extremizing diterapkan di log-odds
relatif terhadap baseline eksplisit. Masukan setelah as_of ditolak dan
agregat ditahan jika jumlah keluarga belum memenuhi batas.
"""
from collections import defaultdict
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _probability, _rational, _stamp
from .devil_advocate import _number
from .forecaster import _display


MAX_INPUT_BYTES = 4_000_000
MAX_FORECASTS = 2_000
MAX_FAMILIES = 200


class AggregateError(ValueError):
    """Ramalan atau dasar agregasi tidak bisa dibandingkan."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise AggregateError("Objek agregasi tidak sesuai skema.")


def _text(value, label, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise AggregateError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise AggregateError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _extreme(p, baseline, strength):
    if strength == 1 or p in (0, 1):
        return p

    def decimal(q):
        return Decimal(q.numerator) / Decimal(q.denominator)

    def log_odds(q):
        return decimal(q / (1 - q)).ln()

    with localcontext(Context(prec=70, rounding=ROUND_HALF_EVEN)):
        midpoint = log_odds(baseline)
        adjusted = midpoint + decimal(strength) * (log_odds(p) - midpoint)
        value = 1 / (1 + (-adjusted).exp())
    return Fraction(value)


def aggregate(raw):
    _shape(raw, ("question_id", "as_of", "output_ref", "baseline", "extremity", "minimum_families", "forecasts"))
    question = _text(raw["question_id"], "ID pertanyaan")
    now = _stamp(raw["as_of"])
    output_ref = _text(raw["output_ref"], "sumber agregat", 512)
    baseline = raw["baseline"]
    _shape(baseline, ("probability", "source_ref", "known_at"))
    base_probability = _probability(baseline["probability"])
    base_known = _stamp(baseline["known_at"])
    base_ref = _text(baseline["source_ref"], "sumber baseline", 512)
    if not 0 < base_probability < 1 or base_known > now or base_ref == output_ref:
        raise AggregateError("Dasar agregasi harus tersedia, interior, dan berdiri sendiri.")
    strength = _number(raw["extremity"])
    if not 1 <= strength <= 4:
        raise AggregateError("Faktor extremizing wajib 1–4.")
    minimum = raw["minimum_families"]
    if type(minimum) is not int or not 1 <= minimum <= MAX_FAMILIES:
        raise AggregateError("minimum_families di luar batas.")
    input_rows = raw["forecasts"]
    if not isinstance(input_rows, list) or len(input_rows) > MAX_FORECASTS:
        raise AggregateError("Daftar ramalan melampaui batas.")
    groups = defaultdict(list)
    seen_ids = set()
    seen_refs = {base_ref, output_ref}
    for row in input_rows:
        _shape(row, ("id", "question_id", "probability", "forecast_at", "forecast_ref", "family", "weight"))
        identifier = _text(row["id"], "ID ramalan")
        ref = _text(row["forecast_ref"], "sumber ramalan", 512)
        family = _text(row["family"], "keluarga")
        at = _stamp(row["forecast_at"])
        weight = row["weight"]
        if row["question_id"] != question or identifier in seen_ids or ref in seen_refs or at > now:
            raise AggregateError("Ramalan ganda, asing, atau belum tersedia.")
        if type(weight) is not int or not 1 <= weight <= 10_000:
            raise AggregateError("Bobot ramalan harus integer 1–10000.")
        groups[family].append((identifier, _probability(row["probability"]), weight, at, ref))
        seen_ids.add(identifier)
        seen_refs.add(ref)
    if len(groups) > MAX_FAMILIES:
        raise AggregateError("Keluarga ramalan melampaui batas.")
    group_report = []
    probabilities = []
    for family, items in sorted(groups.items()):
        total_weight = sum(item[2] for item in items)
        probability = sum(item[1] * item[2] for item in items) / total_weight
        probabilities.append(probability)
        group_report.append({
            "family": family, "weighted_mean": _rational(probability), "total_weight": total_weight,
            "inputs": [{"id": identifier, "forecast_at": at.isoformat(), "source_ref": ref,
                        "probability": _rational(value), "weight": weight}
                       for identifier, value, weight, at, ref in sorted(items)],
        })
    common = {
        "schema": "ace.forecast-aggregator.v1", "question_id": question, "as_of": now.isoformat(),
        "minimum_families": minimum, "family_count": len(groups), "groups": group_report,
        "extremity": _rational(strength),
        "baseline": {"probability": _rational(base_probability), "source_ref": base_ref,
                     "known_at": base_known.isoformat()},
    }
    if len(groups) < minimum:
        return {**common, "status": "insufficient_families", "raw_mean": None, "forecast": None,
                "family_spread": None, "leave_one_family_out": []}
    total = sum(probabilities)
    average = total / len(probabilities)
    final_probability = _extreme(average, base_probability, strength)
    count_after = len(probabilities) - 1
    sensitivities = []
    for group, original in zip(group_report, probabilities):
        row = {"family_removed": group["family"]}
        if count_after < minimum:
            row.update(status="insufficient_families", probability=None, raw_change=None)
        else:
            alternate = (total - original) / count_after
            row.update(status="aggregated", probability=_display(_extreme(alternate, base_probability, strength)),
                       raw_change=_rational(alternate - average))
        sensitivities.append(row)
    return {
        **common, "status": "aggregated", "raw_mean": _rational(average),
        "family_spread": _rational(max(probabilities) - min(probabilities)),
        "leave_one_family_out": sensitivities,
        "forecast": {"question_id": question, "probability": _display(final_probability),
                     "forecast_at": now.isoformat(), "forecast_ref": output_ref},
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
            raise AggregateError("Masukan agregasi melampaui batas.")
        result = aggregate(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "aggregated")


if __name__ == "__main__":
    raise SystemExit(main())
