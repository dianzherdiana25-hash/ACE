"""Ukur biaya dan manfaat deliberasi per kelas dari kasus berpasangan.

Skor kualitas dan satuan sumber daya berasal dari kartu observasi.
Konversi ke unit nilai berasal dari kebijakan yang dirujuk untuk
setiap kelas. Perbandingan mengabaikan pasangan tidak lengkap sambil
melaporkan kekurangannya. Rasio hanya terdefinisi untuk biaya tambahan
positif. Semua nilai tetap dalam satuan analitis yang dideklarasikan.
"""
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from ._advanced import InputError, integer, json_main, rows, shape, text, unique
from .brier_scorer import _rational


MAX_ROWS = 20_000
MAX_UNITS = 10**9


@dataclass(frozen=True, slots=True)
class Observation:
    score: int
    elapsed_ms: int
    credits: int
    judgement_ref: str
    resource_ref: str

    @classmethod
    def read(cls, raw, refs):
        shape(raw, ("score", "elapsed_ms", "credits", "judgement_ref", "resource_ref"))
        return cls(integer(raw["score"], 0, 100), integer(raw["elapsed_ms"], 0, MAX_UNITS),
                   integer(raw["credits"], 0, MAX_UNITS),
                   unique(text(raw["judgement_ref"], "sumber skor"), refs),
                   unique(text(raw["resource_ref"], "sumber beban"), refs))

    def export(self):
        return {"score": self.score, "elapsed_ms": self.elapsed_ms, "credits": self.credits,
                "judgement_ref": self.judgement_ref, "resource_ref": self.resource_ref}


@dataclass(frozen=True, slots=True)
class Policy:
    key: str
    ref: str
    per_point: int
    per_millisecond: int
    per_credit: int

    @classmethod
    def read(cls, row, refs):
        shape(row, ("class", "ref", "value_per_point", "cost_per_ms", "cost_per_credit"))
        return cls(text(row["class"], "kelas"), unique(text(row["ref"], "sumber kebijakan"), refs),
                   integer(row["value_per_point"], 0, MAX_UNITS), integer(row["cost_per_ms"], 0, MAX_UNITS),
                   integer(row["cost_per_credit"], 0, MAX_UNITS))

    def export(self):
        return {"class": self.key, "ref": self.ref, "value_per_point": self.per_point,
                "cost_per_ms": self.per_millisecond, "cost_per_credit": self.per_credit}


def _observation(first, second, policy):
    quality = second.score - first.score
    elapsed = second.elapsed_ms - first.elapsed_ms
    credits = second.credits - first.credits
    value = quality * policy.per_point
    cost = elapsed * policy.per_millisecond + credits * policy.per_credit
    return {"quality_points": quality, "elapsed_ms": elapsed, "credits": credits,
            "gross_value": value, "added_cost": cost, "net_value": value - cost}


def _summarize(items, minimum):
    if not items:
        return {"status": "no_pairs", "net_per_case": None, "totals": None, "roi": None,
                "break_even_value_per_point": None, "paired_net_signs": {"positive": 0, "zero": 0, "negative": 0}}
    keys = ("quality_points", "elapsed_ms", "credits", "gross_value", "added_cost", "net_value")
    totals = {name: sum(item[name] for item in items) for name in keys}
    sufficient = len(items) >= minimum
    total_cost = totals["added_cost"]
    total_quality = totals["quality_points"]
    return {
        "status": "measured" if sufficient else "insufficient_pairs",
        "net_per_case": _rational(Fraction(totals["net_value"], len(items))) if sufficient else None,
        "totals": totals,
        "roi": _rational(Fraction(totals["net_value"], total_cost)) if sufficient and total_cost > 0 else None,
        "break_even_value_per_point": _rational(Fraction(max(total_cost, 0), total_quality))
        if sufficient and total_quality > 0 else None,
        "paired_net_signs": {"positive": sum(item["net_value"] > 0 for item in items),
                             "zero": sum(item["net_value"] == 0 for item in items),
                             "negative": sum(item["net_value"] < 0 for item in items)},
    }


def measure(raw):
    shape(raw, ("protocol_ref", "analysis_unit", "minimum_pairs", "policies", "cases"))
    protocol = text(raw["protocol_ref"], "protokol")
    refs = {protocol}
    unit = text(raw["analysis_unit"], "satuan analisis")
    minimum = integer(raw["minimum_pairs"], 1, MAX_ROWS)
    policies = {}
    for row in rows(raw["policies"], 1, 100):
        item = Policy.read(row, refs)
        if item.key in policies:
            raise InputError("Kebijakan kelas ganda.")
        policies[item.key] = item

    case_ids = set()
    groups = defaultdict(list)
    for row in rows(raw["cases"], 0, MAX_ROWS):
        shape(row, ("case_id", "class", "case_ref", "baseline", "deliberation"))
        key = unique(text(row["case_id"], "ID kasus"), case_ids)
        evidence = unique(text(row["case_ref"], "sumber kasus"), refs)
        kind = text(row["class"], "kelas")
        if kind not in policies:
            raise InputError("Kasus harus menunjuk kelas dengan kebijakan nilai eksplisit.")
        arms = {name: Observation.read(row[name], refs) if row[name] is not None else None
                for name in ("baseline", "deliberation")}
        missing = [name for name, obs in arms.items() if obs is None]
        delta = _observation(arms["baseline"], arms["deliberation"], policies[kind]) if not missing else None
        groups[kind].append({"case_id": key, "source_ref": evidence, "missing": missing, "delta": delta,
                             "observations": {name: obs.export() if obs else None for name, obs in arms.items()}})
    result = []
    for key, policy in sorted(policies.items()):
        records = sorted(groups[key], key=lambda record: record["case_id"])
        pairs = [row["delta"] for row in records if row["delta"] is not None]
        result.append({"class": key, "policy": policy.export(), "pairs": len(pairs),
                       "incomplete": len(records) - len(pairs), "cases": records, **_summarize(pairs, minimum)})
    return {"schema": "ace.deliberation-roi.v1", "protocol_ref": protocol,
            "analysis_unit": unit, "minimum_pairs": minimum, "classes": result}


def main(argv=None):
    return json_main(argv, __doc__, measure)


if __name__ == "__main__":
    raise SystemExit(main())
