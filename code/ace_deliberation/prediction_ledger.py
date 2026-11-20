"""Kunci ramalan berurutan dengan jendela yang tercatat sebelum resolusi.

Setiap perubahan probabilitas menambah versi. Registrasi mengunci batas
ramalan dan aturan resolusi. Auditor memakai checkpoint eksternal untuk
mendeteksi pemotongan. Ledger mendukung bukti fixture lokal dan menyimpan
rujukan tersendiri untuk setiap resolusi.
"""
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path

from .brier_scorer import _probability, _stamp
from .dissent_ledger import GENESIS, LedgerError, _entry, _locked, _validate_anchor, _wire


MAX_EVENTS = 40_000
MAX_BYTES = 24_000_000
MAX_RECORD = 65_536


class PredictionError(LedgerError):
    """Peristiwa ramalan tidak sah atau rantainya telah berubah."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise PredictionError("Field ledger ramalan tidak sesuai skema.")


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise PredictionError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise PredictionError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _timestamp(raw):
    try:
        return _stamp(raw)
    except ValueError as exc:
        raise PredictionError("Cap waktu ledger wajib ISO 8601 berzona.") from exc


def _normalize(raw):
    if not isinstance(raw, dict) or raw.get("kind") not in ("register", "forecast", "resolve"):
        raise PredictionError("Jenis peristiwa ramalan tidak dikenal.")
    base_fields = ("event_id", "question_id", "at", "source_ref", "kind")
    extras = {"register": ("locks_at", "resolution_rule_ref"), "forecast": ("forecaster", "probability"),
              "resolve": ("outcome",)}
    kind = raw["kind"]
    _shape(raw, (*base_fields, *extras[kind]))
    at = _timestamp(raw["at"])
    row = {"event_id": _text(raw["event_id"], "ID event", 120),
           "question_id": _text(raw["question_id"], "ID pertanyaan", 120),
           "source_ref": _text(raw["source_ref"], "sumber event", 512),
           "at": at.isoformat(), "kind": kind}
    if kind == "register":
        cutoff = _timestamp(raw["locks_at"])
        if cutoff <= at:
            raise PredictionError("Batas ramalan harus lewat waktu registrasi.")
        rule_ref = _text(raw["resolution_rule_ref"], "aturan resolusi", 512)
        if rule_ref == row["source_ref"]:
            raise PredictionError("Registrasi dan aturan resolusi perlu sumber berbeda.")
        row.update(locks_at=cutoff.isoformat(), resolution_rule_ref=rule_ref)
    elif kind == "forecast":
        try:
            _probability(raw["probability"])
        except ValueError as exc:
            raise PredictionError("Probabilitas ramalan tidak sah.") from exc
        row.update(forecaster=_text(raw["forecaster"], "peramal", 120), probability=str(raw["probability"]))
    elif type(raw["outcome"]) is int and raw["outcome"] in (0, 1):
        row["outcome"] = raw["outcome"]
    else:
        raise PredictionError("Resolusi wajib integer 0 atau 1.")
    return row


@dataclass
class _Question:
    registration: dict
    last_event: datetime
    forecasts: dict = field(default_factory=dict)
    resolution: dict | None = None


@dataclass
class _State:
    records: list = field(default_factory=list)
    ids: set = field(default_factory=set)
    refs: set = field(default_factory=set)
    questions: dict = field(default_factory=dict)
    bytes_read: int = 0

    @property
    def checkpoint(self):
        return {"sequence": len(self.records), "sha256": self.records[-1]["sha256"] if self.records else GENESIS}

    def verify_anchor(self, anchor):
        if anchor is None:
            return
        _validate_anchor(anchor)
        sequence = anchor["sequence"]
        if sequence > len(self.records):
            raise PredictionError("Ledger terpotong sebelum checkpoint.")
        digest = GENESIS if not sequence else self.records[sequence - 1]["sha256"]
        if digest != anchor["sha256"]:
            raise PredictionError("Hash berbeda dari checkpoint.")

    def prepare(self, event):
        if event["event_id"] in self.ids or event["source_ref"] in self.refs:
            raise PredictionError("Event atau rujukan telah digunakan.")
        at = _timestamp(event["at"])
        question = self.questions.get(event["question_id"])
        if event["kind"] == "register":
            if question is not None:
                raise PredictionError("Pertanyaan sudah terdaftar.")
            return at
        if question is None or question.resolution is not None or at <= question.last_event:
            raise PredictionError("Pertanyaan belum dibuka, sudah teresolusi, atau waktu mundur.")
        cutoff = _timestamp(question.registration["locks_at"])
        if event["kind"] == "forecast" and at >= cutoff:
            raise PredictionError("Jendela ramalan sudah dikunci.")
        if event["kind"] == "resolve" and (at < cutoff or not question.forecasts):
            raise PredictionError("Resolusi memerlukan ramalan dan jendelanya sudah berakhir.")
        return at

    def register(self, row, at):
        event = row["event"]
        identifier = event["question_id"]
        if event["kind"] == "register":
            self.questions[identifier] = _Question(event, at)
        else:
            question = self.questions[identifier]
            question.last_event = at
            if event["kind"] == "forecast":
                question.forecasts.setdefault(event["forecaster"], []).append(event)
            else:
                question.resolution = event
        self.ids.add(event["event_id"])
        self.refs.add(event["source_ref"])
        self.records.append(row)


def _load(stream):
    state = _State()
    while raw := stream.readline(MAX_RECORD + 1):
        number = len(state.records) + 1
        state.bytes_read += len(raw)
        if (number > MAX_EVENTS or state.bytes_read > MAX_BYTES or len(raw) > MAX_RECORD
                or not raw.endswith(b"\n")):
            raise PredictionError("Ledger melewati batas atau record terakhir terpotong.")
        try:
            row = json.loads(raw)
            _shape(row, ("sequence", "previous_sha256", "event", "sha256"))
            event = _normalize(row["event"])
            at = state.prepare(event)
            expected = _entry(number, state.checkpoint["sha256"], event)
            if _wire(expected) + b"\n" != raw:
                raise PredictionError("Rantai atau representasi ledger berubah.")
        except (ValueError, RecursionError) as exc:
            raise PredictionError(f"Record {number} tidak sah.") from exc
        state.register(expected, at)
    return state


def append_event(path, raw, *, anchor=None):
    event = _normalize(raw)
    if anchor is not None:
        _validate_anchor(anchor)
    with _locked(path, writable=True, create=anchor is None or not anchor["sequence"]) as stream:
        state = _load(stream)
        state.verify_anchor(anchor)
        state.prepare(event)
        row = _entry(len(state.records) + 1, state.checkpoint["sha256"], event)
        payload = _wire(row) + b"\n"
        if len(state.records) >= MAX_EVENTS or state.bytes_read + len(payload) > MAX_BYTES or len(payload) > MAX_RECORD:
            raise PredictionError("Penambahan melampaui kapasitas ledger.")
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return row


def audit(path, *, anchor=None):
    with _locked(path, writable=False) as stream:
        state = _load(stream)
    state.verify_anchor(anchor)
    return {
        "schema": "ace.prediction-ledger.v1", "checkpoint": state.checkpoint,
        "anchor_checked": anchor is not None,
        "questions": {
            identifier: {"registration": question.registration,
                         "forecast_version_counts": {actor: len(rows) for actor, rows in sorted(question.forecasts.items())},
                         "latest": {actor: rows[-1] for actor, rows in sorted(question.forecasts.items())},
                         "resolution": question.resolution}
            for identifier, question in sorted(state.questions.items())
        },
        "events": state.records,
    }


def _json_source(path):
    with path.open("rb") as handle:
        data = handle.read(MAX_RECORD + 1)
    if len(data) > MAX_RECORD:
        raise PredictionError("Event atau checkpoint melampaui batas ukuran.")
    return json.loads(data)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    append = sub.add_parser("append")
    audit_command = sub.add_parser("audit")
    for command in (append, audit_command):
        command.add_argument("ledger", type=Path)
        command.add_argument("--anchor", type=Path)
    append.add_argument("event", type=Path)
    args = parser.parse_args(argv)
    try:
        anchor = _json_source(args.anchor) if args.anchor is not None else None
        if args.anchor is not None and anchor is None:
            raise PredictionError("Checkpoint tidak boleh kosong.")
        if args.operation == "append":
            output = append_event(args.ledger, _json_source(args.event), anchor=anchor)
        else:
            output = audit(args.ledger, anchor=anchor)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
