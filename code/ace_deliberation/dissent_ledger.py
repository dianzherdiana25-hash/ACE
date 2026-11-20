"""Pertahankan dissent sebagai bukti tersendiri ketika putusan ditambahkan.

Ledger JSONL hanya menambah record. Penulis mengunci berkas untuk mencegah
dua append memilih head yang sama. Auditor dapat membandingkan checkpoint
yang disimpan terpisah untuk mendeteksi pemotongan suffix. Hash membuktikan
integritas relatif terhadap checkpoint eksternal dan tidak membuktikan
identitas penulis.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat


GENESIS = "0" * 64
MAX_ROW_BYTES = 128_000
MAX_ROWS = 50_000
MAX_BYTES = 32_000_000
MAX_REFS = 512
_DIGEST = re.compile(r"[0-9a-f]{64}")


class LedgerError(ValueError):
    """Masukan atau rantai tidak dapat diverifikasi."""


def _text(value, field_name, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise LedgerError(f"{field_name} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise LedgerError(f"{field_name} tidak sah.") from exc
    return value.strip()


def _normalize(event):
    common = {"event_id", "case_id", "kind", "actor", "statement", "refs"}
    if not isinstance(event, dict):
        raise LedgerError("Event wajib berupa objek.")
    kind = event.get("kind")
    if kind not in ("dissent", "decision"):
        raise LedgerError("Jenis event tidak dikenal.")
    expected = common | ({"outcome"} if kind == "decision" else set())
    if event.keys() != expected:
        raise LedgerError("Field event tidak sesuai skema.")
    result = {key: _text(event[key], key, limit) for key, limit in (
        ("event_id", 96), ("case_id", 96), ("actor", 96), ("statement", 8_000),
    )}
    refs = event["refs"]
    if not isinstance(refs, list) or len(refs) > MAX_REFS:
        raise LedgerError("refs wajib berupa larik berbatas.")
    refs = [_text(ref, "ref", 512) for ref in refs]
    if len(set(refs)) != len(refs):
        raise LedgerError("Rujukan ganda.")
    if kind == "dissent" and not refs:
        raise LedgerError("Dissent perlu rujukan klaim atau bukti.")
    result.update(kind=kind, refs=sorted(refs))
    if kind == "decision":
        outcome = event["outcome"]
        if outcome not in ("adopt", "reject", "defer"):
            raise LedgerError("Outcome putusan tidak dikenal.")
        result["outcome"] = outcome
    return result


def _wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _entry(seq, previous, event):
    body = {"sequence": seq, "previous_sha256": previous, "event": event}
    return {**body, "sha256": hashlib.sha256(_wire(body)).hexdigest()}


@dataclass
class _LedgerState:
    entries: list = field(default_factory=list)
    seen: set = field(default_factory=set)
    dissent_by_case: dict = field(default_factory=dict)
    byte_count: int = 0

    @property
    def checkpoint(self):
        return {"sequence": len(self.entries),
                "sha256": self.entries[-1]["sha256"] if self.entries else GENESIS}

    def validate(self, event):
        if event["event_id"] in self.seen:
            raise LedgerError("event_id ganda.")
        if event["kind"] == "decision":
            expected = self.dissent_by_case.get(event["case_id"], set())
            if set(event["refs"]) != expected:
                raise LedgerError("Putusan wajib menyebut semua dan hanya dissent kasusnya.")

    def register(self, row):
        event = row["event"]
        self.entries.append(row)
        self.seen.add(event["event_id"])
        if event["kind"] == "dissent":
            self.dissent_by_case.setdefault(event["case_id"], set()).add(event["event_id"])

    def check_anchor(self, anchor):
        if anchor is None:
            return
        if (not isinstance(anchor, dict) or set(anchor) != {"sequence", "sha256"}
                or type(anchor["sequence"]) is not int or anchor["sequence"] < 0
                or not isinstance(anchor["sha256"], str) or not _DIGEST.fullmatch(anchor["sha256"])):
            raise LedgerError("Bentuk checkpoint tidak sah.")
        position = anchor["sequence"]
        if position > len(self.entries):
            raise LedgerError("Ledger terpotong sebelum checkpoint.")
        digest = GENESIS if position == 0 else self.entries[position - 1]["sha256"]
        if digest != anchor["sha256"]:
            raise LedgerError("Ledger tidak cocok dengan checkpoint.")


@contextmanager
def _locked(path, *, writable):
    flags = os.O_NOFOLLOW | os.O_NONBLOCK
    flags |= os.O_RDWR | os.O_CREAT | os.O_APPEND if writable else os.O_RDONLY
    fd = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise LedgerError("Ledger harus berkas reguler.")
        fcntl.flock(fd, fcntl.LOCK_EX if writable else fcntl.LOCK_SH)
        with os.fdopen(os.dup(fd), "r+b" if writable else "rb") as stream:
            yield stream
    finally:
        os.close(fd)


def _read(stream):
    state = _LedgerState()
    while raw := stream.readline(MAX_ROW_BYTES + 1):
        state.byte_count += len(raw)
        if (len(raw) > MAX_ROW_BYTES or state.byte_count > MAX_BYTES
                or len(state.entries) >= MAX_ROWS):
            raise LedgerError("Ledger melebihi batas replay.")
        number = len(state.entries) + 1
        if not raw.endswith(b"\n"):
            raise LedgerError(f"Baris ledger {number} belum lengkap.")
        try:
            row = json.loads(raw)
            if not isinstance(row, dict):
                raise LedgerError("Record wajib berupa objek.")
            event = _normalize(row.get("event"))
            state.validate(event)
            expected = _entry(number, state.checkpoint["sha256"], event)
            if _wire(expected) + b"\n" != raw:
                raise LedgerError("Hash, skema, serialisasi, atau urutan berubah.")
        except (ValueError, RecursionError, TypeError) as exc:
            raise LedgerError(f"Baris ledger {number} tidak sah.") from exc
        state.register(expected)
    return state


def append_event(path, raw, *, anchor=None):
    """Tambah dissent atau putusan dengan pemeriksaan ulang rantai di bawah lock."""
    event = _normalize(raw)
    with _locked(path, writable=True) as stream:
        state = _read(stream)
        state.check_anchor(anchor)
        state.validate(event)
        row = _entry(len(state.entries) + 1, state.checkpoint["sha256"], event)
        encoded = _wire(row) + b"\n"
        if (len(state.entries) >= MAX_ROWS or len(encoded) > MAX_ROW_BYTES
                or state.byte_count + len(encoded) > MAX_BYTES):
            raise LedgerError("Append akan melampaui batas ledger.")
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
        return row


def audit(path, *, anchor=None, case_id=None):
    """Baca seluruh rantai dan keluarkan sudut pandang satu kasus bila dipilih."""
    if case_id is not None:
        case_id = _text(case_id, "case_id", 96)
    with _locked(path, writable=False) as stream:
        state = _read(stream)
    state.check_anchor(anchor)
    rows = [row for row in state.entries
            if case_id is None or row["event"]["case_id"] == case_id]
    return {
        "schema": "ace.dissent-ledger-audit.v1",
        "checkpoint": state.checkpoint,
        "anchor_checked": anchor is not None,
        "case_id": case_id,
        "dissent_count": sum(row["event"]["kind"] == "dissent" for row in rows),
        "decision_count": sum(row["event"]["kind"] == "decision" for row in rows),
        "events": rows,
    }


def _json_input(path):
    with path.open("rb") as stream:
        blob = stream.read(MAX_ROW_BYTES + 1)
    if len(blob) > MAX_ROW_BYTES:
        raise LedgerError("Berkas masukan melebihi batas ukuran.")
    return json.loads(blob)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    append = sub.add_parser("append", help="Tambah event dissent atau keputusan.")
    inspect = sub.add_parser("audit", help="Verifikasi dan ringkas ledger.")
    for command in (append, inspect):
        command.add_argument("ledger", type=Path)
        command.add_argument("--anchor", type=Path)
    append.add_argument("event", type=Path)
    inspect.add_argument("--case")
    args = parser.parse_args(argv)
    try:
        anchor = _json_input(args.anchor) if args.anchor is not None else None
        if args.anchor is not None and anchor is None:
            raise LedgerError("Checkpoint kosong.")
        if args.command == "append":
            result = append_event(args.ledger, _json_input(args.event), anchor=anchor)
        else:
            result = audit(args.ledger, anchor=anchor, case_id=args.case)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
