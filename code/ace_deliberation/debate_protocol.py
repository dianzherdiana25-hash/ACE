"""Batasi keputusan internal pada debat yang selesai dan dapat diputar ulang.

Program menerima kontribusi terstruktur. Urutan giliran disepakati dalam
rencana. Penutupan tidak menghapus sanggahan, dan batas anggaran menahan
keputusan jika putaran wajib belum lengkap.
"""
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path


MAX_TURNS = 2_000
MAX_TEXT = 16_384
MAX_REFS = 128
MAX_INPUT_BYTES = 4_000_000


class DebateError(ValueError):
    """Rencana atau transisi debat melanggar kontrak."""


class Role(StrEnum):
    PROPONENT = "proponent"
    CHALLENGER = "challenger"
    REVIEWER = "reviewer"


class Move(StrEnum):
    ARGUMENT = "argument"
    OBJECTION = "objection"
    RESPONSE = "response"
    SYNTHESIS = "synthesis"


_ALLOWED = {
    Role.PROPONENT: {Move.ARGUMENT, Move.RESPONSE},
    Role.CHALLENGER: {Move.OBJECTION, Move.ARGUMENT},
    Role.REVIEWER: {Move.SYNTHESIS, Move.OBJECTION},
}


def _text(value, name, limit=MAX_TEXT):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise DebateError(f"{name} harus berupa teks nonkosong hingga {limit} karakter.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise DebateError(f"{name} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _nat(value, name, minimum=0, maximum=MAX_TURNS):
    if type(value) is not int or not minimum <= value <= maximum:
        raise DebateError(f"{name} harus bilangan bulat {minimum}–{maximum}.")
    return value


def _object(value, obligatory, optional=()):
    if not isinstance(value, dict) or not set(obligatory) <= value.keys():
        raise DebateError("Objek debat belum lengkap.")
    if value.keys() - set(obligatory) - set(optional):
        raise DebateError("Objek debat memuat field yang tidak dikenal.")
    return value


def _refs(values, label):
    if not isinstance(values, list) or len(values) > MAX_REFS:
        raise DebateError(f"{label} harus larik hingga {MAX_REFS} rujukan.")
    refs = tuple(_text(value, label, 512) for value in values)
    if len(set(refs)) != len(refs):
        raise DebateError(f"{label} ganda.")
    return refs


def _sha(record):
    wire = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(wire.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Seat:
    participant: str
    role: Role

    @classmethod
    def from_dict(cls, value):
        _object(value, ("participant", "role"))
        try:
            role = Role(value["role"])
        except ValueError as exc:
            raise DebateError("Peran kursi tidak dikenal.") from exc
        return cls(_text(value["participant"], "participant", 80), role)

    def as_dict(self):
        return {"participant": self.participant, "role": self.role.value}


@dataclass(frozen=True, slots=True)
class DebatePlan:
    debate_id: str
    question: str
    seats: tuple[Seat, ...]
    rounds: int
    budget: int

    @classmethod
    def from_dict(cls, raw):
        _object(raw, ("debate_id", "question", "seats", "rounds", "budget"))
        seats = raw["seats"]
        if not isinstance(seats, list) or not 3 <= len(seats) <= 32:
            raise DebateError("Rencana memerlukan 3–32 kursi.")
        parsed = tuple(Seat.from_dict(seat) for seat in seats)
        if len({seat.participant for seat in parsed}) != len(parsed):
            raise DebateError("Peserta hanya boleh memegang satu kursi.")
        if {seat.role for seat in parsed} != set(Role):
            raise DebateError("Rencana wajib memiliki pengusul, penyanggah, dan peninjau.")
        if parsed[0].role != Role.PROPONENT or parsed[-1].role != Role.REVIEWER:
            raise DebateError("Giliran dimulai pengusul dan ditutup peninjau.")
        rounds = _nat(raw["rounds"], "rounds", 1, 32)
        budget = _nat(raw["budget"], "budget", 1, 10_000_000)
        return cls(_text(raw["debate_id"], "debate_id", 80),
                   _text(raw["question"], "question"), parsed, rounds, budget)

    def as_dict(self):
        return {
            "debate_id": self.debate_id,
            "question": self.question,
            "seats": [seat.as_dict() for seat in self.seats],
            "rounds": self.rounds,
            "budget": self.budget,
        }


@dataclass(frozen=True, slots=True)
class Turn:
    turn_id: str
    participant: str
    move: Move
    statement: str
    targets: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    cost: int

    @classmethod
    def from_dict(cls, raw):
        _object(raw, ("turn_id", "participant", "move", "statement", "cost"),
                ("targets", "evidence_refs"))
        try:
            move = Move(raw["move"])
        except ValueError as exc:
            raise DebateError("Jenis kontribusi tidak dikenal.") from exc
        return cls(_text(raw["turn_id"], "turn_id", 80),
                   _text(raw["participant"], "participant", 80), move,
                   _text(raw["statement"], "statement"),
                   _refs(raw.get("targets", []), "targets"),
                   _refs(raw.get("evidence_refs", []), "evidence_refs"),
                   _nat(raw["cost"], "cost", 1, 10_000_000))

    def as_dict(self):
        return {
            "turn_id": self.turn_id,
            "participant": self.participant,
            "move": self.move.value,
            "statement": self.statement,
            "targets": list(self.targets),
            "evidence_refs": list(self.evidence_refs),
            "cost": self.cost,
        }


class DebateProtocol:
    """Mesin giliran sinkron dengan transcript deterministik untuk satu rencana."""

    def __init__(self, plan):
        self.plan = DebatePlan.from_dict(plan)
        self._turns = {}
        self._spent = 0
        self._decision = None

    @property
    def next_turn(self):
        if self._decision is not None:
            return None
        turn = len(self._turns)
        round_index, seat_index = divmod(turn, len(self.plan.seats))
        if round_index >= self.plan.rounds:
            return None
        seat = self.plan.seats[seat_index]
        return {"round": round_index + 1, **seat.as_dict()}

    @property
    def spent(self):
        return self._spent

    def submit(self, raw):
        expected = self.next_turn
        if expected is None:
            raise DebateError("Giliran debat sudah lengkap atau debat sudah ditutup.")
        turn = Turn.from_dict(raw)
        if turn.participant != expected["participant"]:
            raise DebateError("Kontribusi tiba di luar giliran.")
        role = Role(expected["role"])
        if turn.move not in _ALLOWED[role]:
            raise DebateError("Kontribusi tidak diizinkan bagi peran ini.")
        if turn.turn_id in self._turns:
            raise DebateError("turn_id ganda.")
        self._validate_targets(turn, role)
        if self._spent + turn.cost > self.plan.budget:
            raise DebateError("Kontribusi melampaui anggaran rencana.")
        self._turns[turn.turn_id] = turn
        self._spent += turn.cost
        return {"round": expected["round"], "role": expected["role"], **turn.as_dict()}

    def _validate_targets(self, turn, role):
        if turn.move != Move.ARGUMENT and not turn.targets:
            raise DebateError("Kontribusi ini perlu merujuk giliran sebelumnya.")
        if any(target not in self._turns for target in turn.targets):
            raise DebateError("Kontribusi merujuk giliran yang belum ada.")
        targets = [self._turns[ref] for ref in turn.targets]
        if turn.move in (Move.OBJECTION, Move.RESPONSE) and any(
            prior.participant == turn.participant for prior in targets
        ):
            raise DebateError("Sanggahan dan jawaban wajib merujuk peserta lain.")
        if turn.move == Move.RESPONSE and any(prior.move != Move.OBJECTION for prior in targets):
            raise DebateError("Jawaban hanya boleh menyasar sanggahan.")
        if role == Role.CHALLENGER and turn.move != Move.OBJECTION and not any(
            prior.move == Move.OBJECTION and prior.participant == turn.participant
            for prior in self._turns.values()
        ):
            raise DebateError("Kontribusi pertama penyanggah wajib berupa sanggahan.")

    def close(self, raw):
        if self._decision is not None or self.next_turn is not None:
            raise DebateError("Keputusan hanya bisa dicatat sekali setelah semua giliran.")
        _object(raw, ("outcome", "rationale", "basis_turns"))
        outcome = raw["outcome"]
        if outcome not in ("adopt", "reject", "defer"):
            raise DebateError("Outcome putusan tidak dikenal.")
        rationale = _text(raw["rationale"], "rationale")
        basis = _refs(raw["basis_turns"], "basis_turns")
        if not basis or any(ref not in self._turns for ref in basis):
            raise DebateError("Putusan wajib merujuk giliran yang sudah tercatat.")
        if not any(self._turns[ref].move == Move.SYNTHESIS for ref in basis):
            raise DebateError("Putusan wajib merujuk sintesis peninjau.")
        objections = {
            turn.turn_id for turn in self._turns.values() if turn.move == Move.OBJECTION
        }
        addressed = {
            target
            for turn in self._turns.values()
            if turn.move in (Move.RESPONSE, Move.SYNTHESIS)
            for target in turn.targets
        }
        if outcome == "adopt" and objections - addressed:
            raise DebateError("Putusan adopsi tertahan oleh sanggahan yang belum ditanggapi.")
        self._decision = (outcome, rationale, basis)
        return self.report()["decision"]

    def report(self):
        decision = None
        if self._decision is not None:
            outcome, rationale, basis = self._decision
            decision = {"outcome": outcome, "rationale": rationale, "basis_turns": list(basis)}
        encoded = {
            "schema": "ace.debate-protocol.v1",
            "plan": self.plan.as_dict(),
            "turns": [item.as_dict() for item in self._turns.values()],
            "spent": self._spent,
            "next_turn": self.next_turn,
            "dissent_turns": [item.turn_id for item in self._turns.values()
                              if item.move == Move.OBJECTION],
            "decision": decision,
        }
        return {**encoded, "sha256": _sha(encoded)}


def replay(raw):
    """Jalankan masukan terstruktur kembali sampai titik terakhir yang tercatat."""
    _object(raw, ("plan", "turns"), ("decision",))
    turns = raw["turns"]
    if not isinstance(turns, list) or len(turns) > MAX_TURNS:
        raise DebateError("Daftar giliran melebihi batas replay.")
    protocol = DebateProtocol(raw["plan"])
    for turn in turns:
        protocol.submit(turn)
    if raw.get("decision") is not None:
        protocol.close(raw["decision"])
    return protocol.report()


def verify_report(report):
    """Verifikasi hash dan bahwa laporan terbangun kembali dari masukan yang sama."""
    if not isinstance(report, dict):
        return False
    try:
        original = {key: report[key] for key in ("plan", "turns", "decision")}
        return replay(original) == report
    except (ValueError, KeyError, TypeError):
        return False


def main(argv=None):
    """Titik masuk lokal membaca berkas masukan dan mencetak hasil replay."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--verify-report", action="store_true")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            payload = stream.read(MAX_INPUT_BYTES + 1)
        if len(payload) > MAX_INPUT_BYTES:
            raise DebateError("Berkas replay melampaui batas ukuran.")
        raw = json.loads(payload)
        if args.verify_report:
            valid = verify_report(raw)
            print(json.dumps({"valid": valid}))
            return int(not valid)
        print(json.dumps(replay(raw), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
