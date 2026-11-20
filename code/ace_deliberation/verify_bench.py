"""Periksa gerbang EVO 0051 dari penilaian berpasangan dan hasil held-out.

Penilai dan keluaran kedua lengan diberikan dari luar. Program memeriksa
cakupan, rujukan, dan aritmetika gerbang. Pemeriksaan struktur tidak
membuktikan bahwa penilaian independen atau bahwa data berasal dari run nyata.
"""
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import score_brier
from .decision_brief import make_brief


GAIN_POINTS_REQUIRED = Fraction(10)
PRECEDENT_COVERAGE_REQUIRED = Fraction(1)
MAX_DECISIONS = 1_000
MAX_BYTES = 50_000_000


class BenchError(ValueError):
    """Masukan bench tidak lengkap atau lengan tidak bisa dibandingkan."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise BenchError("Field benchmark tidak sesuai skema.")


def _ref(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 512 or "\0" in value:
        raise BenchError("Rujukan hasil atau penilaian tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise BenchError("Teks rujukan bukan UTF-8 yang sah.") from exc
    return value.strip()


def _run(raw, *, candidate):
    keys = ("decision_ref", "score_ref", "points")
    _shape(raw, (*keys, "brief_input") if candidate else keys)
    points = raw["points"]
    if type(points) is not int or not 0 <= points <= 100:
        raise BenchError("Penilaian berupa poin integer 0–100.")
    return {"decision_ref": _ref(raw["decision_ref"]), "score_ref": _ref(raw["score_ref"]),
            "points": points}


def _fraction(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def evaluate(raw):
    """Laporkan ketiga ambang secara terpisah tanpa memanggil organ."""
    _shape(raw, ("paired_decisions", "brier_input"))
    inputs = raw["paired_decisions"]
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= MAX_DECISIONS:
        raise BenchError("Perbandingan memerlukan pasangan penilaian berbatas.")
    paired = {}
    seen_refs = set()
    for record in inputs:
        _shape(record, ("case_id", "candidate", "single_organ"))
        case_id = _ref(record["case_id"])
        if case_id in paired:
            raise BenchError("ID kasus bench ganda.")
        candidate = _run(record["candidate"], candidate=True)
        baseline = _run(record["single_organ"], candidate=False)
        refs = {run[key] for run in (candidate, baseline) for key in ("decision_ref", "score_ref")}
        if len(refs) != 4 or refs & seen_refs:
            raise BenchError("Rujukan penilaian atau putusan dipakai ulang.")
        seen_refs.update(refs)
        brief = make_brief(record["candidate"]["brief_input"])
        if brief["debate_id"] != case_id:
            raise BenchError("Brief bukan berasal dari kasus yang dinilai.")
        citation = brief["precedent"]
        paired[case_id] = {
            "case_id": case_id, "candidate": candidate, "single_organ": baseline,
            "candidate_debate_sha256": brief["debate_sha256"],
            "gain_points": candidate["points"] - baseline["points"],
            "precedent_ref": citation["source_ref"] if citation is not None else None,
            "precedent_case_id": citation["case_id"] if citation is not None else None,
        }

    cases = [paired[case_id] for case_id in sorted(paired)]
    gain = Fraction(sum(case["gain_points"] for case in cases), len(cases))
    coverage = Fraction(sum(case["precedent_ref"] is not None for case in cases), len(cases))
    scores = score_brier(raw["brier_input"])
    requirements = {
        "deliberation_gain_points": {"required": _fraction(GAIN_POINTS_REQUIRED), "observed": _fraction(gain),
                                     "met": gain >= GAIN_POINTS_REQUIRED},
        "forecast_beats_base_rate": {"observed": scores["improvement"], "met": scores["verdict"] == "better"},
        "precedent_coverage": {"required": _fraction(PRECEDENT_COVERAGE_REQUIRED), "observed": _fraction(coverage),
                               "met": coverage == PRECEDENT_COVERAGE_REQUIRED},
    }
    return {"schema": "ace.evo0051-bench-arithmetic.v1", "case_count": len(cases),
            "requirements": requirements, "arithmetic_checks_met": all(row["met"] for row in requirements.values()),
            "cases": cases, "brier": scores}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise BenchError("Berkas benchmark melampaui batas.")
        result = evaluate(json.loads(data))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(not result["arithmetic_checks_met"])


if __name__ == "__main__":
    raise SystemExit(main())
