"""Rotasikan kursi agar penugasan peran bisa diperiksa tanpa mengambil suara.

Setiap putaran mengisi kebutuhan kursi secara eksak. Pemilihan berbiaya
minimum memakai riwayat peran dan penalti pengulangan langsung. Optimasi
dijalankan per putaran agar keputusan sekarang bisa direproduksi dari
riwayat yang tersedia saat itu.
"""
from collections import Counter
import json
from pathlib import Path

from .debate_protocol import Role


MAX_PEOPLE = 32
MAX_ROUNDS = 32
MAX_HISTORY = 512
MAX_BYTES = 4_000_000
ROLES = tuple(sorted(role.value for role in Role))


class RotationError(ValueError):
    """Rencana rotasi atau bukti penugasan tidak sah."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise RotationError("Field rotasi tidak sesuai skema.")


def _text(value, name, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise RotationError(f"{name} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise RotationError(f"{name} bukan teks UTF-8.") from exc
    return value.strip()


def _number(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise RotationError(f"Jumlah wajib bilangan bulat {low}–{high}.")
    return value


def _roster(raw):
    if not isinstance(raw, list) or not 3 <= len(raw) <= MAX_PEOPLE:
        raise RotationError("Roster harus memiliki 3–32 peserta.")
    roster = {}
    for member in raw:
        _shape(member, ("participant", "eligible_roles"))
        participant = _text(member["participant"], "peserta")
        eligible = member["eligible_roles"]
        if (not isinstance(eligible, list) or not 1 <= len(eligible) <= len(ROLES)
                or any(not isinstance(role, str) or role not in ROLES for role in eligible)
                or len(set(eligible)) != len(eligible) or participant in roster):
            raise RotationError("Kelayakan peran atau peserta tidak sah.")
        roster[participant] = tuple(sorted(eligible))
    return roster


def _history(raw, roster):
    if not isinstance(raw, list) or len(raw) > MAX_HISTORY:
        raise RotationError("Riwayat rotasi melebihi batas.")
    totals = {participant: Counter() for participant in roster}
    previous = {}
    refs = []
    for record in raw:
        _shape(record, ("source_ref", "assignments"))
        ref = _text(record["source_ref"], "sumber riwayat", 512)
        if ref in refs:
            raise RotationError("Rujukan riwayat ganda.")
        refs.append(ref)
        assignments = record["assignments"]
        if not isinstance(assignments, dict) or not assignments or assignments.keys() - roster.keys():
            raise RotationError("Riwayat harus menunjuk peserta dalam roster.")
        previous = {}
        for participant, role in assignments.items():
            if role not in ROLES:
                raise RotationError("Peran riwayat tidak dikenal.")
            totals[participant][role] += 1
            previous[participant] = role
    return totals, previous, refs


def _assign(roster, capacities, counts, previous, repeat_penalty):
    """Dynamic programming dengan kapasitas setiap tiga jenis kursi."""
    members = sorted(roster)
    pending = {tuple(capacities[role] for role in ROLES): (0, ())}
    indexes = {role: index for index, role in enumerate(ROLES)}
    for participant in members:
        updated = {}
        for available, (score, path) in pending.items():
            for role in roster[participant]:
                index = indexes[role]
                if not available[index]:
                    continue
                rest = (*available[:index], available[index] - 1, *available[index + 1:])
                extra = counts[participant][role]
                if previous.get(participant) == role:
                    extra += repeat_penalty
                trial = (score + extra, (*path, role))
                if rest not in updated or trial < updated[rest]:
                    updated[rest] = trial
        pending = updated
    result = pending.get((0, 0, 0))
    if result is None:
        return None
    total, path = result
    return total, dict(zip(members, path))


def rotate(raw):
    _shape(raw, ("roster", "seats", "rounds", "history", "repeat_penalty"))
    roster = _roster(raw["roster"])
    _shape(raw["seats"], ROLES)
    capacities = {role: _number(raw["seats"][role], 1, MAX_PEOPLE) for role in ROLES}
    if sum(capacities.values()) != len(roster):
        raise RotationError("Jumlah kursi wajib sama dengan roster.")
    rounds = _number(raw["rounds"], 1, MAX_ROUNDS)
    penalty = _number(raw["repeat_penalty"], 0, 10_000)
    counts, previous, refs = _history(raw["history"], roster)
    planned = []
    for number in range(1, rounds + 1):
        selected = _assign(roster, capacities, counts, previous, penalty)
        if selected is None:
            return {"schema": "ace.role-rotation.v1", "status": "infeasible", "blocked_round": number,
                    "history_refs": refs, "schedule": planned, "repeat_penalty": penalty}
        score, assignment = selected
        repeated = [name for name, role in assignment.items() if previous.get(name) == role]
        order = {"proponent": 0, "challenger": 1, "reviewer": 2}
        seats = [{"participant": name, "role": role}
                 for name, role in sorted(assignment.items(), key=lambda pair: (order[pair[1]], pair[0]))]
        planned.append({"round": number, "cost": score, "repeated": repeated, "seats": seats})
        for name, role in assignment.items():
            counts[name][role] += 1
        previous = assignment
    return {"schema": "ace.role-rotation.v1", "status": "scheduled", "blocked_round": None,
            "history_refs": refs, "schedule": planned, "repeat_penalty": penalty,
            "role_counts_after": {name: {role: counts[name][role] for role in ROLES}
                                  for name in sorted(roster)}}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            blob = handle.read(MAX_BYTES + 1)
        if len(blob) > MAX_BYTES:
            raise RotationError("Berkas rotasi melampaui batas.")
        result = rotate(json.loads(blob))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "scheduled")


if __name__ == "__main__":
    raise SystemExit(main())
