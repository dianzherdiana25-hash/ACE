"""Susun undangan saksi dengan pertanyaan terbatas dan catat jawaban bersumber.

Paket undangan terikat hash dan tenggat. Pemeriksa hanya menerima
testimoni dari saksi yang tercantum, untuk daftar pertanyaan yang sudah
ditetapkan. Program mengeluarkan paket lokal untuk persetujuan manusia dan
tidak menghubungi organ atau layanan.
"""
import json
from pathlib import Path

from .brier_scorer import _stamp
from .debate_protocol import _sha


MAX_ITEMS = 120
MAX_BYTES = 4_000_000


class WitnessError(ValueError):
    """Undangan atau testimoni keluar dari kontrak yang tercatat."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise WitnessError("Field undangan saksi tidak sesuai skema.")


def _text(value, label, maximum=112):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise WitnessError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise WitnessError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _sequence(raw, minimum, maximum=MAX_ITEMS):
    if not isinstance(raw, list) or not minimum <= len(raw) <= maximum:
        raise WitnessError("Larik rekaman di luar batas.")
    return raw


def _refs(raw, minimum=0):
    result = sorted(_text(value, "rujukan", 512) for value in _sequence(raw, minimum))
    if len(result) != len(set(result)):
        raise WitnessError("Rujukan ganda.")
    return result


def invite(raw):
    _shape(raw, ("invitation_id", "case_id", "topic", "issued_at", "deadline", "expert", "questions"))
    witness = raw["expert"]
    _shape(witness, ("id", "topics", "credential_ref", "conflicts"))
    topic = _text(raw["topic"], "topik")
    topics = _refs(witness["topics"], 1)
    conflicts = _refs(witness["conflicts"])
    if topic not in topics or topic in conflicts:
        raise WitnessError("Kewenangan topik tidak cukup atau ada konflik.")
    start, deadline = _stamp(raw["issued_at"]), _stamp(raw["deadline"])
    if deadline <= start:
        raise WitnessError("Tenggat undangan harus setelah waktu penerbitan.")
    questions = {}
    question_refs = set()
    for row in _sequence(raw["questions"], 1):
        _shape(row, ("id", "question", "source_ref"))
        identifier = _text(row["id"], "ID pertanyaan")
        reference = _text(row["source_ref"], "sumber pertanyaan", 512)
        if identifier in questions or reference in question_refs:
            raise WitnessError("Pertanyaan atau sumber ganda.")
        questions[identifier] = {"id": identifier, "source_ref": reference,
                                 "question": _text(row["question"], "isi pertanyaan", 5_000)}
        question_refs.add(reference)
    body = {
        "schema": "ace.expert-witness-invitation.v1",
        "invitation_id": _text(raw["invitation_id"], "ID undangan"),
        "case_id": _text(raw["case_id"], "ID kasus"), "topic": topic, "issued_at": start.isoformat(),
        "deadline": deadline.isoformat(), "witness_id": _text(witness["id"], "ID saksi"),
        "credential_ref": _text(witness["credential_ref"], "rujukan kompetensi", 512),
        "questions": [questions[key] for key in sorted(questions)],
    }
    return {**body, "sha256": _sha(body)}


def verify_packet(packet, request):
    """Periksa byte undangan terhadap permintaan sumber yang dibawa operator."""
    try:
        return isinstance(packet, dict) and packet == invite(request)
    except (ValueError, RecursionError):
        return False


def examine(raw):
    _shape(raw, ("request", "testimony", "as_of"))
    invitation = invite(raw["request"])
    now = _stamp(raw["as_of"])
    issued, deadline = _stamp(invitation["issued_at"]), _stamp(invitation["deadline"])
    if now < issued:
        raise WitnessError("Undangan belum tersedia pada as_of.")
    questions = {row["id"]: row for row in invitation["questions"]}
    answers = {}
    source_refs = {row["source_ref"] for row in questions.values()} | {invitation["credential_ref"]}
    for record in _sequence(raw["testimony"], 0):
        _shape(record, ("invitation_sha256", "witness_id", "question_id", "received_at",
                        "status", "statement", "evidence_refs", "testimony_ref"))
        if record["invitation_sha256"] != invitation["sha256"] or record["witness_id"] != invitation["witness_id"]:
            raise WitnessError("Testimoni tidak terikat pada undangan dan saksi yang sama.")
        identifier = _text(record["question_id"], "ID pertanyaan")
        edge = _text(record["testimony_ref"], "sumber testimoni", 512)
        at = _stamp(record["received_at"])
        if (identifier not in questions or identifier in answers or edge in source_refs
                or not issued <= at <= now):
            raise WitnessError("Jawaban ganda, asing, atau di luar waktu yang tercatat.")
        state = record["status"]
        if state not in ("answered", "abstained"):
            raise WitnessError("Status jawaban tak dikenal.")
        evidence = _refs(record["evidence_refs"])
        if state == "answered" and not evidence:
            raise WitnessError("Jawaban substantif wajib merujuk bukti.")
        source_refs.add(edge)
        answers[identifier] = {
            "question_id": identifier, "question_ref": questions[identifier]["source_ref"],
            "received_at": at.isoformat(), "status": state, "in_window": at <= deadline,
            "statement": _text(record["statement"], "isi testimoni", 8_000), "testimony_ref": edge,
            "evidence_refs": evidence,
        }
    missing = [key for key in sorted(questions)
               if key not in answers or not answers[key]["in_window"] or answers[key]["status"] != "answered"]
    if not missing:
        status = "complete"
    elif now > deadline:
        status = "expired_incomplete"
    else:
        status = "awaiting_testimony"
    return {"schema": "ace.expert-witness-record.v1", "as_of": now.isoformat(),
            "status": status, "invitation": invitation, "open_questions": missing,
            "testimony": [answers[key] for key in sorted(answers)]}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--invite-only", action="store_true")
    modes.add_argument("--verify-packet", action="store_true",
                       help="Masukan memuat packet dan request yang akan dibandingkan.")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise WitnessError("Masukan saksi melampaui batas.")
        document = json.loads(data)
        if args.verify_packet:
            _shape(document, ("packet", "request"))
            valid = verify_packet(document["packet"], document["request"])
            print(json.dumps({"valid": valid}))
            return int(not valid)
        result = invite(document) if args.invite_only else examine(document)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
