"""Ramalkan dari kelas kasus yang sudah selesai sebelum batas informasi.

Dimensi dicocokkan dari yang terpenting ke yang lebih khusus. Jika kelas
terinci terlalu kecil, laporan mencoba prefix yang lebih luas. Riwayat
sesudah cutoff dan kasus target tetap terpisah dari hitungan.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction

from ._advanced import InputError, integer, json_main, labels, rows, shape, stamp, text, unique
from .brier_scorer import _outcome, _rational
from .forecaster import _display


MAX_HISTORY = 30_000


@dataclass(frozen=True, slots=True)
class PriorCase:
    case_id: str
    at: datetime
    ref: str
    outcome: int
    fields: dict

    @classmethod
    def read(cls, row, axes):
        shape(row, ("case_id", "resolved_at", "resolution_ref", "outcome", "fields"))
        shape(row["fields"], axes)
        return cls(text(row["case_id"], "kasus"), stamp(row["resolved_at"]),
                   text(row["resolution_ref"], "sumber resolusi"), _outcome(row["outcome"]),
                   {axis: text(row["fields"][axis], "nilai dimensi") for axis in axes})

    def export(self):
        return {"case_id": self.case_id, "resolved_at": self.at.isoformat(),
                "resolution_ref": self.ref, "outcome": self.outcome}


def _estimate(cases, alpha, beta):
    hits = sum(row.outcome for row in cases)
    count = len(cases)
    estimate = Fraction(hits + alpha, count + alpha + beta)
    return {
        "count": count, "hits": hits, "misses": count - hits,
        "empirical_rate": _rational(Fraction(hits, count)) if count else None,
        "estimate": _rational(estimate), "records": [row.export() for row in cases],
    }


def forecast(raw):
    shape(raw, ("target", "dimensions", "minimum_cases", "window_days", "prior", "history"))
    axes = labels(raw["dimensions"], 1, 8, "dimensi")
    needed = integer(raw["minimum_cases"], 1, MAX_HISTORY)
    window_days = integer(raw["window_days"], 1, 36_500)
    target = raw["target"]
    shape(target, ("question_id", "forecast_at", "forecast_ref", "fields"))
    shape(target["fields"], axes)
    query = {axis: text(target["fields"][axis], "nilai target") for axis in axes}
    question = text(target["question_id"], "pertanyaan target")
    forecast_ref = text(target["forecast_ref"], "sumber ramalan")
    cutoff = stamp(target["forecast_at"])
    prior = raw["prior"]
    shape(prior, ("success", "failure", "source_ref"))
    alpha = integer(prior["success"], 1, 100)
    beta = integer(prior["failure"], 1, 100)
    prior_ref = text(prior["source_ref"], "sumber prior")
    if prior_ref == forecast_ref:
        raise InputError("Rujukan prior dan keluaran bertabrakan.")

    allowed, excluded = [], []
    identifiers, references = set(), {forecast_ref, prior_ref}
    for value in rows(raw["history"], 0, MAX_HISTORY):
        case = PriorCase.read(value, axes)
        unique(case.case_id, identifiers, "ID kasus")
        unique(case.ref, references)
        reason = None
        if case.case_id == question:
            reason = "target_case"
        elif case.at >= cutoff:
            reason = "not_resolved_before_cutoff"
        elif cutoff - case.at > timedelta(days=window_days):
            reason = "outside_window"
        if reason is None:
            allowed.append(case)
        else:
            excluded.append({"case_id": case.case_id, "resolution_ref": case.ref, "reason": reason})
    allowed.sort(key=lambda item: item.case_id)

    levels = []
    selected = None
    selected_cases = None
    for depth in range(len(axes), -1, -1):
        filters = axes[:depth]
        matches = [case for case in allowed if all(case.fields[key] == query[key] for key in filters)]
        levels.append({"dimensions": filters, "count": len(matches)})
        if selected is None and len(matches) >= needed:
            selected = filters
            selected_cases = matches
    result = {
        "schema": "ace.reference-class.v1", "question_id": question, "cutoff": cutoff.isoformat(),
        "prior": {"success": alpha, "failure": beta, "source_ref": prior_ref},
        "attempted_classes": levels, "minimum_cases": needed,
        "excluded": sorted(excluded, key=lambda item: item["case_id"]),
    }
    if selected_cases is None:
        return {**result, "status": "insufficient_cases", "selection": None, "forecast": None}
    facts = _estimate(selected_cases, alpha, beta)
    selected_ids = {case.case_id for case in selected_cases}
    contrast_cases = [case for case in allowed if case.case_id not in selected_ids]
    contrast = _estimate(contrast_cases, alpha, beta) if contrast_cases else None
    point = Fraction(**facts["estimate"])
    # Sensitivitas terpisah dari estimasi saat satu kasus hilang.
    sensitivity = None
    if len(selected_cases) > needed:
        extremes = [Fraction(facts["hits"] + alpha - outcome, len(selected_cases) + alpha + beta - 1)
                    for outcome in sorted({row.outcome for row in selected_cases})]
        sensitivity = {"minimum": _rational(min(extremes)), "maximum": _rational(max(extremes))}
    return {
        **result, "status": "forecasted",
        "selection": {"dimensions": selected, "values": {axis: query[axis] for axis in selected},
                      **facts, "leave_one_case_range": sensitivity},
        "outside_selected_class": contrast,
        "delta_vs_outside_class": (
            _rational(point - Fraction(**contrast["estimate"])) if contrast else None
        ),
        "forecast": {"question_id": question, "forecast_at": cutoff.isoformat(),
                     "forecast_ref": forecast_ref, "probability": _display(point)},
    }


def main(argv=None):
    return json_main(argv, __doc__, forecast)


if __name__ == "__main__":
    raise SystemExit(main())
