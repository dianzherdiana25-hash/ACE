"""Terapkan rubrik yang sama ke argumen dengan penilaian bersumber.

Tiap kriteria memakai median dari penilai yang berbeda. Konflik skor
dan kriteria tanpa kuorum membuka review. Kriteria kritis mengikat
hasil walaupun rerata tertimbang tinggi. Poin datang dari penilai;
program memeriksa struktur dan menghitung hasilnya.
"""
from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
from statistics import median_low, median_high

from .brier_scorer import _rational


MAX_CRITERIA = 50
MAX_ARGUMENTS = 300
MAX_EVALUATIONS = 20_000
MAX_BYTES = 8_000_000


class RubricError(ValueError):
    """Rubrik atau catatan penilaian tidak dapat diterapkan."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise RubricError("Field rubrik tidak sesuai skema.")


def _text(value, label, maximum=128):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise RubricError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise RubricError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _int(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise RubricError(f"Nilai harus integer {lo}–{hi}.")
    return value


def _rows(value, minimum, maximum):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise RubricError("Jumlah record rubrik melewati batas.")
    return value


def _index_rubric(raw, refs):
    index = {}
    for row in _rows(raw, 1, MAX_CRITERIA):
        _shape(row, ("id", "source_ref", "max_points", "weight", "critical_min"))
        identifier = _text(row["id"], "kriteria")
        ref = _text(row["source_ref"], "rujukan rubrik", 512)
        if identifier in index or ref in refs:
            raise RubricError("Kriteria atau sumber rubrik ganda.")
        ceiling = _int(row["max_points"], 1, 100)
        floor = None if row["critical_min"] is None else _int(row["critical_min"], 1, ceiling)
        index[identifier] = (ceiling, _int(row["weight"], 1, 1000), floor, ref)
        refs.add(ref)
    return index


def _score(identifier, rubric, entries, minimum, maximum_spread):
    grades = []
    total_weight = sum(row[1] for row in rubric.values())
    weighted = minimum_weighted = maximum_weighted = Fraction(0)
    gates = []
    for name, (maximum, weight, floor, source) in sorted(rubric.items()):
        votes = sorted(entries[identifier, name], key=lambda row: row["reviewer"])
        points = [row["points"] for row in votes]
        value, spread = None, None
        observed_range = None
        reasons = []
        if len(points) < minimum:
            reasons.append("too_few_reviewers")
        else:
            value = Fraction(median_low(points) + median_high(points), 2)
            low, high = min(points), max(points)
            spread = Fraction(high - low, maximum)
            weighted += value * weight / maximum
            minimum_weighted += Fraction(low * weight, maximum)
            maximum_weighted += Fraction(high * weight, maximum)
            observed_range = {"minimum": low, "maximum": high}
            if spread > maximum_spread:
                reasons.append("reviewer_disagreement")
            if floor is not None and value < floor:
                reasons.append("critical_floor_missed")
        gates.extend(reason for reason in reasons)
        grades.append({"criterion": name, "criterion_ref": source, "weight": weight, "max_points": maximum,
                       "median": _rational(value) if value is not None else None,
                       "spread": _rational(spread) if spread is not None else None,
                       "observed_range": observed_range, "critical_floor": floor, "reasons": reasons, "reviews": votes})
    unavailable = "too_few_reviewers" in gates
    status = ("review_required" if unavailable or "reviewer_disagreement" in gates
              else "critical_floor_missed" if "critical_floor_missed" in gates else "scored")
    bounds = None if unavailable else {
        "minimum": _rational(minimum_weighted / total_weight),
        "maximum": _rational(maximum_weighted / total_weight),
    }
    return {"id": identifier, "status": status, "weighted_score": None if unavailable else _rational(
        weighted / total_weight), "weighted_range": bounds, "grades": grades}


def score(raw):
    _shape(raw, ("rubric", "arguments", "reviews", "minimum_reviewers", "max_spread_percent"))
    minimum = _int(raw["minimum_reviewers"], 1, 40)
    maximum_spread = Fraction(_int(raw["max_spread_percent"], 0, 100), 100)
    refs = set()
    rubric = _index_rubric(raw["rubric"], refs)
    arguments = {}
    for row in _rows(raw["arguments"], 1, MAX_ARGUMENTS):
        _shape(row, ("id", "source_ref"))
        identifier, ref = _text(row["id"], "argumen"), _text(row["source_ref"], "sumber argumen", 512)
        if identifier in arguments or ref in refs:
            raise RubricError("Argumen atau rujukan telah digunakan.")
        arguments[identifier] = ref
        refs.add(ref)
    entries = defaultdict(list)
    seen = set()
    for row in _rows(raw["reviews"], 0, MAX_EVALUATIONS):
        _shape(row, ("argument", "criterion", "reviewer", "points", "source_ref"))
        argument = _text(row["argument"], "ID argumen")
        criterion = _text(row["criterion"], "ID kriteria")
        reviewer = _text(row["reviewer"], "penilai")
        ref = _text(row["source_ref"], "sumber penilaian", 512)
        key = (argument, criterion, reviewer)
        if argument not in arguments or criterion not in rubric or key in seen or ref in refs:
            raise RubricError("Penilaian ganda atau merujuk entri asing.")
        points = _int(row["points"], 0, rubric[criterion][0])
        entries[argument, criterion].append({"reviewer": reviewer, "points": points, "source_ref": ref})
        seen.add(key)
        refs.add(ref)

    return {"schema": "ace.argument-scorer.v1", "minimum_reviewers": minimum,
            "max_spread": _rational(maximum_spread),
            "arguments": [{**_score(key, rubric, entries, minimum, maximum_spread),
                           "source_ref": ref} for key, ref in sorted(arguments.items())]}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise RubricError("Masukan rubrik melampaui batas.")
        print(json.dumps(score(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
