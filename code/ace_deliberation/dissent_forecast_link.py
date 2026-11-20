"""Simpan ramalan alternatif bersama sanggahan yang dapat diputar ulang.

Hash transcript yang diperoleh dari sumber tersendiri menambatkan
giliran dissent. Perbandingan memakai ambang peluang yang diketahui
sebelumnya. Brier hanya terlihat setelah resolusi, tanpa menimpa
ramalan asal atau menyiratkan bahwa selisih berasal dari dissent.
"""
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
import re

from ._advanced import InputError, json_main, labels, probability, rows, shape, stamp, text, unique
from .brier_scorer import Resolution, _rational
from .debate_protocol import verify_report


MAX_ALTERNATIVES = 100


@dataclass(frozen=True, slots=True)
class Forecast:
    chance: Fraction
    at: datetime
    ref: str

    @classmethod
    def read(cls, value, refs):
        return cls(probability(value["probability"]), stamp(value["forecast_at"]),
                   unique(text(value["forecast_ref"], "rujukan ramalan"), refs))

    def export(self):
        return {"probability": _rational(self.chance), "forecast_at": self.at.isoformat(), "forecast_ref": self.ref}


def link(raw):
    shape(raw, ("question_id", "as_of", "threshold", "transcript", "original", "alternatives", "resolution"))
    question = text(raw["question_id"], "pertanyaan")
    as_of = stamp(raw["as_of"])
    deck = raw["transcript"]
    shape(deck, ("question_id", "ref", "anchor_sha256", "anchor_ref", "available_at", "report"))
    if text(deck["question_id"], "pertanyaan terkait") != question:
        raise InputError("ID pertanyaan transcript dan ramalan berbeda.")
    source_ref = text(deck["ref"], "sumber transcript")
    anchor = text(deck["anchor_sha256"], "hash transcript")
    if not re.fullmatch(r"[0-9a-f]{64}", anchor):
        raise InputError("Hash transcript perlu SHA-256 lowercase.")
    references = {source_ref}
    anchor_ref = unique(text(deck["anchor_ref"], "sumber hash"), references)
    available = stamp(deck["available_at"])
    report = deck["report"]
    if not verify_report(report) or report["sha256"] != anchor:
        raise InputError("Transcript gagal replay atau tidak cocok dengan hash.")
    if report["next_turn"] is not None:
        raise InputError("Transcript masih dalam proses.")

    threshold_raw = raw["threshold"]
    shape(threshold_raw, ("probability", "ref", "known_at"))
    threshold = probability(threshold_raw["probability"])
    limit_ref = unique(text(threshold_raw["ref"], "sumber ambang"), references)
    threshold_at = stamp(threshold_raw["known_at"])
    original = raw["original"]
    shape(original, ("probability", "forecast_ref", "forecast_at"))
    base = Forecast.read(original, references)
    if not threshold_at <= base.at <= as_of or available > as_of:
        raise InputError("Ambang, ramalan asal atau transcript berada di luar jendela yang sah.")

    resolution = Resolution.from_dict(raw["resolution"]) if raw["resolution"] is not None else None
    if resolution is not None:
        if resolution.question_id != question or resolution.at <= base.at:
            raise InputError("Resolusi harus cocok dengan ID dan terjadi sesudah ramalan asal.")
        unique(resolution.source_ref, references)
    resolved = resolution is not None and resolution.at <= as_of
    dissent = {turn["turn_id"]: turn for turn in report["turns"]
               if turn["turn_id"] in report["dissent_turns"]}
    alternatives = []
    seen = set()
    for row in rows(raw["alternatives"], 0, MAX_ALTERNATIVES):
        shape(row, ("probability", "forecast_at", "forecast_ref", "dissent_turns"))
        alternative = Forecast.read(row, references)
        picks = sorted(labels(row["dissent_turns"], 1, 30, "dissent"))
        unique(tuple(picks), seen, "Kombinasi dissent")
        if set(picks) - dissent.keys():
            raise InputError("Ramalan alternatif wajib menunjuk giliran dissent.")
        if not max(base.at, available) <= alternative.at <= as_of:
            raise InputError("Ramalan alternatif berada di luar jendela asli dan transcript.")
        if resolution is not None and alternative.at >= resolution.at:
            raise InputError("Ramalan alternatif sudah mengetahui resolusi.")
        record = {
            **alternative.export(),
            "dissent": [{"turn_id": key, "participant": dissent[key]["participant"],
                         "evidence_refs": dissent[key]["evidence_refs"]} for key in picks],
            "delta_probability": _rational(alternative.chance - base.chance),
            "crosses_threshold": (alternative.chance >= threshold) != (base.chance >= threshold),
            "brier": None, "brier_improvement_from_original": None,
        }
        if resolved:
            loss = (alternative.chance - resolution.value)**2
            record.update(brier=_rational(loss),
                          brier_improvement_from_original=_rational((base.chance - resolution.value)**2 - loss))
        alternatives.append(record)
    alternatives.sort(key=lambda item: item["forecast_ref"])
    return {
        "schema": "ace.dissent-forecast-link.v1", "question_id": question, "as_of": as_of.isoformat(),
        "transcript": {"ref": source_ref, "sha256": anchor, "anchor_ref": anchor_ref,
                       "available_at": available.isoformat(), "debate_id": report["plan"]["debate_id"]},
        "threshold": {"probability": _rational(threshold), "ref": limit_ref, "known_at": threshold_at.isoformat()},
        "original": {**base.export(), "brier": _rational((base.chance - resolution.value)**2) if resolved else None},
        "alternatives": alternatives,
        "resolution": {"resolution_ref": resolution.source_ref, "outcome": resolution.value,
                       "resolved_at": resolution.at.isoformat()} if resolved else None,
    }


def main(argv=None):
    return json_main(argv, __doc__, link)


if __name__ == "__main__":
    raise SystemExit(main())
