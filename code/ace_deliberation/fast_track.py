"""Rehearsal deliberasi cepat dengan batas satu ronde dan kuasa terbatas.

Peserta pengusul, penyanggah dan peninjau harus independen menurut
keluarga yang didaftarkan. Data dan batas biaya dibekukan dalam hash
rencana. Usulan baru layak ditinjau dari ronde ini bila sanggahan
mendapat disposisi spesifik dan aturan cepat punya prasyarat lengkap.
"""
from fractions import Fraction

from ._advanced import InputError, integer, json_main, labels, rows, shape, stamp, text, unique
from .brier_scorer import _rational
from .debate_protocol import _sha

ROLES = ("proponent", "challenger", "reviewer")
DISPOSITIONS = ("mitigated", "sustained", "unresolved")
MAX_BUDGET = 1_000_000


def _plan(raw):
    shape(raw, ("case_id", "case_ref", "opens_at", "closes_at", "budget", "impact",
                "reversible", "prior_ref", "conflict_screen_ref", "seats"))
    if type(raw["reversible"]) is not bool:
        raise InputError("Reversibilitas perlu boolean eksplisit.")
    impact = text(raw["impact"], "kelas dampak")
    if impact not in ("low", "high", "uncertain"):
        raise InputError("Kelas dampak tak dikenal.")
    case_ref = text(raw["case_ref"], "sumber kasus")
    references = {case_ref}
    participants, families = set(), set()
    roster = {}
    for seat in rows(raw["seats"], 3, 3):
        shape(seat, ("role", "participant", "family"))
        role = text(seat["role"], "peran")
        if role not in ROLES or role in roster:
            raise InputError("Setiap peran harus diwakili tepat sekali.")
        roster[role] = {
            "role": role, "participant": unique(text(seat["participant"], "peserta"), participants, "Peserta"),
            "family": unique(text(seat["family"], "keluarga"), families, "Keluarga"),
        }
    opened, closed = stamp(raw["opens_at"]), stamp(raw["closes_at"])
    if opened >= closed:
        raise InputError("Jendela perlu durasi positif.")
    result = {"case_id": text(raw["case_id"], "ID kasus"), "case_ref": case_ref,
              "opens_at": opened.isoformat(), "closes_at": closed.isoformat(),
              "budget": integer(raw["budget"], 1, MAX_BUDGET), "impact": impact,
              "reversible": raw["reversible"], "seats": [roster[role] for role in ROLES]}
    for key in ("prior_ref", "conflict_screen_ref"):
        result[key] = unique(text(raw[key], key), references) if raw[key] is not None else None
    return result, references


def plan_digest(raw):
    plan, _ = _plan(raw)
    return _sha(plan)


def rehearse(raw):
    shape(raw, ("plan", "plan_sha256", "submissions"))
    plan, references = _plan(raw["plan"])
    digest = _sha(plan)
    if raw["plan_sha256"] != digest:
        raise InputError("Rencana tidak sama dengan hash yang disetujui.")
    blockers = []
    if plan["impact"] != "low":
        blockers.append("impact_requires_deeper_review")
    if not plan["reversible"]:
        blockers.append("not_reversible")
    if plan["prior_ref"] is None:
        blockers.append("precedent_missing")
    if plan["conflict_screen_ref"] is None:
        blockers.append("conflict_screen_missing")
    valid = []
    spent = 0
    last = start = stamp(plan["opens_at"])
    close = stamp(plan["closes_at"])
    used = set()
    for index, row in enumerate(rows(raw["submissions"], 0, 3)):
        shape(row, ("role", "participant", "ref", "submitted_at", "cost", "summary", "basis", "disposition"))
        seat = plan["seats"][index]
        if (row["role"], row["participant"]) != (seat["role"], seat["participant"]):
            raise InputError("Peran atau peserta tidak sesuai giliran.")
        when = stamp(row["submitted_at"])
        if when < last or when > close:
            raise InputError("Waktu kontribusi di luar jendela atau urutan.")
        last = when
        spent += integer(row["cost"], 0, plan["budget"])
        if spent > plan["budget"]:
            raise InputError("Biaya ronde melebihi batas.")
        ref = unique(text(row["ref"], "sumber kontribusi"), references)
        basis = sorted(labels(row["basis"], 0, 20, "sumber kontribusi pendahulu"))
        expected = used if index else set()
        if set(basis) != expected:
            raise InputError("Basis perlu mencakup tepat semua kontribusi pendahulu.")
        used.add(ref)
        disposition = row["disposition"]
        if (index < 2 and disposition is not None) or (index == 2 and disposition not in DISPOSITIONS):
            raise InputError("Disposisi hanya dari peninjau dan wajib memakai kategori sah.")
        valid.append({"role": seat["role"], "participant": seat["participant"], "ref": ref,
                      "submitted_at": when.isoformat(), "cost": row["cost"],
                      "summary": text(row["summary"], "ringkasan", 1500), "basis": basis,
                      "disposition": disposition})
    if len(valid) != len(ROLES):
        blockers.append("round_incomplete")
    elif valid[-1]["disposition"] != "mitigated":
        blockers.append(f"objection_{valid[-1]['disposition']}")
    duration = last - start
    elapsed = Fraction(duration.days * 86_400 + duration.seconds) + Fraction(duration.microseconds, 1_000_000)
    return {
        "schema": "ace.deliberation-fast-track.v1", "case_id": plan["case_id"], "plan_sha256": digest,
        "status": "reviewable" if not blockers else "held", "blockers": blockers,
        "next_role": ROLES[len(valid)] if len(valid) < len(ROLES) else None,
        "budget": plan["budget"], "spent": spent, "elapsed_seconds": _rational(elapsed),
        "round": valid, "plan": plan,
    }


def main(argv=None):
    return json_main(argv, __doc__, rehearse)


if __name__ == "__main__":
    raise SystemExit(main())
