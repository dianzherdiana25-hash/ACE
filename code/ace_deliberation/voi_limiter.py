"""Hentikan putaran tambahan bila nilai informasi bersih tak melewati batas.

Model memakai distribusi keadaan, utilitas pilihan, dan likelihood hasil
uji yang dinyatakan. Nilai informasi dihitung dengan mengoptimalkan pilihan
pada setiap posterior. Biaya dan utilitas memakai satuan internal yang sama.
Laporan merencanakan satu langkah dan tidak menjalankan uji atau putusan.
"""
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _rational
from .scenario_generator import ScenarioError, _probability


MAX_OPTIONS = 40
MAX_STATES = 40
MAX_EXPERIMENTS = 50
MAX_OUTCOMES = 20
MAX_BYTES = 6_000_000


class InformationError(ValueError):
    """Distribusi atau utilitas tidak bisa dipakai dalam perbandingan."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise InformationError("Field nilai informasi tidak sesuai skema.")


def _text(value, label, limit=112):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise InformationError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise InformationError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _prob(raw):
    try:
        return _probability(raw)
    except ScenarioError as exc:
        raise InformationError("Peluang harus pecahan antara 0 dan 1.") from exc


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise InformationError(f"Nilai internal wajib integer {low}–{high}.")
    return value


def _best(prior, actions):
    scored = {key: sum(prior[state] * values[state] for state in prior) for key, values in actions.items()}
    highest = max(scored.values())
    return highest, sorted(key for key, value in scored.items() if value == highest)


def _experiment(row, prior, actions, prior_value, budget, threshold):
    _shape(row, ("id", "source_ref", "cost", "outcomes"))
    identifier = _text(row["id"], "uji")
    source_ref = _text(row["source_ref"], "sumber uji", 512)
    cost = _integer(row["cost"], 0, 10**6)
    outcomes = row["outcomes"]
    if not isinstance(outcomes, dict) or not 2 <= len(outcomes) <= MAX_OUTCOMES:
        raise InformationError("Uji memerlukan 2–20 hasil.")
    normalized = {}
    for outcome, likelihoods in outcomes.items():
        label = _text(outcome, "hasil")
        _shape(likelihoods, prior)
        normalized[label] = {state: _prob(value) for state, value in likelihoods.items()}
    if len(normalized) != len(outcomes):
        raise InformationError("Hasil uji ganda.")
    for state in prior:
        if sum(values[state] for values in normalized.values()) != 1:
            raise InformationError("Peluang hasil uji pada tiap keadaan harus berjumlah 1.")

    expected = Fraction(0)
    posterior_rows = []
    for name, likelihoods in sorted(normalized.items()):
        joint = {state: prior[state] * likelihoods[state] for state in prior}
        mass = sum(joint.values())
        outcome = {"id": name, "probability": _rational(mass), "posterior": None, "best_actions": []}
        if mass:
            posterior = {state: weight / mass for state, weight in joint.items()}
            best, actions_for_outcome = _best(posterior, actions)
            expected += mass * best
            outcome.update(posterior={state: _rational(weight) for state, weight in sorted(posterior.items())},
                           best_actions=actions_for_outcome, conditional_utility=_rational(best))
        posterior_rows.append(outcome)
    gain = expected - prior_value
    net = gain - cost
    result = {
        "id": identifier, "source_ref": source_ref, "cost": cost, "gross_voi": _rational(gain),
        "net_voi": _rational(net), "feasible": cost <= budget, "worth_continuing": cost <= budget and net > threshold,
        "outcomes": posterior_rows,
    }
    return result, net


def compare(raw):
    _shape(raw, ("prior", "utility", "experiments", "budget", "min_net_value"))
    budget = _integer(raw["budget"], 0, 10**6)
    cut = _integer(raw["min_net_value"], 0, 10**6)
    if not isinstance(raw["prior"], dict) or not 2 <= len(raw["prior"]) <= MAX_STATES:
        raise InformationError("Diperlukan 2–40 keadaan.")
    prior = {_text(state, "keadaan"): _prob(value) for state, value in raw["prior"].items()}
    if len(prior) != len(raw["prior"]) or sum(prior.values()) != 1:
        raise InformationError("Keadaan ganda atau prior tidak berjumlah 1.")
    if not isinstance(raw["utility"], dict) or not 2 <= len(raw["utility"]) <= MAX_OPTIONS:
        raise InformationError("Diperlukan 2–40 pilihan.")
    actions = {}
    for key, utilities in raw["utility"].items():
        identifier = _text(key, "pilihan")
        _shape(utilities, prior)
        if identifier in actions:
            raise InformationError("Pilihan ganda.")
        actions[identifier] = {state: _integer(value, -10**6, 10**6) for state, value in utilities.items()}

    first, best_without = _best(prior, actions)
    perfect = sum(prior[state] * max(action[state] for action in actions.values()) for state in prior)
    available = raw["experiments"]
    if not isinstance(available, list) or len(available) > MAX_EXPERIMENTS:
        raise InformationError("Jumlah uji melampaui batas.")
    tests = [_experiment(row, prior, actions, first, budget, cut) for row in available]
    names = {item["id"] for item, _ in tests}
    refs = {item["source_ref"] for item, _ in tests}
    if len(names) != len(tests) or len(refs) != len(tests):
        raise InformationError("ID atau sumber uji ganda.")
    tests.sort(key=lambda pair: (-pair[1], pair[0]["cost"], pair[0]["id"]))
    selected = next((item["id"] for item, _ in tests if item["worth_continuing"]), None)
    return {"schema": "ace.voi-limiter.v1", "status": "continue" if selected is not None else "stop",
            "recommended_experiment": selected, "best_without_additional_information": best_without,
            "starting_expected_utility": _rational(first), "perfect_information_bound": _rational(perfect - first),
            "budget": budget, "min_net_value": cut, "evaluated": [row for row, _ in tests]}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            payload = handle.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise InformationError("Masukan nilai informasi melebihi batas.")
        print(json.dumps(compare(json.loads(payload)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
