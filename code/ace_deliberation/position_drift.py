"""Ukur perubahan posisi antar-putaran pada peserta dan isu yang sama.

Perpindahan peserta dan perpindahan distribusi dilaporkan sebagai metrik
berbeda. Dua peserta yang bertukar posisi bisa memiliki drift individual
meski distribusi agregat tetap. Record yang hilang atau baru tampil
terpisah dari pembanding yang lengkap.
"""
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _rational


MAX_ROUNDS = 120
MAX_ISSUES = 100
MAX_VOTES = 2_000
MAX_BYTES = 8_000_000
VALUES = {"oppose": -1, "undecided": 0, "support": 1}


class DriftError(ValueError):
    """Catatan putaran atau posisi tidak dapat diperbandingkan."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise DriftError("Field drift tidak sesuai skema.")


def _text(raw, label, limit=120):
    if not isinstance(raw, str) or not raw.strip() or len(raw) > limit or "\0" in raw:
        raise DriftError(f"{label} tidak sah.")
    try:
        raw.encode("utf-8")
    except UnicodeError as exc:
        raise DriftError(f"{label} bukan teks UTF-8.") from exc
    return raw.strip()


def _rows(raw, low, high):
    if not isinstance(raw, list) or not low <= len(raw) <= high:
        raise DriftError("Jumlah entri drift melampaui batas.")
    return raw


def _pair(before, after, issues):
    previous, current = before["positions"], after["positions"]
    common = sorted(previous.keys() & current.keys())
    losses = sorted(previous.keys() - current.keys())
    arrivals = sorted(current.keys() - previous.keys())
    data = {issue: {"first": Counter(), "second": Counter(), "n": 0,
                    "movement": 0, "net_shift": 0, "reversals": 0} for issue in issues}
    changed = []
    movement = Fraction(0)
    total = 0
    for actor, issue in common:
        (a, left), (b, right) = previous[actor, issue], current[actor, issue]
        profile = data[issue]
        profile["first"][a] += 1
        profile["second"][b] += 1
        profile["n"] += 1
        weight, ref = issues[issue]
        total += weight
        if a == b:
            continue
        delta = VALUES[b] - VALUES[a]
        profile["movement"] += abs(delta)
        profile["net_shift"] += delta
        profile["reversals"] += int(abs(delta) == 2)
        movement += Fraction(abs(delta) * weight, 2)
        changed.append({"participant": actor, "issue": issue, "issue_ref": ref,
                        "before": a, "after": b, "standardized_shift": _rational(Fraction(delta, 2)),
                        "reversal": abs(delta) == 2, "before_ref": left, "after_ref": right})

    profiles = []
    variation_sum = Fraction(0)
    for issue, values in sorted(data.items()):
        n = values["n"]
        distances = sum(abs(values["first"][stance] - values["second"][stance]) for stance in VALUES)
        tv = Fraction(distances, 2 * n) if n else None
        if tv is not None:
            variation_sum += tv * issues[issue][0] * n
        profiles.append({
            "issue": issue, "paired_count": n, "source_ref": issues[issue][1],
            "total_variation": _rational(tv) if tv is not None else None,
            "individual_drift": _rational(Fraction(values["movement"], n * 2)) if n else None,
            "net_shift": _rational(Fraction(values["net_shift"], n * 2)) if n else None,
            "reversals": values["reversals"],
        })
    return {
        "before_round": before["number"], "before_ref": before["source_ref"],
        "after_round": after["number"], "after_ref": after["source_ref"],
        "paired_count": len(common), "weighted_individual_drift": _rational(movement / total) if total else None,
        "weighted_distribution_drift": _rational(variation_sum / total) if total else None, "changes": changed,
        "arrivals": [{"participant": actor, "issue": issue, "source_ref": current[actor, issue][1]} for actor, issue in arrivals],
        "departures": [{"participant": actor, "issue": issue, "source_ref": previous[actor, issue][1]} for actor, issue in losses],
        "issues": profiles,
    }


def measure(raw):
    _shape(raw, ("issues", "rounds"))
    issues, refs = {}, set()
    for row in _rows(raw["issues"], 1, MAX_ISSUES):
        _shape(row, ("id", "weight", "source_ref"))
        identifier, ref = _text(row["id"], "isu"), _text(row["source_ref"], "sumber isu", 512)
        weight = row["weight"]
        if identifier in issues or ref in refs or type(weight) is not int or not 1 <= weight <= 1_000:
            raise DriftError("Bobot, identitas, atau sumber isu tidak sah.")
        issues[identifier] = weight, ref
        refs.add(ref)

    rounds, numbers = [], set()
    for row in _rows(raw["rounds"], 0, MAX_ROUNDS):
        _shape(row, ("number", "source_ref", "positions"))
        number = row["number"]
        ref = _text(row["source_ref"], "sumber putaran", 512)
        if type(number) is not int or not 1 <= number <= 1_000_000 or number in numbers or ref in refs:
            raise DriftError("Nomor atau rujukan putaran tidak sah.")
        numbers.add(number)
        refs.add(ref)
        observations = {}
        for vote in _rows(row["positions"], 0, MAX_VOTES):
            _shape(vote, ("participant", "issue", "position", "source_ref"))
            actor, issue = (_text(vote[key], key) for key in ("participant", "issue"))
            source = _text(vote["source_ref"], "sumber posisi", 512)
            stance = vote["position"]
            key = actor, issue
            if key in observations or issue not in issues or not isinstance(stance, str) or stance not in VALUES or source in refs:
                raise DriftError("Posisi ganda atau merujuk isu yang asing.")
            observations[key] = stance, source
            refs.add(source)
        rounds.append({"number": number, "source_ref": ref, "positions": observations})
    rounds.sort(key=lambda row: row["number"])
    return {"schema": "ace.position-drift.v1", "round_count": len(rounds),
            "comparisons": [_pair(before, after, issues) for before, after in zip(rounds, rounds[1:])]}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise DriftError("Berkas drift melampaui batas.")
        print(json.dumps(measure(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
