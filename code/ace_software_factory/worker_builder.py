"""Bangun antrean produk dengan lease, percobaan ulang, dan dead-letter.

Lease adalah janji klaim berbatas waktu, bukan jaminan satu eksekusi
handler. Host memasok handler yang aman diulang dan waktu Unix.
Receipt penyelesaian hanya sah dari pemegang lease yang masih aktif.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


RUNTIME = r'''"""Antrean kerja SQLite ber-lease untuk backend lokal."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import re
from secrets import token_urlsafe
import sqlite3


ID = re.compile(r"[a-z][a-z0-9_-]{0,79}")


def validate_key(raw):
    if not isinstance(raw,str) or not ID.fullmatch(raw):
        raise ValueError("key_invalid")
    return raw


def stamp(now):
    if type(now) is not int or not 0 <= now <= 2 ** 40:
        raise ValueError("timestamp_invalid")
    return now


def payload(value):
    data = json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False)
    if len(data) > POLICY["max_payload_bytes"]:
        raise ValueError("payload_too_large")
    return data


@contextmanager
def transaction(path):
    connection=sqlite3.connect(Path(path).absolute().as_uri()+"?mode=rw",uri=True,isolation_level=None,timeout=5)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row=connection.execute("SELECT policy FROM queue_identity").fetchone()
        if row != (POLICY["plan_sha256"],):
            raise ValueError("queue_identity_mismatch")
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize(path):
    path=Path(path)
    with path.open("xb"): pass
    connection=sqlite3.connect(path)
    try:
        with connection:
            connection.executescript(
                "CREATE TABLE queue_identity(policy TEXT PRIMARY KEY);"
                "CREATE TABLE jobs(seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, lane TEXT NOT NULL,"
                "payload TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('queued','leased','done','dead')),"
                "tries INTEGER NOT NULL DEFAULT 0,available INTEGER NOT NULL,lease_until INTEGER,"
                "token_sha TEXT,outcome TEXT) STRICT;"
                "CREATE INDEX pending_jobs ON jobs(lane,state,available,seq);"
            )
            connection.execute("INSERT INTO queue_identity VALUES (?)",(POLICY["plan_sha256"],))
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        connection.close()


def enqueue(path, job, lane, value, now):
    validate_key(job)
    stamp(now)
    if not isinstance(lane,str) or lane not in POLICY["lanes"]:
        raise ValueError("lane_unknown")
    body=payload(value)
    with transaction(path) as db:
        previous=db.execute("SELECT lane,payload,state FROM jobs WHERE id=?",(job,)).fetchone()
        if previous is not None:
            if previous[:2] != (lane,body):
                raise ValueError("job_id_conflict")
            return {"task":job,"state":previous[2],"duplicate":True}
        if db.execute("SELECT count(*) FROM jobs").fetchone()[0] >= POLICY["history_limit"]:
            raise ValueError("history_full")
        db.execute("INSERT INTO jobs(id,lane,payload,state,available) VALUES(?,?,?,'queued',?)",(job,lane,body,now))
        return {"task":job,"state":"queued","duplicate":False}


def claim(path, lane, now):
    stamp(now)
    if not isinstance(lane,str) or lane not in POLICY["lanes"]:
        raise ValueError("lane_unknown")
    policy=POLICY["lanes"][lane]
    with transaction(path) as db:
        db.execute("UPDATE jobs SET state='dead', token_sha=NULL, lease_until=NULL, outcome='lease_exhausted' "
                   "WHERE lane=? AND state='leased' AND lease_until<=? AND tries>=?",
                   (lane,now,policy["max_attempts"]))
        row=db.execute("SELECT id,payload,tries FROM jobs WHERE lane=? AND tries<? AND "
                       "((state='queued' AND available<=?) OR (state='leased' AND lease_until<=?)) "
                       "ORDER BY seq LIMIT 1",(lane,policy["max_attempts"],now,now)).fetchone()
        if row is None:
            return None
        key,body,tries=row
        ticket=token_urlsafe(32)
        anchor=sha256(ticket.encode("ascii")).hexdigest()
        expiry=now+policy["lease_seconds"]
        db.execute("UPDATE jobs SET state='leased',tries=?,lease_until=?,token_sha=?,outcome=NULL WHERE id=?",
                   (tries+1,expiry,anchor,key))
        return {"id":key,"lease":ticket,"leased_until":expiry,"attempt":tries+1,"payload":json.loads(body)}


def finish(path, key, lease, now, *, success):
    validate_key(key)
    stamp(now)
    if not isinstance(lease,str) or len(lease)!=43 or not lease.isascii() or type(success) is not bool:
        raise ValueError("completion_invalid")
    anchor=sha256(lease.encode("ascii")).hexdigest()
    with transaction(path) as db:
        row=db.execute("SELECT lane,tries FROM jobs WHERE id=? AND state='leased' AND token_sha=? AND lease_until>?",
                       (key,anchor,now)).fetchone()
        if row is None:
            return {"status":"lease_lost"}
        lane,tries=row
        maximum=POLICY["lanes"][lane]["max_attempts"]
        new_state="done" if success else "dead" if tries>=maximum else "queued"
        available=now+(POLICY["lanes"][lane]["retry_seconds"] if new_state=="queued" else 0)
        db.execute("UPDATE jobs SET state=?,available=?,lease_until=NULL,token_sha=NULL,outcome=? WHERE id=?",
                   (new_state,available,"handled" if success else "handler_failed",key))
        return {"status":new_state,"attempt":tries,"available":available}


def inspect(path, key):
    validate_key(key)
    with transaction(path) as db:
        row=db.execute("SELECT lane,state,tries,available,lease_until,outcome FROM jobs WHERE id=?",(key,)).fetchone()
    return dict(zip(("lane","state","attempts","available","lease_until","outcome"),row,strict=True)) if row else None
'''


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-worker-plan.v1", ("id", "max_jobs", "max_payload_bytes", "source_ref", "queues"))
    product = identifier(plan["id"], "Produk")
    pointer = text(plan["source_ref"], "Sumber antrean")
    policy = {}
    links = {}
    for row in entries(plan["queues"], 32, minimum=1):
        obj(row, ("id", "max_attempts", "lease_seconds", "retry_seconds", "source_ref"))
        key = identifier(row["id"], "Nama antrean")
        if key in policy:
            raise ContractError("Nama antrean ganda.")
        policy[key] = {"max_attempts": integer(row["max_attempts"], "Percobaan", 1, 8),
                       "lease_seconds": integer(row["lease_seconds"], "Usia lease", 1, 1800),
                       "retry_seconds": integer(row["retry_seconds"], "Jeda retry", 1, 3600)}
        links[key] = text(row["source_ref"], "Sumber aturan antrean")
    contract = {"plan_sha256": expected, "history_limit": integer(plan["max_jobs"], "Batas riwayat", 1, 50_000),
                "max_payload_bytes": integer(plan["max_payload_bytes"], "Batas payload", 16, 10_000),
                "lanes": dict(sorted(policy.items()))}
    content = RUNTIME.replace("import sqlite3\n", f"import sqlite3\n\nPOLICY = {contract!r}\n", 1).encode()
    report = {"schema": "ace.factory-worker-build.v1", "product_id": product, "plan_sha256": expected,
              "source_ref": pointer, "leases": [{"queue": key, "source_ref": links[key], **policy[key]}
                                                 for key in sorted(policy)], "delivery": "at_least_once",
              "runtime": {"path": "product_queue.py", "sha256": sha256(content).hexdigest()}}
    return {"product_queue.py": content, "queue_manifest.json": canonical(report)+b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build(decode(read(args.plan)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
