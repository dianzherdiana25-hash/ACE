"""Timbang dua sisi klaim agar pengulangan sumber tidak menyamar sebagai bukti baru.

Kredibilitas dan verifikasi sumber adalah masukan yang harus dirujuk.
Keluarga sumber yang sama menyumbang paling banyak satu bobot per sisi.
Laporan mempertahankan seluruh bukti yang tidak terpilih atau belum
terverifikasi untuk pemeriksaan silang.
"""
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import re


MAX_SOURCES = 2_000
MAX_EVIDENCE = 10_000
MAX_BYTES = 8_000_000
_PROBABILITY = re.compile(r"[01](?:\.[0-9]{1,12})?")


class EvidenceError(ValueError):
    """Peta klaim, sumber, atau bobot belum dapat diperiksa."""


def _record(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise EvidenceError("Objek pembobotan tidak sesuai skema.")


def _text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise EvidenceError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise EvidenceError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _unit(value):
    if type(value) is int and value in (0, 1):
        return Fraction(value)
    if not isinstance(value, str) or not _PROBABILITY.fullmatch(value):
        raise EvidenceError("Bobot wajib desimal 0–1 dengan hingga 12 digit pecahan.")
    value = Fraction(value)
    if value > 1:
        raise EvidenceError("Bobot di luar rentang [0, 1].")
    return value


def _exact(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    family: str
    ref: str
    credibility: Fraction
    verified: bool

    @classmethod
    def from_dict(cls, row):
        _record(row, ("id", "family", "source_ref", "credibility", "verified"))
        if type(row["verified"]) is not bool:
            raise EvidenceError("verified wajib boolean eksplisit.")
        return cls(_text(row["id"], "ID sumber", 96), _text(row["family"], "keluarga sumber", 96),
                   _text(row["source_ref"], "rujukan sumber", 512), _unit(row["credibility"]), row["verified"])


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    claim: str
    source: str
    ref: str
    stance: str
    strength: Fraction

    @classmethod
    def from_dict(cls, row):
        _record(row, ("id", "claim", "source", "evidence_ref", "stance", "strength"))
        if row["stance"] not in ("support", "oppose"):
            raise EvidenceError("Sisi bukti harus support atau oppose.")
        return cls(_text(row["id"], "ID bukti", 96), _text(row["claim"], "klaim", 96),
                   _text(row["source"], "sumber", 96), _text(row["evidence_ref"], "bukti", 512),
                   row["stance"], _unit(row["strength"]))


def _parse_rows(raw, parse, limit, *, allow_empty=False):
    if not isinstance(raw, list) or len(raw) > limit or (not raw and not allow_empty):
        raise EvidenceError("Jumlah sumber atau bukti di luar batas.")
    rows = [parse(row) for row in raw]
    indexed = {row.id: row for row in rows}
    if len(indexed) != len(rows):
        raise EvidenceError("ID ganda dalam katalog sumber atau bukti.")
    return indexed


def weigh_evidence(raw):
    """Kembalikan kontribusi sumber per klaim dengan provenance yang bisa diaudit."""
    _record(raw, ("claims", "sources", "evidence"))
    if not isinstance(raw["claims"], list) or not 1 <= len(raw["claims"]) <= MAX_SOURCES:
        raise EvidenceError("Diperlukan daftar klaim berbatas.")
    claims = [_text(claim, "ID klaim", 96) for claim in raw["claims"]]
    if len(set(claims)) != len(claims):
        raise EvidenceError("ID klaim ganda.")
    sources = _parse_rows(raw["sources"], Source.from_dict, MAX_SOURCES)
    if len({source.ref for source in sources.values()}) != len(sources):
        raise EvidenceError("Rujukan sumber ganda dalam katalog.")
    evidence = _parse_rows(raw["evidence"], Evidence.from_dict, MAX_EVIDENCE, allow_empty=True)
    by_claim = {claim: [] for claim in claims}
    used_refs = set()
    choices = {}
    for identifier in sorted(evidence):
        item = evidence[identifier]
        if item.claim not in by_claim or item.source not in sources:
            raise EvidenceError("Bukti merujuk klaim atau sumber yang tidak ada.")
        if (item.claim, item.ref) in used_refs:
            raise EvidenceError("Rujukan bukti dihitung dua kali untuk klaim yang sama.")
        used_refs.add((item.claim, item.ref))
        source = sources[item.source]
        weight = source.credibility * item.strength
        by_claim[item.claim].append((item, source, weight))
        if source.verified and weight:
            key = (item.claim, source.family, item.stance)
            if key not in choices or weight > choices[key][1]:
                choices[key] = (item.id, weight)

    results = []
    for claim in sorted(by_claim):
        totals = dict.fromkeys(("support", "oppose"), Fraction(0))
        source_families = {"support": set(), "oppose": set()}
        trace = []
        for item, source, weight in by_claim[claim]:
            chosen = choices.get((claim, source.family, item.stance))
            counted = chosen is not None and chosen[0] == item.id
            if counted:
                totals[item.stance] += weight
                source_families[item.stance].add(source.family)
                state = "counted"
            elif not source.verified:
                state = "unverified_source"
            elif not weight:
                state = "zero_weight"
            else:
                state = "same_family_stronger_or_earlier_id"
            trace.append({"evidence_id": item.id, "evidence_ref": item.ref, "source_ref": source.ref,
                          "family": source.family, "stance": item.stance, "state": state,
                          "raw_weight": _exact(weight), "counted_weight": _exact(weight if counted else Fraction(0))})
        contradictions = sorted(source_families["support"] & source_families["oppose"])
        results.append({"claim": claim, "support": _exact(totals["support"]),
                        "oppose": _exact(totals["oppose"]), "margin": _exact(totals["support"] - totals["oppose"]),
                        "counted_families": {side: sorted(values) for side, values in source_families.items()},
                        "contradictory_families": contradictions, "evidence": trace})
    return {"schema": "ace.evidence-weigher.v1", "claims": results}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            payload = handle.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise EvidenceError("Berkas melampaui batas.")
        result = weigh_evidence(json.loads(payload))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
