"""Pisahkan debat yang masih bergerak dari putaran buntu yang perlu jeda.

Sinyal buntu berasal dari distribusi suara berulang tanpa bukti baru.
Perubahan roster memutus pola agar kelompok yang berbeda tidak
dibandingkan. Jeda dihitung dari siklus deteksi pertama. Semuanya berupa
rencana dan tidak mengubah jadwal organ atau putusan nyata.
"""
from collections import Counter, deque
from math import ceil
from fractions import Fraction
import json
from pathlib import Path


MAX_ROUNDS = 1_000
MAX_VOTERS = 300
MAX_CYCLE = 10**9
MAX_BYTES = 4_000_000


class DeadlockError(ValueError):
    """Rekaman putaran atau kebijakan pendinginan tidak sah."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise DeadlockError("Field kebuntuan tidak sesuai skema.")


def _text(value, label, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise DeadlockError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise DeadlockError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _int(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise DeadlockError("Nilai siklus atau batas evaluasi tidak sah.")
    return value


def _items(raw, minimum, maximum):
    if not isinstance(raw, list) or not minimum <= len(raw) <= maximum:
        raise DeadlockError("Jumlah record kebuntuan melampaui batas.")
    return raw


def _threshold(raw):
    _shape(raw, ("numerator", "denominator"))
    denominator = _int(raw["denominator"], 1, 1_000)
    numerator = _int(raw["numerator"], 1, denominator)
    result = Fraction(numerator, denominator)
    if result <= Fraction(1, 2):
        raise DeadlockError("Ambang konsensus harus lebih dari separuh.")
    return result


def _signature(choices, raw):
    if not isinstance(raw, dict) or not 2 <= len(raw) <= MAX_VOTERS:
        raise DeadlockError("Putaran memerlukan peta posisi peserta.")
    positions = {_text(voter, "pemilih"): _text(choice, "pilihan") for voter, choice in raw.items()}
    if len(positions) != len(raw) or set(positions.values()) - choices:
        raise DeadlockError("Pemilih ganda atau pilihan asing.")
    counts = Counter(positions.values())
    return tuple(sorted(positions)), tuple(sorted(counts.items()))


def _detect(trail, repetitions):
    if len(trail) < repetitions:
        return None
    tail = list(trail)
    steady = tail[-repetitions:]
    if len({row["signature"] for row in steady}) == 1:
        return "unchanged", steady
    if len(tail) >= 2 * repetitions:
        alternating = tail[-2 * repetitions:]
        first, second = (row["signature"] for row in alternating[:2])
        if first != second and all(row["signature"] == (first, second)[index % 2]
                                   for index, row in enumerate(alternating)):
            return "alternating", alternating
    return None


def recommend(raw):
    _shape(raw, ("rounds", "choices", "as_of_cycle", "policy"))
    now = _int(raw["as_of_cycle"], 0, MAX_CYCLE)
    labels = [_text(label, "pilihan") for label in _items(raw["choices"], 2, 30)]
    if len(set(labels)) != len(labels):
        raise DeadlockError("Pilihan ganda.")
    choices = set(labels)
    policy = raw["policy"]
    _shape(policy, ("repetitions", "cooldown_cycles", "consensus"))
    repetitions = _int(policy["repetitions"], 2, 20)
    cooldown = _int(policy["cooldown_cycles"], 1, 100_000)
    threshold = _threshold(policy["consensus"])
    trail = deque(maxlen=2 * repetitions)
    seen_refs, known_evidence = set(), set()
    last_cycle = -1
    previous_roster = None
    detected = None
    cooldowns = []
    trace = []
    for row in _items(raw["rounds"], 0, MAX_ROUNDS):
        _shape(row, ("cycle", "votes", "evidence_refs", "source_ref"))
        cycle = _int(row["cycle"], last_cycle + 1, now)
        last_cycle = cycle
        source = _text(row["source_ref"], "rujukan putaran", 512)
        evidence = [_text(ref, "rujukan bukti", 512) for ref in _items(row["evidence_refs"], 0, 200)]
        if source in seen_refs or len(set(evidence)) != len(evidence):
            raise DeadlockError("Rujukan putaran/bukti ganda.")
        seen_refs.add(source)
        roster, signature = _signature(choices, row["votes"])
        fresh = sorted(set(evidence) - known_evidence)
        known_evidence.update(evidence)
        reached = max(weight for _, weight in signature) >= ceil(len(roster) * threshold)
        if fresh or roster != previous_roster or reached or (
            detected is not None and cycle >= detected["resume_at_cycle"]
        ):
            trail.clear()
            if detected is not None:
                reason = ("consensus" if reached else "new_evidence" if fresh else
                          "roster_changed" if roster != previous_roster else "resumed")
                cooldowns.append({**detected, "closed_at_cycle": cycle, "closed_reason": reason})
            detected = None
        previous_roster = roster
        entry = {"cycle": cycle, "signature": signature, "source_ref": source}
        # Putaran yang membawa bukti baru menjadi dasar streak baru.
        if not reached:
            trail.append(entry)
            if detected is None and (pattern := _detect(trail, repetitions)) is not None:
                kind, witness = pattern
                detected = {"kind": kind, "detected_at_cycle": cycle, "resume_at_cycle": cycle + cooldown,
                            "source_refs": [item["source_ref"] for item in witness]}
        trace.append({"cycle": cycle, "source_ref": source, "new_evidence_refs": fresh,
                      "tallies": dict(signature), "consensus_reached": reached})

    if not trace:
        state = "no_rounds"
    elif trace[-1]["consensus_reached"]:
        state = "consensus_recorded"
    elif detected is None:
        state = "continue"
    else:
        state = "cooldown" if now < detected["resume_at_cycle"] else "cooldown_elapsed"
    return {"schema": "ace.deadlock-breaker.v1", "status": state, "as_of_cycle": now,
            "deadlock": detected, "past_cooldowns": cooldowns, "observation_rounds": trace}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise DeadlockError("Berkas kebuntuan melampaui batas.")
        print(json.dumps(recommend(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
