"""Tandai kesepakatan yang perlu diperiksa ulang sebelum dianggap independen.

Masukan membedakan ballot privat dan putaran publik yang berurutan. Program
mendeteksi indikator yang dapat direproduksi dari ballot. Temuan menuntut
tinjauan dan tidak menetapkan penyebab sosial atau niat peserta.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import unicodedata


MAX_PARTICIPANTS = 300
MAX_INPUT_BYTES = 3_000_000


class ConsensusError(ValueError):
    """Catatan ballot tidak cukup terstruktur untuk diperiksa."""


def _obj(row, required):
    if not isinstance(row, dict) or row.keys() != set(required):
        raise ConsensusError("Objek ballot menyimpang dari skema.")
    return row


def _text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise ConsensusError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ConsensusError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _normalize(text):
    flattened = "".join(char if char.isalnum() else " "
                        for char in unicodedata.normalize("NFKC", text).casefold())
    return " ".join(flattened.split())


@dataclass(frozen=True, slots=True)
class Ballot:
    participant: str
    option: str
    rationale: str
    source_ref: str
    evidence_refs: tuple[str, ...]

    @classmethod
    def from_dict(cls, row):
        _obj(row, ("participant", "option", "rationale", "source_ref", "evidence_refs"))
        refs = row["evidence_refs"]
        if not isinstance(refs, list) or len(refs) > 100:
            raise ConsensusError("evidence_refs wajib larik berbatas.")
        cleaned = tuple(sorted(_text(ref, "ref bukti", 512) for ref in refs))
        if len(set(cleaned)) != len(cleaned):
            raise ConsensusError("Rujukan bukti ganda.")
        return cls(_text(row["participant"], "peserta", 96), _text(row["option"], "pilihan", 96),
                   _text(row["rationale"], "alasan", 4_000), _text(row["source_ref"], "sumber ballot", 512),
                   cleaned)


def _participants(raw):
    if not isinstance(raw, list) or not 3 <= len(raw) <= MAX_PARTICIPANTS:
        raise ConsensusError("Diperlukan 3–300 peserta.")
    participants = {}
    for row in raw:
        _obj(row, ("id", "authority"))
        identifier = _text(row["id"], "ID peserta", 96)
        authority = row["authority"]
        if identifier in participants or type(authority) is not int or not 0 <= authority <= 3:
            raise ConsensusError("Peserta ganda atau tingkat otoritas tidak sah.")
        participants[identifier] = authority
    return participants


def _ballots(rows, participants, options):
    if not isinstance(rows, list) or len(rows) > len(participants):
        raise ConsensusError("Jumlah ballot melampaui jumlah peserta.")
    result = {}
    sources = set()
    for row in rows:
        vote = Ballot.from_dict(row)
        if vote.participant not in participants or vote.option not in options:
            raise ConsensusError("Ballot merujuk peserta atau pilihan asing.")
        if vote.participant in result or vote.source_ref in sources:
            raise ConsensusError("Ballot atau rujukan ballot ganda dalam satu putaran.")
        result[vote.participant] = vote
        sources.add(vote.source_ref)
    return result


def _finding(code, votes):
    return {"code": code, "participants": sorted({vote.participant for vote in votes}),
            "ballot_refs": sorted({vote.source_ref for vote in votes})}


def _shared_rationale(winners):
    by_reason = defaultdict(list)
    for vote in winners:
        reason = _normalize(vote.rationale)
        if len(reason) >= 24:
            by_reason[reason].append(vote)
    return [_finding("repeated_rationale", same) for same in by_reason.values() if len(same) >= 3]


def _authority_shift(public, private, authorities, winner):
    if not public:
        return []
    lead, *later = public
    highest = max(authorities.values())
    if highest == min(authorities.values()) or authorities[lead.participant] != highest or lead.option != winner:
        return []
    switched = [
        vote for vote in later
        if vote.option == winner and authorities[vote.participant] < highest
        and vote.participant in private and private[vote.participant].option != winner
    ]
    if len(switched) < 2:
        return []
    return [_finding("convergence_after_authority",
                     [lead, *switched, *(private[vote.participant] for vote in switched)])]


def inspect_consensus(raw):
    """Uji consensus publik minimal dua pertiga dari semua peserta terdaftar."""
    _obj(raw, ("options", "participants", "private", "public"))
    if not isinstance(raw["options"], list) or not 2 <= len(raw["options"]) <= 20:
        raise ConsensusError("Diperlukan 2–20 pilihan.")
    options = sorted(_text(option, "pilihan", 96) for option in raw["options"])
    if len(set(options)) != len(options):
        raise ConsensusError("Pilihan ganda.")
    people = _participants(raw["participants"])
    private = _ballots(raw["private"], people, options)
    public = _ballots(raw["public"], people, options)
    if {vote.source_ref for vote in private.values()} & {vote.source_ref for vote in public.values()}:
        raise ConsensusError("Ballot privat dan publik wajib memiliki provenance berbeda.")
    tallies = dict.fromkeys(options, 0)
    tallies.update(Counter(vote.option for vote in public.values()))
    apparent = [option for option, count in tallies.items() if 3 * count >= 2 * len(people)]
    winner = apparent[0] if apparent else None
    findings = []
    if winner is not None:
        supporters = [vote for vote in public.values() if vote.option == winner]
        absent = [vote for vote in supporters if vote.participant not in private]
        if absent:
            findings.append(_finding("missing_private_record", absent))
        unsupported = [vote for vote in supporters if not vote.evidence_refs]
        if len(unsupported) >= 2:
            findings.append(_finding("support_without_evidence", unsupported))
        findings.extend(_shared_rationale(supporters))
        findings.extend(_authority_shift(list(public.values()), private, people, winner))
    findings.sort(key=lambda item: (item["code"], item["participants"]))
    if winner is None:
        status = "no_consensus"
    elif findings:
        status = "review_required"
    else:
        status = "no_listed_signal"
    return {"schema": "ace.consensus-detector.v1", "status": status, "apparent_option": winner,
            "registered_count": len(people), "private_count": len(private), "public_count": len(public),
            "tallies": tallies, "findings": findings}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ballots", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.ballots.open("rb") as handle:
            data = handle.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise ConsensusError("Berkas ballot melampaui batas.")
        result = inspect_consensus(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] == "review_required")


if __name__ == "__main__":
    raise SystemExit(main())
