"""Bentangkan tugas web berulang menjadi slot UTC yang dapat diaudit.

Slot diikat ke hash workflow. Riwayat menghindari penjadwalan ulang
slot terminal. Kebijakan run-latest melaporkan slot terlewati tanpa
membuka browser atau menjalankan tugas.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import re
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text


STAMP=re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
MAX_SLOTS=3000


def time_value(value):
    if not isinstance(value,str) or not STAMP.fullmatch(value):
        raise ContractError("Jadwal perlu waktu UTC kanonis.")
    parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    if not 1970<=parsed.year<=2200:
        raise ContractError("Tahun jadwal di luar rentang.")
    return int(parsed.timestamp())


def iso(value):
    return datetime.fromtimestamp(value,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _jobs(plan):
    jobs={}
    for row in entries(plan["tasks"],80,1):
        obj(row,("id","first_at","every_seconds","until","missed_slots","workflow_sha256","source_ref"))
        key=identifier(row["id"],"Tugas")
        first=time_value(row["first_at"])
        end=time_value(row["until"])
        interval=integer(row["every_seconds"],"Interval",60,86400*30)
        if key in jobs or row["missed_slots"] not in ("queue_all","run_latest") or end<=first:
            raise ContractError("Tugas ganda, rentang tidak sah atau kebijakan slot tidak didukung.")
        jobs[key]=(first,end,interval,row["missed_slots"],digest(row["workflow_sha256"]),
                   text(row["source_ref"],"Sumber tugas"))
    return jobs


def schedule(plan,expected,history):
    checked(plan,expected)
    schema(plan,"ace.web.scheduler-plan.v1",("source_ref","window_start","window_end","as_of","tasks"))
    source=text(plan["source_ref"],"Sumber jadwal")
    begin,end,now=(time_value(plan[key]) for key in ("window_start","window_end","as_of"))
    if end<=begin or not begin<=now<=end or end-begin>86400*120:
        raise ContractError("Rentang window atau as_of tidak sah.")
    jobs=_jobs(plan)
    schema(history,"ace.web.scheduler-history.v1",("receipts",))
    observed={}
    for row in entries(history["receipts"],6000):
        obj(row,("task","scheduled_at","finished_at","workflow_sha256","status","source_ref"))
        key=identifier(row["task"],"ID receipt tugas")
        due=time_value(row["scheduled_at"])
        finished=time_value(row["finished_at"])
        if key not in jobs or (key,due) in observed or not due<=finished<=now:
            raise ContractError("Receipt ganda, waktu terbalik, atau tugas tidak dikenal.")
        start,until,period,_,anchor,_=jobs[key]
        if not start<=due<until or (due-start)%period or row["workflow_sha256"]!=anchor or (
            row["status"] not in ("completed","failed","cancelled")
        ):
            raise ContractError("Receipt tidak cocok dengan slot atau workflow.")
        observed[(key,due)]={"status":row["status"],"source_ref":text(row["source_ref"],"Rujukan receipt")}
    decisions=[]
    for key,(start,until,period,catchup,anchor,pointer) in sorted(jobs.items()):
        offset=max(0,(begin-start+period-1)//period)
        ceiling=min(end,until)
        lower=start+offset*period
        count=max(0,(ceiling-lower+period-1)//period)
        if len(decisions)+count>MAX_SLOTS:
            raise ContractError("Rencana menghasilkan terlalu banyak slot.")
        moments=range(lower,ceiling,period)
        ready=[value for value in moments if value<=now and (key,value) not in observed]
        preferred=ready[-1] if ready else None
        for moment in moments:
            terminal=observed.get((key,moment))
            if terminal is not None:
                status="recorded"
            elif moment>now:
                status="scheduled"
            elif catchup=="run_latest" and moment!=preferred:
                status="skipped_by_policy"
            else:
                status="due"
            decisions.append({"task":key,"at":iso(moment),"workflow_sha256":anchor,"source_ref":pointer,
                              "status":status,"receipt":terminal,"id":identity([key,iso(moment),anchor])})
    decisions.sort(key=lambda row:(row["at"],row["task"]))
    counts={state:sum(row["status"]==state for row in decisions)
            for state in ("due","scheduled","recorded","skipped_by_policy")}
    return {"schema":"ace.web.scheduler-report.v1","plan_sha256":expected,"history_sha256":identity(history),
            "source_ref":source,"counts":counts,"slots":decisions}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("history",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=schedule(decode(read(args.plan)),args.expect_sha256,decode(read(args.history)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
