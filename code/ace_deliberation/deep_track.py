"""Putar ulang deliberasi mendalam dengan lima putaran berantai hash.

Ronde memiliki peran dan batas biaya yang sudah ditetapkan. Sanggahan
yang dibuka di ronde tantangan tetap tercatat setelah disposisi,
bersama sumber tanggapannya. Sintesis layak ditelaah ketika kelima
ronde tercatat dan semua sanggahan memiliki disposisi yang sah.
"""
from ._advanced import InputError, integer, json_main, labels, rows, shape, stamp, text, unique
from .debate_protocol import _sha


PHASES = (("framing", "chair"), ("evidence", "investigator"), ("challenge", "challenger"),
          ("response", "respondent"), ("synthesis", "reviewer"))
MAX_UNITS = 1_000_000


def _plan(raw):
    shape(raw, ("case_id", "case_ref", "opens_at", "closes_at", "budget", "round_caps", "roster"))
    opened, closes = stamp(raw["opens_at"]), stamp(raw["closes_at"])
    if opened >= closes:
        raise InputError("Jendela perlu durasi positif.")
    phases = [name for name, _ in PHASES]
    roles = [role for _, role in PHASES]
    shape(raw["round_caps"], phases)
    shape(raw["roster"], roles)
    participants, families = set(), set()
    roster = {}
    for role in roles:
        seat = raw["roster"][role]
        shape(seat, ("participant", "family"))
        roster[role] = {"participant": unique(text(seat["participant"], "peserta"), participants, "Peserta"),
                        "family": unique(text(seat["family"], "keluarga"), families, "Keluarga")}
    budget = integer(raw["budget"], 1, MAX_UNITS)
    return {"case_id": text(raw["case_id"], "kasus"), "case_ref": text(raw["case_ref"], "sumber kasus"),
            "opens_at": opened.isoformat(), "closes_at": closes.isoformat(), "budget": budget,
            "round_caps": {phase: integer(raw["round_caps"][phase], 0, budget) for phase in phases}, "roster": roster}


def plan_digest(raw):
    return _sha(_plan(raw))


def round_digest(round_record):
    """Hitung hash payload ronde, termasuk hash yang mendahuluinya."""
    return _sha(round_record)


def rehearse(raw):
    shape(raw, ("plan", "anchor_sha256", "rounds"))
    plan = _plan(raw["plan"])
    previous = plan_digest(plan)
    if raw["anchor_sha256"] != previous:
        raise InputError("Hash rencana berbeda dari anchor.")
    opened, closed = stamp(plan["opens_at"]), stamp(plan["closes_at"])
    entries, transcript = [], []
    objections = {}
    refs = {plan["case_ref"]}
    published_sources = set()
    last, spent = opened, 0
    for index, row in enumerate(rows(raw["rounds"], 0, len(PHASES))):
        shape(row, ("payload", "sha256"))
        payload = row["payload"]
        shape(payload, ("phase", "participant", "at", "ref", "summary", "cost", "source_refs",
                        "parent_sha256", "new_objections", "responses"))
        phase, role = PHASES[index]
        if payload["phase"] != phase or payload["participant"] != plan["roster"][role]["participant"]:
            raise InputError("Ronde atau peserta tidak sesuai rencana.")
        if payload["parent_sha256"] != previous or row["sha256"] != round_digest(payload):
            raise InputError("Rantai hash ronde tidak cocok.")
        when = stamp(payload["at"])
        if when < last or when > closed:
            raise InputError("Waktu ronde di luar urutan atau jendela.")
        last = when
        cost = integer(payload["cost"], 0, plan["round_caps"][phase])
        spent += cost
        if spent > plan["budget"]:
            raise InputError("Biaya kumulatif melebihi anggaran.")
        ref = unique(text(payload["ref"], "rujukan ronde"), refs)
        sources = labels(payload["source_refs"], 1, 30, "sumber ronde")
        if ref in sources or ref in published_sources:
            raise InputError("Rujukan ronde hanya tersedia setelah ronde dicatat.")
        published_sources.update(sources)
        if index and entries[-1] not in sources:
            raise InputError("Sumber wajib menunjuk ronde sebelumnya.")
        new_objections = rows(payload["new_objections"], 0, 30)
        replies = rows(payload["responses"], 0, 30)
        if (phase == "challenge" and not new_objections) or (phase != "challenge" and new_objections):
            raise InputError("Sanggahan hanya boleh dan wajib dibuka di ronde tantangan.")
        if replies and phase != "response":
            raise InputError("Tanggapan hanya boleh diberikan di ronde jawaban.")
        for objection in new_objections:
            shape(objection, ("id", "summary", "evidence_ref"))
            key = text(objection["id"], "ID sanggahan")
            if key in objections:
                raise InputError("ID sanggahan ganda.")
            source = text(objection["evidence_ref"], "bukti sanggahan")
            if source not in sources or source in entries:
                raise InputError("Bukti sanggahan perlu rujukan langsung di sumber ronde.")
            objections[key] = {"id": key, "summary": text(objection["summary"], "sanggahan", 2000),
                               "evidence_ref": source, "raised_by": ref, "response": None}
        for reply in replies:
            shape(reply, ("id", "disposition", "ref"))
            key = text(reply["id"], "ID tanggapan")
            disposition = reply["disposition"]
            response_ref = text(reply["ref"], "rujukan tanggapan")
            if key not in objections or objections[key]["response"] is not None:
                raise InputError("Tanggapan harus menunjuk satu sanggahan terbuka.")
            if disposition not in ("mitigated", "sustained") or response_ref not in sources or response_ref in entries:
                raise InputError("Disposisi atau rujukan tanggapan tidak sah.")
            objections[key]["response"] = {"disposition": disposition, "source_ref": response_ref,
                                           "responded_by": ref}
        entries.append(ref)
        previous = row["sha256"]
        transcript.append({"phase": phase, "ref": ref, "sha256": previous,
                           "at": when.isoformat(), "cost": cost, "participant": payload["participant"],
                           "summary": text(payload["summary"], "ringkasan", 2000), "source_refs": sorted(sources),
                           "open_objections": sorted(key for key, item in objections.items() if item["response"] is None)})
    blockers = []
    if len(transcript) != len(PHASES):
        blockers.append("incomplete")
    if any(item["response"] is None for item in objections.values()):
        blockers.append("objections_open")
    if any(item["response"] and item["response"]["disposition"] == "sustained" for item in objections.values()):
        blockers.append("objections_sustained")
    return {
        "schema": "ace.deliberation-deep-track.v1", "case_id": plan["case_id"], "case_ref": plan["case_ref"],
        "head_sha256": previous, "anchor_sha256": raw["anchor_sha256"], "rounds": transcript,
        "next_round": PHASES[len(transcript)][0] if len(transcript) < len(PHASES) else None,
        "spent": spent, "budget": plan["budget"], "blockers": blockers,
        "status": "reviewable" if not blockers else "held",
        "dissent": [objections[key] for key in sorted(objections)],
    }


def main(argv=None):
    return json_main(argv, __doc__, rehearse)


if __name__ == "__main__":
    raise SystemExit(main())
