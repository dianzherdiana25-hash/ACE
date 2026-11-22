"""Cari asumsi yang bisa membalikkan konsensus sebelum adopsi dipertimbangkan.

Pemeriksaan menghapus bukti per keluarga sumber atau mengubah asumsi
terukur pada masukan terstruktur. Tantangan membawa referensi masukan dan
hasil perhitungan. combine_downside opsional menguji dampak gabungan
penurunan asumsi dan hilangnya satu keluarga. Keluarnya rekomendasi tidak memberi otoritas
untuk melakukan tindakan.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
from pathlib import Path
import re


MAX_INPUT = 2_000_000
MAX_EVIDENCE = 1_000
MAX_ASSUMPTIONS = 100
MAX_DIGITS = 18
_DECIMAL_LITERAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


class ChallengeError(ValueError):
    """Peta bukti atau asumsi belum cukup untuk audit konsensus."""


def _text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ChallengeError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ChallengeError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _require(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise ChallengeError("Field masukan tantangan tidak lengkap.")


def _number(value):
    if type(value) not in (str, int) or len(str(value)) > 48:
        raise ChallengeError("Bobot wajib desimal eksplisit.")
    if not _DECIMAL_LITERAL.fullmatch(str(value)):
        raise ChallengeError("Format bobot wajib berupa literal desimal.")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ChallengeError("Bobot desimal tidak sah.") from exc
    if (not number.is_finite() or len(number.as_tuple().digits) > MAX_DIGITS
            or not -MAX_DIGITS <= number.as_tuple().exponent <= MAX_DIGITS
            or abs(number) > Decimal(10**10)):
        raise ChallengeError("Bobot desimal melampaui batas.")
    return Fraction(number)


def _decimal(value):
    """Render pecahan berpenyebut 2^a * 5^b menjadi desimal persis."""
    numerator, denominator = value.as_integer_ratio()
    sign = "-" if numerator < 0 else ""
    integer, remainder = divmod(abs(numerator), denominator)
    if not remainder:
        return f"{sign}{integer}"
    digits = []
    while remainder:
        digit, remainder = divmod(remainder * 10, denominator)
        digits.append(str(digit))
    return f"{sign}{integer}." + "".join(digits)


@dataclass(frozen=True)
class Evidence:
    id: str
    family: str
    ref: str
    weight: Fraction

    @classmethod
    def from_dict(cls, value):
        _require(value, ("id", "source_family", "source_ref", "weight"))
        weight = _number(value["weight"])
        if not weight:
            raise ChallengeError("Bobot bukti nol tidak informatif.")
        return cls(_text(value["id"], "id bukti", 80), _text(value["source_family"], "keluarga", 80),
                   _text(value["source_ref"], "ref sumber", 512), weight)


@dataclass(frozen=True)
class Assumption:
    id: str
    ref: str
    low: Fraction
    expected: Fraction
    high: Fraction

    @classmethod
    def from_dict(cls, value):
        _require(value, ("id", "source_ref", "low", "expected", "high"))
        low, expected, high = (_number(value[key]) for key in ("low", "expected", "high"))
        if not low <= expected <= high:
            raise ChallengeError("Nilai asumsi harus berada di dalam intervalnya.")
        return cls(_text(value["id"], "id asumsi", 80), _text(value["source_ref"], "ref asumsi", 512),
                   low, expected, high)


def _rows(values, maximum, parse, name):
    if not isinstance(values, list) or len(values) > maximum:
        raise ChallengeError(f"{name} melebihi batas jumlah.")
    parsed = [parse(value) for value in values]
    if len({row.id for row in parsed}) != len(parsed):
        raise ChallengeError(f"{name} memuat ID ganda.")
    return sorted(parsed, key=lambda row: row.id)


def _scenario(category, identifier, score, threshold, refs):
    return {"kind": category, "id": identifier, "score": _decimal(score),
            "margin": _decimal(score - threshold), "breaks_threshold": score < threshold,
            "source_refs": sorted(set(refs))}


def test_consensus(raw):
    """Uji kerentanan skor untuk usulan yang sudah mencapai konsensus terstruktur."""
    if not isinstance(raw, dict):
        raise ChallengeError("Masukan tantangan wajib berupa objek.")
    fields = {"proposal", "threshold", "evidence", "assumptions"}
    if set(raw) - {"combine_downside"} != fields:
        raise ChallengeError("Field masukan tantangan tidak lengkap.")
    combine_downside = raw.get("combine_downside", False)
    if type(combine_downside) is not bool:
        raise ChallengeError("combine_downside harus boolean.")
    proposal = _text(raw["proposal"], "proposal", 512)
    threshold = _number(raw["threshold"])
    facts = _rows(raw["evidence"], MAX_EVIDENCE, Evidence.from_dict, "evidence")
    assumptions = _rows(raw["assumptions"], MAX_ASSUMPTIONS, Assumption.from_dict, "assumptions")
    if not facts:
        raise ChallengeError("Konsensus membutuhkan sedikitnya satu bukti terstruktur.")
    references = [fact.ref for fact in facts]
    if len(set(references)) != len(references):
        raise ChallengeError("Sumber yang sama tidak boleh dihitung sebagai bukti independen.")

    direct_score = sum((fact.weight for fact in facts), Fraction(0))
    baseline = direct_score + sum((item.expected for item in assumptions), Fraction(0))
    groups = {}
    for fact in facts:
        groups.setdefault(fact.family, []).append(fact)
    scenarios = []
    for name, members in sorted(groups.items()):
        adjusted = baseline - sum(member.weight for member in members)
        scenarios.append(_scenario("remove_source_family", name, adjusted, threshold,
                                   (member.ref for member in members)))
    for item in assumptions:
        adjusted = baseline - (item.expected - item.low)
        scenarios.append(_scenario("lower_assumption", item.id, adjusted, threshold, [item.ref]))
    if assumptions:
        downside = direct_score + sum(item.low for item in assumptions)
        scenarios.append(_scenario("joint_downside", "all", downside, threshold,
                                   (item.ref for item in assumptions)))
        if combine_downside:
            for name, members in sorted(groups.items()):
                scenarios.append(_scenario(
                    "joint_downside_without_family", name,
                    downside - sum(member.weight for member in members), threshold,
                    [member.ref for member in members] + [item.ref for item in assumptions],
                ))

    weakest = min(scenarios, key=lambda row: (Fraction(row["margin"]), row["kind"], row["id"]))
    if baseline < threshold:
        verdict = "baseline_below_threshold"
    elif any(row["breaks_threshold"] for row in scenarios):
        verdict = "reopen"
    else:
        verdict = "survives_declared_challenges"
    return {"schema": "ace.devil-advocate.v1", "proposal": proposal,
            "baseline_score": _decimal(baseline), "threshold": _decimal(threshold),
            "scenarios": scenarios, "weakest": weakest.copy(), "verdict": verdict}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.evidence.open("rb") as stream:
            data = stream.read(MAX_INPUT + 1)
        if len(data) > MAX_INPUT:
            raise ChallengeError("Berkas masukan melampaui batas.")
        result = test_consensus(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["verdict"] != "survives_declared_challenges")


if __name__ == "__main__":
    raise SystemExit(main())
