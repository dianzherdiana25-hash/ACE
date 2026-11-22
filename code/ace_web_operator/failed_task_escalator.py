"""Triage kegagalan tugas web dari receipt dan kebijakan yang eksplisit.

Ulangan hanya direncanakan untuk sebab yang diizinkan dan efek yang
terbukti absen. Tugas dengan status terminal terbaru tidak dieskalasi.
Handoff hanya berupa output lokal untuk peninjauan.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import iso,time_value


def triage(plan,expected,ledger):
    checked(plan,expected)
    schema(plan,"ace.web.failed-task-policy.v1",("source_ref","ledger_sha256","as_of","rules","default_owner_ref"))
    checked(ledger,plan["ledger_sha256"])
    schema(ledger,"ace.web.failed-task-ledger.v1",("source_ref","attempts"))
    source=text(plan["source_ref"],"Aturan eskalasi")
    owner=text(plan["default_owner_ref"],"Rujukan reviewer")
    from_ref=text(ledger["source_ref"],"Rujukan ledger")
    now=time_value(plan["as_of"])
    rules={}
    for row in entries(plan["rules"],80):
        obj(row,("reason","owner_ref","priority","max_retry","wait_seconds","source_ref"))
        reason=identifier(row["reason"],"Jenis kegagalan")
        if reason in rules:
            raise ContractError("Aturan alasan ganda.")
        rules[reason]=(integer(row["priority"],"Prioritas",0,100),integer(row["max_retry"],"Batas ulangan",0,5),
                       integer(row["wait_seconds"],"Jeda ulangan",0,86400),text(row["owner_ref"],"Reviewer"),
                       text(row["source_ref"],"Sumber aturan"))
    attempts={}
    for row in entries(ledger["attempts"],5000):
        obj(row,("task","attempt","workflow_sha256","at","status","reason","effect","receipt_sha256","source_ref"))
        key=identifier(row["task"],"Tugas")
        n=integer(row["attempt"],"Nomor percobaan",1,30)
        at=time_value(row["at"])
        workflow=digest(row["workflow_sha256"])
        digest(row["receipt_sha256"])
        text(row["source_ref"],"Rujukan receipt")
        if (at>now or row["status"] not in ("completed","failed","cancelled") or row["effect"] not in
                ("none_verified","possible","observed") or (row["status"]=="failed")!=(row["reason"] is not None)):
            raise ContractError("Status atau waktu percobaan tidak sah.")
        if row["reason"] is not None:
            identifier(row["reason"],"Alasan gagal")
        series=attempts.setdefault(key,{})
        if n in series:
            raise ContractError("Nomor percobaan ganda.")
        series[n]=(at,workflow,row)
    resolved=0
    jobs=[]
    for key,job in sorted(attempts.items()):
        values=[job[number] for number in sorted(job)]
        if list(sorted(job))!=list(range(1,len(job)+1)) or len({item[1] for item in values})!=1 or (
                [item[0] for item in values]!=sorted(item[0] for item in values)):
            raise ContractError("Urutan receipt berlubang atau workflow berubah.")
        at,workflow,row=values[-1]
        if row["status"]!="failed":
            resolved+=1
            continue
        reason=row["reason"]
        priority,limit,delay,handler,pointer=rules.get(reason,(50,0,0,owner,source))
        safe=row["effect"]=="none_verified" and len(values)<=limit
        dispatch="retry_eligible" if safe and at+delay<=now else "waiting_window" if safe else "operator_review"
        jobs.append({"task":key,"disposition":dispatch,"priority":priority,"owner_ref":handler,
                     "workflow_sha256":workflow,"reason":reason,"attempt":len(values),
                     "next_eligible_at":iso(at+delay) if safe else None,"workflow_effect":row["effect"],
                     "receipt_sha256":row["receipt_sha256"],"source_ref":row["source_ref"],"rule_ref":pointer})
    jobs.sort(key=lambda row:(-row["priority"],row["task"]))
    return {"schema":"ace.web.escalation-report.v1","plan_sha256":expected,"source_ref":source,"ledger_ref":from_ref,
            "ledger_sha256":identity(ledger),"resolved":resolved,"actions":jobs,"executed":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("policy","ledger"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=triage(decode(read(args.policy)),args.expect_sha256,decode(read(args.ledger)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
