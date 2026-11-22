"""Kelola antrean workflow web tanpa mengeksekusi pekerjaan.

Claim dan finalisasi memakai transaksi SQLite. Tiap situs memiliki cap
pekerjaan aktif dan saat lease kedaluwarsa item ditahan untuk peninjauan.
Receipt lama tidak dapat menyelesaikan klaim yang sudah kedaluwarsa.
"""
import argparse
from contextlib import closing,contextmanager
from pathlib import Path
from secrets import token_hex
import sqlite3
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import time_value


class Queue:
    def __init__(self,path,policy,expected):
        checked(policy,expected)
        schema(policy,"ace.web.queue-policy.v1",("source_ref","max_items","lease_seconds","sites"))
        text(policy["source_ref"],"Sumber antrean")
        self._path=Path(path)
        self._version=expected
        self._cap=integer(policy["max_items"],"Kapasitas riwayat",1,20000)
        self._lease=integer(policy["lease_seconds"],"Durasi lease",15,1800)
        self._sites={}
        for row in entries(policy["sites"],30,1):
            obj(row,("id","parallelism"))
            key=identifier(row["id"],"Situs")
            if key in self._sites:
                raise ContractError("Situs terdaftar lebih dari sekali.")
            self._sites[key]=integer(row["parallelism"],"Paralelisme situs",1,12)

    def initialize(self):
        with self._path.open("xb"):
            pass
        try:
            with closing(sqlite3.connect(self._path)) as db,db:
                db.executescript("""
                  CREATE TABLE queue_version (sha TEXT PRIMARY KEY);
                  CREATE TABLE jobs (
                    seq INTEGER PRIMARY KEY,id TEXT NOT NULL UNIQUE,site TEXT NOT NULL,
                    rank INTEGER NOT NULL,ready INTEGER NOT NULL,state TEXT NOT NULL,
                    request_sha TEXT NOT NULL,workflow_sha TEXT NOT NULL,origin_ref TEXT NOT NULL,
                    holder TEXT,lease_sha TEXT,lease_until INTEGER,finish_sha TEXT
                  ) STRICT;
                  CREATE INDEX ready_lane ON jobs(state,site,rank,ready,seq);
                """)
                db.execute("INSERT INTO queue_version VALUES (?)",(self._version,))
        except BaseException:
            self._path.unlink(missing_ok=True)
            raise

    @contextmanager
    def _transaction(self):
        url=self._path.absolute().as_uri()+"?mode=rw"
        with closing(sqlite3.connect(url,uri=True,isolation_level=None,timeout=5)) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT sha FROM queue_version").fetchall()!=[(self._version,)]:
                raise ContractError("DB antrean memiliki policy lain.")
            yield db
            db.commit()

    def enqueue(self,raw):
        schema(raw,"ace.web.queue-task.v1",("id","site","priority","not_before","workflow_sha256","source_ref"))
        key=identifier(raw["id"],"ID tugas")
        site=identifier(raw["site"],"ID situs")
        if site not in self._sites:
            raise ContractError("Situs belum terdaftar.")
        ready=time_value(raw["not_before"])
        priority=integer(raw["priority"],"Prioritas",0,100)
        anchor=identity(raw)
        workflow=digest(raw["workflow_sha256"])
        pointer=text(raw["source_ref"],"Sumber tugas")
        with self._transaction() as db:
            row=db.execute("SELECT request_sha,state FROM jobs WHERE id=?",(key,)).fetchone()
            if row is not None:
                if row[0]!=anchor:
                    raise ContractError("ID tugas menunjuk proposal berbeda.")
                return {"id":key,"status":row[1],"duplicate":True}
            if db.execute("SELECT count(*) FROM jobs").fetchone()[0]>=self._cap:
                raise ContractError("Batas antrean tercapai.")
            db.execute("INSERT INTO jobs(id,site,rank,ready,state,request_sha,workflow_sha,origin_ref) "
                       "VALUES (?,?,?,?,'queued',?,?,?)",(key,site,priority,ready,anchor,workflow,pointer))
        return {"id":key,"status":"queued","duplicate":False}

    @staticmethod
    def _expire(db,now):
        db.execute("UPDATE jobs SET state='needs_review',holder=NULL,lease_sha=NULL,lease_until=NULL "
                   "WHERE state='leased' AND lease_until<=?",(now,))

    def claim(self,actor,now):
        worker=identifier(actor,"Worker")
        at=time_value(now)
        with self._transaction() as db:
            self._expire(db,at)
            active=dict(db.execute("SELECT site,count(*) FROM jobs WHERE state='leased' GROUP BY site"))
            available=[site for site,cap in sorted(self._sites.items()) if active.get(site,0)<cap]
            if not available:
                return {"status":"idle"}
            holders=",".join("?" for _ in available)
            row=db.execute(f"SELECT id,site,workflow_sha,origin_ref FROM jobs WHERE state='queued' AND ready<=? AND site IN ({holders}) "
                           "ORDER BY rank DESC,ready,seq LIMIT 1",(at,*available)).fetchone()
            if row is None:
                return {"status":"idle"}
            key,site,workflow,pointer=row
            ticket=token_hex(20)
            expiry=at+self._lease
            db.execute("UPDATE jobs SET state='leased',holder=?,lease_sha=?,lease_until=? WHERE id=?",
                       (worker,identity(ticket),expiry,key))
        return {"id":key,"site":site,"status":"leased","lease":ticket,"lease_until_unix":expiry,
                "workflow_sha256":workflow,"source_ref":pointer}

    def finish(self,raw,now):
        schema(raw,"ace.web.queue-finish.v1",("id","actor","lease","workflow_sha256","result","receipt_sha256"))
        key=identifier(raw["id"],"Tugas")
        actor=identifier(raw["actor"],"Worker")
        ticket=text(raw["lease"],"Lease",40)
        outcome=raw["result"]
        if outcome not in ("completed","failed"):
            raise ContractError("Tugas perlu hasil terminal.")
        anchor=digest(raw["workflow_sha256"])
        evidence=digest(raw["receipt_sha256"])
        with self._transaction() as db:
            self._expire(db,time_value(now))
            row=db.execute("SELECT state,holder,lease_sha,workflow_sha FROM jobs WHERE id=?",(key,)).fetchone()
            if row!=("leased",actor,identity(ticket),anchor):
                return {"id":key,"status":"held","reason":"lease_or_workflow_mismatch"}
            db.execute("UPDATE jobs SET state=?,holder=NULL,lease_sha=NULL,lease_until=NULL,finish_sha=? WHERE id=?",
                       (outcome,evidence,key))
        return {"id":key,"status":outcome,"receipt_sha256":evidence}

    def summary(self):
        with self._transaction() as db:
            rows=db.execute("SELECT site,state,count(*) FROM jobs GROUP BY site,state ORDER BY site,state").fetchall()
        return {"schema":"ace.web.queue-report.v1","policy_sha256":self._version,
                "summary":[{"site":site,"status":state,"count":amount} for site,state,amount in rows]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database",type=Path)
    parser.add_argument("policy",type=Path)
    parser.add_argument("action",choices=("initialize","enqueue","claim","finish","summary"))
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--at")
    parser.add_argument("--actor")
    parser.add_argument("--input",type=Path)
    args=parser.parse_args(argv)
    try:
        queue=Queue(args.database,decode(read(args.policy)),args.expect_sha256)
        if args.action=="initialize":
            queue.initialize()
            report={"status":"ready"}
        elif args.action in ("enqueue","finish"):
            if args.input is None or args.action=="finish" and not args.at:
                parser.error("Tindakan perlu --input dan waktu untuk finish.")
            item=decode(read(args.input))
            report=queue.enqueue(item) if args.action=="enqueue" else queue.finish(item,args.at)
        elif args.action=="claim":
            report=queue.claim(args.actor,args.at)
        else:
            report=queue.summary()
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,sqlite3.Error,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report.get("status")=="held")


if __name__=="__main__":
    raise SystemExit(main())
