"""Tandai asosiasi antara kepentingan yang dideklarasikan dan ramalan.

Setiap pembanding memakai pertanyaan dan ronde yang sama. Perbedaan
yes/no dinormalisasi ke arah kepentingan yang tercatat. Satu
pertanyaan mendapat satu suara di agregat agar jumlah ramalan per
pertanyaan tidak memperberat hasil. Temuan adalah bahan telaah.
"""
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from ._advanced import InputError, integer, json_main, probability, rows, shape, text, unique
from .brier_scorer import _rational


MAX_RECORDS = 20_000
DIRECTIONS = ("yes", "no", "neutral", "unknown")


@dataclass(frozen=True, slots=True)
class Observation:
    question: str
    round: str
    forecaster: str
    direction: str
    chance: Fraction
    forecast_ref: str
    disclosure_ref: str | None

    @classmethod
    def read(cls, raw, refs):
        shape(raw, ("question_id", "round_id", "forecaster", "direction",
                    "probability", "forecast_ref", "disclosure_ref"))
        direction = text(raw["direction"], "arah kepentingan")
        if direction not in DIRECTIONS:
            raise InputError("Arah kepentingan harus yes, no, neutral, atau unknown.")
        disclosure = raw["disclosure_ref"]
        if (direction == "unknown") != (disclosure is None):
            raise InputError("Arah tercatat memerlukan rujukan, arah unknown memerlukan null.")
        return cls(text(raw["question_id"], "pertanyaan"), text(raw["round_id"], "ronde"),
                   text(raw["forecaster"], "peramal"), direction, probability(raw["probability"]),
                   unique(text(raw["forecast_ref"], "sumber ramalan"), refs),
                   text(disclosure, "sumber kepentingan") if disclosure is not None else None)

    def export(self):
        return {
            "forecaster": self.forecaster, "direction": self.direction,
            "probability": _rational(self.chance), "forecast_ref": self.forecast_ref,
            "disclosure_ref": self.disclosure_ref,
        }


def _mean(values):
    return sum(values, Fraction()) / len(values)


def analyze(raw):
    shape(raw, ("protocol_ref", "records", "min_per_direction", "min_questions", "threshold"))
    protocol = text(raw["protocol_ref"], "protokol")
    minimum = integer(raw["min_per_direction"], 1, 100)
    min_questions = integer(raw["min_questions"], 1, MAX_RECORDS)
    threshold = probability(raw["threshold"])
    if threshold == 0:
        raise InputError("Ambang perlu positif agar selisih nol tidak ditandai.")
    grouped = defaultdict(lambda: defaultdict(list))
    refs, identities = {protocol}, set()
    for row in rows(raw["records"], 0, MAX_RECORDS):
        record = Observation.read(row, refs)
        unique((record.question, record.round, record.forecaster), identities, "Forecaster per pertanyaan dan ronde")
        if record.disclosure_ref == record.forecast_ref:
            raise InputError("Ramalan dan deklarasi kepentingan harus memiliki rujukan terpisah.")
        grouped[record.question, record.round][record.direction].append(record)

    comparison = []
    normalized = defaultdict(lambda: defaultdict(list))
    for (question, round_id), groups in sorted(grouped.items()):
        for direction in DIRECTIONS[:2]:
            exposed = sorted(groups[direction], key=lambda item: item.forecaster)
            neutral = sorted(groups["neutral"], key=lambda item: item.forecaster)
            if not exposed:
                continue
            comparable = len(exposed) >= minimum and len(neutral) >= minimum
            diff = exposed_mean = neutral_mean = None
            if comparable:
                exposed_mean = _mean([r.chance for r in exposed])
                neutral_mean = _mean([r.chance for r in neutral])
                raw_diff = exposed_mean - neutral_mean
                diff = raw_diff if direction == "yes" else -raw_diff
                normalized[direction][question].append(diff)
            comparison.append({
                "question_id": question, "round_id": round_id, "direction": direction,
                "status": ("review" if diff >= threshold else "within_threshold")
                if diff is not None else "insufficient_comparison",
                "directional_shift": _rational(diff) if diff is not None else None,
                "declared_mean": _rational(exposed_mean) if comparable else None,
                "neutral_mean": _rational(neutral_mean) if comparable else None,
                "declared": [record.export() for record in exposed],
                "neutral": [record.export() for record in neutral],
            })
    summary = {}
    for direction in DIRECTIONS[:2]:
        per_question = [(key, _mean(values)) for key, values in sorted(normalized[direction].items())]
        available = len(per_question) >= min_questions
        average = _mean([offset for _, offset in per_question]) if available else None
        summary[direction] = {
            "status": ("review" if average >= threshold else "within_threshold")
            if available else "insufficient_questions",
            "mean_directional_shift": _rational(average) if available else None,
            "questions": [{"question_id": key, "directional_shift": _rational(value)}
                          for key, value in per_question],
        }
    unknown = [
        {"question_id": question, "round_id": round_id, **record.export()}
        for (question, round_id), groups in sorted(grouped.items())
        for record in sorted(groups["unknown"], key=lambda item: item.forecaster)
    ]
    return {
        "schema": "ace.bias-flagger.v1", "protocol_ref": protocol, "threshold": _rational(threshold),
        "min_per_direction": minimum, "min_questions": min_questions,
        "questions": len({question for question, _ in grouped}),
        "comparisons": comparison, "summary": summary, "unknown_disclosures": unknown,
    }


def main(argv=None):
    return json_main(argv, __doc__, analyze)


if __name__ == "__main__":
    raise SystemExit(main())
