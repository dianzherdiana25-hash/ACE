"""Jaga urutan, idempotensi, dan custody turn dialog yang disimpan lokal."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import sqlite3

from ._contracts import PresenceError, canonical, decode, digest, identifier, identity, integer, items, obj, text


TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
ROLES = ("user", "assistant")
LIMIT = 500
APP_ID = 0x41434559


def instant(value):
    if not isinstance(value, str) or not TIME.fullmatch(value):
        raise PresenceError("Timestamp perlu UTC YYYY-MM-DDTHH:MM:SSZ.")
    try:
        return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise PresenceError("Tanggal dialog tidak sah.") from error


def format_time(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def turn(value):
    obj(value, ("session", "id", "role", "speaker", "message", "at", "reply_to", "refs"))
    for key in ("session", "id", "speaker"):
        identifier(value[key], key)
    if value["role"] not in ROLES:
        raise PresenceError("Peran dialog perlu user atau assistant.")
    text(value["message"], "Pesan", 3500)
    instant(value["at"])
    answer = value["reply_to"]
    if answer is not None:
        identifier(answer, "Turn yang dibalas")
    refs = [text(item, "Pointer sumber", 420) for item in items(value["refs"], 25)]
    if len(set(refs)) != len(refs):
        raise PresenceError("Pointer sumber dialog ganda.")
    if value["role"] == "assistant" and not refs:
        raise PresenceError("Pesan assistant perlu rujukan bukti.")
    return value


def initial(session):
    return identity({"schema": "ace.presence.turn-chain.v1", "session": identifier(session, "Sesi")})


def step(session, previous, seq, payload):
    if payload["session"] != session:
        raise PresenceError("Sesi payload tidak sama dengan jurnal.")
    prior = None if previous is None else previous["turn"]
    if prior is None and (payload["role"] != "user" or payload["reply_to"] is not None):
        raise PresenceError("Dialog dimulai oleh user tanpa reply_to.")
    if prior is not None:
        if payload["role"] == prior["role"] or payload["reply_to"] != prior["id"]:
            raise PresenceError("Pergantian peran atau penunjuk balasan tidak cocok.")
        if instant(payload["at"]) < instant(prior["at"]):
            raise PresenceError("Waktu turn tidak boleh mundur.")
    body = {"seq": seq, "previous_sha256": initial(session) if previous is None else previous["sha256"], "turn": payload}
    return {**body, "sha256": identity(body)}


def validate_chain(session, events):
    identifier(session, "Sesi")
    keys = set()
    previous = None
    for ordinal, event in enumerate(items(events, LIMIT), 1):
        obj(event, ("seq", "previous_sha256", "turn", "sha256"))
        digest(event["sha256"])
        digest(event["previous_sha256"])
        integer(event["seq"], "Urutan", ordinal, ordinal)
        row = turn(event["turn"])
        expected = step(session, previous, ordinal, row)
        if expected != event or row["id"] in keys:
            raise PresenceError("Urutan, identitas, atau hash rantai dialog tidak konsisten.")
        previous = event
        keys.add(row["id"])
    return previous["sha256"] if previous else initial(session)


def _connect(path, readonly=False):
    if readonly:
        url = Path(path).absolute().as_uri() + "?mode=ro"
        return sqlite3.connect(url, timeout=3, isolation_level=None, uri=True)
    return sqlite3.connect(path, timeout=3, isolation_level=None)


class Journal:
    """SQLite hanya di lokasi yang dipilih pemanggil untuk sesi dialog paket ini."""

    def __init__(self, path):
        self.path = Path(path)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
        except FileExistsError:
            if self.path.is_symlink() or not self.path.is_file():
                raise PresenceError("Jurnal harus berkas reguler milik paket dialog.")
            with closing(_connect(self.path, readonly=True)) as connection:
                if connection.execute("PRAGMA application_id").fetchone() != (APP_ID,):
                    raise PresenceError("Berkas SQLite bukan jurnal dialog ACE.")
        else:
            os.close(descriptor)
            with closing(_connect(self.path)) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(f"PRAGMA application_id={APP_ID}")
                connection.execute("""
                    CREATE TABLE turns (
                        session TEXT NOT NULL,
                        seq INTEGER NOT NULL,
                        event_id TEXT NOT NULL,
                        record BLOB NOT NULL,
                        PRIMARY KEY (session, seq),
                        UNIQUE (session, event_id)
                    )
                """)
                connection.commit()

    @staticmethod
    def _load(connection, session):
        return [decode(row[0]) for row in connection.execute(
            "SELECT record FROM turns WHERE session=? ORDER BY seq LIMIT ?", (session, LIMIT + 1))]

    def export(self, session):
        with closing(_connect(self.path, readonly=True)) as connection:
            events = self._load(connection, session)
        head = validate_chain(session, events)
        return {"schema": "ace.presence.dialogue-export.v1", "session": session,
                "head_sha256": head, "events": events}

    def append(self, raw):
        payload = turn(raw)
        session = payload["session"]
        with closing(_connect(self.path)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                records = self._load(connection, session)
                validate_chain(session, records)
                for event in records:
                    if event["turn"]["id"] == payload["id"]:
                        if event["turn"] != payload:
                            raise PresenceError("ID turn sudah dipakai dengan isi berbeda.")
                        connection.commit()
                        return event, True
                if len(records) >= LIMIT:
                    raise PresenceError("Batas jumlah turn sesi tercapai.")
                receipt = step(session, records[-1] if records else None, len(records) + 1, payload)
                connection.execute("INSERT INTO turns(session, seq, event_id, record) VALUES (?, ?, ?, ?)",
                                   (session, receipt["seq"], payload["id"], canonical(receipt)))
                connection.commit()
                return receipt, False
            except BaseException:
                connection.rollback()
                raise


def load_export(data):
    result = decode(data)
    obj(result, ("schema", "session", "head_sha256", "events"))
    if result["schema"] != "ace.presence.dialogue-export.v1":
        raise PresenceError("Schema ekspor dialog tidak didukung.")
    if validate_chain(result["session"], result["events"]) != digest(result["head_sha256"]):
        raise PresenceError("Head ekspor tidak cocok dengan seluruh rantai.")
    return result
