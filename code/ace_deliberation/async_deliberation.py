"""Lanjutkan giliran deliberasi lintas siklus dari checkpoint yang bisa direplay.

Pengajuan lebih awal ditahan sampai giliran yang sesuai. Setiap giliran
mempunyai tenggat dalam satuan siklus dan penolakan tidak mengulur tenggat.
Checkpoint membawa masukan serta hasil yang diverifikasi dengan replay
sebelum sesi diteruskan.
"""
from copy import deepcopy
import json
from pathlib import Path

from .debate_protocol import DebateError, DebateProtocol, MAX_INPUT_BYTES, Turn, _sha


MAX_EVENTS = 4_000
MAX_CYCLE = 10**9
MAX_WINDOW = 10_000


class AsyncError(ValueError):
    """Checkpoint atau urutan siklus tidak dapat diteruskan."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise AsyncError("Field deliberasi asinkron tidak sesuai skema.")


def _int(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise AsyncError("Siklus atau batas tunggu di luar rentang.")
    return value


class _AsyncState:
    def __init__(self, plan, first_cycle, patience):
        self.protocol = DebateProtocol(plan)
        self.slot_rank = {
            (number, seat.participant): slot
            for slot, (number, seat) in enumerate(
                (number, seat) for number in range(1, self.protocol.plan.rounds + 1)
                for seat in self.protocol.plan.seats
            )
        }
        self.rank = 0
        self.deadline = first_cycle + patience
        self.patience = patience
        self.pending = {}
        self.receipts = []
        self.expired = False

    def _expire_if(self, cycle):
        if self.protocol.next_turn is not None and cycle > self.deadline:
            self.expired = True

    def _settle(self, at):
        while not self.expired and (bucket := self.pending.pop(self.rank, None)):
            chosen = False
            for item in bucket:
                receipt = {"turn_id": item["turn"]["turn_id"], "arrived_cycle": item["arrived_cycle"],
                           "processed_cycle": at, "round": item["round"]}
                if chosen:
                    self.receipts.append({**receipt, "status": "slot_already_used"})
                    continue
                try:
                    self.protocol.submit(item["turn"])
                except DebateError:
                    self.receipts.append({**receipt, "status": "protocol_refused"})
                    continue
                self.receipts.append({**receipt, "status": "accepted"})
                self.rank += 1
                self.deadline = at + self.patience
                chosen = True

    def handle(self, item):
        cycle = item["arrived_cycle"]
        self._expire_if(cycle)
        slot = self.slot_rank[(item["round"], item["turn"]["participant"])]
        if self.expired or slot < self.rank:
            status = "deadline_exceeded" if self.expired else "slot_already_used"
            self.receipts.append({"turn_id": item["turn"]["turn_id"], "arrived_cycle": cycle,
                                  "processed_cycle": cycle, "round": item["round"], "status": status})
            return
        self.pending.setdefault(slot, []).append(item)
        self._settle(cycle)

    def status(self, as_of):
        self._expire_if(as_of)
        state = "expired" if self.expired else "ready_for_decision" if self.protocol.next_turn is None else "waiting"
        waiting = [item["turn"]["turn_id"] for slot in sorted(self.pending) for item in self.pending[slot]]
        return {"state": state, "next_deadline_cycle": self.deadline if state == "waiting" else None,
                "queued_turn_ids": waiting, "receipts": self.receipts, "debate": self.protocol.report()}


def _parse(events, state, first, as_of):
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise AsyncError("Daftar event asinkron melampaui batas.")
    normalized = []
    seen = set()
    for item in events:
        _shape(item, ("round", "arrived_cycle", "turn"))
        turn = Turn.from_dict(item["turn"])
        round_number = _int(item["round"], 1, state.protocol.plan.rounds)
        at = _int(item["arrived_cycle"], first, as_of)
        if (round_number, turn.participant) not in state.slot_rank or turn.turn_id in seen:
            raise AsyncError("Turn ganda atau peserta belum terdaftar untuk slot itu.")
        seen.add(turn.turn_id)
        normalized.append({"round": round_number, "arrived_cycle": at, "turn": turn.as_dict()})
    return sorted(normalized, key=lambda item: (item["arrived_cycle"], item["turn"]["turn_id"]))


def replay(raw):
    _shape(raw, ("plan", "first_cycle", "wait_cycles", "as_of_cycle", "events"))
    first = _int(raw["first_cycle"], 0, MAX_CYCLE)
    now = _int(raw["as_of_cycle"], first, MAX_CYCLE)
    wait = _int(raw["wait_cycles"], 1, MAX_WINDOW)
    state = _AsyncState(raw["plan"], first, wait)
    events = _parse(raw["events"], state, first, now)
    for item in events:
        state.handle(item)
    source = {"plan": state.protocol.plan.as_dict(), "first_cycle": first,
              "wait_cycles": wait, "as_of_cycle": now, "events": events}
    body = {"schema": "ace.async-deliberation.v1", "source": source, **state.status(now)}
    return {**body, "sha256": _sha(body)}


def verify(checkpoint):
    try:
        return isinstance(checkpoint, dict) and replay(checkpoint["source"]) == checkpoint
    except (KeyError, ValueError, RecursionError):
        return False


def resume(checkpoint, *, through_cycle, incoming):
    """Teruskan checkpoint, memproses penambahan hanya setelah batas sebelumnya."""
    if not verify(checkpoint):
        raise AsyncError("Checkpoint tidak cocok dengan replay.")
    if not isinstance(incoming, list):
        raise AsyncError("Masukan lanjutan harus berupa daftar event.")
    basis = deepcopy(checkpoint["source"])
    horizon = _int(through_cycle, basis["as_of_cycle"], MAX_CYCLE)
    if len(incoming) + len(basis["events"]) > MAX_EVENTS:
        raise AsyncError("Daftar event asinkron melampaui batas.")
    for item in incoming:
        _shape(item, ("round", "arrived_cycle", "turn"))
        _int(item["arrived_cycle"], basis["as_of_cycle"] + 1, horizon)
    basis["events"].extend(incoming)
    basis["as_of_cycle"] = horizon
    return replay(basis)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--resume", type=Path, metavar="CHECKPOINT")
    args = parser.parse_args(argv)

    def read(path):
        with path.open("rb") as handle:
            data = handle.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise AsyncError("Berkas deliberasi melampaui batas.")
        return json.loads(data)

    try:
        incoming = read(args.input)
        if args.resume is not None:
            _shape(incoming, ("through_cycle", "incoming"))
            result = resume(read(args.resume), **incoming)
        else:
            result = replay(incoming)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["state"] == "expired")


if __name__ == "__main__":
    raise SystemExit(main())
