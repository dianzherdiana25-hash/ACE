"""Uji putusan terhadap payoff skenario dengan jejak sumber audit.

Skenario stress dapat berpeluang nol dan tetap masuk uji worst-case.
Expected utility memakai probabilitas yang diberikan. Maximin dan
minimax-regret ditampilkan terpisah agar perubahan pilihan dapat dirunut
ke matriks payoff dan bukan pengukuran eksternal.
"""
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _rational
from .scenario_generator import ScenarioError, _probability


MAX_SCENARIOS = 250
MAX_OPTIONS = 50
MAX_BYTES = 6_000_000
MAX_UTILITY = 10**6


class StressError(ValueError):
    """Tabel skenario atau payoff tidak lengkap."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise StressError("Field uji stress tidak sesuai skema.")


def _text(value, label, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise StressError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise StressError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _unit(value):
    if type(value) is not int or not -MAX_UTILITY <= value <= MAX_UTILITY:
        raise StressError("Payoff harus integer berbatas.")
    return value


def _scenarios(rows, refs):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_SCENARIOS:
        raise StressError("Jumlah skenario di luar batas.")
    output = {}
    for raw in rows:
        _shape(raw, ("id", "source_ref", "probability", "stress"))
        identifier = _text(raw["id"], "ID skenario")
        ref = _text(raw["source_ref"], "rujukan skenario", 512)
        if identifier in output or ref in refs or type(raw["stress"]) is not bool:
            raise StressError("ID atau rujukan ganda, atau stress bukan boolean.")
        try:
            probability = _probability(raw["probability"])
        except ScenarioError as exc:
            raise StressError("Peluang skenario tidak sah.") from exc
        output[identifier] = (probability, raw["stress"], ref)
        refs.add(ref)
    if sum(probability for probability, _, _ in output.values()) != 1:
        raise StressError("Peluang skenario harus berjumlah 1.")
    return dict(sorted(output.items()))


def _options(rows, scenarios, refs):
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_OPTIONS:
        raise StressError("Diperlukan 2–50 pilihan.")
    output = {}
    for raw in rows:
        _shape(raw, ("id", "source_ref", "payoffs"))
        key, ref = _text(raw["id"], "ID pilihan"), _text(raw["source_ref"], "rujukan pilihan", 512)
        if key in output or ref in refs:
            raise StressError("Pilihan atau rujukan ganda.")
        refs.add(ref)
        _shape(raw["payoffs"], scenarios)
        payoffs = {}
        for scenario, payoff in raw["payoffs"].items():
            _shape(payoff, ("utility", "source_ref"))
            payoff_ref = _text(payoff["source_ref"], "rujukan payoff", 512)
            if payoff_ref in refs:
                raise StressError("Rujukan payoff telah dipakai.")
            refs.add(payoff_ref)
            payoffs[scenario] = (_unit(payoff["utility"]), payoff_ref)
        output[key] = (ref, payoffs)
    return dict(sorted(output.items()))


def _dominates(first, second, considered):
    return (all(first[key][0] >= second[key][0] for key in considered)
            and any(first[key][0] > second[key][0] for key in considered))


def stress_test(raw):
    _shape(raw, ("scenarios", "options", "candidate", "minimum_stress_utility"))
    cutoff = _unit(raw["minimum_stress_utility"])
    refs = set()
    scenarios = _scenarios(raw["scenarios"], refs)
    options = _options(raw["options"], scenarios, refs)
    candidate = _text(raw["candidate"], "kandidat")
    if candidate not in options:
        raise StressError("Putusan tidak merujuk pilihan yang dikenal.")
    considered = [key for key, (probability, stress, _) in scenarios.items() if stress or probability]
    best_by_scenario = {key: max(payoffs[key][0] for _, payoffs in options.values()) for key in considered}
    summaries = []
    for name, (ref, payoffs) in options.items():
        low = min(payoffs[key][0] for key in considered)
        expected = sum((probability * payoffs[key][0]
                        for key, (probability, _, _) in scenarios.items()), Fraction(0))
        regret = max(best_by_scenario[key] - payoffs[key][0] for key in considered)
        witnesses = [
            {"scenario": key, "scenario_ref": scenarios[key][2], "utility": payoffs[key][0],
             "payoff_ref": payoffs[key][1], "regret": best_by_scenario[key] - payoffs[key][0]}
            for key in considered
        ]
        summaries.append({
            "id": name, "source_ref": ref, "worst_utility": low, "expected_utility": _rational(expected),
            "max_regret": regret, "meets_floor": low >= cutoff,
            "worst_scenarios": [row for row in witnesses if row["utility"] == low],
            "max_regret_scenarios": [row for row in witnesses if row["regret"] == regret],
            "dominated_by": [other for other, (_, other_payoffs) in options.items()
                             if other != name and _dominates(other_payoffs, payoffs, considered)],
        })
    chosen = next(row for row in summaries if row["id"] == candidate)
    maximin = max(row["worst_utility"] for row in summaries)
    minimax_regret = min(row["max_regret"] for row in summaries)
    return {
        "schema": "ace.worst-case-test.v1", "candidate": candidate,
        "status": "meets_stress_floor" if chosen["meets_floor"] else "breaches_stress_floor",
        "minimum_stress_utility": cutoff, "considered": considered,
        "excluded_zero_probability_nonstress": sorted(set(scenarios) - set(considered)),
        "maximin_choices": [row["id"] for row in summaries if row["worst_utility"] == maximin],
        "minimax_regret_choices": [row["id"] for row in summaries if row["max_regret"] == minimax_regret],
        "options": summaries,
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            blob = handle.read(MAX_BYTES + 1)
        if len(blob) > MAX_BYTES:
            raise StressError("Berkas uji stress melampaui batas.")
        result = stress_test(json.loads(blob))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] == "breaches_stress_floor")


if __name__ == "__main__":
    raise SystemExit(main())
