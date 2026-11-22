"""Gabungkan prediksi manusia dan mesin dengan batas waktu yang sama.

Bobot campuran dipilih dari pasangan historis yang kedua prediksinya
tersedia sebelum resolusi, dan resolusinya tersedia sebelum ramalan baru.
Loss adalah Brier pada data pemilihan bobot. Laporan menyertakan
hasil leave-one-out sebagai diagnosis terpisah, dengan batas sampel.
"""
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction

from ._advanced import InputError, integer, json_main, probability, rows, shape, stamp, text, unique
from .brier_scorer import _outcome, _rational
from .forecaster import _display


MAX_HISTORY = 8_000


@dataclass(frozen=True, slots=True)
class Forecast:
    value: Fraction
    at: datetime
    ref: str

    @classmethod
    def read(cls, raw, refs):
        shape(raw, ("probability", "at", "ref"))
        return cls(probability(raw["probability"]), stamp(raw["at"]), unique(text(raw["ref"], "ramalan"), refs))

    def export(self):
        return {"probability": _rational(self.value), "at": self.at.isoformat(), "ref": self.ref}


@dataclass(frozen=True, slots=True)
class Pair:
    key: str
    person: Forecast
    machine: Forecast
    outcome: int
    at: datetime
    ref: str

    @classmethod
    def read(cls, raw, refs, identifiers):
        shape(raw, ("question_id", "human", "machine", "resolved_at", "outcome", "resolution_ref"))
        return cls(
            unique(text(raw["question_id"], "ID"), identifiers, "ID"),
            Forecast.read(raw["human"], refs), Forecast.read(raw["machine"], refs),
            _outcome(raw["outcome"]), stamp(raw["resolved_at"]),
            unique(text(raw["resolution_ref"], "resolusi"), refs),
        )

    def export(self):
        return {"question_id": self.key, "human": self.person.export(), "machine": self.machine.export(),
                "outcome": self.outcome, "resolved_at": self.at.isoformat(), "resolution_ref": self.ref}

    def coefficients(self):
        difference = self.person.value - self.machine.value
        return difference * (self.outcome - self.machine.value), difference**2


def _weight(numerator, denominator):
    return min(Fraction(1), max(Fraction(), numerator / denominator)) if denominator else Fraction(1, 2)


def _mix(person, machine, human_weight):
    return human_weight * person + (1 - human_weight) * machine


def _score(rows_scored, weights):
    human = machine = hybrid = Fraction()
    for pair, weight in zip(rows_scored, weights, strict=True):
        human += (pair.person.value - pair.outcome)**2
        machine += (pair.machine.value - pair.outcome)**2
        hybrid += (_mix(pair.person.value, pair.machine.value, weight) - pair.outcome)**2
    count = len(rows_scored)
    return {name: _rational(score / count)
            for name, score in (("human", human), ("machine", machine), ("hybrid", hybrid))}


def fit(raw):
    shape(raw, ("target", "history", "minimum_pairs", "protocol_ref"))
    target = raw["target"]
    shape(target, ("question_id", "forecast_at", "forecast_ref", "human", "machine"))
    key = text(target["question_id"], "ID target")
    cutoff = stamp(target["forecast_at"])
    output = text(target["forecast_ref"], "sumber keluaran")
    refs, identifiers = {output}, set()
    protocol = unique(text(raw["protocol_ref"], "protokol"), refs)
    current_human = Forecast.read(target["human"], refs)
    current_machine = Forecast.read(target["machine"], refs)
    if max(current_human.at, current_machine.at) > cutoff:
        raise InputError("Komponen ramalan target tersedia sesudah cutoff.")
    needed = integer(raw["minimum_pairs"], 1, MAX_HISTORY)

    training, excluded = [], []
    for line in rows(raw["history"], 0, MAX_HISTORY):
        pair = Pair.read(line, refs, identifiers)
        if pair.key == key:
            reason = "target_question"
        elif max(pair.person.at, pair.machine.at) >= pair.at:
            reason = "late_forecast"
        elif pair.at >= cutoff:
            reason = "unresolved_at_target_cutoff"
        else:
            training.append(pair)
            continue
        excluded.append({"question_id": pair.key, "reason": reason, "resolution_ref": pair.ref})
    training.sort(key=lambda row: row.key)
    result = {
        "schema": "ace.hybrid-forecast.v1", "question_id": key, "protocol_ref": protocol,
        "cutoff": cutoff.isoformat(), "minimum_pairs": needed, "pairs": [p.export() for p in training],
        "excluded": sorted(excluded, key=lambda item: item["question_id"]),
        "components": {"human": current_human.export(), "machine": current_machine.export()},
    }
    if len(training) < needed:
        return {**result, "status": "insufficient_pairs", "forecast": None, "fit": None}

    coefficients = [case.coefficients() for case in training]
    total_a = sum((a for a, _ in coefficients), Fraction())
    total_b = sum((b for _, b in coefficients), Fraction())
    weight = _weight(total_a, total_b)
    value = _mix(current_human.value, current_machine.value, weight)
    holdout = None
    if len(training) > needed:
        holdout = _score(training, [_weight(total_a - a, total_b - b) for a, b in coefficients])
    return {
        **result, "status": "forecasted",
        "fit": {
            "human_weight": _rational(weight), "machine_weight": _rational(1 - weight),
            "unidentified_weight": total_b == 0,
            "training_brier": _score(training, [weight] * len(training)),
            "leave_one_out_brier": holdout,
        },
        "forecast": {"question_id": key, "forecast_at": cutoff.isoformat(),
                     "forecast_ref": output, "probability": _display(value)},
    }


def main(argv=None):
    return json_main(argv, __doc__, fit)


if __name__ == "__main__":
    raise SystemExit(main())
