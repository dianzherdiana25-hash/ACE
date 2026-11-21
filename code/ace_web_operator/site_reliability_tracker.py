"""Ukur penyelesaian workflow per situs dari receipt yang tertambat.

Denominator meliputi alur sukses dan gagal, sementara bukti tidak
lengkap dicatat terpisah. Threshold hanya dinilai jika ada cukup
sampel. Langkah dan hash run dirujuk untuk audit penyebab.
"""
import argparse
from collections import Counter
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import time_value


def _verdict(receipt):
    schema(receipt,"ace.web.workflow-receipt.v1",("workflow_sha256","browser_sha256","source_ref","status","reason",
                                               "requests","rejected_requests","stages"))
    digest(receipt["workflow_sha256"])
    digest(receipt["browser_sha256"])
    text(receipt["source_ref"],"Sumber workflow")
    outcomes=[]
    for row in entries(receipt["stages"],16,1):
        obj(row,("id","source_ref","requires","steps","status","observations"))
        key=identifier(row["id"],"ID tahap")
        if row["status"] not in ("completed","failed","not_started"):
            raise ContractError("Status tahap tidak diakui.")
        outcomes.append((key,row["status"]))
    status=receipt["status"]
    if status=="completed":
        if any(state!="completed" for _,state in outcomes) or receipt["rejected_requests"]!=0 or receipt["reason"] is not None:
            raise ContractError("Workflow berstatus complete bertentangan dengan receipt.")
        return "completed",None
    if status!="held":
        raise ContractError("Status receipt workflow tidak didukung.")
    first=next((key for key,state in outcomes if state=="failed"),None)
    if receipt["requests"] is None:
        return "unobserved",first
    return "failed",first


def summarize(plan,expected,log):
    checked(plan,expected)
    schema(plan,"ace.web.reliability-plan.v1",("source_ref","from","until","minimum_runs","minimum_bp","sites","log_sha256"))
    checked(log,plan["log_sha256"])
    schema(log,"ace.web.reliability-log.v1",("runs",))
    pointer=text(plan["source_ref"],"Sumber scope")
    lower,upper=(time_value(plan[key]) for key in ("from","until"))
    if lower>=upper:
        raise ContractError("Window statistik terbalik.")
    min_runs=integer(plan["minimum_runs"],"Sampel minimum",1,5000)
    floor=integer(plan["minimum_bp"],"Ambang basis points",0,10_000)
    sites=[identifier(name,"Situs") for name in entries(plan["sites"],80,1)]
    if len(set(sites))!=len(sites):
        raise ContractError("Situs didaftarkan ganda.")
    tracked={site:[] for site in sites}
    seen=set()
    outside=0
    for row in entries(log["runs"],5000):
        obj(row,("id","site","at","receipt_sha256","receipt","source_ref"))
        key=identifier(row["id"],"Run")
        site=identifier(row["site"],"Situs run")
        sample=time_value(row["at"])
        if key in seen or site not in tracked:
            raise ContractError("Run ganda atau menggunakan situs tidak dikenal.")
        seen.add(key)
        if not lower<=sample<upper:
            outside+=1
            continue
        checked(row["receipt"],row["receipt_sha256"])
        verdict,stage=_verdict(row["receipt"])
        tracked[site].append({"id":key,"at":row["at"],"verdict":verdict,"first_failed_stage":stage,
                      "receipt_sha256":row["receipt_sha256"],"source_ref":text(row["source_ref"],"Sumber run")})
    records=[]
    for site,history in sorted(tracked.items()):
        counts=Counter(row["verdict"] for row in history)
        total=counts["completed"]+counts["failed"]
        rate=counts["completed"]*10_000//total if total else None
        status="insufficient_samples" if total<min_runs else "meets_threshold" if rate>=floor else "below_threshold"
        records.append({"site":site,"observed":total,"completed":counts["completed"],"failed":counts["failed"],
                        "unobserved":counts["unobserved"],"completion_bp":rate,"status":status,
                        "runs":sorted(history,key=lambda row:(row["at"],row["id"]))})
    return {"schema":"ace.web.reliability-report.v1","plan_sha256":expected,"log_sha256":identity(log),"source_ref":pointer,
            "out_of_window":outside,"sites":records}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("log",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=summarize(decode(read(args.plan)),args.expect_sha256,decode(read(args.log)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
