"""Awasi giliran debat dengan agenda dan batas waktu yang dapat diputar ulang.

Waktu dibaca dari offset rekaman. Relevansi hanya ditentukan dari rujukan
agenda eksplisit. Intervensi tidak membuat fakta baru atau mengganti
kontribusi pengguna. Sesi yang lewat waktu memerlukan rencana baru.
"""
import json
from pathlib import Path

from .debate_protocol import MAX_INPUT_BYTES, DebateError, DebateProtocol


_MAX_MS = 86_400_000
_MAX_EVENTS = 4_000


class ModerationError(ValueError):
    """Masukan moderasi tidak membentuk rekaman yang dapat diputar ulang."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise ModerationError("Field moderasi tidak sesuai skema.")


def _string(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 128 or "\0" in value:
        raise ModerationError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ModerationError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _offset(value, minimum=0):
    if type(value) is not int or not minimum <= value <= _MAX_MS:
        raise ModerationError("Offset atau anggaran waktu di luar batas.")
    return value


def _topics(raw, label):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 64:
        raise ModerationError(f"{label} memerlukan daftar 1–64 rujukan.")
    parsed = [_string(item, label) for item in raw]
    if len(parsed) != len(set(parsed)):
        raise ModerationError(f"{label} memuat rujukan ganda.")
    return set(parsed)


class Moderator:
    """Terima percobaan giliran tanpa mengubah transcript untuk intervensi."""

    def __init__(self, plan, rules):
        self._debate = DebateProtocol(plan)
        keys = {"agendas", "turn_ms", "total_ms", "open_at_ms"}
        if isinstance(rules, dict) and "required_agendas" in rules:
            keys.add("required_agendas")
        _shape(rules, keys)
        self._agendas = _topics(rules["agendas"], "agenda")
        self._required = (_topics(rules["required_agendas"], "agenda wajib")
                          if "required_agendas" in rules else set())
        if not self._required <= self._agendas:
            raise ModerationError("Agenda wajib harus termasuk agenda sesi.")
        self._turn_limit = _offset(rules["turn_ms"], 1)
        self._total_limit = _offset(rules["total_ms"], 1)
        self._opened = _offset(rules["open_at_ms"])
        if self._turn_limit > self._total_limit or self._opened + self._total_limit > _MAX_MS:
            raise ModerationError("Anggaran sesi tidak mencakup jendela giliran.")
        self._expected_since = self._last = self._opened
        self._events = {}
        self._filled_agendas = set()
        self._phase = "deliberating"

    @property
    def effective_deadline(self):
        if self._phase != "deliberating":
            return None
        global_deadline = self._opened + self._total_limit
        if self._debate.next_turn is None:
            return global_deadline
        return min(global_deadline, self._expected_since + self._turn_limit)

    def _receipt(self, event_id, at, kind, reason, expected, topics=()):
        result = {"event_id": event_id, "at_ms": at, "kind": kind, "reason": reason,
                  "expected_turn": expected, "agenda_refs": sorted(topics)}
        self._events[event_id] = result
        return {**result, "agenda_refs": result["agenda_refs"].copy(),
                "expected_turn": dict(expected) if expected is not None else None}

    def offer(self, raw):
        """Catat tick, kontribusi, atau permintaan putusan pada waktu eksplisit."""
        if len(self._events) >= _MAX_EVENTS:
            raise ModerationError("Rekaman moderasi melampaui batas.")
        if not isinstance(raw, dict) or raw.get("kind") not in ("tick", "utterance", "close"):
            raise ModerationError("Jenis event moderasi tidak dikenal.")
        kind = raw["kind"]
        base = ("kind", "event_id", "at_ms")
        fields = {"tick": base, "utterance": (*base, "message", "agenda_refs"),
                  "close": (*base, "decision")}
        _shape(raw, fields[kind])
        identifier = _string(raw["event_id"], "event_id")
        if identifier in self._events:
            raise ModerationError("event_id moderasi ganda.")
        at = _offset(raw["at_ms"], self._last)
        topics = _topics(raw["agenda_refs"], "agenda kontribusi") if kind == "utterance" else set()
        expected = self._debate.next_turn
        self._last = at
        if self._phase != "deliberating":
            return self._receipt(identifier, at, kind, "session_terminal", expected, topics)
        if at > self.effective_deadline:
            self._phase = "expired"
            return self._receipt(identifier, at, kind, "deadline_exceeded", expected, topics)
        if kind == "tick":
            return self._receipt(identifier, at, kind, "within_deadline", expected)
        if kind == "close":
            if self._required - self._filled_agendas:
                return self._receipt(identifier, at, kind, "required_agenda_uncovered", expected)
            try:
                self._debate.close(raw["decision"])
            except DebateError:
                return self._receipt(identifier, at, kind, "decision_refused", expected)
            self._phase = "closed"
            return self._receipt(identifier, at, kind, "decision_recorded", expected)
        if not topics <= self._agendas:
            return self._receipt(identifier, at, kind, "outside_agenda", expected, topics)
        try:
            self._debate.submit(raw["message"])
        except DebateError:
            return self._receipt(identifier, at, kind, "turn_refused", expected, topics)
        self._expected_since = at
        self._filled_agendas.update(topics)
        return self._receipt(identifier, at, kind, "turn_recorded", expected, topics)

    def report(self):
        return {
            "schema": "ace.moderator.v1", "phase": self._phase, "debrief": self._debate.report(),
            "started_at_ms": self._opened, "last_observed_at_ms": self._last,
            "effective_deadline_ms": self.effective_deadline,
            "agenda_covered": sorted(self._filled_agendas),
            "agenda_uncovered": sorted(self._agendas - self._filled_agendas),
            "required_agenda_uncovered": sorted(self._required - self._filled_agendas),
            "interventions": [
                {**row, "agenda_refs": row["agenda_refs"].copy(),
                 "expected_turn": dict(row["expected_turn"]) if row["expected_turn"] is not None else None}
                for row in self._events.values()
            ],
        }


def moderate(raw):
    _shape(raw, ("plan", "rules", "events"))
    events = raw["events"]
    if not isinstance(events, list) or len(events) > _MAX_EVENTS:
        raise ModerationError("Daftar event moderasi melampaui batas.")
    session = Moderator(raw["plan"], raw["rules"])
    for event in events:
        session.offer(event)
    return session.report()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            blob = handle.read(MAX_INPUT_BYTES + 1)
        if len(blob) > MAX_INPUT_BYTES:
            raise ModerationError("Berkas moderasi melampaui batas.")
        result = moderate(json.loads(blob))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["phase"] == "expired")


if __name__ == "__main__":
    raise SystemExit(main())
