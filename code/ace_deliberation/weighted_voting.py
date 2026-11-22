"""Hitung putusan berbobot keahlian dengan runoff dan bukti roster.

Ballot berurutan kehilangan pilihan teratas saat pilihan itu dieliminasi.
Bobot berasal dari catatan kompetensi untuk topik yang dipilih. Kuorum
dihitung terhadap peserta berhak setelah recusal. Seri yang dapat
mengubah putusan ditahan untuk review.
"""
from fractions import Fraction
import json
from math import ceil
from pathlib import Path


MAX_VOTERS = 800
MAX_CHOICES = 30
MAX_BYTES = 4_000_000


class VotingError(ValueError):
    """Roster, bobot, atau ballot tidak bisa diterapkan."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise VotingError("Field suara tidak sesuai skema.")


def _text(value, label, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise VotingError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise VotingError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _labels(raw, maximum, minimum=0):
    if not isinstance(raw, list) or not minimum <= len(raw) <= maximum:
        raise VotingError("Jumlah pilihan atau record di luar batas.")
    labels = [_text(item, "label") for item in raw]
    if len(set(labels)) != len(labels):
        raise VotingError("Label ganda pada ballot.")
    return labels


def _rows(raw, maximum):
    if not isinstance(raw, list) or len(raw) > maximum:
        raise VotingError("Jumlah record melebihi batas.")
    return raw


def _threshold(raw):
    _shape(raw, ("numerator", "denominator"))
    a, b = raw["numerator"], raw["denominator"]
    if type(a) is not int or type(b) is not int or not 1 <= a <= b <= 1_000:
        raise VotingError("Kuorum bobot wajib rasio positif sampai 1.")
    return Fraction(a, b)


def _runoff(weighted, choices):
    remaining = set(choices)
    rounds = []
    while remaining:
        counts = dict.fromkeys(sorted(remaining), 0)
        active = 0
        for rankings, weight in weighted:
            ballot = next((choice for choice in rankings if choice in remaining), None)
            if ballot is not None:
                counts[ballot] += weight
                active += weight
        step = {"tally": counts, "continuing_weight": active, "eliminated": []}
        rounds.append(step)
        if not active:
            return "no_continuing_ballots", None, rounds
        winner = next((choice for choice in counts if 2 * counts[choice] > active), None)
        if winner is not None:
            return "selected", winner, rounds
        lowest = min(counts.values())
        weakest = [choice for choice, weight in counts.items() if weight == lowest]
        stronger = [weight for weight in counts.values() if weight > lowest]
        if len(weakest) > 1 and (not stronger or len(weakest) * lowest >= min(stronger)):
            return "elimination_tie", None, rounds
        remaining.difference_update(weakest)
        step["eliminated"] = weakest
    return "no_continuing_ballots", None, rounds


def elect(raw):
    _shape(raw, ("topic", "choices", "roster", "recusals", "ballots", "quorum"))
    topic = _text(raw["topic"], "topik")
    choices = sorted(_labels(raw["choices"], MAX_CHOICES, 2))
    fraction = _threshold(raw["quorum"])
    eligible, all_ids, used_refs = {}, set(), set()
    for row in _rows(raw["roster"], MAX_VOTERS):
        _shape(row, ("voter", "topic", "weight", "expertise_ref"))
        name = _text(row["voter"], "pemilih")
        record_topic = _text(row["topic"], "topik keahlian")
        ref = _text(row["expertise_ref"], "sumber keahlian", 512)
        weight = row["weight"]
        key = name, record_topic
        if key in all_ids or ref in used_refs or type(weight) is not int or not 1 <= weight <= 1_000:
            raise VotingError("Bobot tidak sah atau catatan kompetensi ganda.")
        all_ids.add(key)
        used_refs.add(ref)
        if record_topic == topic:
            eligible[name] = weight, ref

    recused = {}
    for row in _rows(raw["recusals"], MAX_VOTERS):
        _shape(row, ("voter", "source_ref"))
        name = _text(row["voter"], "pemilih mundur")
        ref = _text(row["source_ref"], "sumber recusal", 512)
        if name not in eligible or name in recused or ref in used_refs:
            raise VotingError("Catatan mundur ganda atau di luar roster.")
        recused[name] = ref
        used_refs.add(ref)
    allowed = {name: item for name, item in eligible.items() if name not in recused}
    roster_weight = sum(weight for weight, ref in allowed.values())
    needed = ceil(roster_weight * fraction)
    cast = {}
    for row in _rows(raw["ballots"], MAX_VOTERS):
        _shape(row, ("voter", "rankings", "source_ref"))
        voter = _text(row["voter"], "pemilih")
        ref = _text(row["source_ref"], "sumber ballot", 512)
        if voter not in allowed or voter in cast or ref in used_refs:
            raise VotingError("Ballot ganda atau pemilih tidak berhak.")
        ranking = _labels(row["rankings"], len(choices), 1)
        if set(ranking) - set(choices):
            raise VotingError("Ballot memuat pilihan asing.")
        weight, expertise_ref = allowed[voter]
        cast[voter] = {"voter": voter, "rankings": ranking, "weight": weight,
                       "expertise_ref": expertise_ref, "source_ref": ref}
        used_refs.add(ref)

    weighted = [(row["rankings"], row["weight"]) for row in cast.values()]
    total = sum(weight for _, weight in weighted)
    winner, rounds = None, []
    if roster_weight == 0:
        result = "no_eligible_weight"
    elif total < needed:
        result = "quorum_missing"
    else:
        result, winner, rounds = _runoff(weighted, choices)
    return {
        "schema": "ace.weighted-voting.v1", "topic": topic, "status": result, "winner": winner,
        "roster_weight": roster_weight, "required_weight": needed, "participating_weight": total,
        "quorum": {"numerator": fraction.numerator, "denominator": fraction.denominator},
        "eligible_roster": [
            {"voter": voter, "weight": weight, "expertise_ref": ref, "participated": voter in cast}
            for voter, (weight, ref) in sorted(allowed.items())
        ],
        "recusals": [{"voter": key, "source_ref": ref} for key, ref in sorted(recused.items())],
        "ballots": [cast[key] for key in sorted(cast)], "rounds": rounds,
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise VotingError("Berkas suara melampaui batas.")
        result = elect(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "selected")


if __name__ == "__main__":
    raise SystemExit(main())
