"""Bangun antrean email rehearsal yang menghasilkan MIME di spool lokal.

Antrean mengikat template dan menolak duplikat yang berubah. Worker
menghasilkan EML deterministik di DB transaksi. Alamat sengaja memakai
domain .invalid agar spool fixture tidak mempunyai tujuan pengiriman.
"""
import argparse
from contextlib import closing
from datetime import datetime,timezone
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text


ADDRESS=re.compile(r"[a-z0-9][a-z0-9_.+-]{0,62}@[a-z0-9][a-z0-9-]{0,40}\.invalid")


def _address(value):
    if not isinstance(value,str) or not ADDRESS.fullmatch(value):
        raise ContractError("Rehearsal email memerlukan alamat .invalid.")
    return value


def _policy(raw,expected):
    checked(raw,expected)
    schema(raw,"ace.factory-mail-policy.v1",("id","source_ref","sender","recipients","limit","max_bytes","template_sha256"))
    identifier(raw["id"],"ID antrean")
    text(raw["source_ref"],"Sumber antrean")
    sender=_address(raw["sender"])
    recipients={}
    for row in entries(raw["recipients"],250,minimum=1):
        obj(row,("ref","address"))
        key=identifier(row["ref"],"Rujukan penerima")
        if key in recipients:
            raise ContractError("Alias penerima ganda.")
        recipients[key]=_address(row["address"])
    limit=integer(raw["limit"],"Jumlah draf",1,10_000)
    cap=integer(raw["max_bytes"],"Batas MIME",180,30_000)
    digest(raw["template_sha256"])
    return sender,recipients,limit,cap


def initialize(path,policy,expected):
    _policy(policy,expected)
    with path.open("xb"):
        pass
    with closing(sqlite3.connect(path)) as db,db:
        db.executescript("CREATE TABLE version(sha TEXT PRIMARY KEY);"
                         "CREATE TABLE queue(position INTEGER PRIMARY KEY,id TEXT NOT NULL UNIQUE,kind TEXT NOT NULL,"
                         "fingerprint TEXT NOT NULL,time INTEGER NOT NULL,recipient TEXT NOT NULL,"
                         "subject TEXT NOT NULL,body TEXT NOT NULL,mime BLOB,mime_sha256 TEXT) STRICT;")
        db.execute("INSERT INTO version VALUES (?)",(expected,))


def _db(path,expected):
    connection=sqlite3.connect(Path(path).absolute().as_uri()+"?mode=rw",uri=True,isolation_level=None,timeout=3)
    try:
        if connection.execute("SELECT sha FROM version").fetchall()!=[(expected,)]:
            raise ContractError("DB dibuat dengan policy berbeda.")
        return connection
    except BaseException:
        connection.close()
        raise


def enqueue(path,policy,expected,draft,template_anchor,now):
    _,recipients,limit,cap=_policy(policy,expected)
    if digest(template_anchor)!=policy["template_sha256"]:
        raise ContractError("Generator pesan menggunakan template yang berbeda.")
    schema(draft,"ace.factory-notification-draft.v1",("id","channel","recipient_ref","subject","body","template",
                                                    "template_ref","request_sha256","request_ref","status"))
    key=identifier(draft["id"],"ID pesan")
    recipient=identifier(draft["recipient_ref"],"Alias penerima")
    if draft["status"]!="draft" or draft["channel"]!="email_draft" or recipient not in recipients:
        raise ContractError("Draf atau penerima tidak didukung policy.")
    subject=text(draft["subject"],"Judul pesan",180)
    body=draft["body"]
    if not isinstance(body,str) or not body.strip() or len(body.encode())>cap or any(
            not (char.isprintable() or char=="\n") for char in body):
        raise ContractError("Isi email tidak valid.")
    identifier(draft["template"],"Template")
    text(draft["template_ref"],"Sumber template")
    text(draft["request_ref"],"Sumber permintaan")
    digest(draft["request_sha256"])
    when=integer(now,"Waktu draf",0,253_402_300_799)
    fingerprint=identity(draft)
    with closing(_db(path,expected)) as db:
        db.execute("BEGIN IMMEDIATE")
        old=db.execute("SELECT fingerprint,kind FROM queue WHERE id=?",(key,)).fetchone()
        if old is not None:
            if old[0]!=fingerprint:
                raise ContractError("ID email digunakan ulang untuk draf berbeda.")
            return {"id":key,"status":old[1],"duplicate":True}
        if db.execute("SELECT count(*) FROM queue").fetchone()[0]>=limit:
            raise ContractError("Antrean lokal penuh.")
        db.execute("INSERT INTO queue(id,kind,fingerprint,time,recipient,subject,body) VALUES (?,'queued',?,?,?,?,?)",
                   (key,fingerprint,when,recipient,subject,body))
        db.commit()
    return {"id":key,"status":"queued","duplicate":False}


def draft_next(path,policy,expected):
    sender,recipients,_,cap=_policy(policy,expected)
    with closing(_db(path,expected)) as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT id,time,recipient,subject,body FROM queue WHERE kind='queued' ORDER BY position LIMIT 1").fetchone()
        if row is None:
            return {"status":"empty"}
        key,when,lane,subject,body=row
        message=EmailMessage(policy=SMTP)
        message["From"]=sender
        message["To"]=recipients[lane]
        message["Date"]=format_datetime(datetime.fromtimestamp(when,timezone.utc))
        message["Subject"]=subject
        message["Message-ID"]=f"<{key}.{expected[:12]}@draft.invalid>"
        message.set_content(body)
        prepared=message.as_bytes()
        if len(prepared)>cap:
            db.execute("UPDATE queue SET kind='rejected' WHERE id=?",(key,))
            db.commit()
            return {"id":key,"status":"rejected","reason":"mime_size"}
        anchor=sha256(prepared).hexdigest()
        db.execute("UPDATE queue SET kind='drafted',mime=?,mime_sha256=? WHERE id=?",(prepared,anchor,key))
        db.commit()
    return {"id":key,"status":"drafted","sha256":anchor,"bytes":len(prepared)}


def read_draft(path,expected,key):
    identifier(key,"ID pesan")
    with closing(_db(path,expected)) as db:
        result=db.execute("SELECT mime,mime_sha256 FROM queue WHERE id=? AND kind='drafted'",(key,)).fetchone()
    if result is None or sha256(result[0]).hexdigest()!=result[1]:
        raise ContractError("Draft MIME tidak tersedia atau gagal verifikasi.")
    return result[0]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db",type=Path)
    parser.add_argument("policy",type=Path)
    parser.add_argument("action",choices=("initialize","enqueue","draft-next","read-draft"))
    parser.add_argument("--draft",type=Path)
    parser.add_argument("--template-sha256")
    parser.add_argument("--at",type=int)
    parser.add_argument("--id")
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        policy=decode(read(args.policy))
        if args.action=="initialize":
            initialize(args.db,policy,args.expect_sha256)
            report={"status":"ready"}
        elif args.action=="enqueue":
            if args.draft is None or args.template_sha256 is None or args.at is None:
                parser.error("enqueue membutuhkan --draft, --template-sha256, dan --at.")
            report=enqueue(args.db,policy,args.expect_sha256,decode(read(args.draft)),args.template_sha256,args.at)
        elif args.action=="read-draft":
            if not args.id:
                parser.error("read-draft membutuhkan --id.")
            sys.stdout.buffer.write(read_draft(args.db,args.expect_sha256,args.id))
            return 0
        else:
            report=draft_next(args.db,policy,args.expect_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError,sqlite3.Error) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]=="rejected")


if __name__=="__main__":
    raise SystemExit(main())
