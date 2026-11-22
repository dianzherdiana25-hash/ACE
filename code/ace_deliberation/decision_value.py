"""Bandingkan nilai putusan jika peluang ramalan bisa berubah.

Payoff kedua outcome memakai satuan utilitas eksplisit yang sama. Biaya
tetap dikurangi satu kali. Nilai harapan linear dalam peluang, sehingga
seluruh rentang sensitivitas dapat diperiksa dari kedua ujungnya.
Keluaran mendokumentasikan titik impas dan regret terhadap tiap opsi.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from ._advanced import InputError, integer, json_main, probability, rows, shape, text, unique
from .brier_scorer import _rational


MAX_OPTIONS = 30
MAX_UNITS = 10**12


@dataclass(frozen=True, slots=True)
class Action:
    name: str
    yes: int
    no: int
    fixed_cost: int
    source_ref: str

    @classmethod
    def read(cls, raw, identifiers):
        shape(raw, ("id", "utility_yes", "utility_no", "fixed_cost", "source_ref"))
        return cls(unique(text(raw["id"], "opsi"), identifiers, "Opsi"),
                   integer(raw["utility_yes"], -MAX_UNITS, MAX_UNITS),
                   integer(raw["utility_no"], -MAX_UNITS, MAX_UNITS),
                   integer(raw["fixed_cost"], 0, MAX_UNITS), text(raw["source_ref"], "sumber payoff"))

    @property
    def intercept(self):
        return self.no - self.fixed_cost

    @property
    def slope(self):
        return self.yes - self.no

    def expected(self, chance):
        return self.intercept + self.slope * chance


def _bounds(first, last):
    return {"minimum": _rational(min(first, last)), "maximum": _rational(max(first, last))}


def _relation(first, second, lower, upper):
    x0 = first.expected(lower) - second.expected(lower)
    x1 = first.expected(upper) - second.expected(upper)
    if x0 == x1 == 0:
        return "equal"
    if min(x0, x1) >= 0:
        return "dominates"
    if max(x0, x1) <= 0:
        return "dominated"
    return "switches"


def _crossing(first, second):
    slope = first.slope - second.slope
    if slope:
        return Fraction(second.intercept - first.intercept, slope)
    return None


def analyze(raw):
    shape(raw, ("decision_id", "forecast", "baseline", "utility_unit", "options"))
    key = text(raw["decision_id"], "ID putusan")
    unit = text(raw["utility_unit"], "satuan utilitas")
    source = raw["forecast"]
    shape(source, ("ref", "point", "lower", "upper"))
    reference = text(source["ref"], "sumber ramalan")
    lower, point, upper = (probability(source[loc]) for loc in ("lower", "point", "upper"))
    if not lower <= point <= upper:
        raise InputError("Titik ramalan harus berada di dalam interval.")

    identifiers = set()
    actions = sorted((Action.read(row, identifiers) for row in rows(raw["options"], 2, MAX_OPTIONS)),
                     key=lambda item: item.name)
    baseline = text(raw["baseline"], "opsi baseline")
    default = next((action for action in actions if action.name == baseline), None)
    if default is None:
        raise InputError("Baseline tidak ada dalam daftar opsi.")
    highest = max(item.expected(point) for item in actions)
    low_best = max(item.expected(lower) for item in actions)
    high_best = max(item.expected(upper) for item in actions)

    values = []
    for action in actions:
        low_value, value, high_value = (action.expected(prob) for prob in (lower, point, upper))
        values.append({
            "id": action.name, "source_ref": action.source_ref,
            "utility_yes": action.yes, "utility_no": action.no, "fixed_cost": action.fixed_cost,
            "expected_at_point": _rational(value), "expected_range": _bounds(low_value, high_value),
            "gain_at_point": _rational(value - default.expected(point)),
            "gain_range": _bounds(low_value - default.expected(lower), high_value - default.expected(upper)),
            "relation_to_baseline": _relation(action, default, lower, upper),
            "max_regret": _rational(max(low_best - low_value, high_best - high_value)),
            "optimal_throughout_interval": low_value == low_best and high_value == high_best,
        })
    crossings = []
    for first, second in combinations(actions, 2):
        at = _crossing(first, second)
        if at is not None and 0 <= at <= 1:
            crossings.append({"first": first.name, "second": second.name,
                              "break_even": _rational(at), "within_range": lower <= at <= upper})
    minimum_regret = min(Fraction(**row["max_regret"]) for row in values)
    return {
        "schema": "ace.decision-value.v1", "decision_id": key, "forecast_ref": reference,
        "probability": {"lower": _rational(lower), "point": _rational(point), "upper": _rational(upper)},
        "utility_unit": unit, "baseline": baseline, "options": values,
        "optimal_at_point": [action.name for action in actions if action.expected(point) == highest],
        "minimum_max_regret": [row["id"] for row in values if Fraction(**row["max_regret"]) == minimum_regret],
        "break_even": crossings,
    }


def main(argv=None):
    return json_main(argv, __doc__, analyze)


if __name__ == "__main__":
    raise SystemExit(main())
